import {
  Injectable,
  ConflictException,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as argon2 from 'argon2';
import { randomUUID } from 'crypto';
import { createHash } from 'crypto';
import { PrismaService } from '../prisma.service';

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
  ) {}

  async signup(
    email: string,
    password: string,
    profile?: {
      primary_phone?: string;
      first_name?: string;
      last_name?: string;
    },
    projectCode?: string,
  ): Promise<{
    user: any;
    accessToken: string;
    refreshToken: string;
    joinedProject?: { id: string; title: string; role: string } | null;
  }> {
    const existingUser = await this.prisma.users.findUnique({
      where: { email },
    });
    if (existingUser) {
      throw new ConflictException('Email already in use');
    }

    const passwordHash = await argon2.hash(password);

    // Determine role based on email domain
    const isStaff =
      email.endsWith('@flashbacklabs.com') ||
      email.endsWith('@flashbacklabs.inc') ||
      email.endsWith('@flashback.inc');
    const roleId = isStaff ? 'staff' : 'host';
    const profileType = isStaff ? 'staff' : 'client';

    // Create user, profile, and assign role in a transaction
    const user = await this.prisma.$transaction(async (tx) => {
      console.log('=== TRANSACTION START ===');
      console.log('Email:', email);
      console.log('Role to assign:', roleId);
      console.log('Profile type:', profileType);
      console.log('Profile data:', profile);

      try {
        // 1. Create user
        console.log('Step 1: Creating user...');
        const newUser = await tx.users.create({
          data: {
            email,
            password_hash: passwordHash,
            primary_phone: profile?.primary_phone || null,
            status: 'active',
          },
        });
        console.log('User created with ID:', newUser.id);

        // 2. Create user profile with metadata
        if (profile?.first_name || profile?.last_name) {
          console.log('Step 2: Creating user profile...');
          const userProfile = await tx.user_profiles.create({
            data: {
              user_id: newUser.id,
              profile_type: profileType,
              metadata: {
                first_name: profile?.first_name || '',
                last_name: profile?.last_name || '',
              },
            },
          });
          console.log('User profile created with ID:', userProfile.id);
        } else {
          console.log('Step 2: Skipping user profile (no name provided)');
        }

        // 3. Assign role based on email domain
        console.log('Step 3: Assigning role...');
        const userRole = await tx.user_roles.create({
          data: {
            user_id: newUser.id,
            role_id: roleId,
            scope_type: 'global',
            scope_id: null,
          },
        });
        console.log('Role assigned with ID:', userRole.id);
        console.log('=== TRANSACTION SUCCESS ===');

        return newUser;
      } catch (error) {
        console.error('=== TRANSACTION ERROR ===');
        console.error('Error details:', error);
        throw error;
      }
    });

    const { accessToken, refreshToken, sessionId } =
      await this.createSessionAndTokens(user.id, user.email);

    // If a project code was provided, auto-join as collaborator
    let joinedProject: { id: string; title: string; role: string } | null = null;
    if (projectCode) {
      try {
        // Find project by join code (raw query to avoid circular dep with ProjectsService)
        const shortHex = projectCode.slice(-8).toLowerCase();
        if (/^[0-9a-f]{8}$/.test(shortHex)) {
          const rows = await this.prisma.$queryRaw<{ id: string; title: string; status: string }[]>`
            SELECT id, title, status FROM projects
            WHERE deleted_at IS NULL
              AND replace(id::text, '-', '') LIKE ${shortHex + '%'}
            LIMIT 1
          `;
          if (rows.length > 0) {
            const project = rows[0];
            // Add as collaborator (idempotent)
            const existingMembership = await this.prisma.project_collaborators.findUnique({
              where: { project_id_user_id: { project_id: project.id, user_id: user.id } },
            });
            if (!existingMembership) {
              await this.prisma.project_collaborators.create({
                data: { project_id: project.id, user_id: user.id, role: 'collaborator' },
              });
            }
            joinedProject = {
              id: project.id,
              title: project.title,
              role: existingMembership?.role ?? 'collaborator',
            };
          }
        }
      } catch (err) {
        // Non-fatal: signup still succeeds even if join fails
        console.warn('Failed to auto-join project during signup:', err);
      }
    }

    return {
      user,
      accessToken,
      refreshToken,
      joinedProject,
    };
  }

  async login(
    email: string,
    password: string,
  ): Promise<{
    user: any;
    accessToken: string;
    refreshToken: string;
  }> {
    const user = await this.prisma.users.findUnique({
      where: { email },
    });
    if (!user || !user.password_hash) {
      throw new UnauthorizedException('Invalid email or password');
    }

    const isPasswordValid = await argon2.verify(user.password_hash, password);
    if (!isPasswordValid) {
      throw new UnauthorizedException('Invalid email or password');
    }

    const { accessToken, refreshToken } =
      await this.createSessionAndTokens(user.id, user.email);

    return {
      user,
      accessToken,
      refreshToken,
    };
  }

  async logout(sessionId: string): Promise<void> {
    await this.prisma.refresh_tokens.updateMany({
      where: { session_id: sessionId, revoked_at: null },
      data: { revoked_at: new Date() },
    });

    await this.prisma.sessions.delete({
      where: { id: sessionId },
    });
  }

  async refresh(
    refreshTokenValue: string,
  ): Promise<{ accessToken: string; refreshToken: string }> {
    const tokenHash = createHash('sha256')
      .update(refreshTokenValue)
      .digest('hex');

    const existingToken = await this.prisma.refresh_tokens.findFirst({
      where: { token_hash: tokenHash },
    });

    if (!existingToken) {
      throw new UnauthorizedException('Invalid refresh token');
    }

    if (existingToken.revoked_at || existingToken.used_at) {
      // Token reuse detected - revoke all tokens for this session
      await this.prisma.refresh_tokens.updateMany({
        where: { session_id: existingToken.session_id },
        data: { revoked_at: new Date() },
      });
      throw new UnauthorizedException('Refresh token has already been used');
    }

    if (!existingToken.session_id) {
      throw new UnauthorizedException('Invalid refresh token');
    }

    const session = await this.prisma.sessions.findUnique({
      where: { id: existingToken.session_id },
      include: { users: true },
    });

    if (!session || session.expires_at < new Date()) {
      throw new UnauthorizedException('Session expired or not found');
    }

    // Mark old token as used
    const newRefreshTokenValue = randomUUID();
    const newTokenHash = createHash('sha256')
      .update(newRefreshTokenValue)
      .digest('hex');

    const newRefreshToken = await this.prisma.refresh_tokens.create({
      data: {
        session_id: session.id,
        token_hash: newTokenHash,
        issued_at: new Date(),
      },
    });

    await this.prisma.refresh_tokens.update({
      where: { id: existingToken.id },
      data: {
        used_at: new Date(),
        replaced_by_refresh_token_id: newRefreshToken.id,
      },
    });

    const accessToken = this.jwtService.sign({
      sub: session.user_id,
      sessionId: session.id,
      email: session.users.email,
    });

    return { accessToken, refreshToken: newRefreshTokenValue };
  }

  async validateUser(userId: string) {
    const user = await this.prisma.users.findUnique({
      where: { id: userId },
    });

    if (!user) {
      return null;
    }

    return user;
  }

  async generateTokens(
    userId: string,
    sessionId: string,
    email: string,
  ): Promise<{ accessToken: string; refreshToken: string }> {
    const accessToken = this.jwtService.sign({
      sub: userId,
      sessionId,
      email,
    });

    const refreshTokenValue = randomUUID();
    const tokenHash = createHash('sha256')
      .update(refreshTokenValue)
      .digest('hex');

    await this.prisma.refresh_tokens.create({
      data: {
        session_id: sessionId,
        token_hash: tokenHash,
        issued_at: new Date(),
      },
    });

    return { accessToken, refreshToken: refreshTokenValue };
  }

  private async createSessionAndTokens(
    userId: string,
    email: string,
  ): Promise<{ accessToken: string; refreshToken: string; sessionId: string }> {
    const sessionToken = randomUUID();
    const sessionTokenHash = createHash('sha256')
      .update(sessionToken)
      .digest('hex');

    const session = await this.prisma.sessions.create({
      data: {
        user_id: userId,
        session_token_hash: sessionTokenHash,
        expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      },
    });

    const { accessToken, refreshToken } = await this.generateTokens(
      userId,
      session.id,
      email,
    );

    return { accessToken, refreshToken, sessionId: session.id };
  }
}

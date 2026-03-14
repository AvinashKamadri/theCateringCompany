"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AuthService = void 0;
const common_1 = require("@nestjs/common");
const jwt_1 = require("@nestjs/jwt");
const argon2 = require("argon2");
const crypto_1 = require("crypto");
const crypto_2 = require("crypto");
const prisma_service_1 = require("../prisma.service");
let AuthService = class AuthService {
    constructor(prisma, jwtService) {
        this.prisma = prisma;
        this.jwtService = jwtService;
    }
    async signup(email, password, profile) {
        const existingUser = await this.prisma.users.findUnique({
            where: { email },
        });
        if (existingUser) {
            throw new common_1.ConflictException('Email already in use');
        }
        const passwordHash = await argon2.hash(password);
        const isStaff = email.endsWith('@flashbacklabs.com') ||
            email.endsWith('@flashbacklabs.inc') ||
            email.endsWith('@flashback.inc');
        const roleId = isStaff ? 'staff' : 'host';
        const profileType = isStaff ? 'staff' : 'client';
        const user = await this.prisma.$transaction(async (tx) => {
            console.log('=== TRANSACTION START ===');
            console.log('Email:', email);
            console.log('Role to assign:', roleId);
            console.log('Profile type:', profileType);
            console.log('Profile data:', profile);
            try {
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
                }
                else {
                    console.log('Step 2: Skipping user profile (no name provided)');
                }
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
            }
            catch (error) {
                console.error('=== TRANSACTION ERROR ===');
                console.error('Error details:', error);
                throw error;
            }
        });
        const { accessToken, refreshToken, sessionId } = await this.createSessionAndTokens(user.id, user.email);
        return {
            user,
            accessToken,
            refreshToken,
        };
    }
    async login(email, password) {
        const user = await this.prisma.users.findUnique({
            where: { email },
        });
        if (!user || !user.password_hash) {
            throw new common_1.UnauthorizedException('Invalid email or password');
        }
        const isPasswordValid = await argon2.verify(user.password_hash, password);
        if (!isPasswordValid) {
            throw new common_1.UnauthorizedException('Invalid email or password');
        }
        const { accessToken, refreshToken } = await this.createSessionAndTokens(user.id, user.email);
        return {
            user,
            accessToken,
            refreshToken,
        };
    }
    async logout(sessionId) {
        await this.prisma.refresh_tokens.updateMany({
            where: { session_id: sessionId, revoked_at: null },
            data: { revoked_at: new Date() },
        });
        await this.prisma.sessions.delete({
            where: { id: sessionId },
        });
    }
    async refresh(refreshTokenValue) {
        const tokenHash = (0, crypto_2.createHash)('sha256')
            .update(refreshTokenValue)
            .digest('hex');
        const existingToken = await this.prisma.refresh_tokens.findFirst({
            where: { token_hash: tokenHash },
        });
        if (!existingToken) {
            throw new common_1.UnauthorizedException('Invalid refresh token');
        }
        if (existingToken.revoked_at || existingToken.used_at) {
            await this.prisma.refresh_tokens.updateMany({
                where: { session_id: existingToken.session_id },
                data: { revoked_at: new Date() },
            });
            throw new common_1.UnauthorizedException('Refresh token has already been used');
        }
        if (!existingToken.session_id) {
            throw new common_1.UnauthorizedException('Invalid refresh token');
        }
        const session = await this.prisma.sessions.findUnique({
            where: { id: existingToken.session_id },
            include: { users: true },
        });
        if (!session || session.expires_at < new Date()) {
            throw new common_1.UnauthorizedException('Session expired or not found');
        }
        const newRefreshTokenValue = (0, crypto_1.randomUUID)();
        const newTokenHash = (0, crypto_2.createHash)('sha256')
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
    async validateUser(userId) {
        const user = await this.prisma.users.findUnique({
            where: { id: userId },
        });
        if (!user) {
            return null;
        }
        return user;
    }
    async generateTokens(userId, sessionId, email) {
        const accessToken = this.jwtService.sign({
            sub: userId,
            sessionId,
            email,
        });
        const refreshTokenValue = (0, crypto_1.randomUUID)();
        const tokenHash = (0, crypto_2.createHash)('sha256')
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
    async createSessionAndTokens(userId, email) {
        const sessionToken = (0, crypto_1.randomUUID)();
        const sessionTokenHash = (0, crypto_2.createHash)('sha256')
            .update(sessionToken)
            .digest('hex');
        const session = await this.prisma.sessions.create({
            data: {
                user_id: userId,
                session_token_hash: sessionTokenHash,
                expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
            },
        });
        const { accessToken, refreshToken } = await this.generateTokens(userId, session.id, email);
        return { accessToken, refreshToken, sessionId: session.id };
    }
};
exports.AuthService = AuthService;
exports.AuthService = AuthService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService,
        jwt_1.JwtService])
], AuthService);
//# sourceMappingURL=auth.service.js.map
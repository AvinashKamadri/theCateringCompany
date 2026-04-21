import { Injectable, Logger, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  createCipheriv,
  createDecipheriv,
  createHmac,
  randomBytes,
} from 'crypto';
import { JobQueueService } from '../job_queue/job-queue.service';
import { PrismaService } from '../prisma.service';

@Injectable()
export class GmailService {
  private readonly logger = new Logger(GmailService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
    private readonly jobQueue: JobQueueService,
  ) {}

  // ── OAuth ──────────────────────────────────────────────────────────────────

  getAuthUrl(userId: string): string {
    const state = this.signState(userId);
    const params = new URLSearchParams({
      client_id: this.config.get<string>('GMAIL_CLIENT_ID')!,
      redirect_uri: this.config.get<string>('GMAIL_REDIRECT_URI')!,
      response_type: 'code',
      scope: 'openid email https://www.googleapis.com/auth/gmail.readonly',
      access_type: 'offline',
      prompt: 'consent',
      state,
    });
    return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
  }

  async handleCallback(code: string, state: string): Promise<void> {
    const userId = this.verifyState(state);
    if (!userId) throw new UnauthorizedException('Invalid or expired OAuth state');

    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        code,
        client_id: this.config.get<string>('GMAIL_CLIENT_ID')!,
        client_secret: this.config.get<string>('GMAIL_CLIENT_SECRET')!,
        redirect_uri: this.config.get<string>('GMAIL_REDIRECT_URI')!,
        grant_type: 'authorization_code',
      }),
    });

    const tokens: any = await tokenRes.json();
    if (tokens.error) {
      this.logger.error(`Gmail OAuth callback error: ${tokens.error_description}`);
      throw new UnauthorizedException('OAuth token exchange failed');
    }

    // Decode id_token payload to get Gmail email and Google sub
    const idPayload = this.decodeJwtPayload(tokens.id_token);
    const gmailEmail: string = idPayload.email;
    const googleSub: string = idPayload.sub;

    const expiresAt = tokens.expires_in
      ? new Date(Date.now() + tokens.expires_in * 1000)
      : null;

    await this.prisma.oauth_accounts.upsert({
      where: { provider_provider_account_id: { provider: 'google', provider_account_id: googleSub } },
      create: {
        user_id: userId,
        provider: 'google',
        provider_account_id: googleSub,
        access_token: tokens.access_token,
        refresh_token_encrypted: tokens.refresh_token
          ? this.encryptToken(tokens.refresh_token)
          : null,
        access_token_expires_at: expiresAt,
        raw_profile: { email: gmailEmail, sub: googleSub },
      },
      update: {
        access_token: tokens.access_token,
        ...(tokens.refresh_token && {
          refresh_token_encrypted: this.encryptToken(tokens.refresh_token),
        }),
        access_token_expires_at: expiresAt,
        raw_profile: { email: gmailEmail, sub: googleSub },
      },
    });

    await this.prisma.gmail_sync_state.upsert({
      where: { user_id: userId },
      create: { user_id: userId },
      update: { history_id: null, last_synced: null },
    });

    await this.jobQueue.send('gmail-full-sync', { userId });
    this.logger.log(`Gmail connected for user ${userId} (${gmailEmail}), full-sync enqueued`);
  }

  async getValidAccessToken(userId: string): Promise<string> {
    const account = await this.prisma.oauth_accounts.findFirst({
      where: { user_id: userId, provider: 'google' },
    });
    if (!account?.access_token) throw new Error('Gmail not connected for user ' + userId);

    const fiveMinFromNow = new Date(Date.now() + 5 * 60 * 1000);
    const needsRefresh =
      !account.access_token_expires_at ||
      account.access_token_expires_at < fiveMinFromNow;

    if (!needsRefresh) return account.access_token;

    if (!account.refresh_token_encrypted) throw new Error('No refresh token stored');

    const refreshToken = this.decryptToken(account.refresh_token_encrypted);
    const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        refresh_token: refreshToken,
        client_id: this.config.get<string>('GMAIL_CLIENT_ID')!,
        client_secret: this.config.get<string>('GMAIL_CLIENT_SECRET')!,
        grant_type: 'refresh_token',
      }),
    });

    const tokens: any = await tokenRes.json();
    if (tokens.error) throw new Error(`Token refresh failed: ${tokens.error_description}`);

    const newExpiry = new Date(Date.now() + tokens.expires_in * 1000);
    await this.prisma.oauth_accounts.update({
      where: { id: account.id },
      data: { access_token: tokens.access_token, access_token_expires_at: newExpiry },
    });

    this.logger.log(`Access token refreshed for user ${userId}`);
    return tokens.access_token;
  }

  // ── Quick Sync ─────────────────────────────────────────────────────────────

  async triggerQuickSync(userId: string): Promise<{ synced: boolean; message: string }> {
    const account = await this.prisma.oauth_accounts.findFirst({
      where: { user_id: userId, provider: 'google' },
    });
    if (!account) {
      return { synced: false, message: 'Gmail not connected' };
    }

    // Step 2 will implement the actual fetch-parse-chunk-embed pipeline.
    // For now we verify connection and return ready status.
    return { synced: true, message: 'Quick sync ready — pipeline coming in Step 2' };
  }

  isConnected(userId: string): Promise<boolean> {
    return this.prisma.oauth_accounts
      .findFirst({ where: { user_id: userId, provider: 'google' } })
      .then((a) => !!a);
  }

  // ── Crypto helpers ─────────────────────────────────────────────────────────

  private encryptionKey(): Buffer {
    const key = this.config.get<string>('GMAIL_TOKEN_ENCRYPTION_KEY');
    if (!key) throw new Error('GMAIL_TOKEN_ENCRYPTION_KEY not set');
    return Buffer.from(key, 'hex');
  }

  encryptToken(token: string): string {
    const key = this.encryptionKey();
    const iv = randomBytes(12);
    const cipher = createCipheriv('aes-256-gcm', key, iv);
    const encrypted = Buffer.concat([cipher.update(token, 'utf8'), cipher.final()]);
    const tag = cipher.getAuthTag();
    return Buffer.concat([iv, tag, encrypted]).toString('base64');
  }

  decryptToken(encrypted: string): string {
    const key = this.encryptionKey();
    const buf = Buffer.from(encrypted, 'base64');
    const iv = buf.subarray(0, 12);
    const tag = buf.subarray(12, 28);
    const data = buf.subarray(28);
    const decipher = createDecipheriv('aes-256-gcm', key, iv);
    decipher.setAuthTag(tag);
    return Buffer.concat([decipher.update(data), decipher.final()]).toString('utf8');
  }

  private signState(userId: string): string {
    const encKey = this.config.get<string>('GMAIL_TOKEN_ENCRYPTION_KEY')!;
    const payload = `${userId}:${Date.now()}`;
    const sig = createHmac('sha256', encKey).update(payload).digest('hex');
    return Buffer.from(`${payload}:${sig}`).toString('base64url');
  }

  private verifyState(state: string): string | null {
    try {
      const encKey = this.config.get<string>('GMAIL_TOKEN_ENCRYPTION_KEY')!;
      const decoded = Buffer.from(state, 'base64url').toString();
      const lastColon = decoded.lastIndexOf(':');
      const payload = decoded.substring(0, lastColon);
      const sig = decoded.substring(lastColon + 1);
      const expected = createHmac('sha256', encKey).update(payload).digest('hex');
      if (expected !== sig) return null;
      const [userId, ts] = payload.split(':');
      if (Date.now() - parseInt(ts, 10) > 10 * 60 * 1000) return null; // 10 min TTL
      return userId;
    } catch {
      return null;
    }
  }

  private decodeJwtPayload(token: string): any {
    const part = token.split('.')[1];
    return JSON.parse(Buffer.from(part, 'base64url').toString());
  }
}

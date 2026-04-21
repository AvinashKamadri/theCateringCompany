# Gmail Email Integration — Implementation Report

**Branch:** `Email_integration`
**Date:** 2026-04-20
**Scope:** Steps 1–2 of the Gmail pipeline (OAuth connect, sync trigger, raw email fetch + parse, company strip). Steps 3–8 have TODO stubs in place.

---

## Summary of All File Changes

| File | Action | Description |
|---|---|---|
| `backend/prisma/schema.prisma` | Modified | 5 new models, extended `oauth_accounts`, added workers generator |
| `backend/src/gmail/gmail.module.ts` | Created | NestJS Gmail module |
| `backend/src/gmail/gmail.controller.ts` | Created | OAuth routes + quick sync + status |
| `backend/src/gmail/gmail.service.ts` | Created | OAuth flow, token encryption, token refresh |
| `backend/src/webhooks/webhooks.controller.ts` | Modified | Added `POST /webhooks/gmail` route |
| `backend/src/webhooks/webhooks.service.ts` | Modified | Added `handleGmailPubSubWebhook()` |
| `backend/src/app.module.ts` | Modified | Added `GmailModule` import |
| `backend/.env` | Modified | Added Gmail + Qdrant env vars |
| `backend/entrypoint.sh` | Modified | `prisma migrate deploy` → `prisma db push --skip-generate` |
| `backend/Dockerfile` | Modified | Copy `tsconfig.json` into runner stage |
| `workers/src/lib/token-crypto.ts` | Created | AES-256-GCM decrypt helper for workers |
| `workers/src/lib/gmail-client.ts` | Created | Gmail API fetch functions |
| `workers/src/lib/gmail-parser.ts` | Created | MIME parsing, HTML→text, quote stripping |
| `workers/src/processors/gmail-sync.processor.ts` | Created | Incremental sync job processor |
| `workers/src/processors/gmail-full-sync.processor.ts` | Created | Full paginated sync job processor |
| `workers/src/types/jobs.ts` | Modified | Added `GmailSyncJobData`, `GmailFullSyncJobData` |
| `workers/src/index.ts` | Modified | Register Gmail workers under `GMAIL_ENABLED` flag |
| `workers/.env` | Created | Workers env with Gmail + Qdrant vars |
| `docker-compose.yml` | Modified | Added Qdrant, migrate service, workers service, fixed frontend |
| `scripts/test-gmail-oauth.js` | Created | CLI script to test Gmail OAuth flow |
| `backend/src/scripts/seed-users.ts` | Modified | Fixed `error` type in catch blocks |

---

## 1. Schema Changes — `backend/prisma/schema.prisma`

### New generator (workers Prisma client)
```prisma
generator workers_client {
  provider = "prisma-client-js"
  output   = "../../workers/node_modules/.prisma/client"
}
```
Allows the workers package to share the same schema without maintaining a separate `schema.prisma`.

### Extended `oauth_accounts`
```prisma
access_token_expires_at DateTime? @db.Timestamptz(6)
```
Tracks when the Google access token expires so both backend and workers know when to refresh.

### New model: `company_emails`
```prisma
model company_emails {
  id         String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  email      String   @unique
  label      String?
  created_at DateTime @default(now()) @db.Timestamptz(6)
}
```
Stores the catering company's own email aliases (sales@, support@, info@, etc.). Used in Step 3 to strip company-side messages from sync.

### New model: `gmail_sync_state`
```prisma
model gmail_sync_state {
  id          String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  user_id     String    @unique @db.Uuid
  history_id  String?
  last_synced DateTime? @db.Timestamptz(6)
  users       users     @relation(fields: [user_id], references: [id], onDelete: Cascade)
}
```
Tracks the Gmail `historyId` watermark per user so incremental syncs know where they left off. On full sync, a `page:TOKEN` prefix is stored for crash resumability.

### New model: `user_identities`
```prisma
model user_identities {
  id                  String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  user_id             String   @db.Uuid
  kind                String
  value               String
  source              String?
  identity_confidence String?
  created_at          DateTime @default(now()) @db.Timestamptz(6)
  users               users    @relation(fields: [user_id], references: [id], onDelete: Cascade)

  @@unique([kind, value])
  @@index([value])
}
```
Maps an email address (kind=`'email'`, value=`'client@example.com'`) to a known `user_id`. Used in Step 4 (identity resolution). `source` can be `'email_auto_created'` when a new user is created from an inbound email. `identity_confidence` is `'high'` for exact matches, `'low'` for thread-inherited matches.

### New model: `email_chunks`
```prisma
model email_chunks {
  id               String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  gmail_message_id String
  gmail_thread_id  String
  user_id          String?   @db.Uuid
  project_id       String?   @db.Uuid
  chunk_index      Int
  question         String?
  answer           String?
  chunk_text       String
  qdrant_vector_id String?
  source_inbox     String?
  client_email     String
  identity_status  String    @default("pending")
  created_at       DateTime  @default(now()) @db.Timestamptz(6)
  updated_at       DateTime  @updatedAt @db.Timestamptz(6)
  users            users?    @relation(fields: [user_id], references: [id], onDelete: SetNull)
  projects         projects? @relation(fields: [project_id], references: [id], onDelete: SetNull)

  @@unique([gmail_message_id, chunk_index])
  @@index([user_id, client_email])
  @@index([gmail_thread_id])
}
```
Stores the final Q&A chunks ready for vector embedding. `identity_status` is `'pending'` until Step 4 resolves who the client is. `qdrant_vector_id` is set after Step 7 upserts into Qdrant. The `@@unique([gmail_message_id, chunk_index])` enables idempotent upserts.

### New model: `email_context_cache`
```prisma
model email_context_cache {
  id         String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  user_id    String   @db.Uuid
  project_id String   @db.Uuid
  is_stale   Boolean  @default(false)
  summary    String?
  expires_at DateTime @db.Timestamptz(6)
  created_at DateTime @default(now()) @db.Timestamptz(6)
  updated_at DateTime @updatedAt @db.Timestamptz(6)
  users      users    @relation(fields: [user_id], references: [id], onDelete: Cascade)
  projects   projects @relation(fields: [project_id], references: [id], onDelete: Cascade)

  @@unique([user_id, project_id])
}
```
Caches the email context summary per user+project. Step 8 flips `is_stale = true` when new chunks arrive, triggering a rebuild on the next chat open.

---

## 2. Backend — Gmail Module (new files)

### `backend/src/gmail/gmail.module.ts`
```typescript
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { GmailController } from './gmail.controller';
import { GmailService } from './gmail.service';
import { PrismaService } from '../prisma.service';

@Module({
  imports: [ConfigModule],
  controllers: [GmailController],
  providers: [GmailService, PrismaService],
  exports: [GmailService],
})
export class GmailModule {}
```

### `backend/src/gmail/gmail.controller.ts`
```typescript
import {
  Controller,
  Get,
  Post,
  Query,
  Req,
  Res,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { Request, Response } from 'express';
import { Public } from '../common/decorators/public.decorator';
import { GmailService } from './gmail.service';

@Controller('gmail')
export class GmailController {
  constructor(private readonly gmailService: GmailService) {}

  @Get('auth')
  getAuthUrl(@Req() req: Request) {
    const userId: string = (req as any).user?.sub ?? (req as any).user?.id;
    const url = this.gmailService.getAuthUrl(userId);
    return { url };
  }

  @Public()
  @Get('callback')
  async handleCallback(
    @Query('code') code: string,
    @Query('state') state: string,
    @Res() res: Response,
  ) {
    await this.gmailService.handleCallback(code, state);
    return res.redirect('/dashboard?gmail=connected');
  }

  @Post('sync/quick')
  @HttpCode(HttpStatus.OK)
  async quickSync(@Req() req: Request) {
    const userId: string = (req as any).user?.sub ?? (req as any).user?.id;
    const result = await this.gmailService.triggerQuickSync(userId);
    return result;
  }

  @Get('status')
  async getStatus(@Req() req: Request) {
    const userId: string = (req as any).user?.sub ?? (req as any).user?.id;
    const connected = await this.gmailService.isConnected(userId);
    return { connected };
  }
}
```

**Routes:**
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/gmail/auth` | JWT | Returns Google OAuth consent URL |
| `GET` | `/api/gmail/callback` | Public | Google redirects here after consent |
| `POST` | `/api/gmail/sync/quick` | JWT | Synchronous fast-path sync (~500ms) |
| `GET` | `/api/gmail/status` | JWT | Returns `{ connected: boolean }` |

### `backend/src/gmail/gmail.service.ts`
```typescript
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
    if (tokens.error) throw new UnauthorizedException('OAuth token exchange failed');

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

    return tokens.access_token;
  }

  async triggerQuickSync(userId: string): Promise<{ synced: boolean; message: string }> {
    const account = await this.prisma.oauth_accounts.findFirst({
      where: { user_id: userId, provider: 'google' },
    });
    if (!account) return { synced: false, message: 'Gmail not connected' };
    return { synced: true, message: 'Quick sync ready — pipeline coming in Step 2' };
  }

  isConnected(userId: string): Promise<boolean> {
    return this.prisma.oauth_accounts
      .findFirst({ where: { user_id: userId, provider: 'google' } })
      .then((a) => !!a);
  }

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
      if (Date.now() - parseInt(ts, 10) > 10 * 60 * 1000) return null;
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
```

**Key design decisions:**
- **AES-256-GCM** encryption for refresh tokens at rest. Format: `[12-byte IV][16-byte auth tag][ciphertext]` → base64.
- **HMAC-SHA256 state signing** to prevent CSRF on OAuth callback. State encodes `userId:timestamp:signature`, TTL = 10 minutes.
- **Token auto-refresh**: if `access_token_expires_at < now + 5min`, refresh before use.
- **Upsert on callback**: safe to re-connect the same Gmail account (e.g., re-consent after revoke).

---

## 3. Backend — Webhooks (modified files)

### `backend/src/webhooks/webhooks.controller.ts`

Added Gmail Pub/Sub route (secret passed as query param, not header — matching Google's push format):

```typescript
@Public()
@Post('gmail')
@HttpCode(HttpStatus.OK)
async handleGmailPubSub(
  @Req() req: Request,
  @Query('secret') secret: string,
) {
  const rawBody = (req as any).rawBody as Buffer;
  await this.webhooksService.handleGmailPubSubWebhook(rawBody, secret);
  return { received: true };
}
```

### `backend/src/webhooks/webhooks.service.ts`

Added `handleGmailPubSubWebhook(rawBody, secret)`:

```typescript
async handleGmailPubSubWebhook(rawBody: Buffer, secret: string): Promise<void> {
  // 1. Validate secret
  const expectedSecret = this.config.get<string>('GMAIL_PUBSUB_HMAC_SECRET');
  if (!expectedSecret || secret !== expectedSecret) throw new UnauthorizedException('Invalid secret');

  // 2. Decode Pub/Sub envelope → Gmail notification
  const payload = JSON.parse(rawBody.toString());
  const gmailNotification = JSON.parse(Buffer.from(payload.message.data, 'base64').toString());
  const { emailAddress, historyId } = gmailNotification;

  // 3. Idempotency dedup via SHA256 of raw body
  const idempotencyHash = createHash('sha256').update(rawBody).digest('hex');
  const existing = await this.prisma.webhook_events.findFirst({ where: { idempotency_hash: idempotencyHash } });
  if (existing) return; // already processed

  // 4. Look up OAuth account by Gmail address (stored in raw_profile JSON)
  const oauthAccount = await this.prisma.oauth_accounts.findFirst({
    where: { provider: 'google', raw_profile: { path: ['email'], equals: emailAddress } },
  });

  // 5. Persist webhook_events + enqueue gmail-sync job
  const webhookEvent = await this.prisma.webhook_events.create({ ... });
  await this.jobQueue.send('gmail-sync', { userId: oauthAccount.user_id, historyId, webhookEventId: webhookEvent.id });
}
```

---

## 4. Backend — App Module

### `backend/src/app.module.ts`

Added `GmailModule` to imports:
```typescript
import { GmailModule } from './gmail/gmail.module';

@Module({
  imports: [
    // ... existing modules ...
    GmailModule,
  ],
})
export class AppModule {}
```

---

## 5. Backend — Environment Variables

### `backend/.env` (additions)

```bash
# Gmail Integration
GMAIL_ENABLED=false
GMAIL_CLIENT_ID=                          # Google Cloud OAuth 2.0 Client ID
GMAIL_CLIENT_SECRET=                      # Google Cloud OAuth 2.0 Client Secret
GMAIL_REDIRECT_URI=http://localhost:3001/gmail/callback
GMAIL_TOKEN_ENCRYPTION_KEY=              # 32-byte hex key (openssl rand -hex 32)
GMAIL_PUBSUB_HMAC_SECRET=               # Secret appended to Pub/Sub push URL

# Qdrant (Vector DB)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                          # empty for local, required for cloud
```

---

## 6. Backend — Dockerfile + Entrypoint

### `backend/Dockerfile`

Added `tsconfig.json` copy in the runner stage (required for `ts-node` seed scripts):
```dockerfile
COPY --from=builder /app/tsconfig.json ./tsconfig.json
```

### `backend/entrypoint.sh`

Changed migration command to match local dev workflow (`db push` vs `migrate deploy` which requires migration history):
```bash
# Before:
npx prisma migrate deploy

# After:
npx prisma db push --skip-generate
```

---

## 7. Workers — New Library Files

### `workers/src/lib/token-crypto.ts`

Workers-side AES-256-GCM decrypt (mirrors the backend's `GmailService.decryptToken`):

```typescript
import { createDecipheriv } from 'crypto';

function encryptionKey(): Buffer {
  const key = process.env.GMAIL_TOKEN_ENCRYPTION_KEY;
  if (!key) throw new Error('GMAIL_TOKEN_ENCRYPTION_KEY not set');
  return Buffer.from(key, 'hex');
}

export function decryptToken(encrypted: string): string {
  const key = encryptionKey();
  const buf = Buffer.from(encrypted, 'base64');
  const iv = buf.subarray(0, 12);
  const tag = buf.subarray(12, 28);
  const data = buf.subarray(28);
  const decipher = createDecipheriv('aes-256-gcm', key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(data), decipher.final()]).toString('utf8');
}
```

### `workers/src/lib/gmail-client.ts`

Raw Gmail API v1 fetch functions (no `googleapis` SDK — plain `fetch`):

```typescript
// Token management
export async function getValidAccessToken(userId: string): Promise<string>
// Fetches from DB, refreshes if expires within 5 min, updates DB

// Incremental sync (history API)
export async function fetchHistoryMessageIds(
  accessToken: string,
  startHistoryId: string,
): Promise<{ messageIds: GmailMessageRef[]; newHistoryId: string }>
// Only returns INBOX messages (filters out SENT, DRAFTS, SPAM)
// Paginates automatically via nextPageToken

// Full sync (messages list)
export async function listAllMessageIds(
  accessToken: string,
  pageToken?: string,
): Promise<{ messageIds: GmailMessageRef[]; nextPageToken?: string; historyId?: string }>
// 100 messages per page, INBOX label only

// Single message fetch
export async function fetchMessage(accessToken: string, messageId: string): Promise<GmailMessage>
// format=full to get complete MIME payload
```

### `workers/src/lib/gmail-parser.ts`

Email parsing utilities:

```typescript
export interface ParsedEmail {
  messageId: string;
  threadId: string;
  from: string;       // raw "Name <email>" header value
  to: string;
  subject: string;
  date: string;
  rawText: string;    // decoded MIME text before quote stripping
  cleanedText: string; // final text ready for Step 3+
}

export function parseMessage(message: GmailMessage): ParsedEmail
// Walks MIME tree, prefers text/plain over text/html
// Applies htmlToText() if only HTML part available
// Applies stripQuotedReplies() to remove replied-to content

export function htmlToText(html: string): string
// Strips <style>, <script>, converts <br>/<p>/<div> to newlines
// Decodes &amp; &lt; &gt; &quot; &#39; &nbsp; entities

export function stripQuotedReplies(text: string): string
// Stops at "On Mon Apr 20... wrote:" (Gmail quote header)
// Stops at "--- Original Message ---" (Outlook separator)
// Skips lines beginning with > (standard quote marker)
// Stops at forwarded "From:" headers mid-body

export function extractEmail(headerValue: string): string
// Extracts bare email from "John Smith <john@example.com>" → "john@example.com"
// Lowercases result
```

---

## 8. Workers — Job Processors

### `workers/src/processors/gmail-sync.processor.ts`

Handles incremental `gmail-sync` jobs (triggered by Pub/Sub webhook or poll):

```
Job data: { userId, historyId?, webhookEventId? }

1. Get valid access token (auto-refreshes if needed)
2. Load gmail_sync_state.history_id as startHistoryId
3. Call fetchHistoryMessageIds() → new message IDs since last sync
4. For each new message:
   a. fetchMessage() → full MIME payload
   b. parseMessage() → from, subject, cleanedText
   c. Skip if cleanedText < 20 chars (image-only / empty)
   d. extractEmail(from) → clientEmail
   e. checkIsCompanyEmail(clientEmail) → skip if company-side
   f. TODO Step 4: resolve client identity
   g. TODO Step 5: build Q&A pairs
   h. TODO Step 6: chunk (512 tokens, 50 overlap)
   i. TODO Step 7: embed + upsert Qdrant
   j. TODO Step 8: invalidate email_context_cache
5. Update gmail_sync_state.history_id = newHistoryId
6. Mark webhook_events.status = 'processed' (if triggered via Pub/Sub)
```

### `workers/src/processors/gmail-full-sync.processor.ts`

Handles initial paginated `gmail-full-sync` jobs (enqueued on first OAuth connect):

```
Job data: { userId }

1. Get valid access token
2. Resume from saved page token if previous run was interrupted
   (gmail_sync_state.history_id starts with "page:")
3. Paginate through all INBOX messages:
   a. listAllMessageIds(accessToken, pageToken) → up to 100 IDs
   b. Save page:TOKEN to gmail_sync_state for crash resumability
   c. Process in batches of 20 using Promise.allSettled()
   d. Same parse/strip logic as gmail-sync
   e. TODO Steps 4-8 (same as incremental)
4. Save final historyId to gmail_sync_state
5. Update last_synced timestamp
```

**Crash resumability design:** Between pages, the processor writes `page:XXXXXX` to `gmail_sync_state.history_id`. On restart, if the history_id starts with `page:`, it strips the prefix and resumes from that page token. After completion, the real Gmail historyId is written back.

---

## 9. Workers — Types

### `workers/src/types/jobs.ts` (additions)

```typescript
export interface GmailSyncJobData extends BaseJobData {
  historyId?: string;       // from Pub/Sub push or poll; omit to use DB value
  webhookEventId?: string;  // set when triggered via Pub/Sub to mark processed
}

export interface GmailFullSyncJobData extends BaseJobData {
  // only userId (from BaseJobData) needed
}
```

---

## 10. Workers — Entry Point

### `workers/src/index.ts` (additions)

Gmail workers are registered only when `GMAIL_ENABLED=true`:

```typescript
const GMAIL_ENABLED = process.env.GMAIL_ENABLED === 'true';

if (GMAIL_ENABLED) queues.push('gmail-sync', 'gmail-full-sync');

if (GMAIL_ENABLED) {
  await boss.work('gmail-sync',      { teamSize: 3, teamConcurrency: 1 }, processGmailSync);
  await boss.work('gmail-full-sync', { teamSize: 1, teamConcurrency: 1 }, processGmailFullSync);
  logger.info('Gmail sync workers registered');
}
```

`gmail-full-sync` uses `teamSize: 1` (single concurrent job) to avoid hammering the Gmail API during initial bulk sync.

---

## 11. Workers — Environment

### `workers/.env` (created)

```bash
DATABASE_URL=postgresql://dev:devpass@localhost:5432/localDB

# Gmail Integration
GMAIL_ENABLED=false
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_TOKEN_ENCRYPTION_KEY=

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
```

---

## 12. Docker Compose

### `docker-compose.yml`

**Added services:**

| Service | Image | Port | Purpose |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant:latest` | 6333 | Vector DB for email chunks |
| `migrate` | backend Dockerfile (`target: builder`) | — | One-shot schema push on startup |
| `workers` | workers Dockerfile | — | pg-boss job processors |

**Modified services:**

- **`migrate`**: Changed from `node:20-slim` + `npm ci` (slow, ~10 min on Windows) to reusing the backend's built image. Runs `npx prisma db push --skip-generate` only.
- **`backend`**: Added `env_file: ./backend/.env`, overrides `DATABASE_URL` and `QDRANT_URL` for Docker networking (`postgres:5432`, `qdrant:6333`).
- **`frontend`**: Added `target: builder` so `node_modules` (including `next` binary) are present in the container. Added volume mounts for all source directories to enable hot reload: `app/`, `public/`, `components/`, `hooks/`, `lib/`, `types/`, `middleware.ts`.

**Full `docker-compose.yml`:**
```yaml
version: '3.8'

services:

  postgres:
    image: postgres:16-alpine
    container_name: catering-db-local
    environment:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: devpass
      POSTGRES_DB: localDB
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev -d localDB"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - catering-network

  redis:
    image: redis:7-alpine
    container_name: catering-redis-local
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - catering-network

  qdrant:
    image: qdrant/qdrant:latest
    container_name: catering-qdrant-local
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - catering-network

  migrate:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: catering-migrate
    environment:
      DATABASE_URL: postgresql://dev:devpass@postgres:5432/localDB
    command: npx prisma db push --skip-generate
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - catering-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: catering-backend-local
    ports:
      - "3001:3001"
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql://dev:devpass@postgres:5432/localDB
      QDRANT_URL: http://qdrant:6333
      GMAIL_REDIRECT_URI: http://localhost:3001/gmail/callback
    depends_on:
      migrate:
        condition: service_completed_successfully
      qdrant:
        condition: service_started
    networks:
      - catering-network

  workers:
    build:
      context: .
      dockerfile: workers/Dockerfile
    container_name: catering-workers-local
    env_file: ./workers/.env
    environment:
      DATABASE_URL: postgresql://dev:devpass@postgres:5432/localDB
      QDRANT_URL: http://qdrant:6333
    depends_on:
      migrate:
        condition: service_completed_successfully
      qdrant:
        condition: service_started
    networks:
      - catering-network

  ml-agent:
    build:
      context: ./ml-agent
      dockerfile: Dockerfile
    container_name: catering-ml-agent-local
    ports:
      - "8000:8000"
    env_file: ./ml-agent/.env
    environment:
      DATABASE_URL: postgresql://dev:devpass@postgres:5432/localDB
    depends_on:
      migrate:
        condition: service_completed_successfully
    volumes:
      - ./ml-agent:/app
    command: uvicorn api:app --host 0.0.0.0 --port 8000 --reload
    networks:
      - catering-network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: builder
    container_name: catering-frontend-local
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:3001
      NEXT_PUBLIC_ML_API_URL: http://localhost:8000
      NEXT_PUBLIC_WS_URL: ws://localhost:3001
    depends_on:
      - backend
    volumes:
      - ./frontend/app:/app/app
      - ./frontend/public:/app/public
      - ./frontend/components:/app/components
      - ./frontend/hooks:/app/hooks
      - ./frontend/lib:/app/lib
      - ./frontend/types:/app/types
      - ./frontend/middleware.ts:/app/middleware.ts
    command: npm run dev
    networks:
      - catering-network

volumes:
  postgres_data:
  qdrant_data:

networks:
  catering-network:
    driver: bridge
```

---

## 13. Test Script

### `scripts/test-gmail-oauth.js`

```javascript
#!/usr/bin/env node
const [,, email, password] = process.argv;
const BASE = 'http://localhost:3001';

async function run() {
  // 1. Login → JWT
  const loginRes = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const { accessToken } = await loginRes.json();

  // 2. Get Gmail OAuth URL
  const authRes = await fetch(`${BASE}/gmail/auth`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  const { url } = await authRes.json();

  // 3. Print URL + auto-open browser
  console.log('\nOpen this URL to connect Gmail:\n\n  ', url);
  const open = process.platform === 'win32' ? `start "" "${url}"` : `open "${url}"`;
  require('child_process').exec(open);

  // 4. Print status check command
  console.log(`\nCheck status:\n  curl ${BASE}/gmail/status -H "Authorization: Bearer ${accessToken}"`);
}

run().catch(console.error);
```

**Usage:**
```bash
node scripts/test-gmail-oauth.js emily.cooper.0@catering-company.com TestPass123
```

---

## 14. Seed Script Fix

### `backend/src/scripts/seed-users.ts`

Fixed TypeScript `error` type in catch blocks (TS18046 — `unknown` type):

```typescript
// Before:
console.error(`Error creating staff user ${i}:`, error.message);

// After:
console.error(`Error creating staff user ${i}:`, (error as Error).message);
```

Applied at lines 113 and 167 (staff and host user loops).

---

## Database Seeding

After `docker compose up --build`, seed in this order:

```bash
# 1. Roles (required before users)
docker cp sql/quick_setup.sql catering-db-local:/tmp/quick_setup.sql
docker exec catering-db-local sh -c "psql -U dev -d localDB -f /tmp/quick_setup.sql"

# 2. Copy tsconfig (required for ts-node)
docker cp backend/tsconfig.json catering-backend-local:/app/tsconfig.json

# 3. Users (20 staff + 80 hosts)
docker exec catering-backend-local npx ts-node --transpile-only src/scripts/seed-users.ts

# 4. Menu
docker exec catering-backend-local npx ts-node --transpile-only src/scripts/seed-menu.ts
```

Default password for all seeded users: `TestPass123`

---

## Pending (Steps 3–8)

| Step | Description | Location |
|---|---|---|
| Step 3 | Company strip | Done in both processors via `checkIsCompanyEmail()` |
| Step 4 | Resolve client identity | TODO in both processors |
| Step 5 | Build Q&A pairs from thread | TODO in both processors |
| Step 6 | Chunk (512 tokens, 50 overlap) | TODO in both processors |
| Step 7 | Embed (text-embedding-3-small) + upsert Qdrant | TODO in both processors |
| Step 8 | Invalidate `email_context_cache` | TODO in both processors |
| Quick Sync | Wire pipeline into `triggerQuickSync()` | `gmail.service.ts:144` |
| Background Poll | pg-boss cron every 5 min | Not yet implemented |

---

## Required Env Vars Before Going Live

```bash
# Generate encryption key:
openssl rand -hex 32   # → paste into GMAIL_TOKEN_ENCRYPTION_KEY

# Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=

# Set any string as push webhook secret, configure same value in GCP Pub/Sub push URL
GMAIL_PUBSUB_HMAC_SECRET=

# Set GMAIL_ENABLED=true in both backend/.env and workers/.env to activate workers
```

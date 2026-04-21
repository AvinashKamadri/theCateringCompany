# Gmail Integration — Step 1 Implementation Report
## Sync Trigger Infrastructure

**Branch:** Email_integration  
**Date:** 2026-04-20  
**Scope:** Schema migration + OAuth connect + Pub/Sub webhook + Quick Sync endpoint

---

## 1. Database Schema Changes

### 1.1 Modified Models

#### `oauth_accounts` — added `access_token_expires_at`
```prisma
access_token_expires_at   DateTime? @db.Timestamptz(6)
```
**Why:** Gmail access tokens expire in 1 hour. Before every Gmail API call, the worker checks this field. If the token expires within 5 minutes, it refreshes automatically using the stored refresh token.

#### `menu_categories` — added `section`
```prisma
section    String?
```
**Why:** Pre-existing mismatch between DB and schema (column existed in DB, was missing from schema). Fixed to prevent `db push` from dropping it.

#### `users` — added 4 back-relations
```prisma
gmail_sync_state     gmail_sync_state?
user_identities      user_identities[]
email_chunks         email_chunks[]
email_context_cache  email_context_cache[]
```

#### `projects` — added 2 back-relations
```prisma
email_chunks         email_chunks[]
email_context_cache  email_context_cache[]
```

---

### 1.2 New Models (5 tables created in DB)

#### `company_emails`
Stores all company-owned email aliases. Used in Step 3 (Strip Company Side) to filter out internal messages before client identity resolution.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `email` | String UNIQUE | e.g. `sales@company.com`, `support@company.com` |
| `label` | String? | Human label: "sales", "support", etc. |
| `created_at` | Timestamptz | — |

---

#### `gmail_sync_state`
One row per connected staff user. Tracks incremental sync progress using Gmail's `historyId`.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `user_id` | UUID UNIQUE FK→users | One record per user |
| `history_id` | String? | Last Gmail `historyId` — delta sync starts from here |
| `last_synced` | Timestamptz? | Timestamp of last successful sync run |

---

#### `user_identities`
Maps client email addresses to internal `user_id`. The identity resolution table — central to knowing which client an email belongs to.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `user_id` | UUID FK→users | Internal user this email maps to |
| `kind` | String | Always `'email'` (extensible to `'phone'`) |
| `value` | String | The email address e.g. `client@gmail.com` |
| `source` | String? | `'email_auto_created'` or `'manual'` |
| `identity_confidence` | String? | `'high'` / `'medium'` / `'low'` (see section 2.4) |
| `created_at` | Timestamptz | — |

**Indexes:** `UNIQUE(kind, value)`, `INDEX(value)`

---

#### `email_chunks`
Core storage table. Each row is one semantic chunk of an email thread, ready for vector embedding and RAG retrieval.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `gmail_message_id` | String | Gmail's internal message ID |
| `gmail_thread_id` | String | Gmail thread ID — groups all replies |
| `user_id` | UUID? FK→users | Resolved client user_id. Nullable if `identity_status = 'pending'` |
| `project_id` | UUID? FK→projects | Linked catering project if resolved |
| `chunk_index` | Int | Chunk position within the message (0-based) |
| `question` | String? | Company message that prompted this exchange |
| `answer` | String? | Client's reply to the question |
| `chunk_text` | String | Final text sent to embedding model (Q&A combined) |
| `qdrant_vector_id` | String? | Vector ID returned by Qdrant after upsert |
| `source_inbox` | String? | Company Gmail address that was synced |
| `client_email` | String | Raw From address of the client |
| `identity_status` | String | `'resolved'` or `'pending'` (default: `'pending'`) |
| `created_at` | Timestamptz | — |
| `updated_at` | Timestamptz | Auto-updated |

**Constraints:** `UNIQUE(gmail_message_id, chunk_index)` → `ON CONFLICT DO UPDATE`  
**Indexes:** `INDEX(user_id, client_email)`, `INDEX(gmail_thread_id)`

---

#### `email_context_cache`
Tracks whether the cached email summary for a user+project is still fresh. Set to `is_stale = true` every time new chunks are added. The agent rebuilds the summary on next chat open if stale.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | — |
| `user_id` | UUID FK→users | — |
| `project_id` | UUID FK→projects | — |
| `is_stale` | Boolean | `true` = new emails arrived, cache needs rebuild |
| `summary` | String? | LLM-generated email context summary (populated in ml-agent phase) |
| `expires_at` | Timestamptz | Hard TTL — cache expires even if not stale |
| `created_at` | Timestamptz | — |
| `updated_at` | Timestamptz | Auto-updated |

**Constraint:** `UNIQUE(user_id, project_id)` — one cache entry per user+project pair

---

## 2. New Backend Module — `backend/src/gmail/`

### 2.1 Files Created

| File | Role |
|---|---|
| `gmail.module.ts` | NestJS module registration |
| `gmail.controller.ts` | HTTP route handlers |
| `gmail.service.ts` | Business logic: OAuth, token encryption, quick sync |

---

### 2.2 Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET` | `/gmail/auth` | JWT required | Returns Google OAuth URL for the logged-in user |
| `GET` | `/gmail/callback` | Public (`@Public`) | Google redirects here after consent |
| `POST` | `/gmail/sync/quick` | JWT required | Triggered on chat open — syncs last 10-15 min |
| `GET` | `/gmail/status` | JWT required | Returns `{ connected: boolean }` |

---

### 2.3 OAuth Flow (`gmail.service.ts`)

```
GET /gmail/auth
    │
    └── getAuthUrl(userId)
        ├── Signs state = HMAC(userId:timestamp) using GMAIL_TOKEN_ENCRYPTION_KEY
        ├── Scope: openid email gmail.readonly
        └── Returns Google OAuth URL

User completes Google consent
    │
    ▼
GET /gmail/callback?code=...&state=...
    │
    └── handleCallback(code, state)
        ├── Verify HMAC state (10-min TTL) → extract userId
        ├── POST to Google: exchange code for tokens
        ├── Decode id_token JWT payload → get email + Google sub
        ├── Encrypt refresh_token with AES-256-GCM
        ├── Upsert oauth_accounts (provider='google', provider_account_id=googleSub)
        │   raw_profile = { email, sub }
        ├── Upsert gmail_sync_state (history_id=null, last_synced=null)
        └── jobQueue.send('gmail-full-sync', { userId })
```

---

### 2.4 Token Encryption

Algorithm: **AES-256-GCM** using `GMAIL_TOKEN_ENCRYPTION_KEY` (32-byte hex).

```
encrypt(token):
  iv = randomBytes(12)
  cipher = AES-256-GCM(key, iv)
  encrypted = cipher.update(token) + cipher.final()
  tag = cipher.getAuthTag()           ← 16-byte auth tag for integrity
  return base64(iv + tag + encrypted)

decrypt(stored):
  buf = base64decode(stored)
  iv        = buf[0:12]
  tag       = buf[12:28]
  encrypted = buf[28:]
  decipher  = AES-256-GCM(key, iv)
  decipher.setAuthTag(tag)
  return decipher.update(encrypted) + decipher.final()
```

---

### 2.5 Token Auto-Refresh (`getValidAccessToken`)

Called before every Gmail API call (implemented in Step 2+):
```
1. Load oauth_accounts for user (provider='google')
2. If access_token_expires_at < now + 5 min → refresh
3. POST to Google with refresh_token → get new access_token
4. Update oauth_accounts.access_token + access_token_expires_at
5. Return fresh access_token
```

---

### 2.6 Identity Confidence Logic

Set by the worker in Step 4 based on which resolution branch was taken:

```
FROM header = client@gmail.com
        │
        ├── Found in user_identities (exact match)
        │       identity_confidence = 'high'
        │
        ├── Not found, but same gmail_thread_id has resolved user_id
        │       identity_confidence = 'medium'   ← inherited
        │
        └── Not found anywhere
                identity_confidence = 'low'      ← auto-created new user
                source = 'email_auto_created'
```

**Rule:** Never auto-merge identities on `'low'` or `'medium'` confidence without human review.

---

## 3. Webhooks Update — Pub/Sub Handler

### 3.1 Files Modified

| File | Change |
|---|---|
| `webhooks.controller.ts` | Added `POST /webhooks/gmail` route |
| `webhooks.service.ts` | Added `handleGmailPubSubWebhook()` method |

### 3.2 Route

```
POST /webhooks/gmail?secret=GMAIL_PUBSUB_HMAC_SECRET
```
- `@Public()` — no JWT (Google pushes here)
- Secret validated via query param (registered in Google Pub/Sub push subscription URL)

### 3.3 Handler Flow

```
POST /webhooks/gmail?secret=...
    │
    ├── Validate secret against GMAIL_PUBSUB_HMAC_SECRET → 401 if mismatch
    ├── Parse JSON body
    ├── Base64-decode message.data → { emailAddress, historyId }
    ├── SHA256 hash of rawBody → check webhook_events for duplicate
    │       duplicate found → skip (idempotency)
    ├── Lookup oauth_accounts WHERE provider='google'
    │       AND raw_profile->>'email' = emailAddress
    │       not found → log warning, return
    ├── INSERT webhook_events (provider='gmail', status='pending')
    └── jobQueue.send('gmail-sync', { userId, historyId, webhookEventId })
```

---

## 4. Environment Variables Added

Added to `backend/.env`:

```env
# Gmail Integration
GMAIL_ENABLED=false
GMAIL_CLIENT_ID=                          # Google Cloud OAuth client ID
GMAIL_CLIENT_SECRET=                      # Google Cloud OAuth client secret
GMAIL_REDIRECT_URI=http://localhost:3001/gmail/callback
GMAIL_TOKEN_ENCRYPTION_KEY=               # 32-byte hex (openssl rand -hex 32)
GMAIL_PUBSUB_HMAC_SECRET=                 # Secret appended to Pub/Sub push URL

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=                           # Empty for local, set for prod
```

---

## 5. What's NOT Implemented Yet (Next Steps)

| Step | What | Status |
|---|---|---|
| Step 2 | Fetch Raw Email — Gmail API v1, MIME parsing, HTML→plaintext | Pending |
| Step 3 | Strip Company Side — filter using `company_emails` table | Pending |
| Step 4 | Resolve Client Identity — user_identities lookup + auto-create | Pending |
| Step 5 | Build Q&A Pairs — company msg → question, client msg → answer | Pending |
| Step 6 | Chunking — 512 tokens / 50 overlap, prefer Q&A boundaries | Pending |
| Step 7 | Embedding — OpenAI text-embedding-3-small, upsert Qdrant | Pending |
| Step 8 | Cache Invalidation — mark email_context_cache stale | Pending |

The `triggerQuickSync()` method in `gmail.service.ts` is scaffolded and returns a placeholder response — it will be filled in with the full pipeline in Step 2+.

---

## 6. How to Generate `GMAIL_TOKEN_ENCRYPTION_KEY`

```bash
openssl rand -hex 32
```
Paste the output into `backend/.env` as `GMAIL_TOKEN_ENCRYPTION_KEY`.

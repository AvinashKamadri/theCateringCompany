# Gmail Email Integration — Full Implementation Report (Steps 1–7)

**Branch:** `Email_integration`  
**Last Updated:** 2026-04-21  
**Scope:** Complete Gmail pipeline from OAuth connect → email fetch → identity resolution → project routing → conversation accumulation → Qdrant vector storage (Steps 1–6 complete; Step 7 cache invalidation pending)

---

## Overview

When a client emails the catering company directly (without using the chatbot), those emails are now automatically synced, parsed, attributed to the correct client and project, and stored as searchable vectors in Qdrant. This enables the AI agent to greet returning clients with context about their event inquiry.

The pipeline runs in two modes:
- **Full sync** — on first Gmail connect, paginated scan of entire inbox
- **Incremental sync** — triggered by Gmail Pub/Sub push webhook or 5-minute background poll

---

## Pre-Existing Files Modified

These are files that already existed in the codebase before this feature was started and were changed as part of the integration.

### `backend/prisma/schema.prisma`

**What changed:**
- Extended `oauth_accounts` with `access_token_expires_at` — tracks when the Google access token expires so both backend and workers can auto-refresh before API calls
- Extended `users` with back-relations to all new email tables
- Extended `projects` with back-relations to all new email tables
- Added `pending_invitations` model
- Added `email_conversations` model
- Added 5 new models: `company_emails`, `gmail_sync_state`, `user_identities`, `email_chunks`, `email_context_cache`
- Added a second Prisma generator so workers can use the same schema without a separate `schema.prisma`

---

### `backend/src/webhooks/webhooks.controller.ts`

**What changed:**
- Added `POST /webhooks/gmail` route
- Route is `@Public()` — no JWT guard (Google Pub/Sub pushes here, not a logged-in user)
- Secret validated via query param (`?secret=...`) registered in the Google Pub/Sub push subscription URL

---

### `backend/src/webhooks/webhooks.service.ts`

**What changed:**
- Added `handleGmailPubSubWebhook(rawBody, secret)` method
- Handles secret validation, Pub/Sub envelope decoding, idempotency check via SHA256 body hash, OAuth account lookup by Gmail address, and job enqueue

---

### `backend/src/app.module.ts`

**What changed:**
- Added `GmailModule` to the NestJS module imports array so Gmail routes are registered in the app

---

### `backend/src/auth/auth.service.ts`

**What changed:**  
Added an upgrade path for clients who were auto-created by the email pipeline and later sign up through the app.

When a client emails before signing up, the pipeline creates a `users` row with their email but no `password_hash`. When they later register:
- Instead of throwing `ConflictException('Email already in use')`, the service detects the account has no password and treats it as an upgrade
- Sets the password hash, creates their profile, assigns their role
- Retroactively links all their `email_chunks` (where `client_email` matches and `project_id` is null) to the project they just joined
- Marks any `pending_invitations` for that email as accepted

---

### `backend/src/projects/projects.service.ts`

**What changed — `addCollaborator`:**  
Previously threw `NotFoundException` if the invited email was not found in the `users` table. Now instead creates a `pending_invitations` row. This allows staff to invite a client by email before they sign up. When the pipeline encounters an email from that address, it checks `pending_invitations` to route to the correct project.

**What changed — `joinProject`:**  
After creating the `project_collaborators` record, retroactively updates `email_chunks` — any chunks with that user's `client_email` and `project_id = null` get linked to the joined project. Also marks the `pending_invitations` row as accepted.

---

### `backend/entrypoint.sh`

**What changed:**  
Changed `npx prisma migrate deploy` to `npx prisma db push --skip-generate`. The migrate deploy command requires a migrations directory with a tracked history, which was not set up. `db push` applies the current schema state directly, matching how local dev works.

---

### `backend/Dockerfile`

**What changed:**  
Added a `COPY tsconfig.json` step in the runner stage. The seed scripts use `ts-node`, which requires `tsconfig.json` to be present at runtime, not just build time.

---

### `backend/src/scripts/seed-users.ts`

**What changed:**  
Fixed TypeScript type errors in catch blocks — `error` was typed as `unknown` (TS18046), required cast to `Error` before accessing `.message`.

---

### `workers/src/index.ts`

**What changed:**
- Added `gmail-sync` and `gmail-full-sync` to the registered job queues
- Both workers are gated behind a `GMAIL_ENABLED=true` environment variable flag
- `gmail-full-sync` uses `teamSize: 1` to avoid hammering the Gmail API during bulk initial sync
- `gmail-sync` uses `teamSize: 3` for concurrent incremental processing

---

### `workers/src/types/jobs.ts`

**What changed:**  
Added two new job data interfaces:
- `GmailSyncJobData` — carries `historyId` (optional, falls back to DB value) and `webhookEventId` (to mark the event processed after completion)
- `GmailFullSyncJobData` — carries only `userId` (inherited from base)

---

### `workers/package.json`

**What changed:**  
Added runtime dependencies:
- `@qdrant/js-client-rest` — Qdrant vector DB client
- `openai` — for text-embedding-3-small embeddings

---

### `docker-compose.yml`

**What changed:**
- Added `qdrant` service (vector DB, port 6333, persistent volume)
- Added `migrate` service — one-shot container that runs `prisma db push` before backend starts, ensuring schema is always current
- Added `workers` service — runs pg-boss job processors
- Backend and workers both get `QDRANT_URL: http://qdrant:6333` injected via Docker environment override (instead of localhost)
- Frontend updated to use `target: builder` stage so `node_modules` including the `next` binary are present

---

## New Database Tables (Summary)

| Table | Purpose |
|---|---|
| `company_emails` | Stores catering company's own email aliases. Used to strip internal messages from sync. |
| `gmail_sync_state` | One row per connected staff user. Tracks Gmail `historyId` watermark for incremental sync. Also stores `page:TOKEN` for full-sync crash resumability. |
| `user_identities` | Maps client email addresses to internal `user_id`. Central identity lookup table. |
| `email_chunks` | Lightweight tracking table. One row per processed message — stores `gmail_thread_id` + `project_id` so future replies in the same thread inherit the same project automatically. No Q&A extraction. |
| `email_conversations` | One living document per `(user_id, project_id)`. Full conversation text accumulated as emails arrive. |
| `email_context_cache` | Cache status per `(user_id, project_id)`. `is_stale = true` tells the agent to rebuild context on next chat open (Step 8). |
| `pending_invitations` | Bridges the gap when staff invites a client by email before they sign up. |

---

## Cases Handled and How

### 1. Automated / Bot Email Filtering

**Problem:** No-reply systems (DocuSign, Mailchimp, notification services) send emails to the inbox that have no meaningful client content.

**How handled:**  
Two layers, checked before any identity resolution or storage:
- **Pattern matching on From address** — regex list covering `noreply@`, `no-reply@`, `donotreply@`, `mailer@`, `bounce@`, etc.
- **Header inspection** — checks for presence of `auto-submitted`, `list-unsubscribe`, `list-id`, `x-auto-response-suppress`, `x-campaign-id` headers. Also checks `Precedence: bulk/list/junk`.

If either check passes, the message is skipped entirely. No DB write, no identity lookup.

---

### 2. Company-Side Email Stripping

**Problem:** The synced inbox contains both client emails and company replies. Only client emails should be attributed and stored.

**How handled:**  
The `company_emails` table is loaded once per job into a `Set<string>`. For each message, the `From` address is extracted and checked against this set. If it matches (e.g., `sales@company.com`, `info@company.com`), the message is skipped.

Loading once per job (not once per message) avoids repeated DB queries for large syncs.

---

### 3. Identity Resolution — 4 Layers

Determines which internal `user_id` corresponds to the client who sent the email.

**Layer 1 — Exact email match:**  
Look up `user_identities` by `{ kind: 'email', value: clientEmail }`. If found → `user_id` assigned, confidence = `'high'`.

**Layer 2 — Thread inheritance:**  
If no identity record exists, check `email_chunks` for other rows with the same `gmail_thread_id` that already have a `user_id`. If found → inherit that `user_id`, register a new `user_identities` entry for future lookups, confidence = `'medium'`.  
This handles cases like a client replying from a secondary email address (e.g., personal vs. work) within the same conversation.

**Layer 3 — Existing user, missing identity:**  
Check the `users` table directly by email. If a user exists (e.g., seeded users or registered users who emailed before identity records were created) but has no `user_identities` row, create one and return their `user_id`, confidence = `'high'`.  
This fixed a bug where seeded staff/client users were being re-created as new auto-generated users.

**Layer 4 — Auto-create:**  
If no match at any layer, create a new `users` row (email only, no password) and a corresponding `user_identities` row with `source = 'email_auto_created'`. This is the pre-signup user — they can later complete registration via the upgrade path.

---

### 4. Project Resolution — 5 Layers

Determines which catering project an email belongs to.

**Layer 1 — Thread inheritance:**  
Before any project lookup, check `email_chunks` for other rows with the same `gmail_thread_id` that already have a `project_id`. If found, use that project. Ensures all replies in the same conversation stay in the same project regardless of timing.

**Layer 2 — Single active project:**  
Query `project_collaborators` for this user's projects, filter by non-closed statuses (`completed` and `cancelled` are excluded). If exactly one active project exists, use it.

**Layer 3 — Pending invitation by email:**  
If the user has no active project membership (e.g., they emailed before signing up), check `pending_invitations` for their email address with `status = 'pending'`. If found, route to that project. This covers the magic-link / pre-signup scenario where staff already invited them.

**Layer 4 — Auto-create project:**  
If zero active projects and no pending invitation, create a new draft project with `created_via_ai_intake = true` and add the client as `owner` collaborator. This ensures every client email always gets a project even for first-contact inquiries.

**Layer 5 — Ambiguous (2+ active projects):**  
If the user has multiple active projects (e.g., planning a wedding and a birthday separately), attempt keyword scoring: compare the email subject and first 300 characters of body against each project's `title` and `event_date`. Title word matches score 2 points each; month name matches score 3 points; year matches score 1 point. If one project clearly leads (top score > 0 and strictly ahead of runner-up), assign it. Otherwise, store the chunk with `project_id = null` and `identity_status = 'ambiguous_project'` — no Qdrant embed until staff manually assigns.

**Project status filter:**  
Only `draft`, `active`, `confirmed` statuses are eligible. `completed` and `cancelled` are excluded. This ensures new emails from a returning client (planning a new event) don't get mixed into their old completed event's data.

---

### 5. Conversation Accumulation and Vector Storage

**Design decision:** Instead of embedding individual Q&A chunks, maintain one growing conversation document per `(user_id, project_id)` pair. Each new email appends to this document, which is re-embedded and upserted into Qdrant.

**How it works:**  
After the `email_chunks` row is stored, `upsertEmailConversation` is called:
1. Appends the new email entry (formatted with date, from address, subject, cleaned body) to the existing `email_conversations.full_text`
2. Upserts the `email_conversations` row in Postgres
3. Embeds the entire `full_text` using OpenAI `text-embedding-3-small` (1536 dimensions)
4. Upserts a Qdrant point with a stable UUID (`qdrant_point_id`) — same UUID = update existing vector in place, no cleanup needed

The `full_text` is truncated to the last `~30,000 characters` if it exceeds the embedding model's token limit, keeping the most recent context.

**Qdrant collection:** `email_conversations`  
- One point per `(user_id, project_id)` 
- Payload includes: `user_id`, `project_id`, `client_email`, `full_text`, `message_count`, `last_email_at`, `event_title`, `event_date`
- Payload indexes on `user_id` and `project_id` for filtered lookup at chat open time

---

### 6. Auth Upgrade Path (Pre-signup → Full Account)

**Problem:** The pipeline may auto-create a `users` row when a client emails before signing up. When they later register via the app, a naive implementation would throw "email already in use".

**How handled:**  
During registration in `auth.service.ts`, if an existing user is found but `password_hash` is null (indicator of an email-pipeline-created account):
- Set their password, create their profile, assign their role — all in a transaction
- Look up all `email_chunks` where `client_email` matches and `project_id` is null → link them to the project the user joined
- Mark any `pending_invitations` for that email as accepted

---

### 7. Pre-signup Collaborator Invitation

**Problem:** Staff adds a client as collaborator before the client has a user account.

**How handled:**  
`projects.service.ts addCollaborator` was modified: if the invited email doesn't exist in `users`, instead of throwing `NotFoundException`, it creates a `pending_invitations` row with the project ID and email. When the email pipeline processes a message from that address, it checks `pending_invitations` to route to the correct project. When the user signs up and joins, the invitation is marked accepted and `email_chunks` are retroactively linked.

---

### 8. Full-Sync Crash Resumability

**Problem:** A full inbox sync can span hundreds of pages and may be interrupted.

**How handled:**  
Between pages, the full-sync processor writes `page:{nextPageToken}` to `gmail_sync_state.history_id`. On next startup, if `history_id` starts with `page:`, the prefix is stripped and the sync resumes from that page token. After all pages are processed, the real Gmail `historyId` (returned by the messages list API) is written back, enabling future incremental syncs.

---

## Pipeline Flow (End-to-End)

```
Client sends email to catering inbox
          │
          ▼
Gmail Pub/Sub push → POST /webhooks/gmail
          │
          ├── Validate secret
          ├── Decode notification → emailAddress, historyId
          ├── Idempotency check (SHA256 of raw body)
          ├── Lookup userId from oauth_accounts
          └── Enqueue gmail-sync job
                    │
                    ▼
          Worker: gmail-sync processor
                    │
                    ├── Get valid access token (auto-refresh if expiring)
                    ├── Gmail History API → new message IDs since last historyId
                    │
                    └── For each message:
                        ├── Fetch full MIME message
                        ├── Parse: extract from/subject/date, HTML→text, strip quoted replies
                        ├── Skip if: < 20 chars / automated headers / no-reply pattern
                        ├── Skip if: From = company email
                        ├── Resolve identity (4 layers)
                        ├── Resolve project (5 layers incl. ambiguity handling)
                        ├── Upsert minimal email_chunks row (thread→project tracking only)
                        ├── Append email entry to email_conversations.full_text
                        ├── Embed full_text (OpenAI text-embedding-3-small)
                        └── Upsert Qdrant point (stable UUID per user+project)
                    │
                    └── Update gmail_sync_state.history_id
```

---

## Pending

| Item | Status |
|---|---|
| **Step 7 — Cache invalidation** | After each Qdrant upsert, mark `email_context_cache.is_stale = true` for that `(user_id, project_id)`. Awaiting green signal. |
| **Context retrieval (ml-agent)** | At chat open: query Qdrant by `(user_id, project_id)` → pass `full_text` to LLM → structured summary → inject into agent greeting. Separate phase. |
| **Quick Sync wiring** | `POST /gmail/sync/quick` endpoint scaffolded — pipeline not wired in, returns placeholder. |
| **Background poll cron** | pg-boss `schedule()` to enqueue `gmail-sync` for all connected users every 5 minutes. Not started. |
| **Ambiguous project UI** | Staff view to manually assign `project_id` to messages with `identity_status = 'ambiguous_project'`. Not started. |

## Design Decision: No Q&A Extraction

Q&A pair extraction (fetching the full Gmail thread per message, walking backwards to find company question → client answer) was implemented and then removed.

**Reason:** The pipeline appends cleaned email text directly to `email_conversations.full_text` and embeds the full document. This gives the agent a complete, readable conversation per client+project. Q&A structuring added a full thread API call per message with no retrieval benefit for the current use case (agent greeting context).

`email_chunks` still exists as a lightweight tracking table: it stores `gmail_thread_id` + `project_id` per processed message so future replies in the same thread automatically inherit the correct project without re-running project resolution.

# Gmail Thread Context Integration — Production Implementation Plan

## Context

Users communicate with the catering company via Gmail before opening the AI chatbot. Currently the chatbot always starts fresh ("Hi! What's your name?"), losing all prior email context. This feature syncs the **catering company's Gmail inbox**, stores email threads, embeds them into a vector store, and uses **RAG (Retrieval-Augmented Generation)** to inject semantically relevant context — so the chatbot greets users with awareness: *"Hey, you discussed a wedding for 150 guests on June 15th via email. Would you like to proceed with these details or make any changes?"*

The chatbot **presents** the email context as a summary but does **not** pre-fill slots — the user still walks through every question normally, confirming or correcting each value.

All changes scoped to `ml-agent/` only.

---

## Tech Stack

| Layer | Technology | Purpose | Why This Choice |
|---|---|---|---|
| **Email Source** | Gmail API v1 (`google-api-python-client`) | Fetch company inbox threads, incremental sync via `historyId` | Industry standard, supports OAuth2, history-based incremental sync |
| **Email Sync Trigger** | FastAPI Background Tasks + Google Pub/Sub | Poll every 5min (primary), real-time push (secondary), on-demand (fallback) | Three triggers cover all deployment scenarios — no missed emails |
| **Email Parsing** | `html2text` + Python `email.mime` | HTML→plaintext, MIME multipart handling, quoted-reply stripping | Lightweight, no heavy NLP dependency for parsing |
| **Authentication** | Google OAuth 2.0 + Fernet encryption (`cryptography`) | Company Gmail read-only access, refresh token encryption at rest | `gmail.readonly` scope — minimal permissions; Fernet for symmetric encryption of tokens in DB |
| **Primary Database** | PostgreSQL (via Prisma ORM) | Store raw emails in `messages` table, sync state, context cache, OAuth tokens | Already the project's DB — no new infra; emails stored alongside chat messages |
| **Semantic Chunking** | Custom `EmailChunker` (Python) | Split emails into 512-token chunks with 50-token overlap, thread summaries | Optimized for `text-embedding-3-small`; semantic boundaries > arbitrary splits |
| **Embeddings** | OpenAI `text-embedding-3-small` (1536 dims) | Convert email chunks into vector representations | Best cost/quality ratio ($0.02/1M tokens); already have `openai` in requirements |
| **Vector Store** | Qdrant | Store and search email chunk embeddings with metadata filtering | Schema already has `qdrant_vector_id` field; payload indexes for user/project scoping; purpose-built for filtered vector search |
| **Retrieval** | Cosine similarity + custom reranking | Find top-K relevant chunks, boost by recency/chunk-type/keywords | Cosine similarity for semantic match; reranking adds domain-specific signals |
| **Summarization** | GPT-4o-mini (via existing `llm_extract`) | Summarize retrieved chunks into structured context | Already the project's LLM; deterministic (temp=0); structured JSON output |
| **Context Cache** | PostgreSQL `email_context_cache` table | Store pre-computed summaries with stale/invalidation flags | Instant chat startup; cache invalidated on new email sync; 24h TTL safety net |
| **API Layer** | FastAPI | OAuth endpoints, sync triggers, context retrieval, admin/debug | Already the project's web framework |
| **Background Jobs** | `asyncio.create_task` (FastAPI lifespan) | Periodic Gmail sync, Pub/Sub watch renewal, cache cleanup | No external job queue needed; runs in-process; sufficient for single-instance deployment |

### Tech Stack Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                               │
│                                                                              │
│   ┌──────────────┐    ┌──────────────────┐    ┌─────────────────────┐       │
│   │  Gmail API   │    │  Google Pub/Sub   │    │  OpenAI Embeddings  │       │
│   │  (v1, REST)  │    │  (push notifs)    │    │  (text-embed-3-sm)  │       │
│   └──────┬───────┘    └────────┬─────────┘    └──────────┬──────────┘       │
│          │                     │                          │                   │
└──────────┼─────────────────────┼──────────────────────────┼──────────────────┘
           │                     │                          │
           ▼                     ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ml-agent/ (Python 3.10+)                           │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │                      gmail/ package (NEW)                           │     │
│  │                                                                     │     │
│  │  oauth.py ──── Google OAuth 2.0 + Fernet token encryption          │     │
│  │  client.py ─── Gmail API wrapper (async, auto-refresh, backoff)    │     │
│  │  parser.py ─── MIME parsing, HTML cleanup, reply stripping         │     │
│  │  chunker.py ── Semantic chunking (512 tok, 50 overlap)            │     │
│  │  embeddings.py ── OpenAI embedding service (batch + single)        │     │
│  │  vector_store.py ── Qdrant client (upsert, search, delete)        │     │
│  │  indexing_pipeline.py ── chunk → embed → store orchestration       │     │
│  │  sync.py ──── Sync engine (poll + pubsub + on-demand)             │     │
│  │  context_builder.py ── RAG retrieval + rerank + summarize + cache  │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   FastAPI     │  │ Orchestrator │  │  LangGraph   │  │   GPT-4o-    │    │
│  │   (api.py)    │  │              │  │  (agent/)    │  │    mini      │    │
│  │              │  │  inject ctx   │  │  start_node  │  │  (llm.py)   │    │
│  │  /gmail/*    │  │  mid-conv RAG │  │  all nodes   │  │             │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘    │
│         │                 │                  │                  │            │
└─────────┼─────────────────┼──────────────────┼──────────────────┼───────────┘
          │                 │                  │                  │
          ▼                 ▼                  ▼                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            DATA STORES                                       │
│                                                                              │
│   ┌─────────────────────────────┐    ┌──────────────────────────────┐       │
│   │     PostgreSQL (Prisma)     │    │      Qdrant (Vector DB)      │       │
│   │                             │    │                              │       │
│   │  messages (raw emails +     │    │  email_chunks collection     │       │
│   │    chat messages)           │◄──►│  - 1536-dim COSINE vectors  │       │
│   │  email_context_cache        │    │  - payload: text, metadata   │       │
│   │  gmail_sync_state           │    │  - indexes: user_id,         │       │
│   │  oauth_accounts             │    │    project_id, thread_id     │       │
│   │  ai_conversation_states     │    │                              │       │
│   │  users, projects, threads   │    │  qdrant_vector_id linked     │       │
│   │  project_collaborators      │    │  back to messages table      │       │
│   └─────────────────────────────┘    └──────────────────────────────┘       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Flow Diagrams

### Flow 1: Email Sync Pipeline (Background)

```
                    ┌─────────────────────┐
                    │   Sync Triggered     │
                    │  (poll / pubsub /    │
                    │   on-demand)         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Load company OAuth   │
                    │ tokens from DB       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Tokens exist?        │
                    └──────┬─────────┬────┘
                       YES │         │ NO
                           │         │
                           │         ▼
                           │    ┌─────────┐
                           │    │ No-op,  │
                           │    │ return  │
                           │    └─────────┘
                           ▼
                    ┌─────────────────────┐
                    │ Check gmail_sync_    │
                    │ state.history_id     │
                    └──────┬─────────┬────┘
                     EXISTS│         │NULL
                           │         │
                    ┌──────▼──────┐  │
                    │ Incremental │  │
                    │ sync via    │  │
                    │ history API │  │
                    └──────┬──────┘  │
                           │    ┌────▼────────┐
                           │    │ Full sync   │
                           │    │ last 90 days│
                           │    └──────┬──────┘
                           │           │
                           └─────┬─────┘
                                 │
                    ┌────────────▼────────────┐
                    │  For each Gmail thread:  │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
              ▼                  ▼                   ▼
    ┌─────────────────┐ ┌───────────────┐  ┌────────────────┐
    │ Parse emails    │ │ Match sender  │  │ Match to       │
    │ (HTML→text,     │ │ → user        │  │ project        │
    │  strip quotes,  │ │ (by email in  │  │ (1 project →   │
    │  handle MIME)   │ │  users table) │  │  auto-match,   │
    │                 │ │               │  │  N projects →  │
    │ parser.py       │ │ Not found →   │  │  embed+cosine, │
    │                 │ │ SYSTEM_USER_ID│  │  0 projects →  │
    │                 │ │               │  │  create draft)  │
    └────────┬────────┘ └───────┬───────┘  └───────┬────────┘
             │                  │                   │
             └──────────────────┼───────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │     Store in PostgreSQL              │
              │     (messages table,                 │
              │      sender_type='system',           │
              │      gmail metadata in attachments)  │
              └─────────────────┬───────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │     Semantic Chunking                │
              │     ┌─────────────────────────┐     │
              │     │ Thread summary chunk     │     │
              │     │ (subject, participants,  │     │
              │     │  date range, preview)    │     │
              │     └─────────────────────────┘     │
              │     ┌─────────────────────────┐     │
              │     │ Per-message chunks       │     │
              │     │ (512 tok, 50 overlap,    │     │
              │     │  metadata prefix)        │     │
              │     └─────────────────────────┘     │
              │     chunker.py                      │
              └─────────────────┬───────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │     Batch Embed via OpenAI           │
              │     text-embedding-3-small           │
              │     (up to 2048 chunks per call)     │
              │     embeddings.py                    │
              └─────────────────┬───────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │     Upsert to Qdrant                 │
              │     (vector + payload with           │
              │      user_id, project_id,            │
              │      thread_id, text, metadata)      │
              │     vector_store.py                  │
              └─────────────────┬───────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │     Update PostgreSQL                │
              │     - messages.vector_status →       │
              │       'indexed'                      │
              │     - messages.qdrant_vector_id →    │
              │       point ID                       │
              │     - email_context_cache.stale →    │
              │       true (invalidate)              │
              │     - gmail_sync_state.history_id →  │
              │       updated cursor                 │
              └─────────────────────────────────────┘
```

### Flow 2: Chat Start — Context Retrieval

```
                    ┌─────────────────────┐
                    │  User opens chatbot  │
                    │  POST /chat          │
                    │  (first message)     │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  orchestrator.py     │
                    │  Is this a NEW       │
                    │  conversation?       │
                    └──────┬─────────┬────┘
                       YES │         │ NO (existing)
                           │         │
                           │         ▼
                           │    ┌──────────────┐
                           │    │ Normal flow, │
                           │    │ no ctx load  │
                           │    └──────────────┘
                           ▼
                    ┌─────────────────────┐
                    │  user_id available?  │
                    └──────┬─────────┬────┘
                       YES │         │ NO
                           │         │
                           │         ▼
                           │    ┌──────────────┐
                           │    │ Normal flow  │
                           │    │ (new user)   │
                           │    └──────────────┘
                           ▼
              ┌────────────────────────────────┐
              │  Check email_context_cache      │
              │  WHERE user_id AND project_id   │
              └────────┬──────────────┬────────┘
                  FOUND│         NOT  │
                  & NOT│         FOUND│ or STALE
                  STALE│              │
                       │              │
                       ▼              ▼
              ┌──────────────┐  ┌───────────────────────────┐
              │ Return cached │  │ Build retrieval query:    │
              │ summary       │  │ "catering event details   │
              │ (instant)     │  │  for user X, project Y"   │
              └──────┬───────┘  └────────────┬──────────────┘
                     │                       │
                     │                       ▼
                     │          ┌───────────────────────────┐
                     │          │ Embed query via OpenAI     │
                     │          │ text-embedding-3-small     │
                     │          └────────────┬──────────────┘
                     │                       │
                     │                       ▼
                     │          ┌───────────────────────────┐
                     │          │ Qdrant search              │
                     │          │ top_k=15, threshold=0.25   │
                     │          │ FILTERED by user_id +      │
                     │          │ project_id (security)      │
                     │          └────────────┬──────────────┘
                     │                       │
                     │              ┌────────▼────────┐
                     │              │ Chunks found?   │
                     │              └───┬─────────┬───┘
                     │              YES │         │ NO
                     │                  │         │
                     │                  │         ▼
                     │                  │    ┌──────────────────┐
                     │                  │    │ On-demand sync   │
                     │                  │    │ (fallback)       │
                     │                  │    │ → retry search   │
                     │                  │    └───────┬──────────┘
                     │                  │            │
                     │                  │   ┌───────▼──────┐
                     │                  │   │Still nothing? │
                     │                  │   └──┬────────┬──┘
                     │                  │   YES│        │NO
                     │                  │      │        │
                     │                  │      ▼        │
                     │                  │ ┌──────────┐  │
                     │                  │ │Return    │  │
                     │                  │ │None      │  │
                     │                  │ └────┬─────┘  │
                     │                  │      │        │
                     │                  └──┬───┘────────┘
                     │                     │
                     │                     ▼
                     │          ┌───────────────────────────┐
                     │          │ Rerank chunks:             │
                     │          │ - boost thread_summary     │
                     │          │ - boost recent emails      │
                     │          │ - boost catering keywords  │
                     │          │ Take top 10                │
                     │          └────────────┬──────────────┘
                     │                       │
                     │                       ▼
                     │          ┌───────────────────────────┐
                     │          │ LLM summarization          │
                     │          │ (GPT-4o-mini, temp=0)      │
                     │          │ → structured JSON:          │
                     │          │   { summary, details }      │
                     │          └────────────┬──────────────┘
                     │                       │
                     │                       ▼
                     │          ┌───────────────────────────┐
                     │          │ Cache result in            │
                     │          │ email_context_cache        │
                     │          │ (stale=false, TTL=24h)     │
                     │          └────────────┬──────────────┘
                     │                       │
                     └───────────┬───────────┘
                                 │
                                 ▼
                    ┌─────────────────────────────┐
                    │  start_node receives state   │
                    │  with email_context           │
                    └──────────┬──────────────┬───┘
                      HAS CTX  │              │ NO CTX
                               │              │
                    ┌──────────▼──────────┐   │
                    │ Context-aware       │   │
                    │ greeting:           │   │
                    │ "I see you emailed  │   │
                    │  about a wedding    │   │
                    │  for 150 guests on  │   │
                    │  June 15th..."      │   │
                    │                     │   │
                    │ → ask for name to   │   │
                    │   confirm & proceed │   │
                    └──────────┬──────────┘   │
                               │         ┌────▼──────────┐
                               │         │ Normal:       │
                               │         │ "Welcome!     │
                               │         │  What's your  │
                               │         │  name?"       │
                               │         └────┬──────────┘
                               │              │
                               └──────┬───────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │ current_node =   │
                            │ "collect_name"   │
                            │ (same either way)│
                            └──────────────────┘
```

### Flow 3: Mid-Conversation RAG

```
                    ┌────────────────────────────┐
                    │  User sends message         │
                    │  (any node except start,    │
                    │   generate_contract, final)  │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │  Normal slot extraction     │
                    │  (llm_extract as usual)     │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │  Embed user message         │
                    │  (text-embedding-3-small)   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │  Qdrant search              │
                    │  top_k=3, threshold=0.4     │
                    │  (higher bar than greeting  │
                    │   — precision over recall)   │
                    │  Scoped to user + project   │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │  Top result score ≥ 0.4?     │
                    └──────┬─────────────────┬────┘
                       YES │                 │ NO
                           │                 │
                           ▼                 ▼
              ┌──────────────────────┐  ┌──────────────────┐
              │ Append email chunks  │  │ No supplement,   │
              │ to llm_respond()     │  │ normal response  │
              │ as supplementary     │  │ generation       │
              │ context:             │  │                  │
              │                      │  │                  │
              │ "--- Relevant email  │  │                  │
              │  context ---         │  │                  │
              │  [Email from X on Y] │  │                  │
              │  ... chunk text ...  │  │                  │
              │  --- End ---         │  │                  │
              │  Use only if         │  │                  │
              │  directly relevant"  │  │                  │
              └──────────┬───────────┘  └────────┬─────────┘
                         │                       │
                         └───────────┬───────────┘
                                     │
                                     ▼
                    ┌────────────────────────────┐
                    │  LLM generates response     │
                    │  (with or without email     │
                    │   supplement — transparent   │
                    │   to user)                   │
                    └────────────────────────────┘
```

### Flow 4: OAuth Setup (One-Time Staff Action)

```
    ┌──────────────┐     ┌──────────────────────┐     ┌───────────────────┐
    │  Admin/Staff  │────►│ GET /gmail/auth/url   │────►│ Google OAuth      │
    │  clicks       │     │ (generates URL with   │     │ consent screen    │
    │  "Connect     │     │  HMAC-signed state)   │     │ (gmail.readonly)  │
    │   Gmail"      │     └──────────────────────┘     └─────────┬─────────┘
    └──────────────┘                                              │
                                                                  │ auth code
                                                                  ▼
    ┌──────────────────────────────────────────────────────────────────────┐
    │  POST /gmail/auth/callback                                          │
    │                                                                      │
    │  1. Verify HMAC state (CSRF check)                                  │
    │  2. Exchange auth code → access_token + refresh_token               │
    │  3. Encrypt refresh_token with Fernet (GMAIL_TOKEN_ENCRYPTION_KEY)  │
    │  4. Store in oauth_accounts table (provider='google')               │
    │  5. Fetch Gmail profile → store company email address               │
    │  6. Trigger initial full sync (last 90 days)                        │
    └──────────────────────────────────────────────────────────────────────┘
```

---

## Why RAG, Not Concatenation

Simply appending raw email text into the prompt fails at production scale:

| Problem | Impact |
|---|---|
| Token waste | 50 emails × 500 tokens = 25K tokens stuffed into every LLM call |
| Noise | Irrelevant emails (billing, spam replies) pollute context |
| No semantic filtering | Can't distinguish "wedding for 150 guests" from "invoice #4821" |
| Latency | More tokens = slower LLM response |
| Cost | gpt-4o-mini charges per token — wasted context = wasted money |

**RAG solves all of these:**
1. Emails are chunked and embedded at sync time (background, zero chat-time cost)
2. At chat time, only semantically relevant chunks are retrieved (top-K similarity search)
3. Retrieved chunks are summarized into a compact context blob
4. The summary is cached — subsequent requests are instant

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SYNC PIPELINE (Background)                   │
│                                                                     │
│  Gmail API ──► Parser ──► Chunker ──► Embedder ──► Qdrant          │
│     │              │           │           │           │             │
│     │         raw emails   semantic    OpenAI      vector           │
│     │                      chunks    embeddings    store            │
│     │              │                                                │
│     │              └──► PostgreSQL (messages table, gmail metadata)  │
│     │                                                               │
│  Triggers: Background Poll (5min) + Pub/Sub Webhook + On-Demand    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     RETRIEVAL PIPELINE (Chat Time)                   │
│                                                                     │
│  New conversation ──► Embed user/project query                      │
│                           │                                         │
│                    Qdrant similarity search (top-K chunks)           │
│                           │                                         │
│                    LLM summarization (chunks → structured summary)   │
│                           │                                         │
│                    Cache summary in email_context_cache table        │
│                           │                                         │
│                    Inject into start_node greeting                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     MID-CONVERSATION RAG (Any Node)                  │
│                                                                     │
│  User says something ambiguous ──► Embed user message               │
│                                        │                            │
│                                 Qdrant search (scoped to project)   │
│                                        │                            │
│                                 Inject relevant email chunks         │
│                                 as additional context to LLM call    │
└─────────────────────────────────────────────────────────────────────┘
```

**Key design decisions:**
- **Company inbox sync** — single Gmail OAuth for the catering company's email (e.g. `info@thecatering-company.com`). Staff manages the OAuth.
- **Qdrant as vector store** — schema already has `qdrant_vector_id` and `vector_status` fields on messages table. Env vars documented in onboarding guide.
- **OpenAI embeddings** — `text-embedding-3-small` (1536 dims, $0.02/1M tokens). Already have `openai` + `langchain-openai` in requirements.
- **Three sync triggers** — all built, switchable via config. Background poll primary, Pub/Sub for real-time, on-demand as fallback.

---

## Email Sync Triggers (All Three Built)

### Trigger A: Background Polling (Primary)

A FastAPI background asyncio task runs every N seconds, calls Gmail API with `historyId` for incremental sync.

```python
async def periodic_gmail_sync():
    interval = int(os.getenv("GMAIL_SYNC_INTERVAL_SECONDS", "300"))
    while True:
        try:
            await sync_company_inbox()
        except Exception as e:
            logger.error(f"Gmail sync error: {e}")
        await asyncio.sleep(interval)
```

- Works in any deployment (local, Docker, Render)
- No external infra dependency
- Configurable interval via env var

### Trigger B: Google Pub/Sub Push (Real-Time)

Register Gmail watch → Pub/Sub → webhook endpoint. Near real-time (seconds).

```python
@app.post("/gmail/webhook")
async def gmail_push_notification(request: Request):
    data = await request.json()
    # Decode Pub/Sub message → extract historyId → fetch + process new messages

# Watch renewal every 6 days (expires at 7)
async def renew_gmail_watch():
    while True:
        await gmail_client.watch(body={'topicName': TOPIC, 'labelIds': ['INBOX']})
        await asyncio.sleep(6 * 24 * 3600)
```

- Requires publicly accessible URL + GCP Pub/Sub setup
- Best for production with real-time requirements

### Trigger C: On-Demand (Fallback)

Emails fetched when a user opens chatbot and no cached context exists.

```python
if not cached_context and user_id:
    await sync_on_demand(user_email=user_email)
    context = await retrieve_and_summarize(user_id, project_id)
```

- Fills gaps when polling hasn't caught up
- Ensures first-time users always get context

### Production Strategy

All three are built. Deployment config controls which are active:

```env
GMAIL_SYNC_MODE=hybrid          # poll+ondemand | pubsub+ondemand | all
GMAIL_SYNC_INTERVAL_SECONDS=300 # for polling mode
GMAIL_PUBSUB_ENABLED=false      # enable when GCP is configured
```

---

## Phase 1: Schema & DB Layer

### 1.1 New table: `email_context_cache`

Stores pre-computed summaries so chat startup is instant:

```prisma
model email_context_cache {
  id                  String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  user_id             String?   @db.Uuid
  project_id          String?   @db.Uuid
  summary             String                  // LLM-generated summary
  extracted_details   Json                    // {"name": "John", "event_date": "June 15", ...}
  email_thread_ids    String[]                // gmail thread IDs included in this summary
  email_count         Int
  participants        String[]
  embedding_ids       String[]                // qdrant point IDs used to build this summary
  version             Int       @default(1)   // incremented on re-summarization
  stale               Boolean   @default(false) // marked true when new emails arrive
  created_at          DateTime  @default(now()) @db.Timestamptz(6)
  updated_at          DateTime  @default(now()) @db.Timestamptz(6)
  expires_at          DateTime?               @db.Timestamptz(6) // TTL for auto-cleanup

  @@unique([user_id, project_id])
  @@index([user_id])
  @@index([project_id])
  @@index([stale])
}
```

**Cache invalidation strategy:**
- When sync processes new emails for a user/project → mark `stale = true`
- On chat start, if `stale = true` → re-retrieve from Qdrant → re-summarize → update cache
- If `stale = false` → serve cached summary instantly
- TTL: `expires_at` set to 24h after creation as safety net

### 1.2 New table: `gmail_sync_state`

Tracks incremental sync cursor:

```prisma
model gmail_sync_state {
  id              String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  account_email   String    @unique         // company email address
  history_id      String?                   // Gmail history ID for incremental sync
  last_synced_at  DateTime? @db.Timestamptz(6)
  sync_status     String    @default("idle") // idle | syncing | error
  error_message   String?
  total_synced    Int       @default(0)      // running count of synced messages
  created_at      DateTime  @default(now()) @db.Timestamptz(6)
  updated_at      DateTime  @default(now()) @db.Timestamptz(6)
}
```

### 1.3 Map existing production tables in ml-agent's Prisma schema

**`oauth_accounts`** — already exists in production DB:
```prisma
model oauth_accounts {
  id                      String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  user_id                 String   @db.Uuid
  provider                String
  provider_account_id     String
  access_token            String?
  refresh_token_encrypted String?
  raw_profile             Json?
  created_at              DateTime @default(now()) @db.Timestamptz(6)
  users                   users    @relation(fields: [user_id], references: [id], onDelete: Cascade)
  @@unique([provider, provider_account_id])
}
```

**`project_collaborators`** — already exists in production DB:
```prisma
model project_collaborators {
  project_id String   @db.Uuid
  user_id    String   @db.Uuid
  role       String?
  added_at   DateTime @default(now()) @db.Timestamptz(6)
  added_by   String?  @db.Uuid
  projects   projects @relation(fields: [project_id], references: [id], onDelete: Cascade)
  users      users    @relation(fields: [user_id], references: [id], onDelete: Cascade)
  @@id([project_id, user_id])
}
```

### 1.4 DB functions in `database/db_manager.py`

**User/Project lookup:**
- `find_user_by_email(email) -> dict | None`
- `find_projects_for_user(user_id) -> list[dict]` — via project_collaborators + owner

**Gmail message storage:**
- `save_gmail_message(thread_id, project_id, content, gmail_metadata) -> str` — messages table with `sender_type='system'`, gmail metadata in `attachments` JSONB
- `find_gmail_messages_for_project(project_id) -> list[dict]`
- `gmail_message_exists(gmail_message_id) -> bool` — dedup check via `attachments->>'gmail_message_id'`

**OAuth:**
- `load_oauth_tokens(user_id, provider='google') -> dict | None`
- `save_oauth_tokens(user_id, provider, tokens, profile)`

**Sync state:**
- `get_gmail_sync_state(account_email) -> dict | None`
- `upsert_gmail_sync_state(account_email, history_id, status, error=None)`

**Context cache:**
- `get_email_context_cache(user_id, project_id) -> dict | None`
- `upsert_email_context_cache(user_id, project_id, summary, details, thread_ids, embedding_ids, participants, email_count)`
- `mark_context_cache_stale(user_id=None, project_id=None)` — called after sync
- `cleanup_expired_caches()` — delete where `expires_at < now()`

**Vector status:**
- `update_message_vector_status(message_id, status, qdrant_vector_id=None)`
- `get_pending_vector_messages(limit=100) -> list[dict]` — for batch embedding

---

## Phase 2: Vector Store & Embedding Pipeline

### 2.1 `gmail/embeddings.py` — Embedding service

```python
from openai import AsyncOpenAI

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dims, best cost/quality ratio
EMBEDDING_DIMENSIONS = 1536

class EmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed up to 2048 texts in one API call."""
        response = await self.client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS
        )
        return [item.embedding for item in response.data]

    async def embed_single(self, text: str) -> list[float]:
        """Embed a single text for query-time retrieval."""
        result = await self.embed_texts([text])
        return result[0]
```

### 2.2 `gmail/vector_store.py` — Qdrant operations

```python
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)

COLLECTION_NAME = "email_chunks"

class VectorStore:
    def __init__(self):
        self.client = AsyncQdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=30
        )

    async def ensure_collection(self):
        """Create collection if it doesn't exist. Idempotent."""
        collections = await self.client.get_collections()
        if COLLECTION_NAME not in [c.name for c in collections.collections]:
            await self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=1536,
                    distance=Distance.COSINE
                )
            )
            # Create payload indexes for filtered search
            await self.client.create_payload_index(COLLECTION_NAME, "user_id", "keyword")
            await self.client.create_payload_index(COLLECTION_NAME, "project_id", "keyword")
            await self.client.create_payload_index(COLLECTION_NAME, "gmail_thread_id", "keyword")

    async def upsert_chunks(self, points: list[PointStruct]):
        """Batch upsert embedding points."""
        await self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True  # ensure durability
        )

    async def search(
        self,
        query_vector: list[float],
        user_id: str | None = None,
        project_id: str | None = None,
        top_k: int = 10,
        score_threshold: float = 0.3
    ) -> list[dict]:
        """Semantic search with mandatory user/project scoping."""
        filters = []
        if user_id:
            filters.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
        if project_id:
            filters.append(FieldCondition(key="project_id", match=MatchValue(value=project_id)))

        results = await self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=Filter(must=filters) if filters else None,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "text": hit.payload["text"],
                "metadata": hit.payload
            }
            for hit in results
        ]

    async def delete_by_thread(self, gmail_thread_id: str):
        """Delete all chunks for a thread (for re-indexing)."""
        await self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="gmail_thread_id", match=MatchValue(value=gmail_thread_id))]
            )
        )
```

### 2.3 `gmail/chunker.py` — Semantic chunking

Emails are not split arbitrarily — they're chunked **semantically** to preserve meaning:

```python
@dataclass
class EmailChunk:
    text: str
    metadata: dict  # user_id, project_id, gmail_thread_id, gmail_message_id,
                    # from_address, subject, date, chunk_index, chunk_type

class EmailChunker:
    MAX_CHUNK_TOKENS = 512       # optimal for text-embedding-3-small
    OVERLAP_TOKENS = 50          # overlap between chunks for continuity

    def chunk_thread(self, parsed_thread: ParsedEmailThread, user_id: str | None,
                     project_id: str | None) -> list[EmailChunk]:
        chunks = []

        # 1. Thread-level summary chunk (always first)
        thread_summary = self._build_thread_summary(parsed_thread)
        chunks.append(EmailChunk(
            text=thread_summary,
            metadata={
                "chunk_type": "thread_summary",
                "gmail_thread_id": parsed_thread.gmail_thread_id,
                "subject": parsed_thread.subject,
                "user_id": user_id,
                "project_id": project_id,
                "participants": parsed_thread.participants,
                "date_range": f"{parsed_thread.earliest_date} to {parsed_thread.latest_date}",
            }
        ))

        # 2. Per-message chunks (with sliding window if message is long)
        for email in parsed_thread.emails:
            message_chunks = self._chunk_single_message(email, parsed_thread, user_id, project_id)
            chunks.extend(message_chunks)

        return chunks

    def _chunk_single_message(self, email, thread, user_id, project_id) -> list[EmailChunk]:
        """Split a single email into semantic chunks with overlap."""
        # Prepend email metadata as context for each chunk
        prefix = f"From: {email.from_address}\nSubject: {thread.subject}\nDate: {email.date}\n\n"
        body = email.body_text

        if self._count_tokens(prefix + body) <= self.MAX_CHUNK_TOKENS:
            return [EmailChunk(
                text=prefix + body,
                metadata={
                    "chunk_type": "email_body",
                    "gmail_thread_id": thread.gmail_thread_id,
                    "gmail_message_id": email.gmail_message_id,
                    "from_address": email.from_address,
                    "subject": thread.subject,
                    "date": email.date,
                    "user_id": user_id,
                    "project_id": project_id,
                }
            )]

        # Sliding window split for long emails
        return self._sliding_window_split(prefix, body, {
            "chunk_type": "email_body_part",
            "gmail_thread_id": thread.gmail_thread_id,
            "gmail_message_id": email.gmail_message_id,
            "from_address": email.from_address,
            "subject": thread.subject,
            "date": email.date,
            "user_id": user_id,
            "project_id": project_id,
        })

    def _build_thread_summary(self, thread: ParsedEmailThread) -> str:
        """Structured thread-level overview for high-level retrieval."""
        return (
            f"Email thread: {thread.subject}\n"
            f"Participants: {', '.join(thread.participants)}\n"
            f"Messages: {len(thread.emails)}\n"
            f"Date range: {thread.earliest_date} to {thread.latest_date}\n"
            f"Latest message preview: {thread.emails[-1].body_text[:300]}"
        )
```

**Why this chunking strategy:**
- **Thread summary chunk** — retrieved for broad "what did we discuss?" queries
- **Per-message chunks** — retrieved for specific detail queries ("what date did they mention?")
- **Metadata on every chunk** — enables filtered search (by user, project, thread)
- **512 token chunks** — optimal size for `text-embedding-3-small` (tested by OpenAI)
- **50 token overlap** — prevents loss of meaning at chunk boundaries

### 2.4 `gmail/indexing_pipeline.py` — Orchestrates sync → chunk → embed → store

```python
class IndexingPipeline:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStore()
        self.chunker = EmailChunker()

    async def index_thread(self, parsed_thread: ParsedEmailThread,
                           user_id: str | None, project_id: str | None):
        """Full pipeline: chunk → embed → store for one email thread."""

        # 1. Chunk the thread
        chunks = self.chunker.chunk_thread(parsed_thread, user_id, project_id)

        # 2. Batch embed all chunks
        texts = [c.text for c in chunks]
        embeddings = await self.embedding_service.embed_texts(texts)

        # 3. Build Qdrant points
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = str(uuid.uuid4())
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "text": chunk.text,
                    **chunk.metadata
                }
            ))

        # 4. Upsert to Qdrant
        await self.vector_store.upsert_chunks(points)

        # 5. Update message vector_status in PostgreSQL
        for chunk, point in zip(chunks, points):
            if "gmail_message_id" in chunk.metadata:
                await update_message_vector_status(
                    gmail_message_id=chunk.metadata["gmail_message_id"],
                    status="indexed",
                    qdrant_vector_id=str(point.id)
                )

        # 6. Invalidate context cache for this user/project
        await mark_context_cache_stale(user_id=user_id, project_id=project_id)

        return len(points)

    async def reindex_thread(self, gmail_thread_id: str, parsed_thread, user_id, project_id):
        """Delete old embeddings and re-index (for updated threads)."""
        await self.vector_store.delete_by_thread(gmail_thread_id)
        return await self.index_thread(parsed_thread, user_id, project_id)
```

---

## Phase 3: Gmail Module

### 3.1 `gmail/oauth.py` — OAuth flow for company inbox

- `get_authorization_url(redirect_uri, state) -> str` — Google OAuth URL with `gmail.readonly` scope
- `exchange_code_for_tokens(code, redirect_uri) -> dict`
- `store_tokens(user_id, tokens, profile)` — encrypts refresh token with Fernet (`GMAIL_TOKEN_ENCRYPTION_KEY`)
- `load_tokens(user_id) -> (access_token, refresh_token) | None` — decrypts
- `get_company_oauth_user_id() -> str | None` — finds user_id with company Gmail OAuth
- CSRF via HMAC-signed `state` parameter

### 3.2 `gmail/client.py` — Gmail API wrapper

- `GmailClient(access_token, refresh_token, client_id, client_secret)`
- Auto-refreshes expired tokens, updates DB on refresh
- `list_threads(query, max_results) -> list[dict]`
- `get_thread(thread_id) -> dict` — full thread with messages
- `get_profile() -> dict` — company email address
- `get_history(start_history_id) -> dict` — incremental sync
- All async via `asyncio.to_thread()` wrapping google-api-python-client
- Exponential backoff on 429/500 (max 3 retries, base 1s)

### 3.3 `gmail/parser.py` — Email parsing

```python
@dataclass
class ParsedEmail:
    gmail_message_id: str
    from_address: str
    to_addresses: list[str]
    cc_addresses: list[str]
    subject: str
    date: str                   # ISO 8601
    body_text: str              # cleaned plain text

@dataclass
class ParsedEmailThread:
    gmail_thread_id: str
    subject: str
    participants: list[str]     # unique email addresses
    emails: list[ParsedEmail]   # chronological order
    earliest_date: str
    latest_date: str
```

- HTML → plain text via `html2text`
- Strips quoted reply text (lines starting with `>`, `On ... wrote:` blocks)
- Truncates per-message body to 4000 chars (preserves first + last portions)
- Handles multipart MIME (prefers text/plain, falls back to text/html)
- Extracts inline images as `[image attachment]` placeholders

### 3.4 `gmail/sync.py` — Sync engine

```python
async def sync_company_inbox():
    """Main sync entry point. Called by all three triggers."""
    # 1. Load company OAuth tokens
    tokens = await load_company_tokens()
    if not tokens:
        logger.info("No company Gmail OAuth configured — skipping sync")
        return

    # 2. Get sync state (history_id for incremental)
    sync_state = await get_gmail_sync_state(COMPANY_EMAIL)
    await upsert_gmail_sync_state(COMPANY_EMAIL, sync_state.get("history_id"), "syncing")

    try:
        client = GmailClient(tokens)
        pipeline = IndexingPipeline()

        if sync_state and sync_state.get("history_id"):
            # Incremental sync via history API
            new_threads = await client.get_history(sync_state["history_id"])
        else:
            # Full initial sync (last 90 days)
            new_threads = await client.list_threads(query="newer_than:90d", max_results=500)

        for raw_thread in new_threads:
            parsed = parse_gmail_thread(raw_thread)

            # Match sender to user
            user_id = await match_sender_to_user(parsed)

            # Match to project
            project_id = await match_to_project(user_id, parsed)

            # Store raw messages in PostgreSQL
            await store_email_messages(parsed, user_id, project_id)

            # Chunk → embed → store in Qdrant
            await pipeline.index_thread(parsed, user_id, project_id)

        # Update sync cursor
        new_history_id = await client.get_current_history_id()
        await upsert_gmail_sync_state(COMPANY_EMAIL, new_history_id, "idle")

    except Exception as e:
        await upsert_gmail_sync_state(COMPANY_EMAIL, None, "error", str(e))
        raise
```

**Email-to-user matching:**
1. Extract sender email from parsed email
2. Look up in `users.email` → if found, we know the user
3. If not found: store with `SYSTEM_USER_ID`, tag `{"unmatched_sender": "email@..."}` in metadata

**Email-to-project matching (for matched users):**
1. Find user's active projects via `project_collaborators` + `projects.owner_user_id`
2. If exactly 1 active project → match
3. If multiple → embed email subject+body → cosine similarity against each project's `ai_event_summary` → best match
4. If no project → create new draft project with `created_via_ai_intake: true`

---

## Phase 4: Context Retrieval & Summarization

### 4.1 `gmail/context_builder.py` — RAG retrieval + LLM summarization

This is the core of the context pipeline. Two modes:

**Mode 1: Conversation start (greeting context)**

```python
async def build_email_context(
    user_id: str | None = None,
    project_id: str | None = None,
    user_email: str | None = None
) -> EmailContext | None:
    """Build context for conversation start. Uses cache when available."""

    # 1. Check cache first
    cached = await get_email_context_cache(user_id, project_id)
    if cached and not cached["stale"]:
        return EmailContext(**cached)

    # 2. Cache miss or stale — retrieve from Qdrant
    query = _build_retrieval_query(user_id, project_id, user_email)
    query_embedding = await embedding_service.embed_single(query)

    chunks = await vector_store.search(
        query_vector=query_embedding,
        user_id=user_id,
        project_id=project_id,
        top_k=15,                    # retrieve more, then rerank
        score_threshold=0.25
    )

    if not chunks:
        # Fallback: on-demand sync if no indexed emails found
        if user_email:
            await sync_on_demand(user_email)
            chunks = await vector_store.search(
                query_vector=query_embedding,
                user_id=user_id,
                project_id=project_id,
                top_k=15
            )
        if not chunks:
            return None

    # 3. Rerank: prioritize thread summaries and recent emails
    ranked_chunks = _rerank_chunks(chunks)[:10]

    # 4. LLM summarization of retrieved chunks
    summary, extracted_details = await _summarize_chunks(ranked_chunks)

    # 5. Build context object
    context = EmailContext(
        summary=summary,
        extracted_details=extracted_details,
        project_id=project_id,
        email_thread_subjects=list(set(c["metadata"]["subject"] for c in ranked_chunks)),
        participants=list(set(
            c["metadata"].get("from_address", "")
            for c in ranked_chunks if c["metadata"].get("from_address")
        )),
        raw_email_count=len(set(c["metadata"].get("gmail_message_id") for c in ranked_chunks)),
        chunk_ids=[c["id"] for c in ranked_chunks]
    )

    # 6. Cache the result
    await upsert_email_context_cache(
        user_id=user_id,
        project_id=project_id,
        summary=context.summary,
        details=context.extracted_details,
        thread_ids=list(set(c["metadata"]["gmail_thread_id"] for c in ranked_chunks)),
        embedding_ids=context.chunk_ids,
        participants=context.participants,
        email_count=context.raw_email_count
    )

    return context
```

**Mode 2: Mid-conversation retrieval (any node)**

```python
async def retrieve_relevant_email_context(
    user_message: str,
    user_id: str | None = None,
    project_id: str | None = None,
    top_k: int = 5
) -> str | None:
    """Retrieve email context relevant to a specific user message.
    Used mid-conversation when user references something from email."""

    query_embedding = await embedding_service.embed_single(user_message)

    chunks = await vector_store.search(
        query_vector=query_embedding,
        user_id=user_id,
        project_id=project_id,
        top_k=top_k,
        score_threshold=0.4   # higher threshold for mid-conversation (more precise)
    )

    if not chunks or chunks[0]["score"] < 0.4:
        return None  # nothing relevant enough

    # Format as compact context string
    context_parts = []
    for chunk in chunks:
        meta = chunk["metadata"]
        context_parts.append(
            f"[Email from {meta.get('from_address', '?')} on {meta.get('date', '?')}]\n"
            f"{chunk['text'][:500]}"
        )

    return "\n---\n".join(context_parts)
```

### 4.2 Reranking strategy

```python
def _rerank_chunks(chunks: list[dict]) -> list[dict]:
    """Rerank retrieved chunks by relevance signals beyond cosine similarity."""
    for chunk in chunks:
        score = chunk["score"]  # cosine similarity (0-1)
        meta = chunk["metadata"]

        # Boost thread summaries (best for greeting context)
        if meta.get("chunk_type") == "thread_summary":
            score *= 1.3

        # Boost recent emails (recency bias)
        if meta.get("date"):
            days_old = (datetime.now() - parse_date(meta["date"])).days
            recency_boost = max(0.8, 1.0 - (days_old / 365))
            score *= recency_boost

        # Boost emails with catering-relevant keywords
        text_lower = chunk["text"].lower()
        catering_keywords = ["wedding", "event", "guests", "menu", "catering", "date", "venue"]
        keyword_hits = sum(1 for kw in catering_keywords if kw in text_lower)
        score *= (1.0 + keyword_hits * 0.05)

        chunk["rerank_score"] = score

    return sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
```

### 4.3 LLM summarization prompt

```python
async def _summarize_chunks(chunks: list[dict]) -> tuple[str, dict]:
    """Use LLM to generate structured summary from retrieved chunks."""
    chunks_text = "\n\n---\n\n".join(c["text"] for c in chunks)

    response = await llm_extract(
        system_prompt=(
            "You are summarizing email conversations between a customer and a catering company. "
            "Extract a concise summary AND structured details.\n\n"
            "Return JSON with exactly this format:\n"
            "{\n"
            '  "summary": "2-3 sentence natural language summary of what was discussed",\n'
            '  "details": {\n'
            '    "client_name": "name or null",\n'
            '    "event_type": "wedding/corporate/birthday/etc or null",\n'
            '    "event_date": "date mentioned or null",\n'
            '    "guest_count": "number or null",\n'
            '    "venue": "venue or null",\n'
            '    "service_type": "drop-off/on-site or null",\n'
            '    "menu_preferences": "any food preferences mentioned or null",\n'
            '    "special_requests": "any special requests or null",\n'
            '    "budget": "budget if mentioned or null"\n'
            "  }\n"
            "}\n\n"
            "Only include details explicitly mentioned in the emails. Use null for anything not mentioned."
        ),
        user_message=f"Email excerpts:\n\n{chunks_text}"
    )

    parsed = json.loads(response)
    return parsed["summary"], parsed["details"]
```

---

## Phase 5: Conversation Flow Integration

### 5.1 `agent/state.py` — Add email_context field

```python
class ConversationState(TypedDict):
    ...
    email_context: dict | None  # RAG-retrieved gmail context (summary + details)
```

### 5.2 `orchestrator.py` — Inject context on new conversations + mid-conversation RAG

**On new conversation:**
```python
if not existing:
    email_ctx = None
    if user_id:
        try:
            email_ctx = await build_email_context(user_id=user_id, project_id=project_id)
        except Exception as e:
            logger.warning(f"Failed to load email context: {e}")

    state["email_context"] = email_ctx.__dict__ if email_ctx else None
```

**On every message (mid-conversation RAG):**
```python
# After slot extraction, before response generation
if user_id and state.get("current_node") not in ("start", "generate_contract", "final"):
    try:
        email_supplement = await retrieve_relevant_email_context(
            user_message=message,
            user_id=user_id,
            project_id=project_id,
            top_k=3
        )
        if email_supplement:
            state["email_context_supplement"] = email_supplement
    except Exception:
        pass  # non-critical — don't block conversation
```

### 5.3 `agent/nodes/start.py` — Context-aware greeting

```python
async def start_node(state: ConversationState) -> ConversationState:
    state = dict(state)
    state["slots"] = initialize_empty_slots()

    email_ctx = state.get("email_context")

    if email_ctx and email_ctx.get("summary"):
        context = (
            f"Email conversation summary: {email_ctx['summary']}\n"
            f"Details mentioned: {json.dumps(email_ctx.get('extracted_details', {}), indent=2)}\n"
            f"Participants: {', '.join(email_ctx.get('participants', []))}\n"
            f"Subjects: {', '.join(email_ctx.get('email_thread_subjects', []))}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "You have context from prior email conversations with this customer (shown below). "
            "Greet them warmly, mention you noticed their email exchange, and briefly summarize "
            "what was discussed. Present the key details you found. Then ask for their first and "
            "last name to get started (even if mentioned in email — we need to confirm).\n\n"
            "Do NOT pre-fill any booking details. The customer will confirm each one during the "
            "normal intake flow.",
            context
        )
    else:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['start']}",
            "A new customer has started a conversation. Welcome them and ask for their name."
        )

    state["current_node"] = "collect_name"
    state["messages"] = add_ai_message(state, response)
    return state
```

### 5.4 `agent/nodes/helpers.py` — Augment `llm_respond` with email supplement

Modify `llm_respond` to accept optional email context:

```python
async def llm_respond(system_prompt: str, context: str, email_supplement: str | None = None) -> str:
    if email_supplement:
        context += (
            "\n\n--- Relevant email context ---\n"
            f"{email_supplement}\n"
            "--- End email context ---\n"
            "Use the email context above only if directly relevant to the customer's current question."
        )
    # ... rest of existing llm_respond logic
```

---

## Phase 6: API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/gmail/auth/url` | GET | Generate OAuth authorization URL |
| `/gmail/auth/callback` | POST | Exchange auth code for tokens |
| `/gmail/sync` | POST | Trigger manual sync |
| `/gmail/sync/status` | GET | Sync status + stats |
| `/gmail/context/{user_id}` | GET | Get/preview email context for a user |
| `/gmail/context/{user_id}/invalidate` | POST | Force cache invalidation |
| `/gmail/webhook` | POST | Pub/Sub push notification receiver |
| `/gmail/search` | POST | Direct semantic search over email embeddings (debug/admin) |

### Background tasks in lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await vector_store.ensure_collection()  # idempotent Qdrant setup

    tasks = []

    # Background polling (if enabled)
    sync_mode = os.getenv("GMAIL_SYNC_MODE", "hybrid")
    if sync_mode in ("hybrid", "poll+ondemand", "all"):
        tasks.append(asyncio.create_task(periodic_gmail_sync()))

    # Pub/Sub watch renewal (if enabled)
    if os.getenv("GMAIL_PUBSUB_ENABLED", "false").lower() == "true":
        tasks.append(asyncio.create_task(renew_gmail_watch()))

    # Cache cleanup (hourly)
    tasks.append(asyncio.create_task(periodic_cache_cleanup()))

    yield

    for task in tasks:
        task.cancel()
    await close_client()
```

---

## Phase 7: Dependencies

### `requirements.txt` additions

```
# Gmail API
google-api-python-client>=2.100.0
google-auth-oauthlib>=1.2.0
google-auth>=2.25.0

# Vector store
qdrant-client>=1.12.0

# Email parsing
html2text>=2024.2.0

# Token encryption
cryptography>=42.0.0
```

**Note:** `openai` (for embeddings) and `langchain-openai` are already in requirements.

### Environment variables

```env
# Gmail OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GMAIL_TOKEN_ENCRYPTION_KEY=...            # Fernet key (base64)
GMAIL_OAUTH_STATE_SECRET=...              # HMAC signing key
GMAIL_COMPANY_EMAIL=info@thecatering.com

# Sync configuration
GMAIL_SYNC_MODE=hybrid                    # poll+ondemand | pubsub+ondemand | all
GMAIL_SYNC_INTERVAL_SECONDS=300
GMAIL_PUBSUB_ENABLED=false

# Vector store (already documented in onboarding guide)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=...

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small    # or text-embedding-3-large for higher quality
```

---

## Files Summary

### New files (all in `ml-agent/`)

| File | Purpose |
|---|---|
| `gmail/__init__.py` | Package init |
| `gmail/oauth.py` | OAuth URL, token exchange, Fernet encryption |
| `gmail/client.py` | Gmail API wrapper (threads, history, auto-refresh) |
| `gmail/parser.py` | Parse raw Gmail → structured `ParsedEmailThread` |
| `gmail/chunker.py` | Semantic chunking (thread summaries + per-message + sliding window) |
| `gmail/embeddings.py` | OpenAI embedding service (`text-embedding-3-small`) |
| `gmail/vector_store.py` | Qdrant operations (upsert, search, delete, collection management) |
| `gmail/indexing_pipeline.py` | Orchestrates chunk → embed → store pipeline |
| `gmail/sync.py` | Sync engine (all three triggers, user/project matching) |
| `gmail/context_builder.py` | RAG retrieval + reranking + LLM summarization + caching |
| `tests/test_gmail_parser.py` | Parser + chunker unit tests |
| `tests/test_gmail_context.py` | Context builder + vector search tests |
| `tests/test_gmail_indexing.py` | Indexing pipeline integration tests |

### Modified files (all in `ml-agent/`)

| File | Change |
|---|---|
| `database/schema.prisma` | Add `oauth_accounts`, `project_collaborators`, `gmail_sync_state`, `email_context_cache` models |
| `database/db_manager.py` | Add ~14 new DB functions (oauth, sync state, cache, vector status) |
| `agent/state.py` | Add `email_context` and `email_context_supplement` to `ConversationState` |
| `orchestrator.py` | Load email context on new conversation + mid-conversation RAG |
| `agent/nodes/start.py` | Context-aware greeting |
| `agent/nodes/helpers.py` | Augment `llm_respond` with optional email supplement |
| `api.py` | Add 8 gmail endpoints + background tasks in lifespan |
| `requirements.txt` | Add qdrant-client, google, cryptography, html2text |

---

## Security

- **gmail.readonly** scope only — never send emails
- Refresh tokens encrypted at rest with Fernet
- Access tokens short-lived (1hr), auto-refreshed
- OAuth state parameter HMAC-signed (CSRF prevention)
- Single company OAuth connection (staff-managed)
- Qdrant searches always scoped by `user_id`/`project_id` (no cross-user data leakage)
- Exponential backoff on Gmail API 429/500 (max 3 retries)
- Email bodies truncated before embedding (no PII in overly long chunks)

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Token refresh fails | Mark sync_status='error', retry next cycle, alert via log |
| Sender email not in users table | Store with SYSTEM_USER_ID, embed with `user_id=null`, tag in metadata |
| Multiple projects for same user | Embed email → cosine similarity against project `ai_event_summary` → best match |
| Very long email threads (100+) | Chunker handles via sliding window; retrieval returns only top-K relevant |
| Duplicate emails | Dedup via `gmail_message_id` check before insert + Qdrant upsert is idempotent |
| No company OAuth set up | Sync no-ops; context_builder returns None; chatbot works normally |
| Qdrant unavailable | Catch exception, log error, fall back to no-context greeting |
| Cache stale + Qdrant down | Serve stale cache with warning flag rather than no context |
| Email context but conversation already started | Only inject full context at `start` node; mid-conversation uses supplement |
| Gmail API rate limit (429) | Exponential backoff, max 3 retries, then skip to next cycle |
| Embedding API rate limit | Batch embeddings (up to 2048 per call), backoff on 429 |

---

## Verification

1. **Schema**: `prisma db push` + `prisma generate` — verify new models
2. **Qdrant**: Verify collection creation via `/gmail/search` endpoint
3. **OAuth flow**: GET `/gmail/auth/url` → consent → verify tokens in DB
4. **Sync + Indexing**: POST `/gmail/sync` → verify messages in PostgreSQL + vectors in Qdrant
5. **Context retrieval**: GET `/gmail/context/{user_id}` → verify summary from cached RAG
6. **Chat with context**: POST `/chat` → bot greets with email summary
7. **Chat without context**: POST `/chat` (no emails) → original welcome
8. **Mid-conversation RAG**: User references email detail → bot responds with awareness
9. **Cache invalidation**: New email arrives → cache marked stale → next chat rebuilds
10. **Tests**: `pytest tests/test_gmail_*.py`

---

## Implementation Order

1. Schema changes (`email_context_cache`, `gmail_sync_state`, map existing tables) → `prisma generate`
2. DB functions in `db_manager.py`
3. `gmail/embeddings.py` + `gmail/vector_store.py` + `gmail/chunker.py`
4. `gmail/parser.py` + `gmail/client.py` + `gmail/oauth.py`
5. `gmail/indexing_pipeline.py`
6. `gmail/sync.py`
7. `gmail/context_builder.py` (RAG retrieval + reranking + summarization + caching)
8. Modify `state.py` → `orchestrator.py` → `start.py` → `helpers.py`
9. API endpoints in `api.py` + background tasks
10. Tests

# TheCateringCompany Platform

A full-stack catering company management platform with AI-powered event intake, Slack-like messaging, contract management, e-signing, payments, and background workers.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (App Router), React 19, Tailwind CSS 4, Zustand, TanStack Query, socket.io-client |
| Backend | NestJS, Prisma, PostgreSQL 16, socket.io, Argon2, JWT HTTP-only cookies |
| Workers | pg-boss (PostgreSQL-backed queue), Puppeteer PDF, Stripe, SendGrid |
| ML Agent | FastAPI, LangGraph, LangChain-OpenAI (gpt-4o-mini) |
| Infrastructure | Docker Compose (dev), AWS EC2 + RDS + S3 (prod), AWS CDK (IaC) |

## Architecture

```
frontend/          Next.js app (Vercel in prod)
backend/           NestJS API server — port 3001
workers/           Background jobs (pg-boss processors)
ml-agent/          FastAPI AI chat agent — port 8000
infra/             AWS CDK stack (RDS + S3)
```

### Production Infrastructure
- **Frontend**: Vercel
- **Backend + Workers + ML Agent**: AWS EC2 (Docker Compose)
- **Database**: AWS RDS PostgreSQL 16
- **Job Queue**: pg-boss (runs on RDS — no Redis)
- **Storage**: AWS S3
- **IaC**: AWS CDK TypeScript (`infra/`)

## Local Development

### Prerequisites

- Node.js 20+
- Docker & Docker Compose
- Python 3.11+ (for ml-agent)

### 1. Clone & Install

```bash
git clone <repo-url>
cd TheCateringCompany

# Install all dependencies
cd backend && npm install
cd ../workers && npm install
cd ../frontend && npm install
cd ../ml-agent && pip install -r requirements.txt
```

### 2. Environment Setup

```bash
cp .env.example .env
```

Key variables for local dev:

```env
DATABASE_URL=postgresql://dev:devpass@localhost:5432/localDB
JWT_SECRET=supersecret_replace_me
OPENAI_API_KEY=sk-...
CORS_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_ML_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:3001
```

### 3. Run with Docker Compose

```bash
docker compose up --build
```

This starts: postgres, backend, workers, ml-agent, frontend.

### 4. Access

- Frontend: http://localhost:3000
- Backend API: http://localhost:3001/api
- ML Agent: http://localhost:8000/health

## Key Features

### AI Event Intake (ML Agent)
- LangGraph 11-node state machine
- Collects event details, guest count, menu selections via conversational AI
- Fetches real menu items from DB — no hallucination
- Stateless: all state persisted to PostgreSQL

### Authentication
- Signup/login with Argon2 password hashing
- HTTP-only JWT cookies (access + refresh token rotation)
- Session management with server-side revocation

### Projects & Messaging
- Create projects (catering events)
- Slack-like threaded messaging
- Real-time updates via socket.io
- @mentions support

### Contracts & E-Signing
- Versioned contracts (`contract_group_id`, `version_number`)
- PDF generation via Puppeteer (background worker)
- DocuSeal integration for e-signatures (`DOCUSEAL_ENABLED`)

### Payments (Stripe-Gated)
- Disabled by default (`STRIPE_ENABLED=false`)
- Mock mode: returns fake client secrets, still persists DB records
- Real mode: Stripe SDK with idempotency keys

### Background Workers (pg-boss)
- `webhooks` — Stripe/external webhook handling
- `payments` — Payment intent reconciliation
- `pdf_generation` — Contract PDF rendering
- `notifications` — Email via SendGrid (mock in dev)
- `virus_scan` — File scanning (mock in dev)
- `vector_indexing` — Semantic search embeddings (optional, `VECTOR_ENABLED`)
- `pricing_recalc` — Pricing calculations and margin alerts

## Database

Schema lives in `backend/prisma/schema.prisma` (57 models, 58 tables).

### Migrations

```bash
# Dev
cd backend && npx prisma migrate dev --name my_change

# Production (runs automatically on container start)
cd backend && npx prisma migrate deploy
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for full AWS deployment guide.

**Quick summary:**
1. `infra/` — run `npx cdk deploy` to create RDS + S3
2. EC2 — clone repo, create `.env.production`, run `docker compose -f docker-compose.gcp.yml up -d --build`
3. Vercel — import repo, set root to `frontend`, add env vars

## Project Structure

```
TheCateringCompany/
├── backend/                  # NestJS API
│   ├── src/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── projects/
│   │   ├── contracts/
│   │   ├── messages/
│   │   ├── attachments/
│   │   ├── payments/
│   │   ├── webhooks/
│   │   ├── notifications/
│   │   ├── sockets/
│   │   └── workers_producers/
│   └── prisma/
├── workers/                  # pg-boss background jobs
│   └── src/processors/       # 7 processors
├── frontend/                 # Next.js app
│   └── app/
├── ml-agent/                 # FastAPI + LangGraph
│   └── agent/nodes/          # 11 LangGraph nodes
├── infra/                    # AWS CDK (RDS + S3)
│   └── lib/infra-stack.ts
├── docker-compose.yml        # Local dev
├── docker-compose.gcp.yml    # Production (EC2)
├── .env.example              # Dev env template
├── .env.production.example   # Prod env template
└── DEPLOYMENT.md
```

## API Endpoints

### Auth
- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `GET  /api/auth/me`

### Projects
- `GET  /api/projects`
- `POST /api/projects`
- `GET  /api/projects/:id`

### Contracts
- `POST /api/projects/:projectId/contracts`
- `POST /api/contracts/:id/generate-pdf`

### Messages
- `GET  /api/projects/:projectId/threads`
- `POST /api/projects/:projectId/threads`
- `GET  /api/threads/:threadId`
- `POST /api/threads/:threadId/messages`

### Attachments
- `POST /api/attachments/sign`
- `POST /api/attachments/complete`

### Payments
- `POST /api/payments/create-intent`

### Webhooks
- `POST /api/webhooks/stripe`

### Notifications
- `GET  /api/notifications`
- `POST /api/notifications/:id/ack`

## WebSocket Events

**Server → Client**: `message.created`, `thread.created`, `notification.created`, `contract.updated`, `payment.updated`

**Client → Server**: `thread:join`, `thread:leave`, `message.typing`

## Troubleshooting

**Backend fails to start** — Check `DATABASE_URL`, run `npx prisma migrate deploy`

**Workers fail** — Check `DATABASE_URL`, check logs: `docker compose logs workers`

**Frontend can't reach backend** — Check `NEXT_PUBLIC_API_URL`, verify CORS origin in backend logs

**Prisma errors** — Run `npx prisma generate`, or `npx prisma migrate reset` (dev only)

## License

MIT

# CateringCo Platform

A full-stack catering company management platform with Slack-like messaging, contract management, payments (Stripe-gated), and background workers.

## Tech Stack

- **Frontend**: Next.js 16 (App Router), React 19, Tailwind CSS 4, socket.io-client, Zustand, TanStack Query
- **Backend**: NestJS, Prisma, PostgreSQL, socket.io, argon2, BullMQ
- **Workers**: BullMQ processors (webhooks, payments, PDF generation, vector indexing, notifications, virus scanning, pricing)
- **Infrastructure**: Redis, Docker Compose, GitHub Actions CI

## Architecture

- **Backend** (`backend/`): NestJS API server with Prisma ORM, JWT auth via HTTP-only cookies, socket.io gateway
- **Workers** (`workers/`): Separate Node.js service processing background jobs (PDF generation with Puppeteer, Stripe webhooks, notifications, etc.)
- **Frontend** (`frontend/`): Next.js app with real-time messaging, project management, contract viewing

## Database Schema

The authoritative schema is in [`sql/schema_final.sql`](sql/schema_final.sql). It includes 33 tables covering:

- **Identity & RBAC**: users, user_profiles, roles, role_permissions, user_roles
- **Auth**: sessions, auth_tokens, refresh_tokens, service_accounts, api_keys
- **Projects**: projects, project_collaborators, crm_pipeline
- **Messaging**: threads, messages (Slack-like threaded messaging)
- **Contracts**: contracts (versioned with contract_group_id), clause_templates, contract_clauses, change_orders
- **Payments**: payment_requests, payments, payment_schedules (with idempotency)
- **Webhooks**: webhook_events (retries & idempotency)
- **Attachments**: attachments (with virus scanning)
- **Pricing**: pricing_packages, project_pricing, margin_alerts
- **Events & Notifications**: events, notifications, activity_log

## Getting Started

### Prerequisites

- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 16 (or use Docker)
- Redis 7 (or use Docker)

### 1. Clone & Install

```bash
git clone <repo-url>
cd cateringCo

# Install backend dependencies
cd backend
npm install

# Install workers dependencies
cd ../workers
npm install

# Install frontend dependencies
cd ../frontend
npm install
```

### 2. Environment Setup

Copy `.env.example` to `.env` in the root:

```bash
cp .env.example .env
```

Key environment variables:

```env
DATABASE_URL=postgresql://dev:devpass@localhost:5432/localDB
REDIS_URL=redis://localhost:6379
JWT_SECRET=supersecret_replace_me
STRIPE_ENABLED=false  # Set to true when Stripe keys are configured
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
R2_ACCESS_KEY=
R2_SECRET_KEY=
CORS_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:3001
```

### 3. Database Setup

#### Option A: Docker Compose (Recommended)

```bash
docker-compose up -d postgres redis
```

#### Option B: Local Postgres

```bash
psql -U postgres -f sql/schema_final.sql
```

### 4. Prisma Setup

```bash
cd backend
npx prisma generate
npx prisma db pull  # Introspect existing DB
npx prisma migrate dev --name init  # Create baseline migration
```

### 5. Run Services

#### Development (separate terminals)

```bash
# Terminal 1: Backend
cd backend
npm run start:dev

# Terminal 2: Workers
cd workers
npm run start:dev

# Terminal 3: Frontend
cd frontend
npm run dev
```

#### Production (Docker Compose)

```bash
docker-compose up --build
```

### 6. Access the App

- Frontend: http://localhost:3000
- Backend API: http://localhost:3001/api
- Sign up at http://localhost:3000/signup

## Key Features

### Authentication
- Signup/login with argon2 password hashing
- HTTP-only JWT cookies (access token + refresh token rotation)
- Session management with server-side revocation

### Projects & Messaging
- Create projects (catering events)
- Slack-like threading: threads → messages → replies
- Real-time updates via socket.io
- @mentions support

### Contracts
- Versioned contracts with `contract_group_id`, `version_number`, `previous_version_id`
- PDF generation (background worker using Puppeteer)
- Track contract status (draft, sent, signed, etc.)

### Payments (Stripe-Gated)
- **Stripe disabled by default** (`STRIPE_ENABLED=false`)
- Mock mode: Returns fake client secrets, still persists DB records
- Real mode: Calls Stripe SDK with idempotency keys
- Webhook handling: Raw events persisted → background worker processes

### Attachments
- Presigned R2/S3 upload URLs (direct client upload)
- Virus scanning (worker enqueues scan, supports ClamAV or mock)
- Only serve attachments with `virus_scan_status = 'clean'`

### Background Workers (BullMQ)
- **webhooks**: Process Stripe/external webhooks
- **payments**: Reconcile PaymentIntents
- **pdf_generation**: Render contracts to PDF
- **vector_indexing**: Create embeddings for semantic search (optional, gated by `VECTOR_ENABLED`)
- **notifications**: Send emails/SMS (mock in local)
- **virus_scan**: Scan uploaded files
- **pricing_recalc**: Recalculate pricing, trigger margin alerts

All workers are **idempotent** (check domain-level status before processing). After N retries (default 5), failed jobs create an `events` row for manual review.

## Stripe Integration

### Local Development (Mock Mode)

```env
STRIPE_ENABLED=false
```

- `POST /api/payments/create-intent` returns `{ id: 'mock_pi_...', clientSecret: 'mock_secret_...' }`
- `payment_requests` and `payments` tables still populated
- UI/tests work identically to real Stripe

### Staging/Production (Real Mode)

1. Set Stripe keys in `.env`:
   ```env
   STRIPE_ENABLED=true
   STRIPE_SECRET_KEY=sk_live_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

2. Configure webhook endpoint in Stripe Dashboard:
   - URL: `https://your-domain.com/api/webhooks/stripe`
   - Events: `payment_intent.succeeded`, `payment_intent.payment_failed`, etc.

3. Test in staging first, then enable in production

## Database Migrations

### Add a new table/column

1. Edit `backend/prisma/schema.prisma`
2. Create migration:
   ```bash
   cd backend
   npx prisma migrate dev --name add_new_table
   ```
3. Commit `prisma/schema.prisma` and `prisma/migrations/`

### Production Migration

```bash
cd backend
npx prisma migrate deploy
```

This runs all pending migrations. Safe to run multiple times (idempotent).

## Testing

### Backend Unit Tests

```bash
cd backend
npm test
```

### Backend E2E Tests

```bash
cd backend
npm run test:e2e
```

### Frontend Tests

```bash
cd frontend
npm test
```

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push:

1. **Backend**: Install → Prisma generate → Lint → Build
2. **Workers**: Install → Copy Prisma schema → Generate → Lint → Build
3. **Frontend**: Install → Lint → Build

Services (postgres, redis) are provisioned as GitHub Actions service containers.

## Project Structure

```
cateringCo/
├── sql/
│   └── schema_final.sql          # Authoritative DB schema
├── backend/                       # NestJS API
│   ├── src/
│   │   ├── main.ts
│   │   ├── app.module.ts
│   │   ├── auth/                 # Auth module
│   │   ├── users/
│   │   ├── projects/
│   │   ├── contracts/
│   │   ├── messages/
│   │   ├── attachments/
│   │   ├── payments/
│   │   ├── webhooks/
│   │   ├── notifications/
│   │   ├── sockets/              # socket.io gateway
│   │   ├── workers_producers/    # BullMQ queue registration
│   │   └── common/               # Guards, decorators, filters
│   ├── prisma/
│   │   ├── schema.prisma
│   │   └── migrations/
│   └── package.json
├── workers/                       # Background jobs
│   ├── src/
│   │   ├── index.ts
│   │   ├── processors/           # 7 processors
│   │   └── lib/                  # Shared libs (prisma, redis, logger)
│   └── package.json
├── frontend/                      # Next.js app
│   ├── app/
│   │   ├── (auth)/               # Login/signup pages
│   │   └── (main)/               # Main app (projects, messages)
│   ├── components/
│   ├── hooks/
│   ├── lib/
│   ├── stores/
│   ├── types/
│   ├── providers/
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## API Endpoints

### Auth
- `POST /api/auth/signup` - Create user
- `POST /api/auth/login` - Authenticate
- `POST /api/auth/logout` - Revoke session
- `POST /api/auth/refresh` - Rotate refresh token
- `GET /api/auth/me` - Get current user

### Projects
- `GET /api/projects` - List projects
- `GET /api/projects/:id` - Get project (includes latest contract)
- `POST /api/projects` - Create project

### Contracts
- `POST /api/projects/:projectId/contracts` - Create contract version
- `POST /api/contracts/:id/generate-pdf` - Enqueue PDF generation

### Messages
- `GET /api/projects/:projectId/threads` - List threads
- `POST /api/projects/:projectId/threads` - Create thread
- `GET /api/threads/:threadId` - Get thread with messages
- `POST /api/threads/:threadId/messages` - Send message

### Attachments
- `POST /api/attachments/sign` - Get presigned upload URL
- `POST /api/attachments/complete` - Mark upload complete

### Payments
- `POST /api/payments/create-intent` - Create payment intent (mock or real)

### Webhooks
- `POST /api/webhooks/stripe` - Stripe webhook endpoint (public)
- `POST /api/webhooks/:provider` - Generic webhook endpoint

### Notifications
- `GET /api/notifications` - List notifications
- `POST /api/notifications/:id/ack` - Mark notification as read

## WebSocket Events

### Server → Client
- `message.created` - New message in a thread
- `thread.created` - New thread in a project
- `notification.created` - New notification for user
- `contract.updated` - Contract status changed
- `payment.updated` - Payment status changed

### Client → Server
- `thread:join` - Join a thread room
- `thread:leave` - Leave a thread room
- `message.typing` - User is typing

## Troubleshooting

### Backend fails to start

- Check `DATABASE_URL` is correct
- Ensure Postgres is running: `docker-compose ps`
- Run migrations: `npx prisma migrate deploy`

### Workers fail

- Check `REDIS_URL` is correct
- Ensure Redis is running: `redis-cli ping`
- Check worker logs: `docker-compose logs workers`

### Frontend can't connect to backend

- Ensure `NEXT_PUBLIC_API_URL` points to backend
- Check CORS is enabled: backend logs should show allowed origin

### Prisma errors

- Regenerate client: `npx prisma generate`
- Reset DB (dev only): `npx prisma migrate reset`

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit changes: `git commit -am 'Add feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

## License

MIT

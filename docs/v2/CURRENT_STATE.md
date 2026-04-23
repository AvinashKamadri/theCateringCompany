# Current State — 2026-04-23

Granular status of what's built, what's wired, what's missing. Companion to [ROADMAP_3_STEPS.md](./ROADMAP_3_STEPS.md) and [PRISMA_SCHEMA.md](./PRISMA_SCHEMA.md). The prior high-level 5-system plan lives at [../ARCHITECTURE_5_SYSTEMS.md](../ARCHITECTURE_5_SYSTEMS.md).

---

## Branch & commits

- Working branch: `feat` (local DB dev via Docker; see [../../scripts/](../../scripts/))
- Latest 5 commits:
  - `0e53f77` feat(ml-agent): adopt cascade architecture from ml-agent-branch
  - `4abfc8a` feat: redesign chat ui and ux
  - `30062bb` fix: chat ui rendering issues
  - `d466ce4` feat(ui): updated the inventory page
  - `7203b83` refactor: updated the menu.json

## Local stack

All four services on a shared Docker network (see [../../docker-compose.yml](../../docker-compose.yml)):

| Service | Container | Host port |
|---|---|---|
| Postgres 16 | catering-db-local | **5433** |
| Backend (NestJS) | catering-backend-local | 3001 |
| ML agent (FastAPI + LangGraph) | catering-ml-agent-local | 8000 |
| Frontend (Next.js 16) | catering-frontend-local | 3000 |

One-shot start: `.\scripts\restart-all.ps1`. First-time DB seed: `.\scripts\seed-db.ps1` (roles + 100 users + menu).

---

## Backend modules (`backend/src/`)

| Module | Status | Notes |
|---|---|---|
| `auth/` | ✅ shipped | JWT HTTP-only cookie, Passport, Argon2 |
| `users/` | ✅ shipped | Profiles, role assignments |
| `projects/` | ✅ shipped | CRUD, collaborators, ai-intake create, **waste-logs (new)** |
| `contracts/` | ✅ shipped | Versioned contracts, PDF via Puppeteer worker, DocuSeal webhook, summary enqueue on create |
| `payments/` | ✅ shipped | Stripe (gated), mock provider, reminders cron (`payment-reminders.service.ts`), schedule items |
| `messages/` | ✅ shipped | Threads, messages, mentions, socket.io broadcast |
| `notifications/` | ✅ shipped | In-app + email (SendGrid mock in dev) |
| `crm/` | ✅ shipped | Pipeline stages, leads, analytics |
| `inventory/` | ✅ shipped | Ingredients, dishes, dish↔ingredient links, stock log, menu-feed public endpoint |
| `attachments/` | ✅ shipped | S3/R2 presigned uploads, virus-scan hook |
| `pricing/` | ✅ shipped | Package-based pricing packages, recalc worker |
| `job_queue/` | ✅ shipped | pg-boss publisher |
| `opensign/`, `signwell/` | ✅ shipped | E-sign integrations |
| `sockets/` | ✅ shipped | Socket.io gateway |
| `webhooks/` | ✅ shipped | Stripe, DocuSeal, generic provider routes |
| `common/` | ✅ shipped | Guards, decorators, exception filter |

Missing: `invoices/` (Step 3).

### Routes added this session

- `GET    /api/projects/:projectId/waste-logs`
- `POST   /api/projects/:projectId/waste-logs`  (staff-only)
- `DELETE /api/projects/:projectId/waste-logs/:logId`  (staff-only)

All gated by staff domain `@catering-company.com`, matching `InventoryService` pattern.

---

## ML agent (`ml-agent/`)

Overlaid from `origin/ml-agent-branch` during this session — byte-identical to remote. Architecture is a **tool-based cascade** (not the previous LangGraph nodes/graph model). Key files:

| File | Role |
|---|---|
| `agent/cascade.py` | Main cascade dispatcher |
| `agent/router.py` | Phase / node selection |
| `agent/tools/*.py` | 6 tools: basic_info, menu_selection, add_ons, modification, finalization, plus `base.py` |
| `agent/tone_detector.py` | NEW — detects conversational tone shifts |
| `agent/state.py`, `orchestrator.py` | State machine runtime |
| `agent/instructor_client.py` | OpenAI wrapper with cached prompts (`prompt_cache_key` truncated to 64 chars) |
| `agent/prompt_registry.py` | Canonical prompt strings per node |
| `api.py` | FastAPI server, lifespan, chat/conversation endpoints |
| `tests/golden/*.json` | 8 golden transcripts for regression checks |

Files deleted in the overlay (old graph architecture, 20 files): `agent/graph.py`, `agent/input_hints.py`, `agent/llm.py`, `agent/nodes/*`, `agent/routing.py`, `tests/test_graph_compilation.py`, `tests/test_nodes.py`, `tests/test_routing.py`, `tests/test_tools.py`, `tools/missing_info.py`, `tools/modification_detection.py`, `tools/slot_extraction.py`, `tools/slot_validation.py`.

### Runtime dependency on `menu_categories.section`

ml-agent's generated Prisma client reads `menu_categories.section` in 4 places (`database/db_manager.py`). Backend's Prisma schema **now also declares** `section` (aligned during this session — previously drifted). Local DB has the column + composite unique on `(section, name)`.

---

## Frontend (`frontend/app/`)

| Route | Status |
|---|---|
| `/signin`, `/signup`, `/forgot-password` | ✅ |
| `/chat` (public intake) | ✅ updated from ml-agent-branch this session |
| `/(dashboard)/` | ✅ layout with `app-nav.tsx` (pill/glass nav) |
| `/(dashboard)/projects` (list) | ✅ |
| `/(dashboard)/projects/[id]` | ✅ + **event-waste UI (new)** |
| `/(dashboard)/projects/[id]/chat` | ✅ (project-scoped chat) |
| `/(dashboard)/projects/[id]/chat-enhanced` | ✅ |
| `/(dashboard)/projects/join` | ✅ join via code |
| `/(dashboard)/contracts/[id]` | ✅ |
| `/(dashboard)/crm` | ✅ staff-only CRM |
| `/(dashboard)/inventory` | ✅ staff-only, 2-tab (Ingredients / Dishes) |
| `/menu` | ✅ public, hits `/api/inventory/menu-feed` |
| `/(dashboard)/invoices` | ❌ not built (Step 3) |

### Chat UI bar

The chat input dock at the bottom of `/chat` was restyled this session: detached from the edge, `rounded-2xl`, soft drop shadow. Matches the nav's floating-pill convention without adopting the glass-white palette (dark bar stays for on-image contrast).

### Staff-only gate

Currently `currentUser.email?.endsWith('@catering-company.com')`. Matches backend's `InventoryService.assertStaff` and the new `ProjectsService.assertStaff`. No role-table check on frontend — backend is the source of truth.

---

## Database

- Docker Postgres 16, volume `postgres_data`, user `cateringco` / `local_dev_password` / db `cateringco_dev`.
- **3 migrations applied:**
  1. `20260321094550_init`
  2. `20260415000000_add_section_to_menu_categories`
  3. `20260420061929_add_payment_reminders_and_conversation_summary`
- **Non-migration ad-hoc changes applied this session** (because Prisma shadow-DB drift checks refused to auto-apply):
  - Added `menu_categories.section` TEXT NOT NULL DEFAULT ''
  - Replaced `menu_categories_name_key` unique with composite `menu_categories_section_name_key` on `(section, name)`
  - Created `project_waste_logs` table (via `prisma db push --accept-data-loss`)

The backend's `schema.prisma` is now the source of truth and matches reality. If prod RDS ever needs this synced, the cleanest path is to edit the `20260415…` migration to ship as-is (already applied there) and add a new `20260423…_add_project_waste_logs` migration. For local, `prisma db push` already aligned everything.

### Seed state

After the last session's wipes + reseeds:
- 3 roles (`staff`, `host`, `collaborator`), 33 role_permissions rows
- 0 users (wiped via `TRUNCATE users CASCADE` earlier; re-run `npm run seed:users` to add 20 staff + 80 hosts)
- 15 menu_categories, 78 menu_items, 154 dishes, 6 pricing_packages, 182 menu_item_dishes links

---

## Infrastructure / deploy

- **Local:** Docker Compose (`docker-compose.yml`)
- **Prod:** EC2 with `docker-compose.gcp.yml` + `.env.production` (backend, ml-agent, workers only — frontend on Vercel, DB on RDS)
- **No code was changed that affects prod** during this session. All config changes were to local-only files (`backend.env`, `backend/.env`, `ml-agent.env`, `docker-compose.yml` — which is only used locally).
- Cloudflare quick-tunnel for ml-agent → Vercel; URL rotates on restart (known gotcha, see [../../memory](memory) or the user's session notes).

---

## What's staged to commit (not yet committed)

- **ml-agent overlay** from `origin/ml-agent-branch` — 54 files (34 modified/added, 20 deleted)
- **Chat UI overlay** from same branch — 2 files (`app/chat/page.tsx`, `components/chat/ai-chat.tsx`)
- **Local dev setup** — `docker-compose.yml` (port 5433, version key removed), 4 new scripts in `scripts/` (`restart-db.ps1`, `seed-db.ps1`, plus edits to existing three)
- **Schema alignment** — `backend/prisma/schema.prisma` now declares `section` on `menu_categories` + `project_waste_logs` model; `seed-menu.ts` upsert adjusted for composite unique
- **Waste-log feature** — new service methods + 3 routes + frontend modal
- **Chat input bar redesign** — `rounded-2xl` floating pill
- **Payment reminders service** — your in-flight edit to `backend/src/payments/payment-reminders.service.ts`
- **Docs** — this file, `ROADMAP_3_STEPS.md`, `PRISMA_SCHEMA.md` (all under `docs/v2/`)

Reasonable commit split:
1. `feat(ml-agent): adopt cascade architecture + chat UI from ml-agent-branch` — the ml-agent overlay + 2 chat files
2. `chore(dev): local Docker stack + scripts, remove obsolete compose version key` — compose, scripts, envs
3. `feat(projects): event-level waste logs` — schema, API, UI
4. `fix(schema): align menu_categories.section across all Prisma schemas` — schema drift resolution
5. `docs: add v2/ roadmap, current-state, prisma-schema` — docs

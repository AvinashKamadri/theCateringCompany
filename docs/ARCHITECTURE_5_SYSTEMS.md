# TheCateringCompany — 5-System Architecture

This document describes the 5 logical systems that make up the catering platform, what's built, and what's planned. The first phase — **Ingredients + Dishes** — is now live on the `deploy` branch.

Rooted plan: `C:\Users\avina\.claude\plans\rosy-hatching-wilkinson.md`.

---

## System overview

| # | System | Purpose | Status |
|---|--------|---------|--------|
| 1 | People / Conversations | Who is involved, every chat message they exchanged, a summary at contract-time. | Existing schema + Phase 2 summary work planned |
| 2 | Menu / Dishes / Ingredients | Structured menu → dishes → ingredients with macros + allergens. | **Phase 1 shipped** |
| 3 | Projects / Timelines | Projects, collaborators, timeline milestones, progress, manual food-waste logging. | Existing schema + Phase 2 waste-log work planned |
| 4 | Inventory / Ingredients | Staff-added ingredients with macros, allergens, and stock log (purchases, consumption, waste). | **Phase 1 shipped** |
| 5 | Invoices / Payments | Contracts calculate amounts; payments track what's paid, due dates, and future installments with reminder triggers. | Existing schema + Phase 3 reminder-job work planned |

Phase 1 and 4 overlap by design — the ingredients model is the foundation of both the menu breakdown (System 2) and the stock-tracking dashboard (System 4).

---

## 1. People / Conversations

**Purpose.** Every person connected to a project — clients, collaborators, staff — plus every message in every thread. When a contract is created, an LLM summary captures the conversation history so future staff can pick up the context without scrolling.

**Existing tables:**
- `users`, `user_profiles`, `oauth_accounts`
- `threads`, `messages`, `message_mentions`
- `ai_conversation_states` — the slot-filling state for AI intake chats
- `project_collaborators` — who is attached to which project

**Planned (Phase 2):**
- `projects.conversation_summary` (new column)
- `project_summaries` (new table) — one row per contract generation, keeps a history
- Hook in `backend/src/contracts/contracts.service.ts` that enqueues an LLM summarization job after a contract is created

**Out of scope for now:** Gmail OAuth extraction (to be added later).

---

## 2. Menu / Dishes / Ingredients — *Phase 1 shipped*

**Model.**

```
menu_categories (existing)
  └── menu_items (existing)
        └── menu_item_dishes  ← NEW (join)
              └── dishes      ← NEW
                    └── dish_ingredients  ← NEW (join)
                          └── ingredients ← NEW
```

**Why a separate `dishes` table?** The comma-separated descriptions in `menu_items.description` (e.g. *"Chicken Piccata, Red Wine Braised Beef Roast, Vegetable Farfalle, Long Grain Buttered Rice, Roasted Mixed Veggies, Green Beans, Dinner Rolls"*) are sub-items. Many combo platters reuse the same sub-item — Dinner Rolls, Mashed Potatoes, etc. A separate `dishes` table lets you **define each dish once and link it into multiple menu items**, and attach ingredients (and macros/allergens) to a dish exactly once.

**Seeding.** `backend/src/scripts/seed-menu.ts` now:
1. Seeds menu categories and menu items (as before)
2. Seeds pricing packages (as before)
3. **New:** parses each `menu_items.description` into dish names, upserts into `dishes`, and creates `menu_item_dishes` links with `sort_order` matching the position in the original description

Run it via `npx ts-node src/scripts/seed-menu.ts` from `backend/`.

**API.** See System 4 below — the same module serves the menu and the inventory.

**Frontend.**
- `frontend/app/menu/page.tsx` now fetches from `GET /api/inventory/menu-feed` (public endpoint) and renders each menu item with its dishes and the ingredients attached to those dishes (with a green leaf chip per ingredient).

---

## 3. Projects / Timelines

**Purpose.** Everything that happens for a catered event — guests, venue, event date, the people on it, the timeline of milestones, and progress toward completion. Food-waste logging hangs off here so it can be reported per project.

**Existing tables (no changes in Phase 1):**
- `projects` — core event details, owner, status, event_date, guest_count, ai_event_summary
- `event_timeline_items` — titled milestones with scheduled_at / completed_at
- `project_collaborators` — members on a project
- `crm_pipeline` — stage, lead score, assigned staff
- `project_portion_estimates` — per-menu-item quantities
- `project_staff_requirements` — staffing roles + hours
- `activity_log` — change-tracking

**Planned (Phase 2):**
- Manual food-waste logging: `ingredient_stock_log` rows with `source='waste'` and `project_id` set (already supported in Phase 1 schema)
- `project_waste_logs` (new table) for higher-level per-event waste reports not tied to a specific ingredient

---

## 4. Inventory / Ingredients — *Phase 1 shipped*

**New tables.**

### `ingredients`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| name | text unique | e.g. "Chicken breast" |
| calories_per_100g | decimal(10,2) | optional |
| carbs_g_per_100g | decimal(10,2) | optional |
| protein_g_per_100g | decimal(10,2) | optional |
| fat_g_per_100g | decimal(10,2) | optional |
| allergens | text[] | e.g. ["dairy","gluten"] |
| default_unit | text | "g" or "ml" |
| default_price | decimal(10,2) | optional |
| created_by_user_id | uuid | |

### `dishes`
| column | type | notes |
|---|---|---|
| id | uuid pk | |
| name | text unique | e.g. "Chicken Piccata" |
| description | text | optional long-form |

### `menu_item_dishes` (join)
Composite PK `(menu_item_id, dish_id)` with `sort_order`.

### `dish_ingredients` (join)
Composite PK `(dish_id, ingredient_id)` with `weight_g`, `volume_ml`, `notes`.

### `ingredient_stock_log`
Per-event or per-purchase stock changes. `source ∈ {'staff_manual','purchase','consumption','waste'}`. Optional `project_id` to attribute the change to a specific event.

**Backend module** — `backend/src/inventory/`
- `InventoryModule` (registered in `app.module.ts`)
- `InventoryService` — staff-gated CRUD + one public endpoint
- Routes (all under `/api/inventory`, staff-only unless noted):
  - `GET/POST/PATCH/DELETE /ingredients` (and `/ingredients/:id`)
  - `GET/POST/PATCH /dishes`, `GET /dishes/:id`
  - `POST /dishes/:id/ingredients` — upsert a dish↔ingredient link
  - `DELETE /dishes/:id/ingredients/:ingredientId`
  - `POST /stock-log` — staff records stock in/out
  - `GET /stock-log?ingredient_id=...` — last 200 events
  - `GET /menu-feed` — **public** — menu items + dishes + ingredients (consumed by the menu page)

**Staff gate.** `InventoryService` gates everything behind emails ending in `@catering-company.com`, following the same pattern used by `CrmService`.

**Frontend** — `frontend/app/(dashboard)/inventory/page.tsx`
- Two-tab layout:
  - **Ingredients** — table of all ingredients with macros, allergens, default unit/price. Buttons: "Log stock" (opens a modal with delta + source picker) and delete.
  - **Dishes** — grid of dishes. Each dish card lists the ingredients linked to it with amounts (g/ml), and shows how many menu items it appears in. "Add ingredient" opens a modal that picks an ingredient and records a weight/volume.
- Staff-only via `RoleGuard role="staff"`.
- Added to the top nav for staff users (`Inventory` pill with `Package` icon).

---

## 5. Invoices / Payments

**Purpose.** Every contract totals what the client will be billed. Payments track what they've paid, what's due, and what's scheduled for the future. Future payments that haven't been paid by their due date should trigger reminders.

**Existing tables (no changes in Phase 1):**
- `contracts` — amount, status, signatures, pdf_path
- `change_orders` / `change_order_lines` — post-contract adjustments
- `payment_schedules` — installment plans
- `payment_schedule_items` — individual due amounts + due_date + status
- `payments` — actual payments (Stripe or mock)
- `payment_requests` — one-off payment links
- `cost_of_goods` — COGS tracking

**Planned (Phase 3):**
- `invoices` + `invoice_lines` (new tables) for line-itemized invoice PDFs separate from contracts
- A daily job in `backend/src/job_queue/` that scans `payment_schedule_items` for items due within N days and sends an email + in-app notification via the existing `NotificationsModule`
- Overdue path: items past due_date get flagged, and the assigned staff from `crm_pipeline.assigned_staff_user_id` is notified
- New `frontend/app/(dashboard)/invoices/page.tsx` with a list view (contract, due date, paid/unpaid, reminder status) and a detail page that supports a manual "Send reminder now" button

Explicitly deferred: auto-charge via Stripe. Reminders only for now.

---

## How the phases fit together

```
Phase 1 (now)      Phase 2                  Phase 3
───────────────    ──────────────────────   ──────────────────────────
ingredients        conversation_summary     invoices + invoice_lines
dishes             project_summaries        daily reminder job
dish_ingredients   project_waste_logs       overdue notifier
menu_item_dishes   summary job hook         invoices UI page
stock_log          waste-log UI
inventory UI
menu page refresh
```

Each phase ships independently. Phase 1 does not depend on 2 or 3; Phase 3 layers on top of the existing payments schema.

---

## Running Phase 1 locally

```bash
# 1. Start the SSH tunnel + docker compose (or local postgres on 5433)
#    see scripts/restart-backend.ps1 for the backend container flow

# 2. Apply the migration
cd backend
npx prisma migrate dev --name add_ingredients_dishes

# 3. (Optional) seed dishes from existing menu item descriptions
npx ts-node src/scripts/seed-menu.ts

# 4. Start backend + frontend
npm run start:dev                             # backend
cd ../frontend && npm run dev                 # frontend

# 5. Visit http://localhost:3000/inventory  (staff account required)
#    Create an ingredient, link it to a dish, log some stock.
#    Visit /menu to see the public rendering with dish + ingredient breakdown.
```

---

## File index (Phase 1)

- [backend/prisma/schema.prisma](../backend/prisma/schema.prisma) — 5 new models + inverse relation on `menu_items`
- [backend/src/scripts/seed-menu.ts](../backend/src/scripts/seed-menu.ts) — adds `seedDishes()`
- [backend/src/inventory/inventory.module.ts](../backend/src/inventory/inventory.module.ts)
- [backend/src/inventory/inventory.service.ts](../backend/src/inventory/inventory.service.ts)
- [backend/src/inventory/inventory.controller.ts](../backend/src/inventory/inventory.controller.ts)
- [backend/src/app.module.ts](../backend/src/app.module.ts) — registers `InventoryModule`
- [frontend/app/(dashboard)/inventory/page.tsx](../frontend/app/(dashboard)/inventory/page.tsx)
- [frontend/app/menu/page.tsx](../frontend/app/menu/page.tsx) — now hits `/inventory/menu-feed`
- [frontend/components/layout/app-nav.tsx](../frontend/components/layout/app-nav.tsx) — staff nav now includes Inventory

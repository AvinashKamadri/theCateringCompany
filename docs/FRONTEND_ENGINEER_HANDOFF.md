# Frontend Engineer Handoff — New 5-System UI Surfaces

Summary of the new frontend surfaces that shipped with the 5-system architecture (People, Menu, Projects, Inventory, Invoices). All pages are staff-only except where noted.

---

## Route map

| Route | Audience | Status |
|---|---|---|
| `/menu` | **Staff only** (moved from public) | Renders `/inventory/menu-feed` — categories → menu items → linked dishes → ingredient chips + allergen warnings |
| `/inventory` | Staff only | Two-tab: Ingredients / Dishes. CRUD + stock logging |
| `/contracts/[id]` | Host + staff | **NEW:** per-line-item expandable breakdown with dishes, ingredients, and allergen warnings vs dietary restrictions |
| `/projects/[id]` | Host + staff | **NEW staff-only tile:** "Food Waste" + LogWasteModal |

Navigation ([frontend/components/layout/app-nav.tsx](../frontend/components/layout/app-nav.tsx)) already has `Menu` + `Inventory` links gated on `@catering-company.com` emails.

---

## Data flow

```
              ┌─────────────────────┐
              │  Next.js frontend   │
              └──────────┬──────────┘
                         │  apiClient (JWT cookie)
                         ▼
              ┌─────────────────────┐
              │  NestJS /api        │
              │  /inventory/*       │
              │  /contracts/*       │
              │  /payments/*        │
              └──────────┬──────────┘
                         │
                         ▼
                    Postgres (RDS)
```

All API calls go through `apiClient` ([frontend/lib/api/client.ts](../frontend/lib/api/client.ts)). JSON in / JSON out. JWT is carried by the `app_jwt` cookie — no bearer header.

---

## Endpoints you'll use

### Inventory
- `GET    /api/inventory/ingredients` → `Ingredient[]`
- `POST   /api/inventory/ingredients` → create
- `PATCH  /api/inventory/ingredients/:id` → update
- `DELETE /api/inventory/ingredients/:id`
- `GET    /api/inventory/dishes` → `Dish[]` with linked ingredients + menu items
- `POST   /api/inventory/dishes/:id/ingredients` → link ingredient (body: `{ ingredient_id, weight_g?, volume_ml?, notes? }`)
- `DELETE /api/inventory/dishes/:id/ingredients/:ingredientId`
- `POST   /api/inventory/stock-log` → log stock (body: `{ ingredient_id, delta_g?, delta_ml?, source, project_id?, notes? }`). Source ∈ `'staff_manual' | 'purchase' | 'consumption' | 'waste'`
- `GET    /api/inventory/menu-feed` → staff-only menu w/ dishes + ingredients (powers `/menu`)
- `POST   /api/inventory/resolve-line-items` → contract page uses this. Body: `{ descriptions: string[], dietary_restrictions?: string[] }`. Returns per-description matches with dishes, ingredients, and allergen warnings.

### Payments
- `POST /api/payments/reminders/run` — staff-only, manual trigger for the daily reminder sweep. Returns `{ upcoming: number, overdue: number }`.

---

## Patterns already established

### Staff gate
```tsx
const isStaff = user?.email?.endsWith('@catering-company.com') ?? false;
```
For full-page gating, wrap in `<RoleGuard role="staff">` ([frontend/components/auth/role-guard.tsx](../frontend/components/auth/role-guard.tsx)).

### Debounced API-on-input
See [frontend/app/(dashboard)/contracts/[id]/page.tsx](../frontend/app/(dashboard)/contracts/[id]/page.tsx) — 400ms debounce on `[contract, lineItems]` before POSTing to `/inventory/resolve-line-items`. Copy this pattern for any new "live preview" call.

### Modal shell
Reference [inventory/page.tsx](../frontend/app/(dashboard)/inventory/page.tsx) (`ModalShell`, `Field`, `NumInput` helpers) and the `LogWasteModal` at the bottom of [projects/[id]/page.tsx](../frontend/app/(dashboard)/projects/[id]/page.tsx). Fixed inset, backdrop-blur, rounded-2xl card, submit-on-enter form.

### Ingredient/allergen chips
Emerald for normal, amber for "has allergens". See the breakdown render block in the contract page for copy-paste markup.

---

## What's pending on the frontend

These are the surfaces the backend is **ready for** but no UI exists yet:

### 1. Conversation summary display
Backend now populates `projects.conversation_summary` (string) and a `project_summaries` history table when a contract is created.

**Where to add:** [frontend/app/(dashboard)/projects/[id]/page.tsx](../frontend/app/(dashboard)/projects/[id]/page.tsx) — new `BentoInfoCard` labeled "AI Summary". Render `project.conversation_summary` if present. Optional: "View history" link → list from `project_summaries` (you'll need a new backend endpoint `GET /api/projects/:id/summaries`; flag this if you hit it).

Notes:
- Summary is populated by an async worker, so the field may be `null` for ~30s after contract creation. Show a subtle "Summary being generated…" spinner when `contract exists && !conversation_summary`.
- Expose `conversation_summary` from `projectsApi.getProject` — check `Project` interface at top of the project page file.

### 2. Invoices / payment-schedule UI
Payment reminders are now firing but there's no UI to **view** what was sent or the overall payment schedule per project.

**Where to add:** new route `/invoices` (staff) + per-project section on the project detail page.
- List endpoint needed: `GET /api/payments/schedules?project_id=...` (may need to add to backend — flag if missing).
- For each `payment_schedule_items` row show: label, amount, due_date, status, `last_reminder_sent_at`, `overdue_notified_at`.
- Add "Send reminder now" button that calls `POST /api/payments/reminders/run` (currently global — if per-item reminders are wanted, we'll add `POST /api/payments/schedule-items/:id/remind`).

### 3. Nutrition / macros on dishes
The schema tracks `calories_per_100g`, `carbs/protein/fat_g_per_100g`, and `dish_ingredients.weight_g` per ingredient. No UI currently aggregates macros per dish or per menu item.

**Where to add:** [inventory/page.tsx](../frontend/app/(dashboard)/inventory/page.tsx) dishes tab — show computed totals next to each dish. Client-side computation is fine:
```ts
const totalCals = dish.dish_ingredients.reduce((sum, di) =>
  sum + (Number(di.ingredients.calories_per_100g ?? 0) * Number(di.weight_g ?? 0) / 100), 0);
```

### 4. Waste logs view
Staff can now **log** waste (Project detail → Food Waste tile). There's no **view** yet.

**Where to add:** a new tab or section on `/inventory` that lists recent `ingredient_stock_log` entries with `source='waste'`, joined to the project. Use `GET /api/inventory/stock-log` (already exists; filter client-side by source or ask backend to add a `?source=waste` filter).

---

## Local dev
Standard 4-terminal setup (see [docs/reference_commands.md in memory or README](../README.md)):
1. `docker compose up -d postgres redis`
2. SSH tunnel to RDS on :5433 if using prod data
3. `cd backend && npm run start:dev`
4. `cd frontend && npm run dev`

After schema changes land, restart the backend (Prisma client regenerates automatically via `postinstall`).

## Type-check before pushing
```bash
cd frontend && npx tsc --noEmit
cd ../backend && npx tsc --noEmit
```
Both currently clean.

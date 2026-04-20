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

## Deliverables

These are the surfaces the backend is **ready for** — your job is to build the UI.

---

### 1. Conversation summary display
**File:** [frontend/app/(dashboard)/projects/[id]/page.tsx](../frontend/app/(dashboard)/projects/[id]/page.tsx)

Add a new `BentoInfoCard` labeled **"AI Summary"** that renders `project.conversation_summary`.

- Summary is populated async by a worker ~30s after contract creation. Show a subtle "Summary being generated…" spinner when `contract exists && !conversation_summary`.
- Expose `conversation_summary` on the `Project` interface at the top of the file.
- Optional: "View history" link → list from `project_summaries`. You'll need to add `GET /api/projects/:id/summaries` to the backend — flag this if you get there.

---

### 2. Invoices / payment-schedule UI
**Files:** new route `frontend/app/(dashboard)/invoices/page.tsx` (staff) + a payment section on the project detail page.

Display all `payment_schedule_items` per project: label, amount, due date, status, last reminder sent, overdue flag.

- Fetch from `GET /api/payments/schedules?project_id=...` — this endpoint may need to be added to the backend, flag if missing.
- "Send reminder now" button → `POST /api/payments/reminders/run` (currently global sweep; if per-item is needed we'll add `POST /api/payments/schedule-items/:id/remind`).

---

### 3. Nutrition / macros on dishes
**File:** [frontend/app/(dashboard)/inventory/page.tsx](../frontend/app/(dashboard)/inventory/page.tsx) — dishes tab.

Show computed macro totals next to each dish. Client-side calculation:
```ts
const totalCals = dish.dish_ingredients.reduce((sum, di) =>
  sum + (Number(di.ingredients.calories_per_100g ?? 0) * Number(di.weight_g ?? 0) / 100), 0);
```
Fields available: `calories_per_100g`, `carbs_g_per_100g`, `protein_g_per_100g`, `fat_g_per_100g`, `dish_ingredients.weight_g`.

---

### 4. Waste logs view
**File:** [frontend/app/(dashboard)/inventory/page.tsx](../frontend/app/(dashboard)/inventory/page.tsx) — add a third "Waste Logs" tab.

List recent `ingredient_stock_log` entries where `source = 'waste'`, joined to the project name.

- Use `GET /api/inventory/stock-log`. Filter by `?source=waste` if the backend supports it, otherwise filter client-side.
- Show: ingredient name, quantity lost, project name (if linked), logged date, notes.

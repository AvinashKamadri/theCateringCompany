# TheCateringCompany — UI & Design Overview

A design-oriented tour of the product: who uses it, what they do, which screens exist today, what's coming, and the visual patterns that tie it together. Written for someone picking up the UI/UX side.

---

## 1. Product in one sentence

A catering platform that lets a client plan an event by *chatting with an AI assistant*, get an auto-generated contract, pay in installments, and lets staff run menu, inventory, CRM, and contract operations from the same dashboard.

---

## 2. Users

| Role | Who | Primary goal | Lives in |
|---|---|---|---|
| **Client / Host** | Person booking the event | Plan an event, review the contract, pay | `/chat`, `/projects`, `/contracts` |
| **Staff** | Anyone with `@catering-company.com` email | Manage menu, inventory, CRM pipeline, event timelines | Staff-gated pages + everything above |

Role is derived from email domain (no role-picker UI). The top nav swaps label sets based on role: hosts see *Plan My Event / My Events / Contracts*; staff see *All Events / Contracts / CRM Dashboard / Menu / Inventory*.

---

## 3. Core user journeys

### 3.1 Host — "I want to book a caterer"
1. **Landing / sign up** → arrives at marketing page, signs up.
2. **`/chat` AI intake** → a conversational assistant asks for name, event type, date, guest count, menu picks, add-ons. Structured fields fill on the right panel (`IntakeReviewPanel`).
3. **Contract preview** → once the intake is complete, a contract is generated with line items + a summary of the conversation.
4. **Sign contract** → client signs; a copy is emailed and stored.
5. **Pay installments** → `/contracts/:id` shows the payment schedule with due dates and a "Pay now" per installment.
6. **Event day** → staff fulfill; host gets reminders for upcoming payments.

### 3.2 Staff — "I want to run the week"
1. **`/projects`** → see every event by status (draft, booked, fulfilled), filter by CRM stage.
2. **`/crm`** → pipeline board, lead scores, assigned-staff, follow-up reminders.
3. **`/menu`** → public-facing menu (the same items a host sees in chat).
4. **`/inventory`** → staff-only. Two tabs:
   - **Ingredients** — raw inputs with macros/allergens, stock log
   - **Dishes** — reusable cooked items, recipe (links to ingredients), which menu_items include them
5. **`/contracts/:id`** → same view as host but with staff-only change-order + reminder controls.

---

## 4. Page inventory (what's built today)

| Route | Audience | What it shows |
|---|---|---|
| `/` | Public | Marketing landing |
| `/signin`, `/signup` | Public | Split-screen auth (image left, form right) |
| `/chat` | Host | AI assistant + intake review panel |
| `/projects` | All | Event list (staff = all, host = own) |
| `/projects/[id]` | All | Event detail: timeline, collaborators, AI summary, waste logs |
| `/contracts` | All | Contract list |
| `/contracts/[id]` | All | Contract detail: line items, signatures, payment schedule, reminder controls (staff) |
| `/menu` | All (staff gate) | Menu by category → items → dishes → ingredient chips with allergens |
| `/inventory` | Staff | Ingredients table + dishes grid, stock-log modal, recipe-link modal |
| `/crm` | Staff | Pipeline dashboard |

---

## 5. Visual system

### 5.1 Foundation
- **Font:** system sans (Inter-like via Tailwind default).
- **Palette:** `neutral-*` grays as the dominant surface. Accent colors used *sparingly*:
  - `amber-*` → allergen warnings, "needs attention"
  - `emerald-*` → recipe/linked-ingredient chips, positive state
  - `red-*` → destructive confirms only (delete, unlink)
- **Radii:** `rounded-md` (buttons, inputs), `rounded-xl` (cards), `rounded-full` (nav pill, avatars).
- **Shadow:** very light (`shadow-sm`) on cards; floating nav uses a stronger layered shadow.

### 5.2 Nav — the floating pill
`components/layout/app-nav.tsx` — fixed `top-3`, horizontally centered, `rounded-full`, translucent `bg-white/70` with `backdrop-blur-xl`. Shows logo on the left, navigation in the center, user avatar + logout on the right. Mobile: nav items collapse into a dropdown rendered *below* the pill so the rounded edge doesn't clip the menu.

### 5.3 Cards
Used everywhere: menu items, dish tiles, contract summaries. Consistent: white surface, `border-neutral-200`, `rounded-xl`, subtle hover (`hover:border-neutral-300`), optional top-right "pill" metadata (price, status).

### 5.4 Modals
Rendered via React portal to `document.body` (escapes any transformed ancestor — a common gotcha with the dashboard's page-enter animation). Always `z-[60]` so they sit above the floating nav. Pattern: centered white card, header row with title + close, body with form or content.

### 5.5 Chat bubbles
User message: dark (`bg-black text-white`), right-aligned.
Assistant message: light (`bg-white` on `bg-neutral-50` page), left-aligned with a sparkly avatar.
Time stamp under the bubble in `text-neutral-500`.

### 5.6 Status/allergen chips
Small `px-1.5 py-0.5 rounded text-xs`. Amber for allergens, neutral for tags, emerald for "has recipe" or ingredient presence.

---

## 6. Data domain — what the UI renders

Five logical systems (see `docs/ARCHITECTURE_5_SYSTEMS.md` for the schema-level detail):

1. **People & Conversations** → users, threads, AI intake state, contract-time summaries.
2. **Menu / Dishes / Ingredients** → 3-layer model the menu page walks top-down; the inventory page edits middle + bottom.
3. **Projects / Timelines** → events with milestones, collaborators, portions, staffing, waste.
4. **Inventory** → stock log per ingredient (purchase / consumption / waste / manual).
5. **Invoices / Payments** → contracts with payment schedule → installment items → reminders.

---

## 7. Future / in-flight UI work

### 7.1 Near-term (Phase 2/3 from the architecture doc)
- **Conversation summary** on every contract detail page (auto-generated LLM summary of the AI intake). **Backend shipped, UI in place.**
- **Project waste log UI** — a simple log-entry form on the project detail page, tied to ingredients.
- **Invoice page** — dedicated `/invoices` list + detail with a "Send reminder now" button (currently reminders run on a cron; no manual trigger UI).
- **Payment reminder timeline** — visualize which reminders have fired / will fire on the contract page.

### 7.2 Inventory polish
- Recipe editor UX — currently a single modal per dish; consider an inline table for faster entry.
- Bulk ingredient import (CSV) for staff onboarding.
- Stock-log history view with filters (by source, date range, project).

### 7.3 Chat / AI
- Editable intake — let clients click on a slot in the review panel to override an AI-filled value.
- Voice input for clients using the assistant on mobile.
- Multi-language support (the chat model can already do it; UI needs language selector + RTL audit).

### 7.4 Wedding-specific surface
- First-class partner / fiancée fields on the project form (currently not in schema — would unlock personalized reminders, joint signatures on contracts, "you and Priya have 3 tasks left this week" style copy).
- Cake builder UI — pick flavors + fillings (currently stored as free-text description in the menu_item).

### 7.5 Explicit non-goals (deferred)
- Gmail OAuth to pull client email threads into the conversation system.
- Stripe auto-charge on due dates (reminders only).

---

## 8. Key UX principles

1. **One canonical nav.** No nested left sidebars. The floating top pill is the only navigation surface.
2. **Portal every modal.** Transformed ancestors break `position: fixed` — every modal goes through a portal to `document.body` so centering and z-index stay predictable.
3. **Tables for dense data, cards for browseable data.** Ingredients = table. Dishes = card grid. Menu items = card grid. Contracts / projects = list with summary row.
4. **Role-derived UI.** Never render a "Switch role" UI. The staff gate is quiet — hosts just don't see staff controls.
5. **Allergen warnings cascade.** If an ingredient has an allergen, the chip surfaces on the dish, the menu_item, and the contract summary. One source of truth, repeated wherever the user is looking.
6. **AI output is never trusted raw.** Every AI-filled slot is editable by the user. The review panel is the source of truth for what the contract will say.

---

## 9. Files a designer should open first

- [frontend/components/layout/app-nav.tsx](../frontend/components/layout/app-nav.tsx) — the floating nav
- [frontend/app/(dashboard)/layout.tsx](../frontend/app/(dashboard)/layout.tsx) — page frame + enter animation
- [frontend/app/(dashboard)/menu/page.tsx](../frontend/app/(dashboard)/menu/page.tsx) — menu card pattern
- [frontend/app/(dashboard)/inventory/page.tsx](../frontend/app/(dashboard)/inventory/page.tsx) — tables + grids + modal pattern
- [frontend/components/chat/ai-chat.tsx](../frontend/components/chat/ai-chat.tsx) — message bubble pattern
- [frontend/components/chat/IntakeReviewPanel.tsx](../frontend/components/chat/IntakeReviewPanel.tsx) — structured side-panel pattern
- [frontend/app/globals.css](../frontend/app/globals.css) — animation keyframes + global chips
- [docs/ARCHITECTURE_5_SYSTEMS.md](./ARCHITECTURE_5_SYSTEMS.md) — backend story behind the screens

# 3-Step Roadmap — Waste, Cost, Invoices

Companion to [ARCHITECTURE_5_SYSTEMS.md](./ARCHITECTURE_5_SYSTEMS.md). Focuses on the next three deliverables in order.

---

## Step 1 — Event-level waste logs ✅ *shipped 2026-04-23*

**Goal.** Record higher-level food waste per event that is not tied to a specific ingredient row in `ingredients`. Complements the Phase-1 ingredient-level waste mechanism (`ingredient_stock_log` with `source='waste'`), which stays in place.

**Schema.** One new table.

```prisma
model project_waste_logs {
  id                String    @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  project_id        String    @db.Uuid                              // FK → projects.id (Cascade)
  logged_by_user_id String?   @db.Uuid                              // FK → users.id (SetNull)
  total_weight_kg   Decimal?  @db.Decimal(10, 2)
  reason            String?
  notes             String?
  logged_at         DateTime  @default(now()) @db.Timestamptz(6)
  created_at        DateTime  @default(now()) @db.Timestamptz(6)
  updated_at        DateTime  @default(now()) @db.Timestamptz(6)

  @@index([project_id, logged_at(sort: Desc)], map: "ix_project_waste_logs_project")
}
```

**API.**
- `GET  /api/projects/:projectId/waste-logs` — any project member
- `POST /api/projects/:projectId/waste-logs` — staff only (`@catering-company.com` gate)
- `DELETE /api/projects/:projectId/waste-logs/:logId` — staff only

**Frontend.** The Food Waste bento on the project detail page now shows a list of recent event-waste entries, plus two buttons:
1. **Log event waste** (primary, black) — opens a modal with weight/reason/notes, no ingredient required
2. **Log ingredient waste** (secondary, outlined) — opens the existing ingredient-level modal (unchanged)

Staff-only card; invisible to clients/collaborators.

**Files changed (Step 1).**
- `backend/prisma/schema.prisma` — added model + relations on `projects` and `users`
- `backend/src/projects/projects.service.ts` — `listWasteLogs`, `createWasteLog`, `deleteWasteLog`, plus `assertProjectReadable` / `assertStaff` helpers
- `backend/src/projects/projects.controller.ts` — three new routes
- `frontend/app/(dashboard)/projects/[id]/page.tsx` — list UI + `LogEventWasteModal`
- `backend/src/scripts/seed-menu.ts` — upsert adjusted for composite `(section, name)` unique on `menu_categories`

No workers changes. No job-queue additions.

---

## Step 2 — Cost calculation (quick win) ⏳ *next*

**Goal.** For any project, produce a running total of:
- Ingredient COGS (per-menu-item → per-dish → per-ingredient unit cost × quantity)
- Labour (staff hours × hourly rate from `project_staff_requirements`)
- Waste delta (event-level waste × avg ingredient cost as a rough proxy, or ignore if no weight)

…and surface it on the project page so staff can see margin vs. the signed contract amount.

**Proposed approach (short).**
1. **Backend** — add `GET /api/projects/:projectId/cost-breakdown` returning `{ ingredients_total, labour_total, waste_adjustment, grand_total, contract_total, margin }`. Pure computation over existing tables (`ingredients.default_price`, `dish_ingredients.weight_g`, `order_items.quantity`, `project_staff_requirements.hours × hourly_rate`, `project_waste_logs.total_weight_kg`). No new models.
2. **Frontend** — new "Cost breakdown" bento card on the project detail page, staff-only. Shows the four sub-totals and margin with a colored status chip.
3. **Defer** — real-time recalc, historical cost snapshots, currency conversion. Compute on read for now; if perf is a problem we add `cost_snapshots`.

**Open questions to resolve before coding.**
- Do we include waste as a negative adjustment (you already paid for it) or a positive cost (double-counts if already in ingredients_total)? **Lean: show waste as info-only, don't double-count.**
- Where does the labour hourly rate live? Currently absent from `project_staff_requirements`. Options: (a) add `hourly_rate` column, (b) read from a new `roles.default_rate` table, (c) flat rate constant. **Lean: (a), simplest.**
- Rounding: 2dp USD? Keep `Decimal(12,2)` throughout.

**Estimate.** 2-3 hours: one service method, one controller route, one bento card, one new column on `project_staff_requirements`.

---

## Step 3 — Invoices (properly scoped) ⏳ *after step 2*

**Goal.** Separate "what the client owes" from the contract itself. A contract is the agreement; an invoice is the bill with line items and a due date.

**New tables.**

```prisma
model invoices {
  id               String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  invoice_number   String   @unique                    // INV-0001 sequence
  project_id       String   @db.Uuid                   // FK → projects
  contract_id      String?  @db.Uuid                   // FK → contracts, nullable
  status           invoice_status @default(draft)      // draft | sent | paid | overdue | cancelled
  total_amount     Decimal  @db.Decimal(12, 2)
  currency         String   @default("USD")
  issued_at        DateTime?  @db.Timestamptz(6)
  due_date         DateTime?  @db.Date
  paid_at          DateTime?  @db.Timestamptz(6)
  pdf_path         String?                              // S3/R2 key
  created_by       String   @db.Uuid                   // FK → users
  created_at       DateTime @default(now()) @db.Timestamptz(6)
  updated_at       DateTime @default(now()) @db.Timestamptz(6)
  lines            invoice_lines[]
}

model invoice_lines {
  id           String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  invoice_id   String   @db.Uuid
  description  String
  quantity     Decimal  @db.Decimal(10, 2)
  unit_price   Decimal  @db.Decimal(10, 2)
  line_total   Decimal  @db.Decimal(12, 2)
  sort_order   Int      @default(0)
  invoices     invoices @relation(fields: [invoice_id], references: [id], onDelete: Cascade)
}

enum invoice_status { draft sent paid overdue cancelled }
```

**Numbering.** Sequential `INV-0001`, `INV-0002`, …, generated via a Postgres sequence or a "next number" stored in a singleton row. Not UUID; humans read these.

**Creation flow.**
- Manual staff action on project page: **Generate invoice** → picks line items (existing `payment_schedule_items` or free-form) → creates invoice → kicks off a PDF job (same puppeteer worker as contracts).
- Future: auto-generate on schedule milestone, but not in Step 3.

**UI.**
- `frontend/app/(dashboard)/invoices/page.tsx` — cross-project list: number, project, due, status
- `frontend/app/(dashboard)/invoices/[id]/page.tsx` — detail: lines, status chip, download PDF, "Mark as paid" (staff), "Send" (staff)

**PDF.** Re-use the contracts Puppeteer pipeline in `workers/`. One new template.

**Payments wiring.** An invoice `paid_at` is set when the sum of `payments` where `payments.invoice_id = invoice.id` meets `total_amount`. Requires a new `payment.invoice_id` FK (nullable; existing payments link only to schedule/project).

**Reminders.** Already partly built (`payment-reminders.service.ts` runs daily). Extend to scan invoices with `status='sent'` and `due_date < today + N`, emit the same notifications path.

**Deferred.** Auto-charge via Stripe, credit notes, partial-payment allocation UX, multi-currency. Stick to USD + manual "Mark as paid".

**Estimate.** 6-8 hours: 2 migrations, new module (`invoices/`), 2 frontend pages, 1 PDF template, reminder extension.

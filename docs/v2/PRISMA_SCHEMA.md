# Prisma Schema Reference — 2026-04-23

Source of truth: [backend/prisma/schema.prisma](../../backend/prisma/schema.prisma) (~1700 lines). This doc groups the 61 models and 20 enums by domain and flags what's been added/changed in recent sessions.

---

## Model inventory by domain

### Auth & users (7)
- `users` — email, password_hash, primary_phone, status, soft delete
- `user_profiles` — profile_type (staff/client), metadata JSONB
- `user_roles` — user × role, scoped (global / project)
- `roles` — `staff` / `host` / `collaborator` (domain = platform | client)
- `role_permissions` — role × permission
- `auth_tokens`, `refresh_tokens`, `sessions` — JWT / refresh rotation + device sessions
- `oauth_accounts`, `api_keys`, `service_accounts`

### Projects (11)
- `projects` — core event, owner, status, event_date, guest_count, `conversation_summary` (Phase 2), `ai_event_summary`
- `project_collaborators` — user × project × role (owner | manager | collaborator | viewer)
- `project_summaries` — LLM summary history (one row per contract generation)
- **`project_waste_logs`** — ★ NEW this session. Event-level waste entries
- `project_portion_estimates` — per-menu-item quantity estimates
- `project_pricing` — pricing snapshots
- `project_staff_requirements` — staffing plan (roles × hours)
- `project_upsell_items` — upsell products
- `event_timeline_items` — milestones with scheduled/completed_at
- `event_analytics` — post-event stats
- `follow_ups` — post-event follow-up tasks

### Menu / Inventory (7)
- `menu_categories` — ★ `section` column + composite `@@unique([section, name])` (drift resolved this session)
- `menu_items` — with `category_id`, `unit_price`, `tags[]`, `allergens[]`, `active`
- `menu_item_dishes` — join, composite PK, `sort_order`
- `dishes` — reusable cooked items / option choices
- `dish_ingredients` — join with `weight_g`, `volume_ml`, `notes`
- `ingredients` — name, macros (per 100g), allergens, default unit/price
- `ingredient_stock_log` — source ∈ {`staff_manual`,`purchase`,`consumption`,`waste`}, optional `project_id`

### Contracts / Signing (6)
- `contracts` — versioned, status (draft → pending_staff_approval → approved → sent → signed / rejected), pdf_path
- `contract_signatures` — per-signer row (signer_role, signed_at)
- `contract_clauses` — line-item clauses
- `clause_templates`, `clause_rules` — clause library + rule-based inclusion
- `venue_clause_overrides` — venue-specific overrides

### Change orders (2)
- `change_orders` — post-contract adjustments
- `change_order_lines`

### Payments (5)
- `payments` — actual payments (Stripe or mock)
- `payment_schedules` — installment plans
- `payment_schedule_items` — individual due amounts, due_date, status
- `payment_requests` — one-off pay-link requests
- `cost_of_goods` — COGS tracking (consumed by pricing service)

### Pricing (1)
- `pricing_packages` — bronze/silver/gold/platinum/wedding packages with margin targets

### Intake / AI (3)
- `ai_conversation_states` — slot-filling state for the ml-agent (cascade runtime)
- `ai_generations` — record of LLM calls (token usage, entity_type)
- `intake_form_templates`, `intake_submissions` — pre-ml-agent manual form intake

### Messaging (3)
- `threads` — per-project chat threads
- `messages` — body, author_user_id, `ai_hint` JSONB
- `message_mentions` — @-mention join

### Notifications (2)
- `notifications` — in-app bell list (recipient, title, body, link, acked_at)
- `notification_templates` — template strings per channel

### Attachments / Storage (1)
- `attachments` — owner_type + owner_id polymorphic reference, S3 path, `virus_scan_status`

### BEO (3)
- `banquet_event_orders` — event-day ops sheet
- `beo_line_items` — dish/equipment rows
- `beo_staff_assignments`

### CRM (3)
- `crm_pipeline` — 1 row per project with stage, lead_score, assigned_staff
- `client_risk_flags` — flagged concerns
- `margin_alerts` — triggered when a project's margin dips

### Venues (1)
- `venues`

### Cross-cutting (5)
- `activity_log` — audit trail across the app
- `events` — domain event bus rows (used by workers + listeners)
- `webhook_events` — raw incoming webhook payloads with `status`
- `order_items` — project × menu_item × quantity

---

## Enums (20)

`ai_entity_type`, `beo_status`, `contract_status`, `esign_provider`, `flag_severity`, `intake_status`, `notification_channel`, `owner_type`, `payment_status`, `price_type`, `project_status`, `risk_flag_type`, `risk_level`, `scope_type`, `service_style`, `signer_role`, `source_type`, `upsell_status`, `virus_scan_status`, `webhook_status`.

Planned (Step 3): `invoice_status` (`draft` | `sent` | `paid` | `overdue` | `cancelled`).

---

## Recent schema changes (this session)

### ★ `project_waste_logs` — NEW

```prisma
model project_waste_logs {
  id                String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  project_id        String   @db.Uuid
  logged_by_user_id String?  @db.Uuid
  total_weight_kg   Decimal? @db.Decimal(10, 2)
  reason            String?
  notes             String?
  logged_at         DateTime @default(now()) @db.Timestamptz(6)
  created_at        DateTime @default(now()) @db.Timestamptz(6)
  updated_at        DateTime @default(now()) @db.Timestamptz(6)
  projects          projects @relation(fields: [project_id], references: [id], onDelete: Cascade, onUpdate: NoAction)
  users             users?   @relation(fields: [logged_by_user_id], references: [id], onDelete: SetNull, onUpdate: NoAction)

  @@index([project_id, logged_at(sort: Desc)], map: "ix_project_waste_logs_project")
}
```

Relations added on `projects` and `users` to back-reference.

### ★ `menu_categories` — section realigned

Before (drifted, schema-only):
```prisma
model menu_categories {
  name  String @unique
  ...
}
```

After (schema matches DB and ml-agent schema):
```prisma
model menu_categories {
  section String @default("")
  name    String
  ...
  @@unique([section, name])
}
```

This resolves a three-way drift: migration file added `section`; backend schema had removed it; ml-agent schema always had it. Now all three agree. DB unique index replaced `menu_categories_name_key` → `menu_categories_section_name_key (section, name)`.

---

## Upcoming (Step 3) — invoices

Two new tables + one new enum. See [ROADMAP_3_STEPS.md §Step 3](./ROADMAP_3_STEPS.md#step-3--invoices-properly-scoped--after-step-2) for full shape. Will also add `payments.invoice_id String?` FK to link existing payments to invoices.

---

## Conventions

- UUID pk via `gen_random_uuid()` (Postgres, not Prisma's `uuid()`)
- `created_at` / `updated_at` always `Timestamptz(6)` with `@default(now())`
- Soft delete pattern only where needed (`deleted_at`, `deleted_by`) — mainly on `projects`, `users`, `contracts`, `payments`
- JSONB for flexible metadata (contract body, user profile metadata, ai_event_summary)
- Enums used aggressively for status fields; free-text for user-entered reasons (e.g., `project_waste_logs.reason`)
- `@@index([col_a, col_b(sort: Desc)])` for list-queries ordered by time
- Cross-table relations use explicit `@relation` names when there are multiple FKs between the same two tables (many such cases on `users` → `projects`, `users` → `contracts`)

---

## How to inspect live

From the local DB:

```powershell
# list all tables
'\dt' | docker exec -i catering-db-local psql -U cateringco -d cateringco_dev

# describe one
'\d project_waste_logs' | docker exec -i catering-db-local psql -U cateringco -d cateringco_dev

# what migrations ran
'SELECT migration_name, finished_at FROM _prisma_migrations ORDER BY finished_at;' | docker exec -i catering-db-local psql -U cateringco -d cateringco_dev
```

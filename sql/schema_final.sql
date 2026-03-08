-- schema_final.sql
-- Production-grade schema (includes senior-dev-required changes).
-- Run: psql -U <user> -d <db> -f schema_final.sql

-- ===============
-- Extensions
-- ===============
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
-- Optional if you use pgvector locally:
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ===============
-- ENUM TYPES
-- ===============
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_status') THEN
    CREATE TYPE project_status AS ENUM ('draft','active','confirmed','completed','cancelled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
    CREATE TYPE payment_status AS ENUM ('pending','authorized','paid','failed','refunded','void');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contract_status') THEN
    CREATE TYPE contract_status AS ENUM ('draft','sent','signed','cancelled','expired','superseded');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'webhook_status') THEN
    CREATE TYPE webhook_status AS ENUM ('pending','processed','failed','duplicate');
  END IF;
END$$;

-- ===============
-- Utility: updated_at trigger
-- ===============
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

-- ===============
-- 0001: Identity & RBAC
-- ===============
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NULL,
  primary_phone TEXT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL,
  deleted_by UUID NULL
);
CREATE INDEX IF NOT EXISTS ix_users_status_created_at ON users (status, created_at);

CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  profile_type TEXT NOT NULL, -- 'client' | 'staff' | 'system'
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_user_profiles_type ON user_profiles (profile_type);

CREATE TABLE IF NOT EXISTS roles (
  id TEXT PRIMARY KEY, -- e.g. 'admin', 'sales', 'ops', 'finance', 'legal'
  description TEXT NULL,
  domain TEXT NULL  -- optional domain tag
);

CREATE TABLE IF NOT EXISTS role_permissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission TEXT NOT NULL, -- e.g. 'contracts.create', 'pricing.edit'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- user_roles: surrogate id to allow NULL scope_id (global)
CREATE TABLE IF NOT EXISTS user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id TEXT NOT NULL REFERENCES roles(id),
  scope_type TEXT NOT NULL, -- 'global'|'company'|'project'
  scope_id UUID NULL,
  granted_by UUID NULL,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_user_roles_role ON user_roles (role_id);

-- Unique index treating NULL scope_id as global sentinel
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_roles_unique_scope
  ON user_roles (user_id, role_id, scope_type, COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'::uuid));


-- ===============
-- 0002: Auth / Sessions / API keys
-- ===============
CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_token_hash TEXT NOT NULL,
  created_at timestamptz DEFAULT now(),
  last_active_at timestamptz NULL,
  expires_at timestamptz NOT NULL,
  device_info JSONB NULL,
  ip_address TEXT NULL,
  revoked_at timestamptz NULL
);
CREATE INDEX IF NOT EXISTS ix_sessions_user_active ON sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS auth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,
  type TEXT NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz DEFAULT now(),
  consumed_at timestamptz NULL
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL,
  issued_at timestamptz NOT NULL DEFAULT now(),
  used_at timestamptz NULL,
  revoked_at timestamptz NULL,
  replaced_by_refresh_token_id UUID NULL
);

CREATE TABLE IF NOT EXISTS service_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  owner_user_id UUID REFERENCES users(id),
  metadata JSONB NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  service_account_id UUID REFERENCES service_accounts(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL,
  scopes TEXT[] NOT NULL,
  expires_at timestamptz NULL,
  revoked_at timestamptz NULL,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_keys_service ON api_keys(service_account_id);

-- Optional oauth_accounts if needed later
CREATE TABLE IF NOT EXISTS oauth_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  provider_account_id TEXT NOT NULL,
  access_token TEXT NULL,
  refresh_token_encrypted TEXT NULL,
  raw_profile JSONB NULL,
  created_at timestamptz DEFAULT now(),
  UNIQUE(provider, provider_account_id)
);

-- ===============
-- 0003: Projects & CRM core
-- ===============
CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id UUID NOT NULL REFERENCES users(id),
  title TEXT NOT NULL,
  event_date DATE NULL,
  event_end_date DATE NULL,
  guest_count INT NULL,
  status project_status NOT NULL DEFAULT 'draft',
  ai_event_summary TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL,
  deleted_by UUID NULL,
  signed_contract_id UUID NULL
);
CREATE INDEX IF NOT EXISTS ix_projects_status_event_date ON projects (status, event_date);
CREATE INDEX IF NOT EXISTS ix_projects_owner ON projects (owner_user_id);

CREATE TABLE IF NOT EXISTS project_collaborators (
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY(project_id, user_id)
);

CREATE TABLE IF NOT EXISTS crm_pipeline (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL UNIQUE REFERENCES projects(id),
  assigned_staff_user_id UUID NULL REFERENCES users(id),
  pipeline_stage TEXT NULL,
  lead_source TEXT NULL,
  lead_score INT NULL,
  follow_up_at TIMESTAMPTZ NULL,
  lost_reason TEXT NULL,
  notes TEXT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===============
-- 0004: Messages & Threading (collaboration)
-- ===============
CREATE TABLE IF NOT EXISTS threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  subject TEXT NULL,
  created_by UUID NULL REFERENCES users(id),
  is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
  message_count INT NOT NULL DEFAULT 0,
  last_activity_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_threads_project_last_activity ON threads (project_id, last_activity_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  parent_message_id UUID NULL REFERENCES messages(id) ON DELETE SET NULL,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  author_id UUID NULL REFERENCES users(id),
  sender_type TEXT NULL,
  content TEXT NOT NULL,
  attachments JSONB NULL, -- small metadata list {attachment_id, filename}
  qdrant_vector_id TEXT NULL,
  vector_indexed_at TIMESTAMPTZ NULL,
  vector_status TEXT NULL DEFAULT 'pending',
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_edited_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS ix_messages_thread_created_at ON messages (thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_messages_active ON messages (thread_id, created_at) WHERE is_deleted = false;

-- Maintain threads.message_count via triggers (defined below)

-- ===============
-- 0005: Attachments (secure)
-- ===============
CREATE TABLE IF NOT EXISTS attachments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type TEXT NOT NULL, -- 'project','message','contract','user'
  owner_id UUID NOT NULL,
  project_id UUID NULL REFERENCES projects(id),
  filename TEXT NOT NULL,
  mime_type TEXT NULL,
  size_bytes BIGINT NULL CHECK (size_bytes IS NULL OR size_bytes >= 0),
  storage_provider TEXT NULL,
  storage_path TEXT NULL,
  checksum TEXT NULL,
  virus_scan_status TEXT NOT NULL DEFAULT 'pending', -- 'pending','scanning','clean','infected','quarantined'
  quarantine_reason TEXT NULL,
  quarantined_at TIMESTAMPTZ NULL,
  preview_allowed BOOLEAN NOT NULL DEFAULT false,
  uploaded_by UUID NULL REFERENCES users(id),
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_attachments_project ON attachments (project_id) WHERE preview_allowed = true;
CREATE INDEX IF NOT EXISTS ix_attachments_owner ON attachments (owner_type, owner_id);
ALTER TABLE attachments ADD CONSTRAINT chk_attachments_owner_type CHECK (owner_type IN ('project','message','user','contract','pricing','other'));

-- ===============
-- 0006: Pricing (packages + project snapshot)
-- ===============
CREATE TABLE IF NOT EXISTS pricing_packages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT NULL,
  category VARCHAR(100) NULL,
  base_price NUMERIC(12,2) NULL,
  currency CHAR(3) NOT NULL DEFAULT 'USD' CHECK (currency ~ '^[A-Z]{3}$'),
  price_type VARCHAR(50) NULL, -- per_person | flat | per_hour
  valid_from DATE NULL,
  valid_to DATE NULL,
  priority INT NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pricing_packages_active ON pricing_packages (active, priority DESC);

CREATE TABLE IF NOT EXISTS project_pricing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  -- optional reference to the original package (not authoritative after snapshot)
  source_pricing_package_id UUID NULL,
  -- snapshot fields (immutable by business logic once contract signed)
  snapshot_name TEXT NULL,
  snapshot_base_price NUMERIC(12,2) NULL,
  snapshot_currency CHAR(3) NULL,
  guest_count_snapshot INT NULL,
  line_items JSONB NULL,
  subtotal NUMERIC(12,2) NULL,
  tax NUMERIC(12,2) NULL,
  service_charge NUMERIC(12,2) NULL,
  admin_fee NUMERIC(12,2) NULL,
  negotiated_adjustment NUMERIC(12,2) NULL,
  final_total NUMERIC(12,2) NULL,
  status TEXT NOT NULL DEFAULT 'calculated',
  approved_by_user_id UUID NULL REFERENCES users(id),
  copied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_project_pricing_project ON project_pricing (project_id);
CREATE INDEX IF NOT EXISTS ix_project_pricing_line_items_gin ON project_pricing USING gin (line_items);

CREATE TABLE IF NOT EXISTS cost_of_goods (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_pricing_id UUID NULL REFERENCES project_pricing(id),
  line_item JSONB NOT NULL,
  cost_amount NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS margin_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  threshold NUMERIC(5,2) NULL,
  current_margin NUMERIC(5,2) NULL,
  triggered_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS ix_margin_alerts_project ON margin_alerts (project_id);

-- ===============
-- 0007: Contracts (versioned & auditable)
-- ===============
CREATE TABLE IF NOT EXISTS contracts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_group_id UUID NOT NULL, -- grouping across versions
  version_number INT NOT NULL,
  previous_version_id UUID NULL REFERENCES contracts(id) ON DELETE SET NULL,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  status contract_status NOT NULL,
  title TEXT NULL,
  -- structured body (clauses + placeholders)
  body JSONB NOT NULL,
  pdf_path TEXT NULL,
  total_amount NUMERIC(12,2) NULL,
  change_reason TEXT NULL,
  metadata JSONB NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_by UUID NOT NULL REFERENCES users(id),
  approved_by_user_id UUID NULL REFERENCES users(id),
  seen_by_client_at TIMESTAMPTZ NULL,
  sent_at TIMESTAMPTZ NULL,
  client_signed_at TIMESTAMPTZ NULL,
  expires_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL,
  deleted_by UUID NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_contract_group_version ON contracts (contract_group_id, version_number);
CREATE INDEX IF NOT EXISTS ix_contracts_project_active ON contracts (project_id) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS ix_contracts_status ON contracts (status);

-- Link projects.signed_contract_id -> contracts.id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint c
    JOIN pg_class t ON c.conrelid = t.oid
    WHERE t.relname = 'projects' AND c.conname = 'fk_projects_signed_contract'
  ) THEN
    ALTER TABLE projects
      ADD CONSTRAINT fk_projects_signed_contract
      FOREIGN KEY (signed_contract_id) REFERENCES contracts(id) ON DELETE SET NULL;
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS clause_templates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  content TEXT NOT NULL,
  last_reviewed_at TIMESTAMPTZ NULL,
  tags TEXT[] NULL
);
CREATE INDEX IF NOT EXISTS ix_clause_templates_name ON clause_templates (name);
CREATE INDEX IF NOT EXISTS ix_clause_templates_tags ON clause_templates USING gin (tags);

CREATE TABLE IF NOT EXISTS clause_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clause_template_id UUID NOT NULL REFERENCES clause_templates(id) ON DELETE CASCADE,
  condition JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS contract_clauses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  clause_template_id UUID NULL REFERENCES clause_templates(id),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===============
-- 0008: Change Orders
-- ===============
CREATE TABLE IF NOT EXISTS change_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_by UUID NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'draft',
  metadata JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS change_order_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  change_order_id UUID NOT NULL REFERENCES change_orders(id) ON DELETE CASCADE,
  description TEXT NOT NULL,
  amount NUMERIC(12,2) NOT NULL
);

-- ===============
-- 0009: Payments + Idempotency + Schedules
-- ===============
CREATE TABLE IF NOT EXISTS payment_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NULL REFERENCES users(id),
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NULL,
  payment_id UUID NULL,
  gateway_txn_id TEXT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_requests_client_key ON payment_requests (client_id, idempotency_key);

CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NULL REFERENCES projects(id),
  payment_schedule_id UUID NULL,
  schedule_item_id UUID NULL,
  payment_request_id UUID NULL REFERENCES payment_requests(id),
  gateway_payment_intent_id TEXT NULL,
  gateway_customer_id TEXT NULL,
  type TEXT NULL,
  amount NUMERIC(12,2) NOT NULL,
  currency CHAR(3) NOT NULL DEFAULT 'USD' CHECK (currency ~ '^[A-Z]{3}$'),
  status payment_status NOT NULL DEFAULT 'pending',
  paid_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at TIMESTAMPTZ NULL,
  deleted_by UUID NULL,
  idempotency_key TEXT NULL -- client-provided to prevent duplicate payments
);
CREATE INDEX IF NOT EXISTS ix_payments_project_status ON payments (project_id, status);
-- Unique index to prevent duplicate payments for same idempotency_key (only non-null)
CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_idempotency_key ON payments (idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS payment_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  installment_type TEXT NULL,
  amount NUMERIC(12,2) NULL,
  due_date DATE NULL,
  reminder_sent_at TIMESTAMPTZ NULL,
  auto_charge BOOLEAN NOT NULL DEFAULT false,
  status TEXT NOT NULL DEFAULT 'scheduled',
  created_by_user_id UUID NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_payment_schedules_project_due ON payment_schedules (project_id, due_date);

CREATE TABLE IF NOT EXISTS payment_schedule_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  schedule_id UUID NOT NULL REFERENCES payment_schedules(id) ON DELETE CASCADE,
  label VARCHAR(100) NULL,
  amount NUMERIC(12,2) NOT NULL,
  due_date DATE NULL,
  status payment_status NOT NULL DEFAULT 'pending',
  gateway_payment_intent_id VARCHAR(255) NULL,
  paid_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_schedule_items_schedule_due ON payment_schedule_items (schedule_id, due_date);

-- ===============
-- 0010: Webhook events (retries & idempotency)
-- ===============
CREATE TABLE IF NOT EXISTS webhook_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider TEXT NOT NULL, -- 'stripe','esign','other'
  external_event_id TEXT NOT NULL,
  event_type TEXT NULL,
  payload JSONB NULL,
  idempotency_hash TEXT NULL, -- canonical payload hash
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at TIMESTAMPTZ NULL,
  status webhook_status NOT NULL DEFAULT 'pending',
  attempt_count INT NOT NULL DEFAULT 0,
  last_attempt_at TIMESTAMPTZ NULL,
  next_attempt_at TIMESTAMPTZ NULL,
  last_response_code INT NULL,
  last_response_body TEXT NULL,
  error TEXT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_webhook_provider_event ON webhook_events (provider, external_event_id);
CREATE INDEX IF NOT EXISTS ix_webhook_idempotency_hash ON webhook_events (idempotency_hash);
CREATE INDEX IF NOT EXISTS ix_webhook_status_next_attempt ON webhook_events (status, next_attempt_at);

-- ===============
-- 0011: Events, Notifications & Activity
-- ===============
CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NULL REFERENCES projects(id),
  event_type TEXT NOT NULL,
  actor_id UUID NULL REFERENCES users(id),
  payload JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_events_project_type ON events (project_id, event_type);

CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NULL REFERENCES events(id) ON DELETE SET NULL,
  recipient_user_id UUID NULL REFERENCES users(id),
  channel VARCHAR(32) NOT NULL, -- 'email','sms','in_app'
  template_id TEXT NULL,
  payload JSONB NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  attempt_count INT NOT NULL DEFAULT 0,
  last_attempt_at TIMESTAMPTZ NULL,
  sent_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_read BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_notifications_status ON notifications (status);

CREATE TABLE IF NOT EXISTS activity_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id UUID NULL REFERENCES users(id),
  actor_profile_id UUID NULL,
  project_id UUID NULL REFERENCES projects(id),
  action TEXT NOT NULL,
  payload JSONB NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_activity_log_project ON activity_log (project_id);

-- ===============
-- 0012: Timeline / Analytics / staffing / upsells / followups
-- ===============
CREATE TABLE IF NOT EXISTS event_timeline_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  title TEXT NOT NULL,
  scheduled_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_analytics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  profit NUMERIC(12,2) NULL,
  revenue NUMERIC(12,2) NULL,
  costs NUMERIC(12,2) NULL,
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS follow_ups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  template_id TEXT NULL,
  scheduled_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS upsell_suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  suggestions JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_staffing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  staffing_plan JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_portions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id),
  portions JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===============
-- 0013: Message mentions (optional)
-- ===============
CREATE TABLE IF NOT EXISTS message_mentions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  mentioned_user_id UUID NOT NULL REFERENCES users(id),
  mention_type TEXT NOT NULL DEFAULT 'direct',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ===============
-- TRIGGERS: updated_at & threads.message_count maintenance
-- ===============
-- Attach updated_at trigger to all tables that have updated_at
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT table_name FROM information_schema.columns
    WHERE column_name = 'updated_at' AND table_schema = 'public'
  LOOP
    EXECUTE format('
      DROP TRIGGER IF EXISTS trg_%1$s_updated_at ON %1$I;
      CREATE TRIGGER trg_%1$s_updated_at BEFORE UPDATE ON %1$I
        FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();
    ', r.table_name);
  END LOOP;
END$$;

-- Thread message_count increment/decrement triggers
CREATE OR REPLACE FUNCTION trg_threads_message_count_after_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE threads
  SET message_count = message_count + 1,
      last_activity_at = NEW.created_at
  WHERE id = NEW.thread_id;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS messages_after_insert ON messages;
CREATE TRIGGER messages_after_insert AFTER INSERT ON messages
  FOR EACH ROW EXECUTE FUNCTION trg_threads_message_count_after_insert();

CREATE OR REPLACE FUNCTION trg_threads_message_count_after_delete()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE threads
  SET message_count = GREATEST(message_count - 1, 0)
  WHERE id = OLD.thread_id;
  RETURN OLD;
END;
$$;
DROP TRIGGER IF EXISTS messages_after_delete ON messages;
CREATE TRIGGER messages_after_delete AFTER DELETE ON messages
  FOR EACH ROW EXECUTE FUNCTION trg_threads_message_count_after_delete();

-- ===============
-- Helpful Indexes (GIN / partial)
-- ===============
CREATE INDEX IF NOT EXISTS ix_clause_templates_tags_gin ON clause_templates USING gin (tags);
CREATE INDEX IF NOT EXISTS ix_project_pricing_line_items_gin ON project_pricing USING gin (line_items);
CREATE INDEX IF NOT EXISTS ix_event_analytics_project ON event_analytics (project_id);

-- End of schema_final.sql

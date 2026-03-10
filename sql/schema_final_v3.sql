-- ============================================================
-- schema_v3_final.sql
-- Complete corrected production schema.
-- Fixes all structural issues, critical problems, and
-- incorporates AI conversation state machine from draft review.
--
-- Run on a fresh database:
--   psql -U <user> -d <db> -f schema_v3_final.sql
-- ============================================================


-- ================================================================
-- EXTENSIONS
-- ================================================================
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
-- CREATE EXTENSION IF NOT EXISTS vector;  -- uncomment for pgvector


-- ================================================================
-- ENUM TYPES
-- ================================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_status') THEN
    CREATE TYPE project_status AS ENUM (
      'draft','active','confirmed','completed','cancelled'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
    CREATE TYPE payment_status AS ENUM (
      'pending','authorized','paid','failed','refunded','void'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contract_status') THEN
    CREATE TYPE contract_status AS ENUM (
      'draft','sent','signed','cancelled','expired','superseded'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'webhook_status') THEN
    CREATE TYPE webhook_status AS ENUM (
      'pending','processed','failed','duplicate'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'virus_scan_status') THEN
    CREATE TYPE virus_scan_status AS ENUM (
      'pending','scanning','clean','infected','quarantined'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_level') THEN
    CREATE TYPE risk_level AS ENUM ('low','normal','high','blocked');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_entity_type') THEN
    CREATE TYPE ai_entity_type AS ENUM (
      'contract','proposal','clause','upsell','follow_up',
      'staffing','portions','intake_parse','pricing','beo'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'upsell_status') THEN
    CREATE TYPE upsell_status AS ENUM (
      'suggested','presented','accepted','declined'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'beo_status') THEN
    CREATE TYPE beo_status AS ENUM (
      'draft','confirmed','in_production','completed','cancelled'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_channel') THEN
    CREATE TYPE notification_channel AS ENUM ('email','sms','in_app');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scope_type') THEN
    CREATE TYPE scope_type AS ENUM ('global','company','project');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'price_type') THEN
    CREATE TYPE price_type AS ENUM ('per_person','flat','per_unit','per_hour');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_type') THEN
    CREATE TYPE source_type AS ENUM ('manual','ai_suggested');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'intake_status') THEN
    CREATE TYPE intake_status AS ENUM (
      'received','parsing','parsed','mapped','failed'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'esign_provider') THEN
    CREATE TYPE esign_provider AS ENUM ('docusign','hellosign','internal');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signer_role') THEN
    CREATE TYPE signer_role AS ENUM ('client','caterer','witness');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_flag_type') THEN
    CREATE TYPE risk_flag_type AS ENUM (
      'late_payment','chargeback','no_show','dispute','manual'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'flag_severity') THEN
    CREATE TYPE flag_severity AS ENUM ('low','medium','high');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'owner_type') THEN
    CREATE TYPE owner_type AS ENUM (
      'project','message','user','contract','pricing','other'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'service_style') THEN
    CREATE TYPE service_style AS ENUM (
      'buffet','plated','stations','cocktail','family_style','food_truck'
    );
  END IF;
END$$;


-- ================================================================
-- UTILITY: updated_at auto-trigger function
-- ================================================================
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;


-- ================================================================
-- 0001: IDENTITY & RBAC
-- ================================================================
CREATE TABLE users (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT        NOT NULL UNIQUE,
  password_hash TEXT        NULL,
  primary_phone TEXT        NULL,
  status        TEXT        NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active','inactive','suspended','deleted')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at    TIMESTAMPTZ NULL,
  deleted_by    UUID        NULL
);
CREATE INDEX ix_users_status_created ON users (status, created_at);
CREATE INDEX ix_users_email          ON users (email);

CREATE TABLE user_profiles (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  profile_type TEXT        NOT NULL
                           CHECK (profile_type IN ('client','staff','system')),
  metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_user_profiles_user ON user_profiles (user_id);
CREATE INDEX ix_user_profiles_type ON user_profiles (profile_type);

CREATE TABLE roles (
  id          TEXT PRIMARY KEY,   -- 'admin' | 'sales' | 'ops' | 'finance' | 'legal'
  description TEXT NULL,
  domain      TEXT NULL
);

CREATE TABLE role_permissions (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id    TEXT        NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission TEXT        NOT NULL,  -- 'contracts.create' | 'pricing.edit'
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (role_id, permission)
);

CREATE TABLE user_roles (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id    TEXT        NOT NULL REFERENCES roles(id),
  scope_type scope_type  NOT NULL,
  scope_id   UUID        NULL,
  granted_by UUID        NULL REFERENCES users(id),
  granted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_user_roles_user ON user_roles (user_id);
CREATE INDEX ix_user_roles_role ON user_roles (role_id);
CREATE UNIQUE INDEX ux_user_roles_scope
  ON user_roles (user_id, role_id, scope_type,
    COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'::uuid));


-- ================================================================
-- 0002: AUTH / SESSIONS / API KEYS
-- ================================================================
CREATE TABLE sessions (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_token_hash TEXT        NOT NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_active_at     TIMESTAMPTZ NULL,
  expires_at         TIMESTAMPTZ NOT NULL,
  device_info        JSONB       NULL,
  ip_address         TEXT        NULL,
  revoked_at         TIMESTAMPTZ NULL
);
CREATE INDEX ix_sessions_user_active ON sessions (user_id) WHERE revoked_at IS NULL;
CREATE INDEX ix_sessions_expires     ON sessions (expires_at) WHERE revoked_at IS NULL;

CREATE TABLE auth_tokens (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  TEXT        NOT NULL UNIQUE,
  type        TEXT        NOT NULL CHECK (type IN ('email_verify','password_reset','invite')),
  expires_at  TIMESTAMPTZ NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  consumed_at TIMESTAMPTZ NULL
);
CREATE INDEX ix_auth_tokens_user ON auth_tokens (user_id);

CREATE TABLE refresh_tokens (
  id                           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id                   UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  token_hash                   TEXT        NOT NULL UNIQUE,
  issued_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  used_at                      TIMESTAMPTZ NULL,
  revoked_at                   TIMESTAMPTZ NULL,
  replaced_by_refresh_token_id UUID        NULL REFERENCES refresh_tokens(id)
);
CREATE INDEX ix_refresh_tokens_session ON refresh_tokens (session_id);

CREATE TABLE service_accounts (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT        NOT NULL,
  owner_user_id UUID        NOT NULL REFERENCES users(id),
  metadata      JSONB       NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE api_keys (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  service_account_id UUID        NOT NULL REFERENCES service_accounts(id) ON DELETE CASCADE,
  name               TEXT        NOT NULL,
  key_hash           TEXT        NOT NULL UNIQUE,
  scopes             TEXT[]      NOT NULL DEFAULT '{}',
  expires_at         TIMESTAMPTZ NULL,
  revoked_at         TIMESTAMPTZ NULL,
  last_used_at       TIMESTAMPTZ NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_api_keys_service ON api_keys (service_account_id);
CREATE INDEX ix_api_keys_active  ON api_keys (service_account_id)
  WHERE revoked_at IS NULL;

CREATE TABLE oauth_accounts (
  id                      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                 UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider                TEXT        NOT NULL,
  provider_account_id     TEXT        NOT NULL,
  access_token            TEXT        NULL,
  refresh_token_encrypted TEXT        NULL,
  raw_profile             JSONB       NULL,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_account_id)
);


-- ================================================================
-- 0003: VENUES
-- Must exist before projects (FK dependency).
-- ================================================================
CREATE TABLE venues (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT        NOT NULL,
  address       TEXT        NULL,
  city          TEXT        NULL,
  state         TEXT        NULL,
  country       CHAR(2)     NOT NULL DEFAULT 'US',
  contact_name  TEXT        NULL,
  contact_email TEXT        NULL,
  contact_phone TEXT        NULL,
  capacity_min  INT         NULL CHECK (capacity_min > 0),
  capacity_max  INT         NULL CHECK (capacity_max >= capacity_min),
  notes         TEXT        NULL,
  metadata      JSONB       NOT NULL DEFAULT '{}'::jsonb,
  active        BOOLEAN     NOT NULL DEFAULT true,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_venues_active ON venues (active);
CREATE INDEX ix_venues_city   ON venues (city);


-- ================================================================
-- 0004: PROJECTS & CRM
-- Note: signed_contract_id and ai_conversation_state_id FKs are
-- added via ALTER TABLE after their target tables are created.
-- ================================================================
CREATE TABLE projects (
  id                       UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id            UUID           NOT NULL REFERENCES users(id),
  venue_id                 UUID           NULL REFERENCES venues(id) ON DELETE SET NULL,
  title                    TEXT           NOT NULL,
  event_date               DATE           NULL,
  event_end_date           DATE           NULL,
  guest_count              INT            NULL CHECK (guest_count > 0),
  status                   project_status NOT NULL DEFAULT 'draft',
  ai_event_summary         TEXT           NULL,
  created_via_ai_intake    BOOLEAN        NOT NULL DEFAULT false,
  -- populated after ai_conversation_states is created
  ai_conversation_state_id UUID           NULL,
  -- populated after contracts is created
  signed_contract_id       UUID           NULL,
  -- payment auto-lock fields
  auto_lock_at             TIMESTAMPTZ    NULL,
  locked_at                TIMESTAMPTZ    NULL,
  locked_reason            TEXT           NULL,
  created_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
  deleted_at               TIMESTAMPTZ    NULL,
  deleted_by               UUID           NULL REFERENCES users(id)
);
CREATE INDEX ix_projects_status_event ON projects (status, event_date);
CREATE INDEX ix_projects_owner        ON projects (owner_user_id);
CREATE INDEX ix_projects_venue        ON projects (venue_id);
CREATE INDEX ix_projects_active       ON projects (status)
  WHERE deleted_at IS NULL;

CREATE TABLE project_collaborators (
  project_id UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id    UUID        NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
  role       TEXT        NULL,    -- 'viewer' | 'editor' | 'owner'
  added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (project_id, user_id)
);

CREATE TABLE crm_pipeline (
  id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id             UUID        NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  assigned_staff_user_id UUID        NULL REFERENCES users(id),
  pipeline_stage         TEXT        NULL,
  lead_source            TEXT        NULL,
  lead_score             INT         NULL CHECK (lead_score BETWEEN 0 AND 100),
  risk_level             risk_level  NOT NULL DEFAULT 'normal',
  risk_flags             TEXT[]      NULL,
  risk_reviewed_at       TIMESTAMPTZ NULL,
  follow_up_at           TIMESTAMPTZ NULL,
  lost_reason            TEXT        NULL,
  notes                  TEXT        NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_crm_pipeline_stage     ON crm_pipeline (pipeline_stage);
CREATE INDEX ix_crm_pipeline_follow_up ON crm_pipeline (follow_up_at)
  WHERE follow_up_at IS NOT NULL;
CREATE INDEX ix_crm_pipeline_risk      ON crm_pipeline (risk_level)
  WHERE risk_level IN ('high','blocked');


-- ================================================================
-- 0005: MENU CATALOG
-- ================================================================
CREATE TABLE menu_categories (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT        NOT NULL UNIQUE,
  sort_order INT         NOT NULL DEFAULT 0,
  active     BOOLEAN     NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE menu_items (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id      UUID        NULL REFERENCES menu_categories(id) ON DELETE SET NULL,
  name             TEXT        NOT NULL,
  description      TEXT        NULL,
  unit_cost        NUMERIC(10,2) NULL CHECK (unit_cost >= 0),   -- COGS
  unit_price       NUMERIC(10,2) NULL CHECK (unit_price >= 0),  -- sell price
  currency         CHAR(3)     NOT NULL DEFAULT 'USD'
                               CHECK (currency ~ '^[A-Z]{3}$'),
  price_type       price_type  NULL,
  minimum_quantity INT         NOT NULL DEFAULT 1 CHECK (minimum_quantity > 0),
  allergens        TEXT[]      NULL,
  tags             TEXT[]      NULL,
  is_upsell        BOOLEAN     NOT NULL DEFAULT false,
  active           BOOLEAN     NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_menu_items_category ON menu_items (category_id);
CREATE INDEX ix_menu_items_active   ON menu_items (active);
CREATE INDEX ix_menu_items_tags     ON menu_items USING gin (tags);
CREATE INDEX ix_menu_items_upsell   ON menu_items (is_upsell) WHERE is_upsell = true;

CREATE TABLE order_items (
  id                 UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id         UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  menu_item_id       UUID          NULL REFERENCES menu_items(id) ON DELETE SET NULL,
  item_name_snapshot TEXT          NOT NULL,
  price_snapshot     NUMERIC(10,2) NOT NULL CHECK (price_snapshot >= 0),
  unit_cost_snapshot NUMERIC(10,2) NULL     CHECK (unit_cost_snapshot >= 0),
  quantity           INT           NOT NULL DEFAULT 1 CHECK (quantity > 0),
  price_type         price_type    NULL,
  notes              TEXT          NULL,
  added_by_user_id   UUID          NULL REFERENCES users(id),
  created_at         TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_order_items_project ON order_items (project_id);


-- ================================================================
-- 0006: INTAKE FORMS & SUBMISSIONS
-- ================================================================
CREATE TABLE intake_form_templates (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT        NOT NULL,
  description TEXT        NULL,
  fields      JSONB       NOT NULL DEFAULT '[]'::jsonb,
  -- [{key, label, type, required, options[], ai_mapping}]
  is_default  BOOLEAN     NOT NULL DEFAULT false,
  active      BOOLEAN     NOT NULL DEFAULT true,
  created_by  UUID        NULL REFERENCES users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_intake_form_default
  ON intake_form_templates (is_default) WHERE is_default = true;

CREATE TABLE intake_submissions (
  id                  UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  form_template_id    UUID           NULL REFERENCES intake_form_templates(id),
  project_id          UUID           NULL REFERENCES projects(id) ON DELETE SET NULL,
  raw_answers         JSONB          NOT NULL DEFAULT '{}'::jsonb,
  ai_parsed_output    JSONB          NULL,
  ai_confidence_score NUMERIC(4,3)   NULL CHECK (ai_confidence_score BETWEEN 0 AND 1),
  missing_fields      TEXT[]         NULL,
  upsell_triggers     TEXT[]         NULL,
  status              intake_status  NOT NULL DEFAULT 'received',
  submitted_by_email  TEXT           NULL,
  submitted_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),
  parsed_at           TIMESTAMPTZ    NULL,
  mapped_at           TIMESTAMPTZ    NULL
);
CREATE INDEX ix_intake_submissions_project ON intake_submissions (project_id);
CREATE INDEX ix_intake_submissions_status  ON intake_submissions (status);


-- ================================================================
-- 0007: THREADS
-- Must exist before ai_conversation_states and messages.
-- ================================================================
CREATE TABLE threads (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  subject          TEXT        NULL,
  created_by       UUID        NULL REFERENCES users(id),
  is_resolved      BOOLEAN     NOT NULL DEFAULT false,
  message_count    INT         NOT NULL DEFAULT 0 CHECK (message_count >= 0),
  last_activity_at TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_threads_project_activity
  ON threads (project_id, last_activity_at DESC);
CREATE INDEX ix_threads_unresolved
  ON threads (project_id) WHERE is_resolved = false;


-- ================================================================
-- 0008: AI CONVERSATION STATES
-- Multi-turn AI intake state machine.
-- Tracks where a client is mid-conversation between turns.
-- ================================================================
CREATE TABLE ai_conversation_states (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id     UUID        NOT NULL UNIQUE REFERENCES threads(id) ON DELETE CASCADE,
  project_id    UUID        NULL REFERENCES projects(id) ON DELETE SET NULL,
  current_node  TEXT        NOT NULL DEFAULT 'start',
  -- node examples: 'start','event_type','guest_count','venue',
  --                'budget','service_style','review','complete'
  slots         JSONB       NOT NULL DEFAULT '{}'::jsonb,
  -- collected fields so far: {event_type, guest_count, venue_name, ...}
  is_completed  BOOLEAN     NOT NULL DEFAULT false,
  next_action   TEXT        NULL,
  -- 'ask_guest_count' | 'ask_venue' | 'generate_contract' etc.
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_conv_states_project
  ON ai_conversation_states (project_id);
CREATE INDEX ix_ai_conv_states_completed
  ON ai_conversation_states (is_completed, updated_at DESC);
CREATE INDEX ix_ai_conv_states_active
  ON ai_conversation_states (is_completed) WHERE is_completed = false;

-- Deferred FK: projects.ai_conversation_state_id
ALTER TABLE projects
  ADD CONSTRAINT fk_projects_ai_conv_state
  FOREIGN KEY (ai_conversation_state_id)
  REFERENCES ai_conversation_states(id) ON DELETE SET NULL;


-- ================================================================
-- 0009: MESSAGES
-- ================================================================
CREATE TABLE messages (
  id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id                UUID        NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  parent_message_id        UUID        NULL REFERENCES messages(id) ON DELETE SET NULL,
  project_id               UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  author_id                UUID        NULL REFERENCES users(id),
  sender_type              TEXT        NULL
                                       CHECK (sender_type IN ('user','ai','system')),
  content                  TEXT        NOT NULL,
  attachments              JSONB       NULL,  -- [{attachment_id, filename, mime_type}]
  ai_conversation_state_id UUID        NULL
                                       REFERENCES ai_conversation_states(id)
                                       ON DELETE SET NULL,
  qdrant_vector_id         TEXT        NULL,
  vector_indexed_at        TIMESTAMPTZ NULL,
  vector_status            TEXT        NOT NULL DEFAULT 'pending'
                                       CHECK (vector_status IN
                                         ('pending','indexing','indexed','failed')),
  is_deleted               BOOLEAN     NOT NULL DEFAULT false,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_edited_at           TIMESTAMPTZ NULL
);
CREATE INDEX ix_messages_thread_created
  ON messages (thread_id, created_at DESC);
CREATE INDEX ix_messages_active
  ON messages (thread_id, created_at) WHERE is_deleted = false;
CREATE INDEX ix_messages_ai_conv_state
  ON messages (ai_conversation_state_id)
  WHERE ai_conversation_state_id IS NOT NULL;
CREATE INDEX ix_messages_vector_pending
  ON messages (vector_status) WHERE vector_status = 'pending';

CREATE TABLE message_mentions (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id        UUID        NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  mentioned_user_id UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mention_type      TEXT        NOT NULL DEFAULT 'direct'
                                CHECK (mention_type IN ('direct','team','all')),
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_message_mentions_message ON message_mentions (message_id);
CREATE INDEX ix_message_mentions_user    ON message_mentions (mentioned_user_id);


-- ================================================================
-- 0010: ATTACHMENTS
-- ================================================================
CREATE TABLE attachments (
  id                UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_type        owner_type       NOT NULL,
  owner_id          UUID             NOT NULL,
  project_id        UUID             NULL REFERENCES projects(id) ON DELETE SET NULL,
  filename          TEXT             NOT NULL,
  mime_type         TEXT             NULL,
  size_bytes        BIGINT           NULL CHECK (size_bytes >= 0),
  storage_provider  TEXT             NULL CHECK (storage_provider IN ('s3','gcs','local')),
  storage_path      TEXT             NULL,
  checksum          TEXT             NULL,
  virus_scan_status virus_scan_status NOT NULL DEFAULT 'pending',
  quarantine_reason TEXT             NULL,
  quarantined_at    TIMESTAMPTZ      NULL,
  preview_allowed   BOOLEAN          NOT NULL DEFAULT false,
  uploaded_by       UUID             NULL REFERENCES users(id),
  uploaded_at       TIMESTAMPTZ      NOT NULL DEFAULT now()
);
CREATE INDEX ix_attachments_owner   ON attachments (owner_type, owner_id);
CREATE INDEX ix_attachments_project ON attachments (project_id)
  WHERE preview_allowed = true;
CREATE INDEX ix_attachments_scan    ON attachments (virus_scan_status)
  WHERE virus_scan_status = 'pending';


-- ================================================================
-- 0011: PRICING
-- ================================================================
CREATE TABLE pricing_packages (
  id          UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT          NOT NULL,
  description TEXT          NULL,
  category    TEXT          NULL,
  base_price  NUMERIC(12,2) NULL CHECK (base_price >= 0),
  currency    CHAR(3)       NOT NULL DEFAULT 'USD' CHECK (currency ~ '^[A-Z]{3}$'),
  price_type  price_type    NULL,
  valid_from  DATE          NULL,
  valid_to    DATE          NULL,
  priority    INT           NOT NULL DEFAULT 0,
  active      BOOLEAN       NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),
  CONSTRAINT chk_pricing_package_dates
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);
CREATE INDEX ix_pricing_packages_active ON pricing_packages (active, priority DESC);

CREATE TABLE project_pricing (
  id                        UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_pricing_package_id UUID          NULL REFERENCES pricing_packages(id) ON DELETE SET NULL,
  snapshot_name             TEXT          NULL,
  snapshot_base_price       NUMERIC(12,2) NULL,
  snapshot_currency         CHAR(3)       NULL CHECK (snapshot_currency ~ '^[A-Z]{3}$'),
  guest_count_snapshot      INT           NULL,
  line_items                JSONB         NULL,
  subtotal                  NUMERIC(12,2) NULL CHECK (subtotal >= 0),
  tax                       NUMERIC(12,2) NULL CHECK (tax >= 0),
  service_charge            NUMERIC(12,2) NULL,
  admin_fee                 NUMERIC(12,2) NULL,
  negotiated_adjustment     NUMERIC(12,2) NULL,
  final_total               NUMERIC(12,2) NULL,
  status                    TEXT          NOT NULL DEFAULT 'calculated'
                                          CHECK (status IN
                                            ('calculated','pending_approval','approved','locked')),
  ai_generated              BOOLEAN       NOT NULL DEFAULT false,
  ai_generation_id          UUID          NULL,  -- FK added after ai_generations
  approved_by_user_id       UUID          NULL REFERENCES users(id),
  approved_at               TIMESTAMPTZ   NULL,
  copied_at                 TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_project_pricing_project   ON project_pricing (project_id);
CREATE INDEX ix_project_pricing_gin       ON project_pricing USING gin (line_items);

CREATE TABLE cost_of_goods (
  id                 UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_pricing_id UUID          NOT NULL REFERENCES project_pricing(id) ON DELETE CASCADE,
  line_item          JSONB         NOT NULL,
  cost_amount        NUMERIC(12,2) NOT NULL CHECK (cost_amount >= 0),
  created_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_cogs_pricing ON cost_of_goods (project_pricing_id);

CREATE TABLE margin_alerts (
  id             UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  threshold      NUMERIC(5,2)  NOT NULL,
  current_margin NUMERIC(5,2)  NULL,
  triggered_at   TIMESTAMPTZ   NOT NULL DEFAULT now(),
  resolved_at    TIMESTAMPTZ   NULL
);
CREATE INDEX ix_margin_alerts_project ON margin_alerts (project_id);
CREATE INDEX ix_margin_alerts_open    ON margin_alerts (triggered_at)
  WHERE resolved_at IS NULL;


-- ================================================================
-- 0012: CONTRACTS & CLAUSE ENGINE
-- ================================================================
CREATE TABLE clause_templates (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name             TEXT        NOT NULL,
  content          TEXT        NOT NULL,
  last_reviewed_at TIMESTAMPTZ NULL,
  tags             TEXT[]      NULL,
  active           BOOLEAN     NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_clause_templates_name ON clause_templates (name);
CREATE INDEX ix_clause_templates_tags ON clause_templates USING gin (tags);

CREATE TABLE clause_rules (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clause_template_id UUID        NOT NULL REFERENCES clause_templates(id) ON DELETE CASCADE,
  condition          JSONB       NOT NULL,
  -- schema: {field, operator, value}
  -- e.g. {"field":"event_type","op":"eq","value":"wedding"}
  --      {"field":"guest_count","op":"gte","value":100}
  priority           INT         NOT NULL DEFAULT 0,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_clause_rules_template ON clause_rules (clause_template_id);

CREATE TABLE venue_clause_overrides (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  venue_id           UUID        NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
  clause_template_id UUID        NOT NULL REFERENCES clause_templates(id) ON DELETE CASCADE,
  override_content   TEXT        NULL,      -- NULL = use clause_templates.content as-is
  is_mandatory       BOOLEAN     NOT NULL DEFAULT false,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (venue_id, clause_template_id)
);

CREATE TABLE contracts (
  id                   UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_group_id    UUID            NOT NULL,
  version_number       INT             NOT NULL,
  previous_version_id  UUID            NULL REFERENCES contracts(id) ON DELETE SET NULL,
  project_id           UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  status               contract_status NOT NULL DEFAULT 'draft',
  title                TEXT            NULL,
  body                 JSONB           NOT NULL,  -- structured clauses + placeholders
  pdf_path             TEXT            NULL,
  total_amount         NUMERIC(12,2)   NULL CHECK (total_amount >= 0),
  change_reason        TEXT            NULL,
  metadata             JSONB           NULL,
  is_active            BOOLEAN         NOT NULL DEFAULT true,
  ai_generated         BOOLEAN         NOT NULL DEFAULT false,
  esign_provider       esign_provider  NULL,
  esign_envelope_id    TEXT            NULL,
  created_by           UUID            NOT NULL REFERENCES users(id),
  approved_by_user_id  UUID            NULL REFERENCES users(id),
  seen_by_client_at    TIMESTAMPTZ     NULL,
  sent_at              TIMESTAMPTZ     NULL,
  client_signed_at     TIMESTAMPTZ     NULL,
  expires_at           TIMESTAMPTZ     NULL,
  created_at           TIMESTAMPTZ     NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ     NOT NULL DEFAULT now(),
  deleted_at           TIMESTAMPTZ     NULL,
  deleted_by           UUID            NULL REFERENCES users(id)
);
CREATE UNIQUE INDEX ux_contract_group_version
  ON contracts (contract_group_id, version_number);
CREATE INDEX ix_contracts_project_active
  ON contracts (project_id) WHERE is_active = true;
CREATE INDEX ix_contracts_status    ON contracts (status);
CREATE INDEX ix_contracts_envelope  ON contracts (esign_envelope_id)
  WHERE esign_envelope_id IS NOT NULL;

CREATE TABLE contract_clauses (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id        UUID        NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  clause_template_id UUID        NULL REFERENCES clause_templates(id) ON DELETE SET NULL,
  content            TEXT        NOT NULL,
  sort_order         INT         NOT NULL DEFAULT 0,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_contract_clauses_contract ON contract_clauses (contract_id);

-- E-signature audit trail — legally defensible per-signer record
CREATE TABLE contract_signatures (
  id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id     UUID          NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  esign_provider  esign_provider NOT NULL,
  envelope_id     TEXT          NULL,
  signer_user_id  UUID          NULL REFERENCES users(id),
  signer_email    TEXT          NOT NULL,
  signer_name     TEXT          NULL,
  signer_role     signer_role   NOT NULL,
  ip_address      TEXT          NULL,
  user_agent      TEXT          NULL,
  signed_at       TIMESTAMPTZ   NULL,
  declined_at     TIMESTAMPTZ   NULL,
  decline_reason  TEXT          NULL,
  audit_trail     JSONB         NULL,   -- full provider audit log payload
  certificate_url TEXT          NULL,
  created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_contract_signatures_contract ON contract_signatures (contract_id);
CREATE INDEX ix_contract_signatures_envelope ON contract_signatures (envelope_id);

-- Deferred FK: projects.signed_contract_id
ALTER TABLE projects
  ADD CONSTRAINT fk_projects_signed_contract
  FOREIGN KEY (signed_contract_id)
  REFERENCES contracts(id) ON DELETE SET NULL;


-- ================================================================
-- 0013: CHANGE ORDERS
-- ================================================================
CREATE TABLE change_orders (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  contract_id UUID        NULL REFERENCES contracts(id) ON DELETE SET NULL,
  created_by  UUID        NULL REFERENCES users(id),
  status      TEXT        NOT NULL DEFAULT 'draft'
                          CHECK (status IN
                            ('draft','pending_approval','approved','rejected','applied')),
  metadata    JSONB       NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_change_orders_project ON change_orders (project_id);
CREATE INDEX ix_change_orders_status  ON change_orders (status)
  WHERE status IN ('draft','pending_approval');

CREATE TABLE change_order_lines (
  id              UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  change_order_id UUID          NOT NULL REFERENCES change_orders(id) ON DELETE CASCADE,
  description     TEXT          NOT NULL,
  amount          NUMERIC(12,2) NOT NULL,
  created_at      TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_change_order_lines_order ON change_order_lines (change_order_id);


-- ================================================================
-- 0014: BANQUET EVENT ORDER (BEO)
-- Operational kitchen/production document. Separate from contract.
-- ================================================================
CREATE TABLE banquet_event_orders (
  id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  contract_id      UUID          NULL REFERENCES contracts(id) ON DELETE SET NULL,
  beo_number       TEXT          NOT NULL,   -- e.g. BEO-2024-0042
  version_number   INT           NOT NULL DEFAULT 1,
  status           beo_status    NOT NULL DEFAULT 'draft',
  event_date       DATE          NULL,
  event_start_time TIMETZ        NULL,
  event_end_time   TIMETZ        NULL,
  guest_count      INT           NULL CHECK (guest_count > 0),
  service_style    service_style NULL,
  setup_notes      TEXT          NULL,
  breakdown_notes  TEXT          NULL,
  kitchen_notes    TEXT          NULL,
  dietary_notes    TEXT          NULL,
  timeline_notes   TEXT          NULL,
  created_by       UUID          NULL REFERENCES users(id),
  confirmed_by     UUID          NULL REFERENCES users(id),
  confirmed_at     TIMESTAMPTZ   NULL,
  created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_beo_number ON banquet_event_orders (beo_number);
CREATE INDEX ix_beo_project        ON banquet_event_orders (project_id);
CREATE INDEX ix_beo_status         ON banquet_event_orders (status);
CREATE INDEX ix_beo_event_date     ON banquet_event_orders (event_date);

CREATE TABLE beo_line_items (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  beo_id        UUID        NOT NULL REFERENCES banquet_event_orders(id) ON DELETE CASCADE,
  order_item_id UUID        NULL REFERENCES order_items(id) ON DELETE SET NULL,
  item_name     TEXT        NOT NULL,
  quantity      INT         NOT NULL CHECK (quantity > 0),
  unit          TEXT        NULL CHECK (unit IN
                              ('portions','trays','bottles','gallons','lbs','units')),
  prep_notes    TEXT        NULL,
  sort_order    INT         NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_beo_line_items_beo ON beo_line_items (beo_id);

CREATE TABLE beo_staff_assignments (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  beo_id     UUID        NOT NULL REFERENCES banquet_event_orders(id) ON DELETE CASCADE,
  role       TEXT        NOT NULL
                         CHECK (role IN
                           ('chef','sous_chef','server','bartender','captain',
                            'busser','setup_crew','security','other')),
  quantity   INT         NOT NULL DEFAULT 1 CHECK (quantity > 0),
  start_time TIMETZ      NULL,
  end_time   TIMETZ      NULL,
  notes      TEXT        NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_beo_staff_beo ON beo_staff_assignments (beo_id);


-- ================================================================
-- 0015: PAYMENTS + IDEMPOTENCY + SCHEDULES
-- ================================================================
CREATE TABLE payment_requests (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id       UUID        NULL REFERENCES users(id),
  idempotency_key TEXT        NOT NULL,
  request_hash    TEXT        NULL,
  payment_id      UUID        NULL,
  gateway_txn_id  TEXT        NULL,
  status          TEXT        NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','processed','failed','duplicate')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_payment_requests_client_key
  ON payment_requests (client_id, idempotency_key);

CREATE TABLE payments (
  id                        UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id                UUID           NULL REFERENCES projects(id) ON DELETE SET NULL,
  payment_schedule_id       UUID           NULL,    -- FK added after payment_schedules
  schedule_item_id          UUID           NULL,    -- FK added after payment_schedule_items
  payment_request_id        UUID           NULL REFERENCES payment_requests(id),
  gateway_payment_intent_id TEXT           NULL,
  gateway_customer_id       TEXT           NULL,
  type                      TEXT           NULL
                                           CHECK (type IN
                                             ('deposit','installment','balance','refund','other')),
  amount                    NUMERIC(12,2)  NOT NULL CHECK (amount > 0),
  currency                  CHAR(3)        NOT NULL DEFAULT 'USD'
                                           CHECK (currency ~ '^[A-Z]{3}$'),
  status                    payment_status NOT NULL DEFAULT 'pending',
  paid_at                   TIMESTAMPTZ    NULL,
  idempotency_key           TEXT           NULL,
  created_at                TIMESTAMPTZ    NOT NULL DEFAULT now(),
  deleted_at                TIMESTAMPTZ    NULL,
  deleted_by                UUID           NULL REFERENCES users(id)
);
CREATE INDEX ix_payments_project_status ON payments (project_id, status);
CREATE UNIQUE INDEX ux_payments_idempotency
  ON payments (idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX ix_payments_gateway_intent ON payments (gateway_payment_intent_id)
  WHERE gateway_payment_intent_id IS NOT NULL;

CREATE TABLE payment_schedules (
  id                 UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id         UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  installment_type   TEXT          NULL
                                   CHECK (installment_type IN
                                     ('deposit_balance','thirds','custom')),
  total_amount       NUMERIC(12,2) NULL CHECK (total_amount > 0),
  due_date           DATE          NULL,
  reminder_sent_at   TIMESTAMPTZ   NULL,
  auto_charge        BOOLEAN       NOT NULL DEFAULT false,
  status             TEXT          NOT NULL DEFAULT 'scheduled'
                                   CHECK (status IN
                                     ('scheduled','active','completed','cancelled')),
  created_by_user_id UUID          NULL REFERENCES users(id),
  created_at         TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_payment_schedules_project_due ON payment_schedules (project_id, due_date);

CREATE TABLE payment_schedule_items (
  id                        UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  schedule_id               UUID           NOT NULL REFERENCES payment_schedules(id)
                                           ON DELETE CASCADE,
  label                     TEXT           NULL,
  amount                    NUMERIC(12,2)  NOT NULL CHECK (amount > 0),
  due_date                  DATE           NULL,
  status                    payment_status NOT NULL DEFAULT 'pending',
  gateway_payment_intent_id TEXT           NULL,
  paid_at                   TIMESTAMPTZ    NULL,
  created_at                TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX ix_schedule_items_schedule_due
  ON payment_schedule_items (schedule_id, due_date);
CREATE INDEX ix_schedule_items_pending
  ON payment_schedule_items (due_date, status)
  WHERE status = 'pending';

-- Deferred FKs back to payment tables
ALTER TABLE payments
  ADD CONSTRAINT fk_payments_schedule
    FOREIGN KEY (payment_schedule_id) REFERENCES payment_schedules(id) ON DELETE SET NULL,
  ADD CONSTRAINT fk_payments_schedule_item
    FOREIGN KEY (schedule_item_id) REFERENCES payment_schedule_items(id) ON DELETE SET NULL;

-- Client payment risk flags
CREATE TABLE client_risk_flags (
  id          UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID           NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  project_id  UUID           NULL REFERENCES projects(id) ON DELETE SET NULL,
  flag_type   risk_flag_type NOT NULL,
  severity    flag_severity  NOT NULL DEFAULT 'medium',
  notes       TEXT           NULL,
  flagged_by  UUID           NULL REFERENCES users(id),
  resolved_at TIMESTAMPTZ    NULL,
  resolved_by UUID           NULL REFERENCES users(id),
  created_at  TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX ix_client_risk_flags_user    ON client_risk_flags (user_id);
CREATE INDEX ix_client_risk_flags_project ON client_risk_flags (project_id);
CREATE INDEX ix_client_risk_flags_open    ON client_risk_flags (user_id)
  WHERE resolved_at IS NULL;


-- ================================================================
-- 0016: WEBHOOK EVENTS
-- ================================================================
CREATE TABLE webhook_events (
  id                 UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  provider           TEXT           NOT NULL
                                    CHECK (provider IN ('stripe','docusign','hellosign','other')),
  external_event_id  TEXT           NOT NULL,
  event_type         TEXT           NULL,
  payload            JSONB          NULL,
  idempotency_hash   TEXT           NULL,
  received_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),
  processed_at       TIMESTAMPTZ    NULL,
  status             webhook_status NOT NULL DEFAULT 'pending',
  attempt_count      INT            NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  last_attempt_at    TIMESTAMPTZ    NULL,
  next_attempt_at    TIMESTAMPTZ    NULL,
  last_response_code INT            NULL,
  last_response_body TEXT           NULL,
  error              TEXT           NULL
);
CREATE UNIQUE INDEX ux_webhook_provider_event ON webhook_events (provider, external_event_id);
CREATE INDEX ix_webhook_idempotency_hash ON webhook_events (idempotency_hash);
CREATE INDEX ix_webhook_status_next      ON webhook_events (status, next_attempt_at)
  WHERE status IN ('pending','failed');


-- ================================================================
-- 0017: EVENTS, NOTIFICATIONS & ACTIVITY LOG
-- ================================================================
CREATE TABLE events (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID        NULL REFERENCES projects(id) ON DELETE SET NULL,
  event_type TEXT        NOT NULL,
  actor_id   UUID        NULL REFERENCES users(id),
  payload    JSONB       NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_events_project_type ON events (project_id, event_type);
CREATE INDEX ix_events_actor        ON events (actor_id);

CREATE TABLE notification_templates (
  id         UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
  key        TEXT                 NOT NULL UNIQUE,
  channel    notification_channel NOT NULL,
  subject    TEXT                 NULL,         -- email subject
  body       TEXT                 NOT NULL,     -- handlebars/mustache template
  variables  TEXT[]               NULL,         -- documented variable names
  version    INT                  NOT NULL DEFAULT 1,
  active     BOOLEAN              NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ          NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ          NOT NULL DEFAULT now()
);
CREATE INDEX ix_notification_templates_channel ON notification_templates (channel);
CREATE INDEX ix_notification_templates_active  ON notification_templates (active)
  WHERE active = true;

CREATE TABLE notifications (
  id                UUID                 PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id          UUID                 NULL REFERENCES events(id) ON DELETE SET NULL,
  recipient_user_id UUID                 NULL REFERENCES users(id) ON DELETE SET NULL,
  channel           notification_channel NOT NULL,
  template_key      TEXT                 NULL REFERENCES notification_templates(key)
                                         ON DELETE SET NULL ON UPDATE CASCADE,
  payload           JSONB                NULL,
  status            TEXT                 NOT NULL DEFAULT 'pending'
                                         CHECK (status IN
                                           ('pending','sending','sent','failed','bounced')),
  attempt_count     INT                  NOT NULL DEFAULT 0,
  last_attempt_at   TIMESTAMPTZ          NULL,
  sent_at           TIMESTAMPTZ          NULL,
  created_at        TIMESTAMPTZ          NOT NULL DEFAULT now(),
  is_read           BOOLEAN              NOT NULL DEFAULT false
);
CREATE INDEX ix_notifications_status    ON notifications (status)
  WHERE status IN ('pending','failed');
CREATE INDEX ix_notifications_recipient ON notifications (recipient_user_id, is_read);

CREATE TABLE activity_log (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_user_id    UUID        NULL REFERENCES users(id),
  actor_profile_id UUID        NULL,
  project_id       UUID        NULL REFERENCES projects(id) ON DELETE SET NULL,
  action           TEXT        NOT NULL,
  payload          JSONB       NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_activity_log_project ON activity_log (project_id);
CREATE INDEX ix_activity_log_actor   ON activity_log (actor_user_id, created_at DESC);


-- ================================================================
-- 0018: AI GENERATION AUDIT LOG
-- Every AI output is fully traceable.
-- ================================================================
CREATE TABLE ai_generations (
  id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type     ai_entity_type NOT NULL,
  entity_id       UUID           NULL,
  project_id      UUID           NULL REFERENCES projects(id) ON DELETE SET NULL,
  triggered_by    UUID           NULL REFERENCES users(id),
  model           TEXT           NOT NULL,    -- 'claude-sonnet-4-20250514'
  prompt_version  TEXT           NULL,
  prompt_hash     TEXT           NULL,        -- SHA256 of rendered prompt
  input_summary   JSONB          NULL,        -- key inputs (not full prompt)
  output          TEXT           NULL,        -- full raw AI output
  output_tokens   INT            NULL CHECK (output_tokens >= 0),
  input_tokens    INT            NULL CHECK (input_tokens >= 0),
  latency_ms      INT            NULL CHECK (latency_ms >= 0),
  was_applied     BOOLEAN        NOT NULL DEFAULT false,
  feedback_rating INT            NULL CHECK (feedback_rating BETWEEN 1 AND 5),
  feedback_notes  TEXT           NULL,
  created_at      TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_generations_entity  ON ai_generations (entity_type, entity_id);
CREATE INDEX ix_ai_generations_project ON ai_generations (project_id);
CREATE INDEX ix_ai_generations_model   ON ai_generations (model, created_at DESC);
CREATE INDEX ix_ai_generations_applied ON ai_generations (was_applied, entity_type);

-- Deferred FK: project_pricing.ai_generation_id
ALTER TABLE project_pricing
  ADD CONSTRAINT fk_project_pricing_ai_gen
  FOREIGN KEY (ai_generation_id)
  REFERENCES ai_generations(id) ON DELETE SET NULL;


-- ================================================================
-- 0019: TIMELINE / ANALYTICS / FOLLOW-UPS
-- ================================================================
CREATE TABLE event_timeline_items (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  title        TEXT        NOT NULL,
  description  TEXT        NULL,
  scheduled_at TIMESTAMPTZ NULL,
  completed_at TIMESTAMPTZ NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_timeline_project_sched
  ON event_timeline_items (project_id, scheduled_at);

CREATE TABLE event_analytics (
  id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  profit        NUMERIC(12,2) NULL,
  revenue       NUMERIC(12,2) NULL CHECK (revenue >= 0),
  costs         NUMERIC(12,2) NULL CHECK (costs >= 0),
  margin_pct    NUMERIC(5,2)  NULL,  -- computed: (profit/revenue)*100
  calculated_at TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_event_analytics_project ON event_analytics (project_id);

CREATE TABLE follow_ups (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  template_key TEXT        NULL REFERENCES notification_templates(key) ON DELETE SET NULL,
  scheduled_at TIMESTAMPTZ NULL,
  sent_at      TIMESTAMPTZ NULL,
  status       TEXT        NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending','sent','skipped','failed')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_follow_ups_project  ON follow_ups (project_id);
CREATE INDEX ix_follow_ups_pending  ON follow_ups (scheduled_at)
  WHERE status = 'pending';


-- ================================================================
-- 0020: STRUCTURED STAFFING / PORTIONS / UPSELLS
-- Typed rows — queryable, AI-linked, and analytically useful.
-- ================================================================

CREATE TABLE project_staff_requirements (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  role             TEXT        NOT NULL,
  quantity         INT         NOT NULL DEFAULT 1 CHECK (quantity > 0),
  hours_estimated  NUMERIC(5,2) NULL CHECK (hours_estimated > 0),
  rate_per_hour    NUMERIC(10,2) NULL CHECK (rate_per_hour >= 0),
  total_cost       NUMERIC(10,2) NULL CHECK (total_cost >= 0),
  notes            TEXT        NULL,
  source           source_type NOT NULL DEFAULT 'manual',
  ai_generation_id UUID        NULL REFERENCES ai_generations(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_proj_staff_project ON project_staff_requirements (project_id);

CREATE TABLE project_portion_estimates (
  id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  menu_item_id     UUID          NULL REFERENCES menu_items(id) ON DELETE SET NULL,
  item_name        TEXT          NOT NULL,
  guest_count      INT           NOT NULL CHECK (guest_count > 0),
  quantity         NUMERIC(10,3) NOT NULL CHECK (quantity > 0),
  unit             TEXT          NULL
                                 CHECK (unit IN
                                   ('lbs','portions','trays','gallons','units')),
  waste_factor     NUMERIC(4,3)  NOT NULL DEFAULT 0.10
                                 CHECK (waste_factor BETWEEN 0 AND 1),
  source           source_type   NOT NULL DEFAULT 'manual',
  ai_generation_id UUID          NULL REFERENCES ai_generations(id) ON DELETE SET NULL,
  created_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_proj_portions_project ON project_portion_estimates (project_id);

CREATE TABLE project_upsell_items (
  id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        UUID          NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  menu_item_id      UUID          NULL REFERENCES menu_items(id) ON DELETE SET NULL,
  title             TEXT          NOT NULL,
  description       TEXT          NULL,
  estimated_revenue NUMERIC(10,2) NULL CHECK (estimated_revenue >= 0),
  status            upsell_status NOT NULL DEFAULT 'suggested',
  presented_at      TIMESTAMPTZ   NULL,
  responded_at      TIMESTAMPTZ   NULL,
  source            source_type   NOT NULL DEFAULT 'ai_suggested',
  ai_generation_id  UUID          NULL REFERENCES ai_generations(id) ON DELETE SET NULL,
  created_at        TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX ix_proj_upsells_project ON project_upsell_items (project_id);
CREATE INDEX ix_proj_upsells_status  ON project_upsell_items (status);


-- ================================================================
-- TRIGGERS: updated_at on all tables that have it
-- ================================================================
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT table_name
    FROM information_schema.columns
    WHERE column_name = 'updated_at'
      AND table_schema = 'public'
  LOOP
    EXECUTE format('
      DROP TRIGGER IF EXISTS trg_%1$s_updated_at ON %1$I;
      CREATE TRIGGER trg_%1$s_updated_at
        BEFORE UPDATE ON %1$I
        FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at();
    ', r.table_name);
  END LOOP;
END$$;


-- ================================================================
-- TRIGGERS: threads.message_count maintenance
-- ================================================================
CREATE OR REPLACE FUNCTION trg_threads_msg_count_insert()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE threads
  SET message_count    = message_count + 1,
      last_activity_at = NEW.created_at
  WHERE id = NEW.thread_id;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_messages_after_insert ON messages;
CREATE TRIGGER trg_messages_after_insert
  AFTER INSERT ON messages
  FOR EACH ROW EXECUTE FUNCTION trg_threads_msg_count_insert();

CREATE OR REPLACE FUNCTION trg_threads_msg_count_delete()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE threads
  SET message_count = GREATEST(message_count - 1, 0)
  WHERE id = OLD.thread_id;
  RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS trg_messages_after_delete ON messages;
CREATE TRIGGER trg_messages_after_delete
  AFTER DELETE ON messages
  FOR EACH ROW EXECUTE FUNCTION trg_threads_msg_count_delete();


-- ================================================================
-- End of schema_v3_final.sql
-- ================================================================

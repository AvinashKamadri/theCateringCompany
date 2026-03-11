-- ============================================================
-- migrate_to_production.sql
-- Drops old simplified tables, creates 11 production tables
-- in the existing catering_company database.
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- DROP OLD SIMPLIFIED TABLES
-- ============================================================
DROP TABLE IF EXISTS ai_tags CASCADE;
DROP TABLE IF EXISTS contracts CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS conversation_states CASCADE;

-- ============================================================
-- ENUM TYPES (only what the 11 tables need)
-- ============================================================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'project_status') THEN
    CREATE TYPE project_status AS ENUM (
      'draft','active','confirmed','completed','cancelled'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contract_status') THEN
    CREATE TYPE contract_status AS ENUM (
      'draft','sent','signed','cancelled','expired','superseded'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ai_entity_type') THEN
    CREATE TYPE ai_entity_type AS ENUM (
      'contract','proposal','clause','upsell','follow_up',
      'staffing','portions','intake_parse','pricing','beo'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'price_type') THEN
    CREATE TYPE price_type AS ENUM ('per_person','flat','per_unit','per_hour');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'esign_provider') THEN
    CREATE TYPE esign_provider AS ENUM ('docusign','hellosign','internal');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signer_role') THEN
    CREATE TYPE signer_role AS ENUM ('client','caterer','witness');
  END IF;
END$$;


-- ============================================================
-- UTILITY: updated_at trigger
-- ============================================================
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;


-- ============================================================
-- 1. USERS (minimal — just for FK references)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
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
CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);


-- ============================================================
-- 2. PROJECTS
-- ============================================================
CREATE TABLE IF NOT EXISTS projects (
  id                       UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_user_id            UUID           NOT NULL REFERENCES users(id),
  title                    TEXT           NOT NULL,
  event_date               DATE           NULL,
  event_end_date           DATE           NULL,
  guest_count              INT            NULL CHECK (guest_count > 0),
  status                   project_status NOT NULL DEFAULT 'draft',
  ai_event_summary         TEXT           NULL,
  created_via_ai_intake    BOOLEAN        NOT NULL DEFAULT false,
  ai_conversation_state_id UUID           NULL,
  signed_contract_id       UUID           NULL,
  created_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ    NOT NULL DEFAULT now(),
  deleted_at               TIMESTAMPTZ    NULL,
  deleted_by               UUID           NULL REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_projects_status_event ON projects (status, event_date);
CREATE INDEX IF NOT EXISTS ix_projects_owner ON projects (owner_user_id);


-- ============================================================
-- 3. THREADS
-- ============================================================
CREATE TABLE IF NOT EXISTS threads (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  subject          TEXT        NULL,
  created_by       UUID        NULL REFERENCES users(id),
  is_resolved      BOOLEAN     NOT NULL DEFAULT false,
  message_count    INT         NOT NULL DEFAULT 0 CHECK (message_count >= 0),
  last_activity_at TIMESTAMPTZ NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_threads_project_activity
  ON threads (project_id, last_activity_at DESC);


-- ============================================================
-- 4. AI CONVERSATION STATES
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_conversation_states (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id     UUID        NOT NULL UNIQUE REFERENCES threads(id) ON DELETE CASCADE,
  project_id    UUID        NULL REFERENCES projects(id) ON DELETE SET NULL,
  current_node  TEXT        NOT NULL DEFAULT 'start',
  slots         JSONB       NOT NULL DEFAULT '{}'::jsonb,
  is_completed  BOOLEAN     NOT NULL DEFAULT false,
  next_action   TEXT        NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_conv_states_project
  ON ai_conversation_states (project_id);
CREATE INDEX IF NOT EXISTS ix_ai_conv_states_active
  ON ai_conversation_states (is_completed) WHERE is_completed = false;

-- Deferred FK: projects.ai_conversation_state_id
ALTER TABLE projects
  ADD CONSTRAINT fk_projects_ai_conv_state
  FOREIGN KEY (ai_conversation_state_id)
  REFERENCES ai_conversation_states(id) ON DELETE SET NULL;


-- ============================================================
-- 5. MESSAGES
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
  id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id                UUID        NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  parent_message_id        UUID        NULL REFERENCES messages(id) ON DELETE SET NULL,
  project_id               UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  author_id                UUID        NULL REFERENCES users(id),
  sender_type              TEXT        NULL
                                       CHECK (sender_type IN ('user','ai','system')),
  content                  TEXT        NOT NULL,
  attachments              JSONB       NULL,
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
CREATE INDEX IF NOT EXISTS ix_messages_thread_created
  ON messages (thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_messages_active
  ON messages (thread_id, created_at) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS ix_messages_ai_conv_state
  ON messages (ai_conversation_state_id)
  WHERE ai_conversation_state_id IS NOT NULL;


-- ============================================================
-- 6. CONTRACTS
-- ============================================================
CREATE TABLE IF NOT EXISTS contracts (
  id                   UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_group_id    UUID            NOT NULL,
  version_number       INT             NOT NULL,
  previous_version_id  UUID            NULL REFERENCES contracts(id) ON DELETE SET NULL,
  project_id           UUID            NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  status               contract_status NOT NULL DEFAULT 'draft',
  title                TEXT            NULL,
  body                 JSONB           NOT NULL,
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
CREATE UNIQUE INDEX IF NOT EXISTS ux_contract_group_version
  ON contracts (contract_group_id, version_number);
CREATE INDEX IF NOT EXISTS ix_contracts_project_active
  ON contracts (project_id) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS ix_contracts_status ON contracts (status);

-- Deferred FK: projects.signed_contract_id
ALTER TABLE projects
  ADD CONSTRAINT fk_projects_signed_contract
  FOREIGN KEY (signed_contract_id)
  REFERENCES contracts(id) ON DELETE SET NULL;


-- ============================================================
-- 7. CONTRACT CLAUSES
-- ============================================================
CREATE TABLE IF NOT EXISTS contract_clauses (
  id                 UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id        UUID        NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  clause_template_id UUID        NULL,
  content            TEXT        NOT NULL,
  sort_order         INT         NOT NULL DEFAULT 0,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_contract_clauses_contract ON contract_clauses (contract_id);


-- ============================================================
-- 8. MENU CATEGORIES
-- ============================================================
CREATE TABLE IF NOT EXISTS menu_categories (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT        NOT NULL UNIQUE,
  sort_order INT         NOT NULL DEFAULT 0,
  active     BOOLEAN     NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ============================================================
-- 9. MENU ITEMS
-- ============================================================
CREATE TABLE IF NOT EXISTS menu_items (
  id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id      UUID          NULL REFERENCES menu_categories(id) ON DELETE SET NULL,
  name             TEXT          NOT NULL,
  description      TEXT          NULL,
  unit_cost        NUMERIC(10,2) NULL CHECK (unit_cost >= 0),
  unit_price       NUMERIC(10,2) NULL CHECK (unit_price >= 0),
  currency         CHAR(3)       NOT NULL DEFAULT 'USD'
                                 CHECK (currency ~ '^[A-Z]{3}$'),
  price_type       price_type    NULL,
  minimum_quantity INT           NOT NULL DEFAULT 1 CHECK (minimum_quantity > 0),
  allergens        TEXT[]        NULL,
  tags             TEXT[]        NULL,
  is_upsell        BOOLEAN       NOT NULL DEFAULT false,
  active           BOOLEAN       NOT NULL DEFAULT true,
  created_at       TIMESTAMPTZ   NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_menu_items_category ON menu_items (category_id);
CREATE INDEX IF NOT EXISTS ix_menu_items_active ON menu_items (active);
CREATE INDEX IF NOT EXISTS ix_menu_items_tags ON menu_items USING gin (tags);


-- ============================================================
-- 10. PRICING PACKAGES
-- ============================================================
CREATE TABLE IF NOT EXISTS pricing_packages (
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
CREATE INDEX IF NOT EXISTS ix_pricing_packages_active ON pricing_packages (active, priority DESC);


-- ============================================================
-- 11. AI GENERATIONS (audit log)
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_generations (
  id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type     ai_entity_type NOT NULL,
  entity_id       UUID           NULL,
  project_id      UUID           NULL REFERENCES projects(id) ON DELETE SET NULL,
  triggered_by    UUID           NULL REFERENCES users(id),
  model           TEXT           NOT NULL,
  prompt_version  TEXT           NULL,
  prompt_hash     TEXT           NULL,
  input_summary   JSONB          NULL,
  output          TEXT           NULL,
  output_tokens   INT            NULL CHECK (output_tokens >= 0),
  input_tokens    INT            NULL CHECK (input_tokens >= 0),
  latency_ms      INT            NULL CHECK (latency_ms >= 0),
  was_applied     BOOLEAN        NOT NULL DEFAULT false,
  feedback_rating INT            NULL CHECK (feedback_rating BETWEEN 1 AND 5),
  feedback_notes  TEXT           NULL,
  created_at      TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_ai_generations_entity ON ai_generations (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_ai_generations_project ON ai_generations (project_id);
CREATE INDEX IF NOT EXISTS ix_ai_generations_model ON ai_generations (model, created_at DESC);


-- ============================================================
-- TRIGGERS: updated_at
-- ============================================================
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


-- ============================================================
-- TRIGGERS: threads.message_count
-- ============================================================
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


-- ============================================================
-- SYSTEM USER (for FK references)
-- ============================================================
INSERT INTO users (id, email, status)
VALUES ('00000000-0000-0000-0000-000000000001', 'ai-system@flashbacklabs.com', 'active')
ON CONFLICT (email) DO NOTHING;


-- ============================================================
-- DONE
-- ============================================================

-- ========== AI Agent Test Database Schema ==========
-- Minimal schema for testing the AI agent in isolation
-- Only includes tables that the AI agent directly interacts with

-- ========== 1. Projects Table (minimal version) ==========
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    event_date TEXT NULL,
    guest_count INTEGER NULL,
    status TEXT DEFAULT 'draft',
    created_via_ai_intake INTEGER DEFAULT 0,
    ai_conversation_state_id TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX ix_projects_ai_intake ON projects (created_via_ai_intake) WHERE created_via_ai_intake = 1;

-- ========== 2. Threads Table ==========
CREATE TABLE threads (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    subject TEXT NULL,
    created_by TEXT NOT NULL,
    is_resolved INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    last_activity_at TEXT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX ix_threads_project ON threads (project_id);

-- ========== 3. Messages Table ==========
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    parent_message_id TEXT NULL,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL,
    sender_type TEXT NOT NULL,  -- 'client', 'staff', 'ai'
    content TEXT NOT NULL,
    attachments TEXT NULL,  -- JSON string
    ai_conversation_state_id TEXT NULL,
    is_deleted INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    last_edited_at TEXT NULL
);

CREATE INDEX ix_messages_thread ON messages (thread_id, created_at);
CREATE INDEX ix_messages_project ON messages (project_id);
CREATE INDEX ix_messages_ai_conversation ON messages (ai_conversation_state_id) WHERE ai_conversation_state_id IS NOT NULL;

-- ========== 4. Contracts Table (versioned — matches production schema) ==========
CREATE TABLE contracts (
    id TEXT PRIMARY KEY,
    contract_group_id TEXT NOT NULL,        -- group per logical contract
    version_number INTEGER NOT NULL,
    previous_version_id TEXT NULL REFERENCES contracts(id) ON DELETE SET NULL,
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status TEXT NOT NULL,                   -- draft | pending_client | signed | cancelled
    title TEXT NULL,
    body TEXT NOT NULL,                     -- JSON string (JSONB in production)
    pdf_path TEXT NULL,
    total_amount REAL NULL,
    change_reason TEXT NULL,
    metadata TEXT NULL,                     -- JSON string (JSONB in production)
    is_active INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL,
    approved_by_user_id TEXT NULL,
    seen_by_client_at TEXT NULL,
    sent_at TEXT NULL,
    client_signed_at TEXT NULL,
    expires_at TEXT NULL,
    ai_conversation_state_id TEXT NULL,
    created_at TEXT NOT NULL,
    deleted_at TEXT NULL,
    deleted_by TEXT NULL
);

CREATE UNIQUE INDEX ux_contract_group_version ON contracts (contract_group_id, version_number);
CREATE INDEX ix_contracts_project_active ON contracts (project_id) WHERE is_active = 1;
CREATE INDEX ix_contracts_status ON contracts (status);
CREATE INDEX ix_contracts_ai_conversation ON contracts (ai_conversation_state_id) WHERE ai_conversation_state_id IS NOT NULL;

-- ========== 5. AI Conversation States ==========
CREATE TABLE ai_conversation_states (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL UNIQUE REFERENCES threads(id) ON DELETE CASCADE,
    project_id TEXT NULL REFERENCES projects(id) ON DELETE CASCADE,
    current_node TEXT NOT NULL DEFAULT 'start',
    slots TEXT NOT NULL,  -- JSON string with slot data
    is_completed INTEGER DEFAULT 0,
    next_action TEXT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX ix_ai_conversation_states_thread ON ai_conversation_states (thread_id);
CREATE INDEX ix_ai_conversation_states_project ON ai_conversation_states (project_id);
CREATE INDEX ix_ai_conversation_states_completed ON ai_conversation_states (is_completed, updated_at DESC);

-- ========== Triggers ==========

-- Trigger to update thread message count
CREATE TRIGGER trg_update_thread_message_count_insert
AFTER INSERT ON messages
FOR EACH ROW
BEGIN
    UPDATE threads 
    SET message_count = message_count + 1,
        last_activity_at = NEW.created_at
    WHERE id = NEW.thread_id;
END;

CREATE TRIGGER trg_update_thread_message_count_delete
AFTER DELETE ON messages
FOR EACH ROW
BEGIN
    UPDATE threads 
    SET message_count = MAX(0, message_count - 1)
    WHERE id = OLD.thread_id;
END;

-- Trigger to update conversation state timestamp
CREATE TRIGGER trg_update_conversation_state_timestamp
BEFORE UPDATE ON ai_conversation_states
FOR EACH ROW
BEGIN
    SELECT datetime('now') INTO NEW.updated_at;
END;

-- ========== Summary ==========
-- This schema includes only the tables the AI agent touches:
-- 1. projects - AI creates projects from conversations
-- 2. threads - Each conversation is a thread
-- 3. messages - All chat messages (user + AI)
-- 4. contracts - AI generates contracts
-- 5. ai_conversation_states - Tracks slot-filling state

-- CreateEnum
CREATE TYPE "ai_entity_type" AS ENUM ('contract', 'proposal', 'clause', 'upsell', 'follow_up', 'staffing', 'portions', 'intake_parse', 'pricing', 'beo');

-- CreateEnum
CREATE TYPE "beo_status" AS ENUM ('draft', 'confirmed', 'in_production', 'completed', 'cancelled');

-- CreateEnum
CREATE TYPE "contract_status" AS ENUM ('draft', 'pending_staff_approval', 'rejected', 'approved', 'sent', 'signed', 'cancelled', 'expired', 'superseded');

-- CreateEnum
CREATE TYPE "esign_provider" AS ENUM ('docusign', 'hellosign', 'internal');

-- CreateEnum
CREATE TYPE "flag_severity" AS ENUM ('low', 'medium', 'high');

-- CreateEnum
CREATE TYPE "intake_status" AS ENUM ('received', 'parsing', 'parsed', 'mapped', 'failed');

-- CreateEnum
CREATE TYPE "notification_channel" AS ENUM ('email', 'sms', 'in_app');

-- CreateEnum
CREATE TYPE "owner_type" AS ENUM ('project', 'message', 'user', 'contract', 'pricing', 'other');

-- CreateEnum
CREATE TYPE "payment_status" AS ENUM ('pending', 'authorized', 'paid', 'failed', 'refunded', 'void');

-- CreateEnum
CREATE TYPE "price_type" AS ENUM ('per_person', 'flat', 'per_unit', 'per_hour');

-- CreateEnum
CREATE TYPE "project_status" AS ENUM ('draft', 'active', 'confirmed', 'completed', 'cancelled');

-- CreateEnum
CREATE TYPE "risk_flag_type" AS ENUM ('late_payment', 'chargeback', 'no_show', 'dispute', 'manual');

-- CreateEnum
CREATE TYPE "risk_level" AS ENUM ('low', 'normal', 'high', 'blocked');

-- CreateEnum
CREATE TYPE "scope_type" AS ENUM ('global', 'company', 'project');

-- CreateEnum
CREATE TYPE "service_style" AS ENUM ('buffet', 'plated', 'stations', 'cocktail', 'family_style', 'food_truck');

-- CreateEnum
CREATE TYPE "signer_role" AS ENUM ('client', 'caterer', 'witness');

-- CreateEnum
CREATE TYPE "source_type" AS ENUM ('manual', 'ai_suggested');

-- CreateEnum
CREATE TYPE "upsell_status" AS ENUM ('suggested', 'presented', 'accepted', 'declined');

-- CreateEnum
CREATE TYPE "virus_scan_status" AS ENUM ('pending', 'scanning', 'clean', 'infected', 'quarantined');

-- CreateEnum
CREATE TYPE "webhook_status" AS ENUM ('pending', 'processed', 'failed', 'duplicate');

-- CreateTable
CREATE TABLE "activity_log" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "actor_user_id" UUID,
    "actor_profile_id" UUID,
    "project_id" UUID,
    "action" TEXT NOT NULL,
    "payload" JSONB,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "activity_log_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_conversation_states" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "thread_id" UUID NOT NULL,
    "project_id" UUID,
    "current_node" TEXT NOT NULL DEFAULT 'start',
    "slots" JSONB NOT NULL DEFAULT '{}',
    "is_completed" BOOLEAN NOT NULL DEFAULT false,
    "next_action" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ai_conversation_states_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_generations" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "entity_type" "ai_entity_type" NOT NULL,
    "entity_id" UUID,
    "project_id" UUID,
    "triggered_by" UUID,
    "model" TEXT NOT NULL,
    "prompt_version" TEXT,
    "prompt_hash" TEXT,
    "input_summary" JSONB,
    "output" TEXT,
    "output_tokens" INTEGER,
    "input_tokens" INTEGER,
    "latency_ms" INTEGER,
    "was_applied" BOOLEAN NOT NULL DEFAULT false,
    "feedback_rating" INTEGER,
    "feedback_notes" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ai_generations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "api_keys" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "service_account_id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "key_hash" TEXT NOT NULL,
    "scopes" TEXT[] DEFAULT ARRAY[]::TEXT[],
    "expires_at" TIMESTAMPTZ(6),
    "revoked_at" TIMESTAMPTZ(6),
    "last_used_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "api_keys_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "attachments" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "owner_type" "owner_type" NOT NULL,
    "owner_id" UUID NOT NULL,
    "project_id" UUID,
    "filename" TEXT NOT NULL,
    "mime_type" TEXT,
    "size_bytes" BIGINT,
    "storage_provider" TEXT,
    "storage_path" TEXT,
    "checksum" TEXT,
    "virus_scan_status" "virus_scan_status" NOT NULL DEFAULT 'pending',
    "quarantine_reason" TEXT,
    "quarantined_at" TIMESTAMPTZ(6),
    "preview_allowed" BOOLEAN NOT NULL DEFAULT false,
    "uploaded_by" UUID,
    "uploaded_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "attachments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "auth_tokens" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "token_hash" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "expires_at" TIMESTAMPTZ(6) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "consumed_at" TIMESTAMPTZ(6),

    CONSTRAINT "auth_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "banquet_event_orders" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "contract_id" UUID,
    "beo_number" TEXT NOT NULL,
    "version_number" INTEGER NOT NULL DEFAULT 1,
    "status" "beo_status" NOT NULL DEFAULT 'draft',
    "event_date" DATE,
    "event_start_time" TIMETZ(6),
    "event_end_time" TIMETZ(6),
    "guest_count" INTEGER,
    "service_style" "service_style",
    "setup_notes" TEXT,
    "breakdown_notes" TEXT,
    "kitchen_notes" TEXT,
    "dietary_notes" TEXT,
    "timeline_notes" TEXT,
    "created_by" UUID,
    "confirmed_by" UUID,
    "confirmed_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "banquet_event_orders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "beo_line_items" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "beo_id" UUID NOT NULL,
    "order_item_id" UUID,
    "item_name" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL,
    "unit" TEXT,
    "prep_notes" TEXT,
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "beo_line_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "beo_staff_assignments" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "beo_id" UUID NOT NULL,
    "role" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "start_time" TIMETZ(6),
    "end_time" TIMETZ(6),
    "notes" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "beo_staff_assignments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "change_order_lines" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "change_order_id" UUID NOT NULL,
    "description" TEXT NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "change_order_lines_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "change_orders" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "contract_id" UUID,
    "created_by" UUID,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "metadata" JSONB,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "change_orders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clause_rules" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "clause_template_id" UUID NOT NULL,
    "condition" JSONB NOT NULL,
    "priority" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "clause_rules_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clause_templates" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "last_reviewed_at" TIMESTAMPTZ(6),
    "tags" TEXT[],
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "clause_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "client_risk_flags" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "project_id" UUID,
    "flag_type" "risk_flag_type" NOT NULL,
    "severity" "flag_severity" NOT NULL DEFAULT 'medium',
    "notes" TEXT,
    "flagged_by" UUID,
    "resolved_at" TIMESTAMPTZ(6),
    "resolved_by" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "client_risk_flags_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "contract_clauses" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "contract_id" UUID NOT NULL,
    "clause_template_id" UUID,
    "content" TEXT NOT NULL,
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "contract_clauses_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "contract_signatures" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "contract_id" UUID NOT NULL,
    "esign_provider" "esign_provider" NOT NULL,
    "envelope_id" TEXT,
    "signer_user_id" UUID,
    "signer_email" TEXT NOT NULL,
    "signer_name" TEXT,
    "signer_role" "signer_role" NOT NULL,
    "ip_address" TEXT,
    "user_agent" TEXT,
    "signed_at" TIMESTAMPTZ(6),
    "declined_at" TIMESTAMPTZ(6),
    "decline_reason" TEXT,
    "audit_trail" JSONB,
    "certificate_url" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "contract_signatures_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "contracts" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "contract_group_id" UUID NOT NULL,
    "version_number" INTEGER NOT NULL,
    "previous_version_id" UUID,
    "project_id" UUID NOT NULL,
    "status" "contract_status" NOT NULL DEFAULT 'draft',
    "title" TEXT,
    "body" JSONB NOT NULL,
    "pdf_path" TEXT,
    "total_amount" DECIMAL(12,2),
    "change_reason" TEXT,
    "metadata" JSONB,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "ai_generated" BOOLEAN NOT NULL DEFAULT false,
    "esign_provider" "esign_provider",
    "esign_envelope_id" TEXT,
    "created_by" UUID NOT NULL,
    "approved_by_user_id" UUID,
    "seen_by_client_at" TIMESTAMPTZ(6),
    "sent_at" TIMESTAMPTZ(6),
    "client_signed_at" TIMESTAMPTZ(6),
    "expires_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMPTZ(6),
    "deleted_by" UUID,

    CONSTRAINT "contracts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "cost_of_goods" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_pricing_id" UUID NOT NULL,
    "line_item" JSONB NOT NULL,
    "cost_amount" DECIMAL(12,2) NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "cost_of_goods_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "crm_pipeline" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "assigned_staff_user_id" UUID,
    "pipeline_stage" TEXT,
    "lead_source" TEXT,
    "lead_score" INTEGER,
    "risk_level" "risk_level" NOT NULL DEFAULT 'normal',
    "risk_flags" TEXT[],
    "risk_reviewed_at" TIMESTAMPTZ(6),
    "follow_up_at" TIMESTAMPTZ(6),
    "lost_reason" TEXT,
    "notes" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "crm_pipeline_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "event_analytics" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "profit" DECIMAL(12,2),
    "revenue" DECIMAL(12,2),
    "costs" DECIMAL(12,2),
    "margin_pct" DECIMAL(5,2),
    "calculated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "event_analytics_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "event_timeline_items" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "scheduled_at" TIMESTAMPTZ(6),
    "completed_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "event_timeline_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "events" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID,
    "event_type" TEXT NOT NULL,
    "actor_id" UUID,
    "payload" JSONB,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "events_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "follow_ups" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "template_key" TEXT,
    "scheduled_at" TIMESTAMPTZ(6),
    "sent_at" TIMESTAMPTZ(6),
    "status" TEXT NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "follow_ups_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "intake_form_templates" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "description" TEXT,
    "fields" JSONB NOT NULL DEFAULT '[]',
    "is_default" BOOLEAN NOT NULL DEFAULT false,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_by" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "intake_form_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "intake_submissions" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "form_template_id" UUID,
    "project_id" UUID,
    "raw_answers" JSONB NOT NULL DEFAULT '{}',
    "ai_parsed_output" JSONB,
    "ai_confidence_score" DECIMAL(4,3),
    "missing_fields" TEXT[],
    "upsell_triggers" TEXT[],
    "status" "intake_status" NOT NULL DEFAULT 'received',
    "submitted_by_email" TEXT,
    "submitted_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "parsed_at" TIMESTAMPTZ(6),
    "mapped_at" TIMESTAMPTZ(6),

    CONSTRAINT "intake_submissions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "margin_alerts" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "threshold" DECIMAL(5,2) NOT NULL,
    "current_margin" DECIMAL(5,2),
    "triggered_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolved_at" TIMESTAMPTZ(6),

    CONSTRAINT "margin_alerts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "menu_categories" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "menu_categories_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "menu_items" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "category_id" UUID,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "unit_cost" DECIMAL(10,2),
    "unit_price" DECIMAL(10,2),
    "currency" CHAR(3) NOT NULL DEFAULT 'USD',
    "price_type" "price_type",
    "minimum_quantity" INTEGER NOT NULL DEFAULT 1,
    "allergens" TEXT[],
    "tags" TEXT[],
    "is_upsell" BOOLEAN NOT NULL DEFAULT false,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "menu_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "message_mentions" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "message_id" UUID NOT NULL,
    "mentioned_user_id" UUID NOT NULL,
    "mention_type" TEXT NOT NULL DEFAULT 'direct',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "message_mentions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "messages" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "thread_id" UUID NOT NULL,
    "parent_message_id" UUID,
    "project_id" UUID NOT NULL,
    "author_id" UUID,
    "sender_type" TEXT,
    "content" TEXT NOT NULL,
    "attachments" JSONB,
    "ai_conversation_state_id" UUID,
    "qdrant_vector_id" TEXT,
    "vector_indexed_at" TIMESTAMPTZ(6),
    "vector_status" TEXT NOT NULL DEFAULT 'pending',
    "is_deleted" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_edited_at" TIMESTAMPTZ(6),

    CONSTRAINT "messages_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "notification_templates" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "key" TEXT NOT NULL,
    "channel" "notification_channel" NOT NULL,
    "subject" TEXT,
    "body" TEXT NOT NULL,
    "variables" TEXT[],
    "version" INTEGER NOT NULL DEFAULT 1,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "notification_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "notifications" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "event_id" UUID,
    "recipient_user_id" UUID,
    "channel" "notification_channel" NOT NULL,
    "template_key" TEXT,
    "payload" JSONB,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "attempt_count" INTEGER NOT NULL DEFAULT 0,
    "last_attempt_at" TIMESTAMPTZ(6),
    "sent_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_read" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "notifications_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "oauth_accounts" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "provider" TEXT NOT NULL,
    "provider_account_id" TEXT NOT NULL,
    "access_token" TEXT,
    "refresh_token_encrypted" TEXT,
    "raw_profile" JSONB,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "oauth_accounts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "order_items" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "menu_item_id" UUID,
    "item_name_snapshot" TEXT NOT NULL,
    "price_snapshot" DECIMAL(10,2) NOT NULL,
    "unit_cost_snapshot" DECIMAL(10,2),
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "price_type" "price_type",
    "notes" TEXT,
    "added_by_user_id" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "order_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payment_requests" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "client_id" UUID,
    "idempotency_key" TEXT NOT NULL,
    "request_hash" TEXT,
    "payment_id" UUID,
    "gateway_txn_id" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payment_requests_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payment_schedule_items" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "schedule_id" UUID NOT NULL,
    "label" TEXT,
    "amount" DECIMAL(12,2) NOT NULL,
    "due_date" DATE,
    "status" "payment_status" NOT NULL DEFAULT 'pending',
    "gateway_payment_intent_id" TEXT,
    "paid_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payment_schedule_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payment_schedules" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "installment_type" TEXT,
    "total_amount" DECIMAL(12,2),
    "due_date" DATE,
    "reminder_sent_at" TIMESTAMPTZ(6),
    "auto_charge" BOOLEAN NOT NULL DEFAULT false,
    "status" TEXT NOT NULL DEFAULT 'scheduled',
    "created_by_user_id" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payment_schedules_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payments" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID,
    "payment_schedule_id" UUID,
    "schedule_item_id" UUID,
    "payment_request_id" UUID,
    "gateway_payment_intent_id" TEXT,
    "gateway_customer_id" TEXT,
    "type" TEXT,
    "amount" DECIMAL(12,2) NOT NULL,
    "currency" CHAR(3) NOT NULL DEFAULT 'USD',
    "status" "payment_status" NOT NULL DEFAULT 'pending',
    "paid_at" TIMESTAMPTZ(6),
    "idempotency_key" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMPTZ(6),
    "deleted_by" UUID,

    CONSTRAINT "payments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "pricing_packages" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "description" TEXT,
    "category" TEXT,
    "base_price" DECIMAL(12,2),
    "currency" CHAR(3) NOT NULL DEFAULT 'USD',
    "price_type" "price_type",
    "valid_from" DATE,
    "valid_to" DATE,
    "priority" INTEGER NOT NULL DEFAULT 0,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "pricing_packages_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_collaborators" (
    "project_id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "role" TEXT,
    "added_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "added_by" UUID,

    CONSTRAINT "project_collaborators_pkey" PRIMARY KEY ("project_id","user_id")
);

-- CreateTable
CREATE TABLE "project_portion_estimates" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "menu_item_id" UUID,
    "item_name" TEXT NOT NULL,
    "guest_count" INTEGER NOT NULL,
    "quantity" DECIMAL(10,3) NOT NULL,
    "unit" TEXT,
    "waste_factor" DECIMAL(4,3) NOT NULL DEFAULT 0.10,
    "source" "source_type" NOT NULL DEFAULT 'manual',
    "ai_generation_id" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "project_portion_estimates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_pricing" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "source_pricing_package_id" UUID,
    "snapshot_name" TEXT,
    "snapshot_base_price" DECIMAL(12,2),
    "snapshot_currency" CHAR(3),
    "guest_count_snapshot" INTEGER,
    "line_items" JSONB,
    "subtotal" DECIMAL(12,2),
    "tax" DECIMAL(12,2),
    "service_charge" DECIMAL(12,2),
    "admin_fee" DECIMAL(12,2),
    "negotiated_adjustment" DECIMAL(12,2),
    "final_total" DECIMAL(12,2),
    "status" TEXT NOT NULL DEFAULT 'calculated',
    "ai_generated" BOOLEAN NOT NULL DEFAULT false,
    "ai_generation_id" UUID,
    "approved_by_user_id" UUID,
    "approved_at" TIMESTAMPTZ(6),
    "copied_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "project_pricing_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_staff_requirements" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "role" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "hours_estimated" DECIMAL(5,2),
    "rate_per_hour" DECIMAL(10,2),
    "total_cost" DECIMAL(10,2),
    "notes" TEXT,
    "source" "source_type" NOT NULL DEFAULT 'manual',
    "ai_generation_id" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "project_staff_requirements_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_upsell_items" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "menu_item_id" UUID,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "estimated_revenue" DECIMAL(10,2),
    "status" "upsell_status" NOT NULL DEFAULT 'suggested',
    "presented_at" TIMESTAMPTZ(6),
    "responded_at" TIMESTAMPTZ(6),
    "source" "source_type" NOT NULL DEFAULT 'ai_suggested',
    "ai_generation_id" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "project_upsell_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "projects" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "owner_user_id" UUID NOT NULL,
    "venue_id" UUID,
    "title" TEXT NOT NULL,
    "event_date" DATE,
    "event_end_date" DATE,
    "guest_count" INTEGER,
    "status" "project_status" NOT NULL DEFAULT 'draft',
    "ai_event_summary" TEXT,
    "created_via_ai_intake" BOOLEAN NOT NULL DEFAULT false,
    "ai_conversation_state_id" UUID,
    "signed_contract_id" UUID,
    "auto_lock_at" TIMESTAMPTZ(6),
    "locked_at" TIMESTAMPTZ(6),
    "locked_reason" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMPTZ(6),
    "deleted_by" UUID,

    CONSTRAINT "projects_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "refresh_tokens" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "session_id" UUID NOT NULL,
    "token_hash" TEXT NOT NULL,
    "issued_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "used_at" TIMESTAMPTZ(6),
    "revoked_at" TIMESTAMPTZ(6),
    "replaced_by_refresh_token_id" UUID,

    CONSTRAINT "refresh_tokens_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "role_permissions" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "role_id" TEXT NOT NULL,
    "permission" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "role_permissions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "roles" (
    "id" TEXT NOT NULL,
    "description" TEXT,
    "domain" TEXT,

    CONSTRAINT "roles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "service_accounts" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "owner_user_id" UUID NOT NULL,
    "metadata" JSONB,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "service_accounts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "sessions" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "session_token_hash" TEXT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_active_at" TIMESTAMPTZ(6),
    "expires_at" TIMESTAMPTZ(6) NOT NULL,
    "device_info" JSONB,
    "ip_address" TEXT,
    "revoked_at" TIMESTAMPTZ(6),

    CONSTRAINT "sessions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "threads" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "subject" TEXT,
    "created_by" UUID,
    "is_resolved" BOOLEAN NOT NULL DEFAULT false,
    "message_count" INTEGER NOT NULL DEFAULT 0,
    "last_activity_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "threads_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "user_profiles" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "profile_type" TEXT NOT NULL,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "user_profiles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "user_roles" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "user_id" UUID NOT NULL,
    "role_id" TEXT NOT NULL,
    "scope_type" "scope_type" NOT NULL,
    "scope_id" UUID,
    "granted_by" UUID,
    "granted_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "user_roles_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "users" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "email" TEXT NOT NULL,
    "password_hash" TEXT,
    "primary_phone" TEXT,
    "status" TEXT NOT NULL DEFAULT 'active',
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deleted_at" TIMESTAMPTZ(6),
    "deleted_by" UUID,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "venue_clause_overrides" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "venue_id" UUID NOT NULL,
    "clause_template_id" UUID NOT NULL,
    "override_content" TEXT,
    "is_mandatory" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "venue_clause_overrides_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "venues" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "address" TEXT,
    "city" TEXT,
    "state" TEXT,
    "country" CHAR(2) NOT NULL DEFAULT 'US',
    "contact_name" TEXT,
    "contact_email" TEXT,
    "contact_phone" TEXT,
    "capacity_min" INTEGER,
    "capacity_max" INTEGER,
    "notes" TEXT,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "venues_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "webhook_events" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "provider" TEXT NOT NULL,
    "external_event_id" TEXT NOT NULL,
    "event_type" TEXT,
    "payload" JSONB,
    "idempotency_hash" TEXT,
    "received_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "processed_at" TIMESTAMPTZ(6),
    "status" "webhook_status" NOT NULL DEFAULT 'pending',
    "attempt_count" INTEGER NOT NULL DEFAULT 0,
    "last_attempt_at" TIMESTAMPTZ(6),
    "next_attempt_at" TIMESTAMPTZ(6),
    "last_response_code" INTEGER,
    "last_response_body" TEXT,
    "error" TEXT,

    CONSTRAINT "webhook_events_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ix_activity_log_actor" ON "activity_log"("actor_user_id", "created_at" DESC);

-- CreateIndex
CREATE INDEX "ix_activity_log_project" ON "activity_log"("project_id");

-- CreateIndex
CREATE UNIQUE INDEX "ai_conversation_states_thread_id_key" ON "ai_conversation_states"("thread_id");

-- CreateIndex
CREATE INDEX "ix_ai_conv_states_completed" ON "ai_conversation_states"("is_completed", "updated_at" DESC);

-- CreateIndex
CREATE INDEX "ix_ai_conv_states_project" ON "ai_conversation_states"("project_id");

-- CreateIndex
CREATE INDEX "ix_ai_generations_applied" ON "ai_generations"("was_applied", "entity_type");

-- CreateIndex
CREATE INDEX "ix_ai_generations_entity" ON "ai_generations"("entity_type", "entity_id");

-- CreateIndex
CREATE INDEX "ix_ai_generations_model" ON "ai_generations"("model", "created_at" DESC);

-- CreateIndex
CREATE INDEX "ix_ai_generations_project" ON "ai_generations"("project_id");

-- CreateIndex
CREATE UNIQUE INDEX "api_keys_key_hash_key" ON "api_keys"("key_hash");

-- CreateIndex
CREATE INDEX "ix_api_keys_service" ON "api_keys"("service_account_id");

-- CreateIndex
CREATE INDEX "ix_attachments_owner" ON "attachments"("owner_type", "owner_id");

-- CreateIndex
CREATE UNIQUE INDEX "auth_tokens_token_hash_key" ON "auth_tokens"("token_hash");

-- CreateIndex
CREATE INDEX "ix_auth_tokens_user" ON "auth_tokens"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "ux_beo_number" ON "banquet_event_orders"("beo_number");

-- CreateIndex
CREATE INDEX "ix_beo_event_date" ON "banquet_event_orders"("event_date");

-- CreateIndex
CREATE INDEX "ix_beo_project" ON "banquet_event_orders"("project_id");

-- CreateIndex
CREATE INDEX "ix_beo_status" ON "banquet_event_orders"("status");

-- CreateIndex
CREATE INDEX "ix_beo_line_items_beo" ON "beo_line_items"("beo_id");

-- CreateIndex
CREATE INDEX "ix_beo_staff_beo" ON "beo_staff_assignments"("beo_id");

-- CreateIndex
CREATE INDEX "ix_change_order_lines_order" ON "change_order_lines"("change_order_id");

-- CreateIndex
CREATE INDEX "ix_change_orders_project" ON "change_orders"("project_id");

-- CreateIndex
CREATE INDEX "ix_clause_rules_template" ON "clause_rules"("clause_template_id");

-- CreateIndex
CREATE INDEX "ix_clause_templates_name" ON "clause_templates"("name");

-- CreateIndex
CREATE INDEX "ix_clause_templates_tags" ON "clause_templates" USING GIN ("tags");

-- CreateIndex
CREATE INDEX "ix_client_risk_flags_project" ON "client_risk_flags"("project_id");

-- CreateIndex
CREATE INDEX "ix_client_risk_flags_user" ON "client_risk_flags"("user_id");

-- CreateIndex
CREATE INDEX "ix_contract_clauses_contract" ON "contract_clauses"("contract_id");

-- CreateIndex
CREATE INDEX "ix_contract_signatures_contract" ON "contract_signatures"("contract_id");

-- CreateIndex
CREATE INDEX "ix_contract_signatures_envelope" ON "contract_signatures"("envelope_id");

-- CreateIndex
CREATE INDEX "ix_contracts_status" ON "contracts"("status");

-- CreateIndex
CREATE UNIQUE INDEX "ux_contract_group_version" ON "contracts"("contract_group_id", "version_number");

-- CreateIndex
CREATE INDEX "ix_cogs_pricing" ON "cost_of_goods"("project_pricing_id");

-- CreateIndex
CREATE UNIQUE INDEX "crm_pipeline_project_id_key" ON "crm_pipeline"("project_id");

-- CreateIndex
CREATE INDEX "ix_crm_pipeline_stage" ON "crm_pipeline"("pipeline_stage");

-- CreateIndex
CREATE INDEX "ix_event_analytics_project" ON "event_analytics"("project_id");

-- CreateIndex
CREATE INDEX "ix_timeline_project_sched" ON "event_timeline_items"("project_id", "scheduled_at");

-- CreateIndex
CREATE INDEX "ix_events_actor" ON "events"("actor_id");

-- CreateIndex
CREATE INDEX "ix_events_project_type" ON "events"("project_id", "event_type");

-- CreateIndex
CREATE INDEX "ix_follow_ups_project" ON "follow_ups"("project_id");

-- CreateIndex
CREATE INDEX "ix_intake_submissions_project" ON "intake_submissions"("project_id");

-- CreateIndex
CREATE INDEX "ix_intake_submissions_status" ON "intake_submissions"("status");

-- CreateIndex
CREATE INDEX "ix_margin_alerts_project" ON "margin_alerts"("project_id");

-- CreateIndex
CREATE UNIQUE INDEX "menu_categories_name_key" ON "menu_categories"("name");

-- CreateIndex
CREATE INDEX "ix_menu_items_active" ON "menu_items"("active");

-- CreateIndex
CREATE INDEX "ix_menu_items_category" ON "menu_items"("category_id");

-- CreateIndex
CREATE INDEX "ix_menu_items_tags" ON "menu_items" USING GIN ("tags");

-- CreateIndex
CREATE INDEX "ix_message_mentions_message" ON "message_mentions"("message_id");

-- CreateIndex
CREATE INDEX "ix_message_mentions_user" ON "message_mentions"("mentioned_user_id");

-- CreateIndex
CREATE INDEX "ix_messages_thread_created" ON "messages"("thread_id", "created_at" DESC);

-- CreateIndex
CREATE UNIQUE INDEX "notification_templates_key_key" ON "notification_templates"("key");

-- CreateIndex
CREATE INDEX "ix_notification_templates_channel" ON "notification_templates"("channel");

-- CreateIndex
CREATE INDEX "ix_notifications_recipient" ON "notifications"("recipient_user_id", "is_read");

-- CreateIndex
CREATE UNIQUE INDEX "oauth_accounts_provider_provider_account_id_key" ON "oauth_accounts"("provider", "provider_account_id");

-- CreateIndex
CREATE INDEX "ix_order_items_project" ON "order_items"("project_id");

-- CreateIndex
CREATE UNIQUE INDEX "ux_payment_requests_client_key" ON "payment_requests"("client_id", "idempotency_key");

-- CreateIndex
CREATE INDEX "ix_schedule_items_schedule_due" ON "payment_schedule_items"("schedule_id", "due_date");

-- CreateIndex
CREATE INDEX "ix_payment_schedules_project_due" ON "payment_schedules"("project_id", "due_date");

-- CreateIndex
CREATE INDEX "ix_payments_project_status" ON "payments"("project_id", "status");

-- CreateIndex
CREATE INDEX "ix_pricing_packages_active" ON "pricing_packages"("active", "priority" DESC);

-- CreateIndex
CREATE INDEX "ix_proj_portions_project" ON "project_portion_estimates"("project_id");

-- CreateIndex
CREATE INDEX "ix_project_pricing_gin" ON "project_pricing" USING GIN ("line_items");

-- CreateIndex
CREATE INDEX "ix_project_pricing_project" ON "project_pricing"("project_id");

-- CreateIndex
CREATE INDEX "ix_proj_staff_project" ON "project_staff_requirements"("project_id");

-- CreateIndex
CREATE INDEX "ix_proj_upsells_project" ON "project_upsell_items"("project_id");

-- CreateIndex
CREATE INDEX "ix_proj_upsells_status" ON "project_upsell_items"("status");

-- CreateIndex
CREATE INDEX "ix_projects_owner" ON "projects"("owner_user_id");

-- CreateIndex
CREATE INDEX "ix_projects_status_event" ON "projects"("status", "event_date");

-- CreateIndex
CREATE INDEX "ix_projects_venue" ON "projects"("venue_id");

-- CreateIndex
CREATE UNIQUE INDEX "refresh_tokens_token_hash_key" ON "refresh_tokens"("token_hash");

-- CreateIndex
CREATE INDEX "ix_refresh_tokens_session" ON "refresh_tokens"("session_id");

-- CreateIndex
CREATE UNIQUE INDEX "role_permissions_role_id_permission_key" ON "role_permissions"("role_id", "permission");

-- CreateIndex
CREATE INDEX "ix_threads_project_activity" ON "threads"("project_id", "last_activity_at" DESC);

-- CreateIndex
CREATE INDEX "ix_user_profiles_type" ON "user_profiles"("profile_type");

-- CreateIndex
CREATE INDEX "ix_user_profiles_user" ON "user_profiles"("user_id");

-- CreateIndex
CREATE INDEX "ix_user_roles_role" ON "user_roles"("role_id");

-- CreateIndex
CREATE INDEX "ix_user_roles_user" ON "user_roles"("user_id");

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE INDEX "ix_users_email" ON "users"("email");

-- CreateIndex
CREATE INDEX "ix_users_status_created" ON "users"("status", "created_at");

-- CreateIndex
CREATE UNIQUE INDEX "venue_clause_overrides_venue_id_clause_template_id_key" ON "venue_clause_overrides"("venue_id", "clause_template_id");

-- CreateIndex
CREATE INDEX "ix_venues_active" ON "venues"("active");

-- CreateIndex
CREATE INDEX "ix_venues_city" ON "venues"("city");

-- CreateIndex
CREATE INDEX "ix_webhook_idempotency_hash" ON "webhook_events"("idempotency_hash");

-- CreateIndex
CREATE UNIQUE INDEX "ux_webhook_provider_event" ON "webhook_events"("provider", "external_event_id");

-- AddForeignKey
ALTER TABLE "activity_log" ADD CONSTRAINT "activity_log_actor_user_id_fkey" FOREIGN KEY ("actor_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "activity_log" ADD CONSTRAINT "activity_log_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "ai_conversation_states" ADD CONSTRAINT "ai_conversation_states_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "ai_conversation_states" ADD CONSTRAINT "ai_conversation_states_thread_id_fkey" FOREIGN KEY ("thread_id") REFERENCES "threads"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "ai_generations" ADD CONSTRAINT "ai_generations_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "ai_generations" ADD CONSTRAINT "ai_generations_triggered_by_fkey" FOREIGN KEY ("triggered_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "api_keys" ADD CONSTRAINT "api_keys_service_account_id_fkey" FOREIGN KEY ("service_account_id") REFERENCES "service_accounts"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "attachments" ADD CONSTRAINT "attachments_uploaded_by_fkey" FOREIGN KEY ("uploaded_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "auth_tokens" ADD CONSTRAINT "auth_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_confirmed_by_fkey" FOREIGN KEY ("confirmed_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "contracts"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "beo_line_items" ADD CONSTRAINT "beo_line_items_beo_id_fkey" FOREIGN KEY ("beo_id") REFERENCES "banquet_event_orders"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "beo_line_items" ADD CONSTRAINT "beo_line_items_order_item_id_fkey" FOREIGN KEY ("order_item_id") REFERENCES "order_items"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "beo_staff_assignments" ADD CONSTRAINT "beo_staff_assignments_beo_id_fkey" FOREIGN KEY ("beo_id") REFERENCES "banquet_event_orders"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "change_order_lines" ADD CONSTRAINT "change_order_lines_change_order_id_fkey" FOREIGN KEY ("change_order_id") REFERENCES "change_orders"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "change_orders" ADD CONSTRAINT "change_orders_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "contracts"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "change_orders" ADD CONSTRAINT "change_orders_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "change_orders" ADD CONSTRAINT "change_orders_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "clause_rules" ADD CONSTRAINT "clause_rules_clause_template_id_fkey" FOREIGN KEY ("clause_template_id") REFERENCES "clause_templates"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_flagged_by_fkey" FOREIGN KEY ("flagged_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_resolved_by_fkey" FOREIGN KEY ("resolved_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contract_clauses" ADD CONSTRAINT "contract_clauses_clause_template_id_fkey" FOREIGN KEY ("clause_template_id") REFERENCES "clause_templates"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contract_clauses" ADD CONSTRAINT "contract_clauses_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "contracts"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contract_signatures" ADD CONSTRAINT "contract_signatures_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "contracts"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contract_signatures" ADD CONSTRAINT "contract_signatures_signer_user_id_fkey" FOREIGN KEY ("signer_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_approved_by_user_id_fkey" FOREIGN KEY ("approved_by_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_deleted_by_fkey" FOREIGN KEY ("deleted_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_previous_version_id_fkey" FOREIGN KEY ("previous_version_id") REFERENCES "contracts"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "cost_of_goods" ADD CONSTRAINT "cost_of_goods_project_pricing_id_fkey" FOREIGN KEY ("project_pricing_id") REFERENCES "project_pricing"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "crm_pipeline" ADD CONSTRAINT "crm_pipeline_assigned_staff_user_id_fkey" FOREIGN KEY ("assigned_staff_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "crm_pipeline" ADD CONSTRAINT "crm_pipeline_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "event_analytics" ADD CONSTRAINT "event_analytics_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "event_timeline_items" ADD CONSTRAINT "event_timeline_items_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "events" ADD CONSTRAINT "events_actor_id_fkey" FOREIGN KEY ("actor_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "events" ADD CONSTRAINT "events_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "follow_ups" ADD CONSTRAINT "follow_ups_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "follow_ups" ADD CONSTRAINT "follow_ups_template_key_fkey" FOREIGN KEY ("template_key") REFERENCES "notification_templates"("key") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "intake_form_templates" ADD CONSTRAINT "intake_form_templates_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "intake_submissions" ADD CONSTRAINT "intake_submissions_form_template_id_fkey" FOREIGN KEY ("form_template_id") REFERENCES "intake_form_templates"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "intake_submissions" ADD CONSTRAINT "intake_submissions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "margin_alerts" ADD CONSTRAINT "margin_alerts_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "menu_items" ADD CONSTRAINT "menu_items_category_id_fkey" FOREIGN KEY ("category_id") REFERENCES "menu_categories"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "message_mentions" ADD CONSTRAINT "message_mentions_mentioned_user_id_fkey" FOREIGN KEY ("mentioned_user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "message_mentions" ADD CONSTRAINT "message_mentions_message_id_fkey" FOREIGN KEY ("message_id") REFERENCES "messages"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_ai_conversation_state_id_fkey" FOREIGN KEY ("ai_conversation_state_id") REFERENCES "ai_conversation_states"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_parent_message_id_fkey" FOREIGN KEY ("parent_message_id") REFERENCES "messages"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_thread_id_fkey" FOREIGN KEY ("thread_id") REFERENCES "threads"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "events"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_recipient_user_id_fkey" FOREIGN KEY ("recipient_user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_template_key_fkey" FOREIGN KEY ("template_key") REFERENCES "notification_templates"("key") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "oauth_accounts" ADD CONSTRAINT "oauth_accounts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_added_by_user_id_fkey" FOREIGN KEY ("added_by_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_menu_item_id_fkey" FOREIGN KEY ("menu_item_id") REFERENCES "menu_items"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payment_requests" ADD CONSTRAINT "payment_requests_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payment_schedule_items" ADD CONSTRAINT "payment_schedule_items_schedule_id_fkey" FOREIGN KEY ("schedule_id") REFERENCES "payment_schedules"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payment_schedules" ADD CONSTRAINT "payment_schedules_created_by_user_id_fkey" FOREIGN KEY ("created_by_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payment_schedules" ADD CONSTRAINT "payment_schedules_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "fk_payments_schedule" FOREIGN KEY ("payment_schedule_id") REFERENCES "payment_schedules"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "fk_payments_schedule_item" FOREIGN KEY ("schedule_item_id") REFERENCES "payment_schedule_items"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "payments_deleted_by_fkey" FOREIGN KEY ("deleted_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "payments_payment_request_id_fkey" FOREIGN KEY ("payment_request_id") REFERENCES "payment_requests"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "payments_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_collaborators" ADD CONSTRAINT "project_collaborators_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_collaborators" ADD CONSTRAINT "project_collaborators_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_portion_estimates" ADD CONSTRAINT "project_portion_estimates_ai_generation_id_fkey" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_portion_estimates" ADD CONSTRAINT "project_portion_estimates_menu_item_id_fkey" FOREIGN KEY ("menu_item_id") REFERENCES "menu_items"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_portion_estimates" ADD CONSTRAINT "project_portion_estimates_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_pricing" ADD CONSTRAINT "fk_project_pricing_ai_gen" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_pricing" ADD CONSTRAINT "project_pricing_approved_by_user_id_fkey" FOREIGN KEY ("approved_by_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_pricing" ADD CONSTRAINT "project_pricing_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_pricing" ADD CONSTRAINT "project_pricing_source_pricing_package_id_fkey" FOREIGN KEY ("source_pricing_package_id") REFERENCES "pricing_packages"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_staff_requirements" ADD CONSTRAINT "project_staff_requirements_ai_generation_id_fkey" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_staff_requirements" ADD CONSTRAINT "project_staff_requirements_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_upsell_items" ADD CONSTRAINT "project_upsell_items_ai_generation_id_fkey" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_upsell_items" ADD CONSTRAINT "project_upsell_items_menu_item_id_fkey" FOREIGN KEY ("menu_item_id") REFERENCES "menu_items"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_upsell_items" ADD CONSTRAINT "project_upsell_items_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "fk_projects_ai_conv_state" FOREIGN KEY ("ai_conversation_state_id") REFERENCES "ai_conversation_states"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "fk_projects_signed_contract" FOREIGN KEY ("signed_contract_id") REFERENCES "contracts"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "projects_deleted_by_fkey" FOREIGN KEY ("deleted_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "projects_owner_user_id_fkey" FOREIGN KEY ("owner_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "projects_venue_id_fkey" FOREIGN KEY ("venue_id") REFERENCES "venues"("id") ON DELETE SET NULL ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_replaced_by_refresh_token_id_fkey" FOREIGN KEY ("replaced_by_refresh_token_id") REFERENCES "refresh_tokens"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "refresh_tokens" ADD CONSTRAINT "refresh_tokens_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "sessions"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "role_permissions" ADD CONSTRAINT "role_permissions_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "service_accounts" ADD CONSTRAINT "service_accounts_owner_user_id_fkey" FOREIGN KEY ("owner_user_id") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "threads" ADD CONSTRAINT "threads_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "threads" ADD CONSTRAINT "threads_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "user_profiles" ADD CONSTRAINT "user_profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_granted_by_fkey" FOREIGN KEY ("granted_by") REFERENCES "users"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_role_id_fkey" FOREIGN KEY ("role_id") REFERENCES "roles"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "user_roles" ADD CONSTRAINT "user_roles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "venue_clause_overrides" ADD CONSTRAINT "venue_clause_overrides_clause_template_id_fkey" FOREIGN KEY ("clause_template_id") REFERENCES "clause_templates"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "venue_clause_overrides" ADD CONSTRAINT "venue_clause_overrides_venue_id_fkey" FOREIGN KEY ("venue_id") REFERENCES "venues"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

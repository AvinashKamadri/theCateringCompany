-- CreateTable
CREATE TABLE "users" (
    "id" UUID NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT,
    "phone" TEXT,
    "role" TEXT NOT NULL DEFAULT 'client',
    "active" BOOLEAN NOT NULL DEFAULT true,
    "metadata" JSONB NOT NULL DEFAULT '{}',
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "users_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "projects" (
    "id" UUID NOT NULL,
    "owner_user_id" UUID NOT NULL,
    "title" TEXT NOT NULL,
    "event_date" DATE,
    "guest_count" INTEGER,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "created_via_ai_intake" BOOLEAN NOT NULL DEFAULT false,
    "ai_conversation_state_id" UUID,
    "venue_id" UUID,
    "auto_lock_at" TIMESTAMPTZ,
    "locked_at" TIMESTAMPTZ,
    "locked_reason" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "projects_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "threads" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "subject" TEXT,
    "created_by" TEXT NOT NULL,
    "is_resolved" BOOLEAN NOT NULL DEFAULT false,
    "message_count" INTEGER NOT NULL DEFAULT 0,
    "last_activity_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "threads_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "messages" (
    "id" UUID NOT NULL,
    "thread_id" UUID NOT NULL,
    "parent_message_id" UUID,
    "project_id" UUID NOT NULL,
    "author_id" UUID NOT NULL,
    "sender_type" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "attachments" JSONB,
    "ai_conversation_state_id" UUID,
    "is_deleted" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_edited_at" TIMESTAMPTZ,

    CONSTRAINT "messages_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_conversation_states" (
    "id" UUID NOT NULL,
    "thread_id" UUID NOT NULL,
    "project_id" UUID,
    "current_node" TEXT NOT NULL DEFAULT 'start',
    "slots" JSONB NOT NULL DEFAULT '{}',
    "is_completed" BOOLEAN NOT NULL DEFAULT false,
    "next_action" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "ai_conversation_states_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "contracts" (
    "id" UUID NOT NULL,
    "contract_group_id" TEXT NOT NULL,
    "version_number" INTEGER NOT NULL,
    "previous_version_id" UUID,
    "project_id" UUID NOT NULL,
    "status" TEXT NOT NULL,
    "title" TEXT,
    "body" JSONB NOT NULL,
    "pdf_path" TEXT,
    "total_amount" DECIMAL(12,2),
    "change_reason" TEXT,
    "metadata" JSONB,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_by" UUID NOT NULL,
    "approved_by_user_id" UUID,
    "seen_by_client_at" TIMESTAMPTZ,
    "sent_at" TIMESTAMPTZ,
    "client_signed_at" TIMESTAMPTZ,
    "expires_at" TIMESTAMPTZ,
    "ai_conversation_state_id" UUID,
    "deleted_at" TIMESTAMPTZ,
    "deleted_by" TEXT,
    "esign_provider" TEXT,
    "esign_envelope_id" TEXT,
    "ai_generated" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "contracts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "crm_pipeline" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "stage" TEXT NOT NULL DEFAULT 'lead',
    "priority" TEXT NOT NULL DEFAULT 'normal',
    "assigned_to" TEXT,
    "last_contact_at" TIMESTAMPTZ,
    "next_follow_up_at" TIMESTAMPTZ,
    "notes" TEXT,
    "risk_level" TEXT DEFAULT 'normal',
    "risk_flags" TEXT[],
    "risk_reviewed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "crm_pipeline_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clause_templates" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "category" TEXT,
    "content" TEXT NOT NULL,
    "variables" TEXT[],
    "is_default" BOOLEAN NOT NULL DEFAULT false,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "clause_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clause_rules" (
    "id" UUID NOT NULL,
    "clause_template_id" UUID NOT NULL,
    "condition_field" TEXT NOT NULL,
    "condition_op" TEXT NOT NULL,
    "condition_value" TEXT NOT NULL,
    "priority" INTEGER NOT NULL DEFAULT 0,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "clause_rules_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "clause_instances" (
    "id" UUID NOT NULL,
    "contract_id" UUID NOT NULL,
    "clause_template_id" UUID,
    "title" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "clause_instances_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_pricing" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "pricing_data" JSONB NOT NULL,
    "total_amount" DECIMAL(12,2),
    "currency" CHAR(3) NOT NULL DEFAULT 'USD',
    "version" INTEGER NOT NULL DEFAULT 1,
    "ai_generated" BOOLEAN NOT NULL DEFAULT false,
    "ai_generation_id" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "project_pricing_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_staffing" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "staffing_plan" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "project_staffing_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_portions" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "portions" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "project_portions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "upsell_suggestions" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "suggestions" JSONB NOT NULL,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "upsell_suggestions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "payments" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "currency" CHAR(3) NOT NULL DEFAULT 'USD',
    "method" TEXT,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "transaction_id" TEXT,
    "paid_at" TIMESTAMPTZ,
    "notes" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "payments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "invoices" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "invoice_num" TEXT NOT NULL,
    "amount" DECIMAL(12,2) NOT NULL,
    "currency" CHAR(3) NOT NULL DEFAULT 'USD',
    "status" TEXT NOT NULL DEFAULT 'draft',
    "due_date" DATE,
    "sent_at" TIMESTAMPTZ,
    "paid_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "invoices_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "notifications" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "project_id" UUID,
    "channel" VARCHAR(32) NOT NULL,
    "template_id" TEXT,
    "subject" TEXT,
    "body" TEXT NOT NULL,
    "read_at" TIMESTAMPTZ,
    "sent_at" TIMESTAMPTZ,
    "template_key" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "notifications_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "venues" (
    "id" UUID NOT NULL,
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
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "venues_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "venue_clause_overrides" (
    "id" UUID NOT NULL,
    "venue_id" UUID NOT NULL,
    "clause_template_id" UUID NOT NULL,
    "override_content" TEXT,
    "is_mandatory" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "venue_clause_overrides_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "menu_categories" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "menu_categories_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "menu_items" (
    "id" UUID NOT NULL,
    "category_id" UUID,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "unit_cost" DECIMAL(10,2),
    "unit_price" DECIMAL(10,2),
    "currency" CHAR(3) NOT NULL DEFAULT 'USD',
    "price_type" TEXT,
    "minimum_quantity" INTEGER NOT NULL DEFAULT 1,
    "allergens" TEXT[],
    "tags" TEXT[],
    "is_upsell" BOOLEAN NOT NULL DEFAULT false,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "menu_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "order_items" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "menu_item_id" UUID,
    "item_name_snapshot" TEXT NOT NULL,
    "price_snapshot" DECIMAL(10,2) NOT NULL,
    "unit_cost_snapshot" DECIMAL(10,2),
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "price_type" TEXT,
    "notes" TEXT,
    "added_by_user_id" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "order_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "intake_form_templates" (
    "id" UUID NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "fields" JSONB NOT NULL DEFAULT '[]',
    "is_default" BOOLEAN NOT NULL DEFAULT false,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_by" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "intake_form_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "intake_submissions" (
    "id" UUID NOT NULL,
    "form_template_id" UUID,
    "project_id" UUID,
    "raw_answers" JSONB NOT NULL DEFAULT '{}',
    "ai_parsed_output" JSONB,
    "ai_confidence_score" DECIMAL(4,3),
    "missing_fields" TEXT[],
    "upsell_triggers" TEXT[],
    "status" TEXT NOT NULL DEFAULT 'received',
    "submitted_by_email" TEXT,
    "submitted_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "parsed_at" TIMESTAMPTZ,
    "mapped_at" TIMESTAMPTZ,

    CONSTRAINT "intake_submissions_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "contract_signatures" (
    "id" UUID NOT NULL,
    "contract_id" UUID NOT NULL,
    "esign_provider" TEXT NOT NULL,
    "envelope_id" TEXT,
    "signer_user_id" UUID,
    "signer_email" TEXT NOT NULL,
    "signer_name" TEXT,
    "signer_role" TEXT,
    "ip_address" TEXT,
    "user_agent" TEXT,
    "signed_at" TIMESTAMPTZ,
    "declined_at" TIMESTAMPTZ,
    "decline_reason" TEXT,
    "audit_trail" JSONB,
    "certificate_url" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "contract_signatures_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "banquet_event_orders" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "contract_id" UUID,
    "beo_number" TEXT NOT NULL,
    "version_number" INTEGER NOT NULL DEFAULT 1,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "event_date" DATE,
    "event_start_time" TIMETZ,
    "event_end_time" TIMETZ,
    "guest_count" INTEGER,
    "service_style" TEXT,
    "setup_notes" TEXT,
    "breakdown_notes" TEXT,
    "kitchen_notes" TEXT,
    "dietary_notes" TEXT,
    "timeline_notes" TEXT,
    "created_by" UUID,
    "confirmed_by" UUID,
    "confirmed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "banquet_event_orders_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "beo_line_items" (
    "id" UUID NOT NULL,
    "beo_id" UUID NOT NULL,
    "order_item_id" UUID,
    "item_name" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL,
    "unit" TEXT,
    "prep_notes" TEXT,
    "sort_order" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "beo_line_items_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "beo_staff_assignments" (
    "id" UUID NOT NULL,
    "beo_id" UUID NOT NULL,
    "role" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "start_time" TIMETZ,
    "end_time" TIMETZ,
    "notes" TEXT,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "beo_staff_assignments_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "notification_templates" (
    "id" UUID NOT NULL,
    "key" TEXT NOT NULL,
    "channel" VARCHAR(32) NOT NULL,
    "subject" TEXT,
    "body" TEXT NOT NULL,
    "variables" TEXT[],
    "version" INTEGER NOT NULL DEFAULT 1,
    "active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "notification_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "client_risk_flags" (
    "id" UUID NOT NULL,
    "user_id" UUID NOT NULL,
    "project_id" UUID,
    "flag_type" TEXT NOT NULL,
    "severity" TEXT NOT NULL DEFAULT 'medium',
    "notes" TEXT,
    "flagged_by" UUID,
    "resolved_at" TIMESTAMPTZ,
    "resolved_by" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "client_risk_flags_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_generations" (
    "id" UUID NOT NULL,
    "entity_type" TEXT NOT NULL,
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
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ai_generations_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_staff_requirements" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "role" TEXT NOT NULL,
    "quantity" INTEGER NOT NULL DEFAULT 1,
    "hours_estimated" DECIMAL(5,2),
    "rate_per_hour" DECIMAL(10,2),
    "total_cost" DECIMAL(10,2),
    "notes" TEXT,
    "source" TEXT NOT NULL DEFAULT 'manual',
    "ai_generation_id" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL,

    CONSTRAINT "project_staff_requirements_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_portion_estimates" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "menu_item_id" UUID,
    "item_name" TEXT NOT NULL,
    "guest_count" INTEGER NOT NULL,
    "quantity" DECIMAL(10,3) NOT NULL,
    "unit" TEXT,
    "waste_factor" DECIMAL(4,3) DEFAULT 0.10,
    "source" TEXT NOT NULL DEFAULT 'manual',
    "ai_generation_id" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "project_portion_estimates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_upsell_items" (
    "id" UUID NOT NULL,
    "project_id" UUID NOT NULL,
    "menu_item_id" UUID,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "estimated_revenue" DECIMAL(10,2),
    "status" TEXT NOT NULL DEFAULT 'suggested',
    "presented_at" TIMESTAMPTZ,
    "responded_at" TIMESTAMPTZ,
    "source" TEXT NOT NULL DEFAULT 'ai_suggested',
    "ai_generation_id" UUID,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "project_upsell_items_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "users_email_key" ON "users"("email");

-- CreateIndex
CREATE INDEX "ix_projects_venue" ON "projects"("venue_id");

-- CreateIndex
CREATE INDEX "projects_ai_conversation_state_id_idx" ON "projects"("ai_conversation_state_id");

-- CreateIndex
CREATE INDEX "ix_threads_project" ON "threads"("project_id");

-- CreateIndex
CREATE INDEX "ix_messages_thread" ON "messages"("thread_id", "created_at");

-- CreateIndex
CREATE INDEX "ix_messages_project" ON "messages"("project_id");

-- CreateIndex
CREATE INDEX "ix_messages_ai_conversation" ON "messages"("ai_conversation_state_id");

-- CreateIndex
CREATE UNIQUE INDEX "ai_conversation_states_thread_id_key" ON "ai_conversation_states"("thread_id");

-- CreateIndex
CREATE INDEX "ix_ai_conversation_states_project" ON "ai_conversation_states"("project_id");

-- CreateIndex
CREATE INDEX "ix_contracts_project_active" ON "contracts"("project_id");

-- CreateIndex
CREATE INDEX "ix_contracts_status" ON "contracts"("status");

-- CreateIndex
CREATE UNIQUE INDEX "ux_contract_group_version" ON "contracts"("contract_group_id", "version_number");

-- CreateIndex
CREATE UNIQUE INDEX "crm_pipeline_project_id_key" ON "crm_pipeline"("project_id");

-- CreateIndex
CREATE INDEX "ix_payments_project" ON "payments"("project_id");

-- CreateIndex
CREATE UNIQUE INDEX "invoices_invoice_num_key" ON "invoices"("invoice_num");

-- CreateIndex
CREATE INDEX "ix_invoices_project" ON "invoices"("project_id");

-- CreateIndex
CREATE INDEX "ix_notifications_user" ON "notifications"("user_id");

-- CreateIndex
CREATE INDEX "ix_venues_active" ON "venues"("active");

-- CreateIndex
CREATE UNIQUE INDEX "venue_clause_overrides_venue_id_clause_template_id_key" ON "venue_clause_overrides"("venue_id", "clause_template_id");

-- CreateIndex
CREATE INDEX "ix_menu_items_category" ON "menu_items"("category_id");

-- CreateIndex
CREATE INDEX "ix_menu_items_active" ON "menu_items"("active");

-- CreateIndex
CREATE INDEX "ix_order_items_project" ON "order_items"("project_id");

-- CreateIndex
CREATE INDEX "ix_intake_submissions_project" ON "intake_submissions"("project_id");

-- CreateIndex
CREATE INDEX "ix_intake_submissions_status" ON "intake_submissions"("status");

-- CreateIndex
CREATE INDEX "ix_contract_signatures_contract" ON "contract_signatures"("contract_id");

-- CreateIndex
CREATE INDEX "ix_contract_signatures_envelope" ON "contract_signatures"("envelope_id");

-- CreateIndex
CREATE UNIQUE INDEX "banquet_event_orders_beo_number_key" ON "banquet_event_orders"("beo_number");

-- CreateIndex
CREATE INDEX "ix_beo_project" ON "banquet_event_orders"("project_id");

-- CreateIndex
CREATE INDEX "ix_beo_status" ON "banquet_event_orders"("status");

-- CreateIndex
CREATE INDEX "ix_beo_line_items_beo" ON "beo_line_items"("beo_id");

-- CreateIndex
CREATE INDEX "ix_beo_staff_beo" ON "beo_staff_assignments"("beo_id");

-- CreateIndex
CREATE UNIQUE INDEX "notification_templates_key_key" ON "notification_templates"("key");

-- CreateIndex
CREATE INDEX "ix_notification_templates_channel" ON "notification_templates"("channel");

-- CreateIndex
CREATE INDEX "ix_client_risk_flags_user" ON "client_risk_flags"("user_id");

-- CreateIndex
CREATE INDEX "ix_client_risk_flags_project" ON "client_risk_flags"("project_id");

-- CreateIndex
CREATE INDEX "ix_ai_generations_entity" ON "ai_generations"("entity_type", "entity_id");

-- CreateIndex
CREATE INDEX "ix_ai_generations_project" ON "ai_generations"("project_id");

-- CreateIndex
CREATE INDEX "ix_ai_generations_model" ON "ai_generations"("model", "created_at" DESC);

-- CreateIndex
CREATE INDEX "ix_project_staff_req_project" ON "project_staff_requirements"("project_id");

-- CreateIndex
CREATE INDEX "ix_project_portions_project" ON "project_portion_estimates"("project_id");

-- CreateIndex
CREATE INDEX "ix_project_upsells_project" ON "project_upsell_items"("project_id");

-- CreateIndex
CREATE INDEX "ix_project_upsells_status" ON "project_upsell_items"("status");

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "projects_owner_user_id_fkey" FOREIGN KEY ("owner_user_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "projects_venue_id_fkey" FOREIGN KEY ("venue_id") REFERENCES "venues"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "projects" ADD CONSTRAINT "projects_ai_conversation_state_id_fkey" FOREIGN KEY ("ai_conversation_state_id") REFERENCES "ai_conversation_states"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "threads" ADD CONSTRAINT "threads_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_thread_id_fkey" FOREIGN KEY ("thread_id") REFERENCES "threads"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "messages" ADD CONSTRAINT "messages_ai_conversation_state_id_fkey" FOREIGN KEY ("ai_conversation_state_id") REFERENCES "ai_conversation_states"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_conversation_states" ADD CONSTRAINT "ai_conversation_states_thread_id_fkey" FOREIGN KEY ("thread_id") REFERENCES "threads"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_approved_by_user_id_fkey" FOREIGN KEY ("approved_by_user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_previous_version_id_fkey" FOREIGN KEY ("previous_version_id") REFERENCES "contracts"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "contracts" ADD CONSTRAINT "contracts_ai_conversation_state_id_fkey" FOREIGN KEY ("ai_conversation_state_id") REFERENCES "ai_conversation_states"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "crm_pipeline" ADD CONSTRAINT "crm_pipeline_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "clause_rules" ADD CONSTRAINT "clause_rules_clause_template_id_fkey" FOREIGN KEY ("clause_template_id") REFERENCES "clause_templates"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "clause_instances" ADD CONSTRAINT "clause_instances_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "contracts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "clause_instances" ADD CONSTRAINT "clause_instances_clause_template_id_fkey" FOREIGN KEY ("clause_template_id") REFERENCES "clause_templates"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_pricing" ADD CONSTRAINT "project_pricing_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_pricing" ADD CONSTRAINT "project_pricing_ai_generation_id_fkey" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_staffing" ADD CONSTRAINT "project_staffing_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_portions" ADD CONSTRAINT "project_portions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "upsell_suggestions" ADD CONSTRAINT "upsell_suggestions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "payments" ADD CONSTRAINT "payments_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "invoices" ADD CONSTRAINT "invoices_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "notifications" ADD CONSTRAINT "notifications_template_key_fkey" FOREIGN KEY ("template_key") REFERENCES "notification_templates"("key") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "venue_clause_overrides" ADD CONSTRAINT "venue_clause_overrides_venue_id_fkey" FOREIGN KEY ("venue_id") REFERENCES "venues"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "venue_clause_overrides" ADD CONSTRAINT "venue_clause_overrides_clause_template_id_fkey" FOREIGN KEY ("clause_template_id") REFERENCES "clause_templates"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "menu_items" ADD CONSTRAINT "menu_items_category_id_fkey" FOREIGN KEY ("category_id") REFERENCES "menu_categories"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_menu_item_id_fkey" FOREIGN KEY ("menu_item_id") REFERENCES "menu_items"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "order_items" ADD CONSTRAINT "order_items_added_by_user_id_fkey" FOREIGN KEY ("added_by_user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "intake_form_templates" ADD CONSTRAINT "intake_form_templates_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "intake_submissions" ADD CONSTRAINT "intake_submissions_form_template_id_fkey" FOREIGN KEY ("form_template_id") REFERENCES "intake_form_templates"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "intake_submissions" ADD CONSTRAINT "intake_submissions_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "contract_signatures" ADD CONSTRAINT "contract_signatures_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "contracts"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "contract_signatures" ADD CONSTRAINT "contract_signatures_signer_user_id_fkey" FOREIGN KEY ("signer_user_id") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_contract_id_fkey" FOREIGN KEY ("contract_id") REFERENCES "contracts"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_created_by_fkey" FOREIGN KEY ("created_by") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "banquet_event_orders" ADD CONSTRAINT "banquet_event_orders_confirmed_by_fkey" FOREIGN KEY ("confirmed_by") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "beo_line_items" ADD CONSTRAINT "beo_line_items_beo_id_fkey" FOREIGN KEY ("beo_id") REFERENCES "banquet_event_orders"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "beo_line_items" ADD CONSTRAINT "beo_line_items_order_item_id_fkey" FOREIGN KEY ("order_item_id") REFERENCES "order_items"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "beo_staff_assignments" ADD CONSTRAINT "beo_staff_assignments_beo_id_fkey" FOREIGN KEY ("beo_id") REFERENCES "banquet_event_orders"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_flagged_by_fkey" FOREIGN KEY ("flagged_by") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "client_risk_flags" ADD CONSTRAINT "client_risk_flags_resolved_by_fkey" FOREIGN KEY ("resolved_by") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_generations" ADD CONSTRAINT "ai_generations_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_generations" ADD CONSTRAINT "ai_generations_triggered_by_fkey" FOREIGN KEY ("triggered_by") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_staff_requirements" ADD CONSTRAINT "project_staff_requirements_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_staff_requirements" ADD CONSTRAINT "project_staff_requirements_ai_generation_id_fkey" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_portion_estimates" ADD CONSTRAINT "project_portion_estimates_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_portion_estimates" ADD CONSTRAINT "project_portion_estimates_menu_item_id_fkey" FOREIGN KEY ("menu_item_id") REFERENCES "menu_items"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_portion_estimates" ADD CONSTRAINT "project_portion_estimates_ai_generation_id_fkey" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_upsell_items" ADD CONSTRAINT "project_upsell_items_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_upsell_items" ADD CONSTRAINT "project_upsell_items_menu_item_id_fkey" FOREIGN KEY ("menu_item_id") REFERENCES "menu_items"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "project_upsell_items" ADD CONSTRAINT "project_upsell_items_ai_generation_id_fkey" FOREIGN KEY ("ai_generation_id") REFERENCES "ai_generations"("id") ON DELETE SET NULL ON UPDATE CASCADE;

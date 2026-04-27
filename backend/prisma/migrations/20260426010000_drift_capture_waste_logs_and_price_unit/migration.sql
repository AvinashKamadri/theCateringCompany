-- Drift capture: previously these objects were ALTERed manually against dev DBs
-- but never written as a migration. Reset would silently lose them and seed
-- scripts would fail with "column does not exist". This migration brings the
-- migration history back in sync with schema.prisma.
--
-- Safe to apply against DBs that already have these objects: every change is
-- guarded with IF NOT EXISTS.

-- AlterTable: ingredients.default_price_unit
ALTER TABLE "ingredients"
  ADD COLUMN IF NOT EXISTS "default_price_unit" TEXT DEFAULT 'g';

-- CreateTable: project_waste_logs
CREATE TABLE IF NOT EXISTS "project_waste_logs" (
  "id"                UUID         NOT NULL DEFAULT gen_random_uuid(),
  "project_id"        UUID         NOT NULL,
  "logged_by_user_id" UUID,
  "total_weight_kg"   DECIMAL(10,2),
  "reason"            TEXT,
  "notes"             TEXT,
  "logged_at"         TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "created_at"        TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at"        TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT "project_waste_logs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX IF NOT EXISTS "ix_project_waste_logs_project"
  ON "project_waste_logs" ("project_id", "logged_at" DESC);

-- AddForeignKey: project_waste_logs → projects
DO $$ BEGIN
  ALTER TABLE "project_waste_logs"
    ADD CONSTRAINT "project_waste_logs_project_id_fkey"
    FOREIGN KEY ("project_id") REFERENCES "projects"("id")
    ON DELETE CASCADE ON UPDATE NO ACTION;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- AddForeignKey: project_waste_logs → users
DO $$ BEGIN
  ALTER TABLE "project_waste_logs"
    ADD CONSTRAINT "project_waste_logs_logged_by_user_id_fkey"
    FOREIGN KEY ("logged_by_user_id") REFERENCES "users"("id")
    ON DELETE SET NULL ON UPDATE NO ACTION;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

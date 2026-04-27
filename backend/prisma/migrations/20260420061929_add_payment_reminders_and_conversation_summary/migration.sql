-- NOTE: this migration was originally generated with the section column being
-- dropped from menu_categories (it pre-dated the section migration in the
-- working schema). Those drops were removed manually so resets do not undo
-- the earlier 20260415000000_add_section_to_menu_categories migration.

-- AlterTable
ALTER TABLE "payment_schedule_items" ADD COLUMN     "last_reminder_sent_at" TIMESTAMPTZ(6),
ADD COLUMN     "overdue_notified_at" TIMESTAMPTZ(6);

-- AlterTable
ALTER TABLE "projects" ADD COLUMN     "conversation_summary" TEXT;

-- CreateTable
CREATE TABLE "ingredients" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "calories_per_100g" DECIMAL(10,2),
    "carbs_g_per_100g" DECIMAL(10,2),
    "protein_g_per_100g" DECIMAL(10,2),
    "fat_g_per_100g" DECIMAL(10,2),
    "allergens" TEXT[],
    "default_unit" TEXT NOT NULL DEFAULT 'g',
    "default_price" DECIMAL(10,2),
    "created_by_user_id" UUID,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ingredients_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "dishes" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "name" TEXT NOT NULL,
    "description" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "dishes_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "menu_item_dishes" (
    "menu_item_id" UUID NOT NULL,
    "dish_id" UUID NOT NULL,
    "sort_order" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "menu_item_dishes_pkey" PRIMARY KEY ("menu_item_id","dish_id")
);

-- CreateTable
CREATE TABLE "dish_ingredients" (
    "dish_id" UUID NOT NULL,
    "ingredient_id" UUID NOT NULL,
    "weight_g" DECIMAL(10,2),
    "volume_ml" DECIMAL(10,2),
    "notes" TEXT,

    CONSTRAINT "dish_ingredients_pkey" PRIMARY KEY ("dish_id","ingredient_id")
);

-- CreateTable
CREATE TABLE "ingredient_stock_log" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "ingredient_id" UUID NOT NULL,
    "delta_g" DECIMAL(10,2),
    "delta_ml" DECIMAL(10,2),
    "unit_price" DECIMAL(10,2),
    "source" TEXT NOT NULL,
    "logged_by" UUID,
    "project_id" UUID,
    "notes" TEXT,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ingredient_stock_log_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "project_summaries" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "project_id" UUID NOT NULL,
    "contract_id" UUID,
    "summary" TEXT NOT NULL,
    "generated_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "project_summaries_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "ingredients_name_key" ON "ingredients"("name");

-- CreateIndex
CREATE INDEX "ix_ingredients_name" ON "ingredients"("name");

-- CreateIndex
CREATE UNIQUE INDEX "dishes_name_key" ON "dishes"("name");

-- CreateIndex
CREATE INDEX "ix_menu_item_dishes_dish" ON "menu_item_dishes"("dish_id");

-- CreateIndex
CREATE INDEX "ix_dish_ingredients_ingredient" ON "dish_ingredients"("ingredient_id");

-- CreateIndex
CREATE INDEX "ix_ingredient_stock_log_ingredient" ON "ingredient_stock_log"("ingredient_id", "created_at" DESC);

-- CreateIndex
CREATE INDEX "ix_ingredient_stock_log_project" ON "ingredient_stock_log"("project_id");

-- CreateIndex
CREATE INDEX "ix_project_summaries_project" ON "project_summaries"("project_id", "generated_at" DESC);

-- (Removed: re-creating menu_categories_name_key here would conflict with
-- the (section, name) unique index from 20260415000000_add_section_to_menu_categories.)

-- AddForeignKey
ALTER TABLE "menu_item_dishes" ADD CONSTRAINT "menu_item_dishes_menu_item_id_fkey" FOREIGN KEY ("menu_item_id") REFERENCES "menu_items"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "menu_item_dishes" ADD CONSTRAINT "menu_item_dishes_dish_id_fkey" FOREIGN KEY ("dish_id") REFERENCES "dishes"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "dish_ingredients" ADD CONSTRAINT "dish_ingredients_dish_id_fkey" FOREIGN KEY ("dish_id") REFERENCES "dishes"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "dish_ingredients" ADD CONSTRAINT "dish_ingredients_ingredient_id_fkey" FOREIGN KEY ("ingredient_id") REFERENCES "ingredients"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "ingredient_stock_log" ADD CONSTRAINT "ingredient_stock_log_ingredient_id_fkey" FOREIGN KEY ("ingredient_id") REFERENCES "ingredients"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- AddForeignKey
ALTER TABLE "project_summaries" ADD CONSTRAINT "project_summaries_project_id_fkey" FOREIGN KEY ("project_id") REFERENCES "projects"("id") ON DELETE CASCADE ON UPDATE NO ACTION;

-- DropIndex
DROP INDEX "menu_categories_name_key";

-- AlterTable
ALTER TABLE "menu_categories" ADD COLUMN "section" TEXT NOT NULL DEFAULT '';

-- CreateIndex
CREATE UNIQUE INDEX "menu_categories_section_name_key" ON "menu_categories"("section", "name");

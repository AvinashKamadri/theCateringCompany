-- CreateEnum
CREATE TYPE "allergen_confidence" AS ENUM ('derived', 'incomplete');

-- AlterTable: default to 'incomplete' so unfilled rows fail closed under
-- strict allergen filtering. Derivation service flips rows to 'derived'
-- whenever the menu_item -> dishes -> ingredients graph is complete.
ALTER TABLE "menu_items"
  ADD COLUMN "allergen_confidence" "allergen_confidence" NOT NULL DEFAULT 'incomplete';

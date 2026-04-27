/**
 * Slice 3 test harness: a tiny "perfect dataset" that wires real ingredients
 * (with allergen tags) onto 10 existing dishes. Idempotent — re-runs simply
 * re-upsert the same ingredient links. Leaves all other menu_items as-is so
 * the rest of the menu remains in `incomplete` state for fail-closed testing.
 *
 * Buckets:
 *   🟢 Derived + safe        Chips & Guacamole
 *   🟢 Derived single        Brie Bites, Caprese Skewers, Charcuterie Boards
 *   🟢 Derived multi         Brownies, Blondies, Bruschetta, Caviar Egg
 *   🟡 Edge — peanuts        Chicken Satay
 *   🟡 Edge — seafood        Ahi Tuna Bites
 *
 * Run:  npx ts-node src/scripts/seed-perfect-dataset.ts
 */

import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

type IngredientSpec = { name: string; allergens: string[] };
type DishSpec = { dish: string; ingredients: string[] };

const INGREDIENTS: IngredientSpec[] = [
  { name: 'All-Purpose Flour', allergens: ['gluten'] },
  { name: 'Butter',            allergens: ['dairy'] },
  { name: 'Eggs',              allergens: ['egg'] },
  { name: 'Dark Chocolate',    allergens: ['dairy'] },
  { name: 'White Sugar',       allergens: [] },
  { name: 'Brown Sugar',       allergens: [] },
  { name: 'Mozzarella',        allergens: ['dairy'] },
  { name: 'Tomato',            allergens: [] },
  { name: 'Basil',             allergens: [] },
  { name: 'Olive Oil',         allergens: [] },
  { name: 'Chicken Breast',    allergens: [] },
  { name: 'Peanut Sauce',      allergens: ['peanuts'] },
  { name: 'Baguette',          allergens: ['gluten'] },
  { name: 'Brie',              allergens: ['dairy'] },
  { name: 'Ahi Tuna',          allergens: ['fish'] },
  { name: 'Soy Sauce',         allergens: ['soy', 'gluten'] },
  { name: 'Tortilla Chips',    allergens: [] },
  { name: 'Avocado',           allergens: [] },
  { name: 'Lime',              allergens: [] },
  { name: 'Prosciutto',        allergens: [] },
  { name: 'Aged Cheddar',      allergens: ['dairy'] },
  { name: 'Caviar',            allergens: ['fish'] },
];

const DISH_INGREDIENTS: DishSpec[] = [
  { dish: 'Brownies',           ingredients: ['All-Purpose Flour', 'Butter', 'Eggs', 'Dark Chocolate', 'White Sugar'] },
  { dish: 'Blondies',           ingredients: ['All-Purpose Flour', 'Butter', 'Eggs', 'Brown Sugar'] },
  { dish: 'Caprese Skewers',    ingredients: ['Mozzarella', 'Tomato', 'Basil', 'Olive Oil'] },
  { dish: 'Bruschetta',         ingredients: ['Baguette', 'Tomato', 'Basil', 'Olive Oil'] },
  { dish: 'Brie Bites',         ingredients: ['Brie', 'Baguette'] },
  { dish: 'Charcuterie Boards', ingredients: ['Prosciutto', 'Aged Cheddar', 'Baguette'] },
  { dish: 'Chicken Satay',      ingredients: ['Chicken Breast', 'Peanut Sauce'] },
  { dish: 'Ahi Tuna Bites',     ingredients: ['Ahi Tuna', 'Soy Sauce', 'Lime'] },
  { dish: 'Chips & Guacamole',  ingredients: ['Tortilla Chips', 'Avocado', 'Lime'] },
  { dish: 'Caviar Egg',         ingredients: ['Eggs', 'Caviar'] },
];

async function main() {
  console.log('Seeding perfect dataset (Slice 3 test harness)...');

  const ingredientIds = new Map<string, string>();
  for (const spec of INGREDIENTS) {
    const row = await prisma.ingredients.upsert({
      where: { name: spec.name },
      update: { allergens: spec.allergens },
      create: { name: spec.name, allergens: spec.allergens, default_unit: 'g' },
      select: { id: true },
    });
    ingredientIds.set(spec.name, row.id);
  }
  console.log(`  Upserted ${INGREDIENTS.length} ingredients.`);

  let linksCreated = 0;
  let dishesMissing: string[] = [];
  for (const spec of DISH_INGREDIENTS) {
    const dish = await prisma.dishes.findUnique({
      where: { name: spec.dish },
      select: { id: true },
    });
    if (!dish) {
      dishesMissing.push(spec.dish);
      continue;
    }
    for (const ingName of spec.ingredients) {
      const ingId = ingredientIds.get(ingName);
      if (!ingId) throw new Error(`Missing ingredient id for ${ingName}`);
      await prisma.dish_ingredients.upsert({
        where: { dish_id_ingredient_id: { dish_id: dish.id, ingredient_id: ingId } },
        update: {},
        create: { dish_id: dish.id, ingredient_id: ingId },
      });
      linksCreated++;
    }
  }
  console.log(`  Linked ${linksCreated} dish_ingredients across ${DISH_INGREDIENTS.length - dishesMissing.length} dishes.`);
  if (dishesMissing.length) {
    console.warn(`  ⚠ Skipped (dish not found): ${dishesMissing.join(', ')}`);
  }

  console.log('\nDone. Now run:\n  npx ts-node src/scripts/recompute-menu-allergens.ts');
  console.log('Expected: changed≈10, plus the rest still incomplete.\n');
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());

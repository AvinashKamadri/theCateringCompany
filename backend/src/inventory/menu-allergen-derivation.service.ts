import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

/**
 * Derives `menu_items.allergens` from the ingredient graph:
 *   menu_items → menu_item_dishes → dishes → dish_ingredients → ingredients.allergens
 *
 * Truth lives in `ingredients.allergens` (staff-maintained).
 * `menu_items.allergens` is a denormalized cache for fast filter queries.
 * This service is the ONLY thing that should write to that cache.
 *
 * All recompute paths are idempotent: a no-op call produces no DB write.
 */
@Injectable()
export class MenuAllergenDerivationService {
  private readonly logger = new Logger(MenuAllergenDerivationService.name);

  constructor(private readonly prisma: PrismaService) {}

  /**
   * Recompute the cache for a single menu_item.
   * Returns true if the cache changed, false if already correct.
   */
  async recomputeForMenuItem(menuItemId: string): Promise<boolean> {
    const item = await this.prisma.menu_items.findUnique({
      where: { id: menuItemId },
      select: {
        id: true,
        name: true,
        allergens: true,
        allergen_confidence: true,
        menu_item_dishes: {
          select: {
            dishes: {
              select: {
                id: true,
                name: true,
                dish_ingredients: {
                  select: { ingredients: { select: { id: true, allergens: true } } },
                },
              },
            },
          },
        },
      },
    });

    if (!item) {
      this.logger.warn(`recomputeForMenuItem: menu_item ${menuItemId} not found`);
      return false;
    }

    const derived = new Set<string>();
    let sawAnyDish = false;
    let sawAnyIngredient = false;

    for (const link of item.menu_item_dishes) {
      sawAnyDish = true;
      const dish = link.dishes;
      if (!dish) continue;
      for (const di of dish.dish_ingredients) {
        sawAnyIngredient = true;
        const ing = di.ingredients;
        if (!ing) continue;
        for (const a of ing.allergens ?? []) {
          if (a) derived.add(a.toLowerCase().trim());
        }
      }
    }

    // Confidence rule (Slice 3): the graph must be complete enough to trust.
    //   - no dishes linked        → incomplete
    //   - dishes but no ingredients → incomplete
    //   - dish + ingredient path   → derived
    // Allergens are written only when derived; incomplete rows keep allergens
    // as [] so the ml-agent fail-closed filter can reject them on confidence.
    const confidence: 'derived' | 'incomplete' =
      sawAnyDish && sawAnyIngredient ? 'derived' : 'incomplete';

    if (!sawAnyDish) {
      this.logger.warn(
        `derivation: menu_item="${item.name}" id=${item.id} has no dish links — marking incomplete`,
      );
    } else if (!sawAnyIngredient) {
      this.logger.warn(
        `derivation: menu_item="${item.name}" id=${item.id} has dishes but none have ingredients — marking incomplete`,
      );
    }

    const next = confidence === 'derived' ? [...derived].sort() : [];
    const prev = [...(item.allergens ?? [])].map((a) => a.toLowerCase().trim()).sort();
    const confidenceChanged = item.allergen_confidence !== confidence;
    const allergensChanged = !arraysEqual(next, prev);
    if (!confidenceChanged && !allergensChanged) return false;

    await this.prisma.menu_items.update({
      where: { id: item.id },
      data: { allergens: next, allergen_confidence: confidence },
    });
    this.logger.log(
      `derivation: menu_item="${item.name}" confidence=${item.allergen_confidence}→${confidence} allergens=[${prev.join(',')}]→[${next.join(',')}]`,
    );
    return true;
  }

  /** Fan-out from a dish change to every menu_item that references it. */
  async recomputeForDish(dishId: string): Promise<void> {
    const links = await this.prisma.menu_item_dishes.findMany({
      where: { dish_id: dishId },
      select: { menu_item_id: true },
    });
    await this.recomputeMany(links.map((l) => l.menu_item_id));
  }

  /**
   * Fan-out from an ingredient change.
   *
   * IMPORTANT: call this BEFORE deleting the ingredient. After delete, the
   * `dish_ingredients` rows are gone (FK cascade) and we can no longer find
   * the affected menu_items. Capture the ids first, mutate, then recompute.
   */
  async findMenuItemsAffectedByIngredient(ingredientId: string): Promise<string[]> {
    const rows = await this.prisma.menu_item_dishes.findMany({
      where: { dishes: { dish_ingredients: { some: { ingredient_id: ingredientId } } } },
      select: { menu_item_id: true },
    });
    return [...new Set(rows.map((r) => r.menu_item_id))];
  }

  async recomputeForIngredient(ingredientId: string): Promise<void> {
    const ids = await this.findMenuItemsAffectedByIngredient(ingredientId);
    await this.recomputeMany(ids);
  }

  async recomputeMany(menuItemIds: string[]): Promise<{ changed: number; failed: number }> {
    let changed = 0;
    let failed = 0;
    for (const id of menuItemIds) {
      try {
        if (await this.recomputeForMenuItem(id)) changed++;
      } catch (err) {
        failed++;
        this.logger.error(`recompute failed for menu_item ${id}: ${(err as Error).message}`);
      }
    }
    return { changed, failed };
  }

  /** Backfill / drift recovery. Safe to run anytime. */
  async recomputeAll(): Promise<{ scanned: number; changed: number; failed: number }> {
    const items = await this.prisma.menu_items.findMany({ select: { id: true } });
    const { changed, failed } = await this.recomputeMany(items.map((i) => i.id));
    return { scanned: items.length, changed, failed };
  }

  /**
   * Data health probe. Returns counts + sample ids for the three known
   * gap conditions. Use this as a periodic check or wire to a dashboard.
   */
  async healthCheck() {
    const [orphanMenuItems, emptyDishes, untaggedIngredients] = await Promise.all([
      this.prisma.menu_items.findMany({
        where: { active: true, menu_item_dishes: { none: {} } },
        select: { id: true, name: true },
        take: 50,
      }),
      this.prisma.dishes.findMany({
        where: { dish_ingredients: { none: {} } },
        select: { id: true, name: true },
        take: 50,
      }),
      this.prisma.ingredients.findMany({
        where: { OR: [{ allergens: { isEmpty: true } }] },
        select: { id: true, name: true },
        take: 50,
      }),
    ]);
    return {
      menu_items_without_dishes: { count: orphanMenuItems.length, sample: orphanMenuItems },
      dishes_without_ingredients: { count: emptyDishes.length, sample: emptyDishes },
      ingredients_without_allergens: { count: untaggedIngredients.length, sample: untaggedIngredients },
    };
  }
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

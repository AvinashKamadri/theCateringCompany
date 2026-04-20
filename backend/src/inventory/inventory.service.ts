import { ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

const STAFF_DOMAIN = '@catering-company.com';

export interface UpsertIngredientDto {
  name: string;
  calories_per_100g?: number | null;
  carbs_g_per_100g?: number | null;
  protein_g_per_100g?: number | null;
  fat_g_per_100g?: number | null;
  allergens?: string[];
  default_unit?: 'g' | 'ml';
  default_price?: number | null;
}

export interface UpsertDishDto {
  name: string;
  description?: string | null;
}

export interface DishIngredientDto {
  ingredient_id: string;
  weight_g?: number | null;
  volume_ml?: number | null;
  notes?: string | null;
}

export interface StockLogDto {
  ingredient_id: string;
  delta_g?: number | null;
  delta_ml?: number | null;
  unit_price?: number | null;
  source: 'staff_manual' | 'purchase' | 'consumption' | 'waste';
  project_id?: string | null;
  notes?: string | null;
}

@Injectable()
export class InventoryService {
  constructor(private readonly prisma: PrismaService) {}

  private assertStaff(email: string) {
    if (!email?.endsWith(STAFF_DOMAIN)) {
      throw new ForbiddenException('Inventory access is restricted to staff accounts.');
    }
  }

  // ─── ingredients ──────────────────────────────────────────────────────────

  async listIngredients(callerEmail: string) {
    this.assertStaff(callerEmail);
    return this.prisma.ingredients.findMany({ orderBy: { name: 'asc' } });
  }

  async getIngredient(callerEmail: string, id: string) {
    this.assertStaff(callerEmail);
    const ing = await this.prisma.ingredients.findUnique({
      where: { id },
      include: {
        dish_ingredients: { include: { dishes: true } },
        ingredient_stock_log: { orderBy: { created_at: 'desc' }, take: 50 },
      },
    });
    if (!ing) throw new NotFoundException('Ingredient not found');
    return ing;
  }

  async createIngredient(callerEmail: string, userId: string, dto: UpsertIngredientDto) {
    this.assertStaff(callerEmail);
    return this.prisma.ingredients.create({
      data: {
        name: dto.name.trim(),
        calories_per_100g: dto.calories_per_100g ?? null,
        carbs_g_per_100g: dto.carbs_g_per_100g ?? null,
        protein_g_per_100g: dto.protein_g_per_100g ?? null,
        fat_g_per_100g: dto.fat_g_per_100g ?? null,
        allergens: dto.allergens ?? [],
        default_unit: dto.default_unit ?? 'g',
        default_price: dto.default_price ?? null,
        created_by_user_id: userId,
      },
    });
  }

  async updateIngredient(callerEmail: string, id: string, dto: Partial<UpsertIngredientDto>) {
    this.assertStaff(callerEmail);
    return this.prisma.ingredients.update({
      where: { id },
      data: {
        ...(dto.name !== undefined && { name: dto.name.trim() }),
        ...(dto.calories_per_100g !== undefined && { calories_per_100g: dto.calories_per_100g }),
        ...(dto.carbs_g_per_100g !== undefined && { carbs_g_per_100g: dto.carbs_g_per_100g }),
        ...(dto.protein_g_per_100g !== undefined && { protein_g_per_100g: dto.protein_g_per_100g }),
        ...(dto.fat_g_per_100g !== undefined && { fat_g_per_100g: dto.fat_g_per_100g }),
        ...(dto.allergens !== undefined && { allergens: dto.allergens }),
        ...(dto.default_unit !== undefined && { default_unit: dto.default_unit }),
        ...(dto.default_price !== undefined && { default_price: dto.default_price }),
        updated_at: new Date(),
      },
    });
  }

  async deleteIngredient(callerEmail: string, id: string) {
    this.assertStaff(callerEmail);
    await this.prisma.ingredients.delete({ where: { id } });
    return { ok: true };
  }

  // ─── dishes ───────────────────────────────────────────────────────────────

  async listDishes(callerEmail: string) {
    this.assertStaff(callerEmail);
    return this.prisma.dishes.findMany({
      orderBy: { name: 'asc' },
      include: {
        dish_ingredients: { include: { ingredients: true } },
        menu_item_dishes: { include: { menu_items: { select: { id: true, name: true } } } },
      },
    });
  }

  async getDish(callerEmail: string, id: string) {
    this.assertStaff(callerEmail);
    const dish = await this.prisma.dishes.findUnique({
      where: { id },
      include: {
        dish_ingredients: { include: { ingredients: true } },
        menu_item_dishes: { include: { menu_items: { select: { id: true, name: true } } } },
      },
    });
    if (!dish) throw new NotFoundException('Dish not found');
    return dish;
  }

  async createDish(callerEmail: string, dto: UpsertDishDto) {
    this.assertStaff(callerEmail);
    return this.prisma.dishes.create({
      data: { name: dto.name.trim(), description: dto.description ?? null },
    });
  }

  async updateDish(callerEmail: string, id: string, dto: Partial<UpsertDishDto>) {
    this.assertStaff(callerEmail);
    return this.prisma.dishes.update({
      where: { id },
      data: {
        ...(dto.name !== undefined && { name: dto.name.trim() }),
        ...(dto.description !== undefined && { description: dto.description }),
        updated_at: new Date(),
      },
    });
  }

  async setDishIngredient(callerEmail: string, dishId: string, dto: DishIngredientDto) {
    this.assertStaff(callerEmail);
    return this.prisma.dish_ingredients.upsert({
      where: {
        dish_id_ingredient_id: { dish_id: dishId, ingredient_id: dto.ingredient_id },
      },
      create: {
        dish_id: dishId,
        ingredient_id: dto.ingredient_id,
        weight_g: dto.weight_g ?? null,
        volume_ml: dto.volume_ml ?? null,
        notes: dto.notes ?? null,
      },
      update: {
        weight_g: dto.weight_g ?? null,
        volume_ml: dto.volume_ml ?? null,
        notes: dto.notes ?? null,
      },
    });
  }

  async removeDishIngredient(callerEmail: string, dishId: string, ingredientId: string) {
    this.assertStaff(callerEmail);
    await this.prisma.dish_ingredients.delete({
      where: { dish_id_ingredient_id: { dish_id: dishId, ingredient_id: ingredientId } },
    });
    return { ok: true };
  }

  // ─── stock log ────────────────────────────────────────────────────────────

  async logStock(callerEmail: string, userId: string, dto: StockLogDto) {
    this.assertStaff(callerEmail);
    return this.prisma.ingredient_stock_log.create({
      data: {
        ingredient_id: dto.ingredient_id,
        delta_g: dto.delta_g ?? null,
        delta_ml: dto.delta_ml ?? null,
        unit_price: dto.unit_price ?? null,
        source: dto.source,
        project_id: dto.project_id ?? null,
        notes: dto.notes ?? null,
        logged_by: userId,
      },
    });
  }

  async listStockLog(callerEmail: string, ingredientId?: string) {
    this.assertStaff(callerEmail);
    return this.prisma.ingredient_stock_log.findMany({
      where: ingredientId ? { ingredient_id: ingredientId } : undefined,
      orderBy: { created_at: 'desc' },
      take: 200,
      include: { ingredients: { select: { id: true, name: true, default_unit: true } } },
    });
  }

  // ─── menu_items with dishes (for menu page) ───────────────────────────────

  // ─── line-item breakdown (allergen + dish expansion for contract page) ───

  async resolveLineItems(
    callerEmail: string,
    descriptions: string[],
    dietaryRestrictions: string[],
  ) {
    this.assertStaff(callerEmail);

    const normalize = (s: string) => s.toLowerCase().trim();
    const dietSet = new Set(dietaryRestrictions.map(normalize).filter(Boolean));

    // Pull all active menu items with their dish graph once, then match in memory.
    const allItems = await this.prisma.menu_items.findMany({
      where: { active: true },
      include: {
        menu_item_dishes: {
          include: {
            dishes: {
              include: { dish_ingredients: { include: { ingredients: true } } },
            },
          },
        },
      },
    });

    const findMatch = (description: string) => {
      const d = normalize(description);
      if (!d) return null;
      // 1. exact name match
      let m = allItems.find((it) => normalize(it.name) === d);
      if (m) return m;
      // 2. description contains menu item name OR vice versa
      m = allItems.find((it) => d.includes(normalize(it.name)) || normalize(it.name).includes(d));
      return m ?? null;
    };

    const results = descriptions.map((description) => {
      const match = findMatch(description);
      if (!match) {
        return {
          description,
          matched_menu_item_id: null as string | null,
          matched_name: null as string | null,
          dishes: [] as Array<{
            id: string;
            name: string;
            ingredients: Array<{ id: string; name: string; allergens: string[] }>;
          }>,
          menu_item_allergens: [] as string[],
          warnings: [] as string[],
        };
      }

      const dishes = match.menu_item_dishes
        .slice()
        .sort((a, b) => a.sort_order - b.sort_order)
        .map((mid) => ({
          id: mid.dishes.id,
          name: mid.dishes.name,
          ingredients: mid.dishes.dish_ingredients.map((di) => ({
            id: di.ingredients.id,
            name: di.ingredients.name,
            allergens: di.ingredients.allergens,
          })),
        }));

      const allAllergens = new Set<string>();
      for (const a of match.allergens) allAllergens.add(normalize(a));
      for (const d of dishes) {
        for (const i of d.ingredients) {
          for (const a of i.allergens) allAllergens.add(normalize(a));
        }
      }

      const warnings: string[] = [];
      for (const a of allAllergens) {
        for (const d of dietSet) {
          if (a === d || a.includes(d) || d.includes(a)) {
            warnings.push(a);
            break;
          }
        }
      }

      return {
        description,
        matched_menu_item_id: match.id,
        matched_name: match.name,
        dishes,
        menu_item_allergens: match.allergens,
        warnings: Array.from(new Set(warnings)),
      };
    });

    return { items: results, dietary_restrictions: Array.from(dietSet) };
  }

  async listMenuItemsWithDishes(callerEmail: string) {
    this.assertStaff(callerEmail);
    return this.prisma.menu_items.findMany({
      where: { active: true },
      orderBy: [{ menu_categories: { sort_order: 'asc' } }, { name: 'asc' }],
      include: {
        menu_categories: { select: { name: true, sort_order: true } },
        menu_item_dishes: {
          orderBy: { sort_order: 'asc' },
          include: {
            dishes: {
              include: { dish_ingredients: { include: { ingredients: true } } },
            },
          },
        },
      },
    });
  }
}

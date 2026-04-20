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

  async listMenuItemsWithDishes() {
    // public — no staff guard, so the menu page can render it
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

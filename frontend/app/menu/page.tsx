"use client";

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, UtensilsCrossed, ChevronRight, AlertCircle, Leaf } from 'lucide-react';
import { apiClient } from '@/lib/api/client';

interface DishIngredient {
  ingredient_id: string;
  weight_g: number | string | null;
  volume_ml: number | string | null;
  ingredients: {
    id: string;
    name: string;
    allergens: string[];
    calories_per_100g: number | string | null;
  };
}

interface Dish {
  id: string;
  name: string;
  description: string | null;
  dish_ingredients: DishIngredient[];
}

interface MenuItem {
  id: string;
  name: string;
  description: string | null;
  unit_price: number | string | null;
  price_type: string | null;
  allergens: string[];
  tags: string[];
  menu_categories: { name: string; sort_order: number } | null;
  menu_item_dishes: { sort_order: number; dishes: Dish }[];
}

function price(item: MenuItem): string {
  const n = typeof item.unit_price === 'string' ? parseFloat(item.unit_price) : item.unit_price ?? 0;
  const suffix =
    item.price_type === 'per_person' ? '/person'
    : item.price_type === 'per_unit' ? '/unit'
    : item.price_type === 'per_hour' ? '/hour'
    : '';
  return `$${n.toFixed(2)}${suffix}`;
}

export default function MenuPage() {
  const [items, setItems] = useState<MenuItem[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<any, MenuItem[]>('/inventory/menu-feed')
      .then(setItems)
      .catch((e) => setErr(e?.message || 'Failed to load menu'));
  }, []);

  const byCategory = useMemo(() => {
    if (!items) return [] as { name: string; sort_order: number; items: MenuItem[] }[];
    const groups = new Map<string, { name: string; sort_order: number; items: MenuItem[] }>();
    for (const item of items) {
      const key = item.menu_categories?.name || 'Uncategorized';
      const sort = item.menu_categories?.sort_order ?? 999;
      if (!groups.has(key)) groups.set(key, { name: key, sort_order: sort, items: [] });
      groups.get(key)!.items.push(item);
    }
    return Array.from(groups.values()).sort((a, b) => a.sort_order - b.sort_order);
  }, [items]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/chat" className="text-gray-600 hover:text-gray-900 transition">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Our Menus</h1>
              <p className="text-sm text-gray-600 mt-1">Explore our catering options — dishes, ingredients, allergens.</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {err && (
          <div className="mb-6 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            <AlertCircle className="h-4 w-4" /> {err}
          </div>
        )}

        {!items && !err && <div className="py-20 text-center text-gray-500">Loading menu…</div>}

        {items && items.length === 0 && (
          <div className="py-20 text-center text-gray-500 text-sm">
            Menu is empty. Run the seed script to populate items.
          </div>
        )}

        {byCategory.map((cat) => (
          <section key={cat.name} className="mb-10">
            <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <UtensilsCrossed className="w-4 h-4 text-gray-500" />
              {cat.name}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {cat.items.map((item) => (
                <div
                  key={item.id}
                  className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition"
                >
                  <div className="p-5">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <h3 className="text-base font-semibold text-gray-900">{item.name}</h3>
                        {item.tags.length > 0 && (
                          <div className="mt-1 flex flex-wrap gap-1">
                            {item.tags.map((t) => (
                              <span key={t} className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                                {t}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="text-sm font-semibold text-gray-900 whitespace-nowrap">{price(item)}</div>
                    </div>

                    {item.menu_item_dishes.length > 0 && (
                      <div className="mt-4">
                        <div className="text-xs font-medium text-gray-500 mb-2">Includes</div>
                        <ul className="space-y-1.5">
                          {item.menu_item_dishes
                            .slice()
                            .sort((a, b) => a.sort_order - b.sort_order)
                            .map(({ dishes: dish }) => (
                              <li key={dish.id} className="text-sm text-gray-700">
                                <div className="flex items-center justify-between gap-2">
                                  <span>{dish.name}</span>
                                  {dish.dish_ingredients.length > 0 && (
                                    <span className="text-xs text-gray-400">
                                      {dish.dish_ingredients.length} ingredient
                                      {dish.dish_ingredients.length === 1 ? '' : 's'}
                                    </span>
                                  )}
                                </div>
                                {dish.dish_ingredients.length > 0 && (
                                  <div className="mt-0.5 ml-2 flex flex-wrap gap-1">
                                    {dish.dish_ingredients.map((di) => (
                                      <span
                                        key={di.ingredient_id}
                                        className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 text-xs rounded flex items-center gap-1"
                                      >
                                        <Leaf className="w-2.5 h-2.5" />
                                        {di.ingredients.name}
                                      </span>
                                    ))}
                                  </div>
                                )}
                              </li>
                            ))}
                        </ul>
                      </div>
                    )}

                    {item.menu_item_dishes.length === 0 && item.description && (
                      <p className="mt-3 text-sm text-gray-600">{item.description}</p>
                    )}

                    {item.allergens.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1">
                        {item.allergens.map((a) => (
                          <span key={a} className="px-1.5 py-0.5 bg-amber-50 text-amber-700 text-xs rounded">
                            ⚠ {a}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}

        <div className="mt-12 bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Need a Custom Menu?</h2>
          <p className="text-gray-600 mb-6">Our chefs can create a personalized menu tailored to your event</p>
          <Link
            href="/chat"
            className="inline-flex items-center gap-2 px-6 py-3 bg-black text-white font-semibold rounded-lg hover:bg-neutral-800 transition"
          >
            Start Planning Your Event
            <ChevronRight className="w-5 h-5" />
          </Link>
        </div>
      </main>
    </div>
  );
}

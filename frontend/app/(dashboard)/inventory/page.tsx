"use client";

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { RoleGuard } from '@/components/auth/RoleGuard';
import { apiClient } from '@/lib/api/client';
import {
  Beef,
  Utensils,
  Plus,
  Trash2,
  PackagePlus,
  AlertCircle,
  X,
  Link2,
  Search,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Ingredient {
  id: string;
  name: string;
  calories_per_100g: number | string | null;
  carbs_g_per_100g: number | string | null;
  protein_g_per_100g: number | string | null;
  fat_g_per_100g: number | string | null;
  allergens: string[];
  default_unit: string;
  default_price: number | string | null;
  created_at: string;
}

interface DishLink {
  menu_item_id: string;
  sort_order: number;
  menu_items: { id: string; name: string };
}

interface DishIngredient {
  dish_id: string;
  ingredient_id: string;
  weight_g: number | string | null;
  volume_ml: number | string | null;
  notes: string | null;
  ingredients: Ingredient;
}

interface Dish {
  id: string;
  name: string;
  description: string | null;
  dish_ingredients: DishIngredient[];
  menu_item_dishes: DishLink[];
}

function toNum(v: number | string | null | undefined): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return Number.isFinite(n) ? n : null;
}

export default function InventoryPage() {
  return (
    <RoleGuard role="staff">
      <InventoryContent />
    </RoleGuard>
  );
}

function InventoryContent() {
  const [tab, setTab] = useState<'ingredients' | 'dishes'>('ingredients');
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [dishes, setDishes] = useState<Dish[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreateIngredient, setShowCreateIngredient] = useState(false);
  const [stockLogFor, setStockLogFor] = useState<Ingredient | null>(null);
  const [linkIngredientFor, setLinkIngredientFor] = useState<Dish | null>(null);

  const reload = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ing, dsh] = await Promise.all([
        apiClient.get<any, Ingredient[]>('/inventory/ingredients'),
        apiClient.get<any, Dish[]>('/inventory/dishes'),
      ]);
      setIngredients(ing);
      setDishes(dsh);
    } catch (e: any) {
      setError(e?.message || 'Failed to load inventory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  const dishesWithRecipe = dishes.filter((d) => d.dish_ingredients.length > 0).length;
  const dishesMissingRecipe = dishes.length - dishesWithRecipe;

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Inventory</h1>
          <p className="text-sm text-neutral-600 mt-1">
            Ingredients, dishes, and stock tracking for the catering operation.
          </p>
        </div>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
        <StatCard label="Ingredients" value={ingredients.length} hint="raw inputs" />
        <StatCard label="Dishes" value={dishes.length} hint="reusable cooked items" />
        <StatCard label="With recipe" value={dishesWithRecipe} hint="dishes linked to ingredients" accent="emerald" />
        <StatCard label="Missing recipe" value={dishesMissingRecipe} hint="need ingredient links" accent={dishesMissingRecipe > 0 ? 'amber' : undefined} />
      </div>

      <div className="flex gap-1 p-1 mb-6 bg-neutral-100 rounded-lg w-fit">
        <button
          onClick={() => setTab('ingredients')}
          className={cn(
            'flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-colors',
            tab === 'ingredients' ? 'bg-white text-black shadow-sm' : 'text-neutral-600 hover:text-black',
          )}
        >
          <Beef className="h-4 w-4" /> Ingredients
          <span className="text-xs text-neutral-400">({ingredients.length})</span>
        </button>
        <button
          onClick={() => setTab('dishes')}
          className={cn(
            'flex items-center gap-2 px-4 py-1.5 rounded-md text-sm font-medium transition-colors',
            tab === 'dishes' ? 'bg-white text-black shadow-sm' : 'text-neutral-600 hover:text-black',
          )}
        >
          <Utensils className="h-4 w-4" /> Dishes
          <span className="text-xs text-neutral-400">({dishes.length})</span>
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          <AlertCircle className="h-4 w-4" />
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center text-neutral-500">Loading…</div>
      ) : tab === 'ingredients' ? (
        <IngredientsTab
          ingredients={ingredients}
          onCreate={() => setShowCreateIngredient(true)}
          onLogStock={(ing) => setStockLogFor(ing)}
          onChange={reload}
        />
      ) : (
        <DishesTab
          dishes={dishes}
          onLinkIngredient={(dish) => setLinkIngredientFor(dish)}
          onChange={reload}
        />
      )}

      {showCreateIngredient && (
        <CreateIngredientModal
          onClose={() => setShowCreateIngredient(false)}
          onCreated={() => {
            setShowCreateIngredient(false);
            reload();
          }}
        />
      )}

      {stockLogFor && (
        <LogStockModal
          ingredient={stockLogFor}
          onClose={() => setStockLogFor(null)}
          onLogged={() => {
            setStockLogFor(null);
            reload();
          }}
        />
      )}

      {linkIngredientFor && (
        <LinkIngredientModal
          dish={linkIngredientFor}
          ingredients={ingredients}
          onClose={() => setLinkIngredientFor(null)}
          onLinked={() => {
            setLinkIngredientFor(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

// ─── StatCard ──────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: number;
  hint?: string;
  accent?: 'emerald' | 'amber';
}) {
  const accentCls =
    accent === 'emerald' ? 'text-emerald-700'
    : accent === 'amber' ? 'text-amber-700'
    : 'text-neutral-900';
  return (
    <div className="bg-white rounded-xl border border-neutral-200 px-4 py-3">
      <div className="text-xs font-medium text-neutral-500">{label}</div>
      <div className={cn('text-2xl font-semibold mt-0.5', accentCls)}>{value}</div>
      {hint && <div className="text-xs text-neutral-400 mt-0.5">{hint}</div>}
    </div>
  );
}

// ─── Ingredients tab ────────────────────────────────────────────────────────

function IngredientsTab({
  ingredients,
  onCreate,
  onLogStock,
  onChange,
}: {
  ingredients: Ingredient[];
  onCreate: () => void;
  onLogStock: (ing: Ingredient) => void;
  onChange: () => void;
}) {
  const handleDelete = async (ing: Ingredient) => {
    if (!confirm(`Delete ingredient "${ing.name}"? All dish links and stock logs will be removed.`)) return;
    try {
      await apiClient.delete(`/inventory/ingredients/${ing.id}`);
      onChange();
    } catch (e: any) {
      alert(e?.message || 'Delete failed');
    }
  };

  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-neutral-100">
        <h2 className="text-sm font-semibold text-neutral-900">Ingredients</h2>
        <button
          onClick={onCreate}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-black text-white text-sm rounded-md hover:bg-neutral-800"
        >
          <Plus className="h-3.5 w-3.5" /> New ingredient
        </button>
      </div>

      {ingredients.length === 0 ? (
        <div className="py-16 text-center text-neutral-500 text-sm">
          No ingredients yet. Click "New ingredient" to add one.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-neutral-600 text-xs uppercase tracking-wide">
              <tr>
                <th className="px-4 py-2 text-left">Name</th>
                <th className="px-4 py-2 text-right">Cal / 100g</th>
                <th className="px-4 py-2 text-right">Carbs</th>
                <th className="px-4 py-2 text-right">Protein</th>
                <th className="px-4 py-2 text-right">Fat</th>
                <th className="px-4 py-2 text-left">Allergens</th>
                <th className="px-4 py-2 text-right">Price / Unit</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {ingredients.map((ing) => (
                <tr key={ing.id} className="border-t border-neutral-100 hover:bg-neutral-50/50">
                  <td className="px-4 py-2.5 font-medium text-neutral-900">{ing.name}</td>
                  <td className="px-4 py-2.5 text-right text-neutral-700">{toNum(ing.calories_per_100g) ?? '—'}</td>
                  <td className="px-4 py-2.5 text-right text-neutral-700">{toNum(ing.carbs_g_per_100g) ?? '—'}g</td>
                  <td className="px-4 py-2.5 text-right text-neutral-700">{toNum(ing.protein_g_per_100g) ?? '—'}g</td>
                  <td className="px-4 py-2.5 text-right text-neutral-700">{toNum(ing.fat_g_per_100g) ?? '—'}g</td>
                  <td className="px-4 py-2.5">
                    {ing.allergens.length === 0 ? (
                      <span className="text-neutral-400">—</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {ing.allergens.map((a) => (
                          <span key={a} className="px-1.5 py-0.5 bg-amber-50 text-amber-700 text-xs rounded">
                            {a}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right text-neutral-700">
                    {toNum(ing.default_price) !== null ? `$${toNum(ing.default_price)!.toFixed(2)}/${ing.default_unit}` : '—'}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => onLogStock(ing)}
                        title="Log stock"
                        className="p-1.5 text-neutral-500 hover:text-black hover:bg-neutral-100 rounded"
                      >
                        <PackagePlus className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(ing)}
                        title="Delete"
                        className="p-1.5 text-neutral-500 hover:text-red-600 hover:bg-red-50 rounded"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Dishes tab ─────────────────────────────────────────────────────────────

function DishesTab({
  dishes,
  onLinkIngredient,
  onChange,
}: {
  dishes: Dish[];
  onLinkIngredient: (dish: Dish) => void;
  onChange: () => void;
}) {
  const [filter, setFilter] = useState('');
  const filtered = useMemo(
    () => dishes.filter((d) => d.name.toLowerCase().includes(filter.toLowerCase())),
    [dishes, filter],
  );

  const handleUnlink = async (dishId: string, ingredientId: string) => {
    try {
      await apiClient.delete(`/inventory/dishes/${dishId}/ingredients/${ingredientId}`);
      onChange();
    } catch (e: any) {
      alert(e?.message || 'Unlink failed');
    }
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
          <input
            placeholder="Filter dishes…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm border border-neutral-200 rounded-md focus:outline-none focus:ring-2 focus:ring-black/10"
          />
        </div>
        <span className="text-xs text-neutral-500 whitespace-nowrap">
          {filtered.length} of {dishes.length}
        </span>
      </div>

      {filtered.length === 0 ? (
        <div className="bg-white rounded-xl border border-neutral-200 py-16 text-center text-neutral-500 text-sm">
          {dishes.length === 0
            ? 'No dishes yet. Run the seed script or add one manually.'
            : 'No dishes match your filter.'}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filtered.map((dish) => {
            const hasRecipe = dish.dish_ingredients.length > 0;
            return (
            <div key={dish.id} className="bg-white rounded-xl border border-neutral-200 p-4 hover:border-neutral-300 transition">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-neutral-900 truncate">{dish.name}</h3>
                    {hasRecipe && (
                      <span className="px-1.5 py-0.5 bg-emerald-50 text-emerald-700 text-[10px] rounded uppercase tracking-wide shrink-0">
                        recipe
                      </span>
                    )}
                  </div>
                  {dish.menu_item_dishes.length > 0 && (
                    <div className="text-xs text-neutral-500 mt-1">
                      {dish.menu_item_dishes
                        .slice(0, 2)
                        .map((m) => m.menu_items.name)
                        .join(', ')}
                      {dish.menu_item_dishes.length > 2 &&
                        ` +${dish.menu_item_dishes.length - 2} more`}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => onLinkIngredient(dish)}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs bg-neutral-100 hover:bg-neutral-200 rounded-md shrink-0"
                >
                  <Link2 className="h-3 w-3" />
                  Add ingredient
                </button>
              </div>

              {dish.dish_ingredients.length === 0 ? (
                <div className="mt-3 text-xs text-neutral-400">No ingredients linked yet.</div>
              ) : (
                <ul className="mt-3 space-y-1.5">
                  {dish.dish_ingredients.map((di) => (
                    <li
                      key={di.ingredient_id}
                      className="flex items-center justify-between text-sm bg-neutral-50 rounded-md px-3 py-1.5"
                    >
                      <div>
                        <span className="font-medium text-neutral-800">{di.ingredients.name}</span>
                        <span className="ml-2 text-neutral-500 text-xs">
                          {toNum(di.weight_g) !== null ? `${toNum(di.weight_g)}g` : ''}
                          {toNum(di.volume_ml) !== null ? `${toNum(di.volume_ml)}ml` : ''}
                        </span>
                      </div>
                      <button
                        onClick={() => handleUnlink(dish.id, di.ingredient_id)}
                        className="text-neutral-400 hover:text-red-600"
                        title="Unlink"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Modals ────────────────────────────────────────────────────────────────

function ModalShell({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-3 border-b border-neutral-100">
          <h3 className="text-sm font-semibold text-neutral-900">{title}</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-black">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

function CreateIngredientModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState('');
  const [cal, setCal] = useState('');
  const [carbs, setCarbs] = useState('');
  const [protein, setProtein] = useState('');
  const [fat, setFat] = useState('');
  const [allergens, setAllergens] = useState('');
  const [unit, setUnit] = useState<'g' | 'ml'>('g');
  const [price, setPrice] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      await apiClient.post('/inventory/ingredients', {
        name: name.trim(),
        calories_per_100g: cal ? parseFloat(cal) : null,
        carbs_g_per_100g: carbs ? parseFloat(carbs) : null,
        protein_g_per_100g: protein ? parseFloat(protein) : null,
        fat_g_per_100g: fat ? parseFloat(fat) : null,
        allergens: allergens
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        default_unit: unit,
        default_price: price ? parseFloat(price) : null,
      });
      onCreated();
    } catch (e: any) {
      setErr(e?.message || 'Create failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="New ingredient" onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Name" required>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
          />
        </Field>
        <div className="grid grid-cols-4 gap-2">
          <Field label="Cal/100g"><NumInput value={cal} onChange={setCal} /></Field>
          <Field label="Carbs (g)"><NumInput value={carbs} onChange={setCarbs} /></Field>
          <Field label="Protein (g)"><NumInput value={protein} onChange={setProtein} /></Field>
          <Field label="Fat (g)"><NumInput value={fat} onChange={setFat} /></Field>
        </div>
        <Field label="Allergens (comma-separated)">
          <input
            value={allergens}
            onChange={(e) => setAllergens(e.target.value)}
            placeholder="dairy, gluten"
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
          />
        </Field>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Default unit">
            <select
              value={unit}
              onChange={(e) => setUnit(e.target.value as 'g' | 'ml')}
              className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
            >
              <option value="g">g</option>
              <option value="ml">ml</option>
            </select>
          </Field>
          <Field label={`Default price / ${unit}`}>
            <NumInput value={price} onChange={setPrice} />
          </Field>
        </div>
        {err && <div className="text-xs text-red-600">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-neutral-600 hover:text-black">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !name.trim()}
            className="px-4 py-1.5 bg-black text-white text-sm rounded-md hover:bg-neutral-800 disabled:opacity-50"
          >
            {submitting ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function LogStockModal({
  ingredient,
  onClose,
  onLogged,
}: {
  ingredient: Ingredient;
  onClose: () => void;
  onLogged: () => void;
}) {
  const [delta, setDelta] = useState('');
  const [source, setSource] = useState<'staff_manual' | 'purchase' | 'consumption' | 'waste'>('staff_manual');
  const [price, setPrice] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const unit = ingredient.default_unit;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      const n = parseFloat(delta);
      if (!Number.isFinite(n)) throw new Error('Enter a valid amount');
      await apiClient.post('/inventory/stock-log', {
        ingredient_id: ingredient.id,
        delta_g: unit === 'g' ? n : null,
        delta_ml: unit === 'ml' ? n : null,
        unit_price: price ? parseFloat(price) : null,
        source,
        notes: notes || null,
      });
      onLogged();
    } catch (e: any) {
      setErr(e?.message || 'Log failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title={`Log stock — ${ingredient.name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-3">
        <Field label={`Delta (${unit}) — positive adds, negative removes`} required>
          <input
            autoFocus
            type="number"
            step="any"
            value={delta}
            onChange={(e) => setDelta(e.target.value)}
            required
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
          />
        </Field>
        <Field label="Source">
          <select
            value={source}
            onChange={(e) => setSource(e.target.value as any)}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
          >
            <option value="staff_manual">Manual adjustment</option>
            <option value="purchase">Purchase</option>
            <option value="consumption">Consumption</option>
            <option value="waste">Waste</option>
          </select>
        </Field>
        <Field label={`Unit price (per ${unit})`}>
          <NumInput value={price} onChange={setPrice} />
        </Field>
        <Field label="Notes">
          <input
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
          />
        </Field>
        {err && <div className="text-xs text-red-600">{err}</div>}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-neutral-600 hover:text-black">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting || !delta}
            className="px-4 py-1.5 bg-black text-white text-sm rounded-md hover:bg-neutral-800 disabled:opacity-50"
          >
            {submitting ? 'Logging…' : 'Log stock'}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

function LinkIngredientModal({
  dish,
  ingredients,
  onClose,
  onLinked,
}: {
  dish: Dish;
  ingredients: Ingredient[];
  onClose: () => void;
  onLinked: () => void;
}) {
  const alreadyLinkedIds = new Set(dish.dish_ingredients.map((d) => d.ingredient_id));
  const available = ingredients.filter((i) => !alreadyLinkedIds.has(i.id));

  const [ingredientId, setIngredientId] = useState(available[0]?.id || '');
  const [weight, setWeight] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const selected = ingredients.find((i) => i.id === ingredientId);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ingredientId) return;
    setSubmitting(true);
    setErr(null);
    try {
      const amount = weight ? parseFloat(weight) : null;
      await apiClient.post(`/inventory/dishes/${dish.id}/ingredients`, {
        ingredient_id: ingredientId,
        weight_g: selected?.default_unit === 'g' ? amount : null,
        volume_ml: selected?.default_unit === 'ml' ? amount : null,
        notes: notes || null,
      });
      onLinked();
    } catch (e: any) {
      setErr(e?.message || 'Link failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title={`Add ingredient to "${dish.name}"`} onClose={onClose}>
      {available.length === 0 ? (
        <div className="text-sm text-neutral-600">
          All ingredients are already linked to this dish. Create a new ingredient first.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <Field label="Ingredient" required>
            <select
              value={ingredientId}
              onChange={(e) => setIngredientId(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
            >
              {available.map((i) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label={`Amount (${selected?.default_unit || 'g'})`}>
            <NumInput value={weight} onChange={setWeight} />
          </Field>
          <Field label="Notes">
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
            />
          </Field>
          {err && <div className="text-xs text-red-600">{err}</div>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm text-neutral-600 hover:text-black">
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-1.5 bg-black text-white text-sm rounded-md hover:bg-neutral-800 disabled:opacity-50"
            >
              {submitting ? 'Linking…' : 'Link ingredient'}
            </button>
          </div>
        </form>
      )}
    </ModalShell>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-xs font-medium text-neutral-700">
      <span>
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function NumInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="number"
      step="any"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-md"
    />
  );
}

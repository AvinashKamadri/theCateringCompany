# Allergen Derivation — Architecture & Plan

**Status:** Slice 1 implemented (backend derivation + fan-out + backfill).
**Owner:** Backend (NestJS) writes, ml-agent reads, LLM presents.
**Date:** 2026-04-25

---

## 1. Why this exists

Dietary allergen filtering is a safety-critical feature. The wrong answer
isn't a UX bug — it's a liability. The earlier proposal (LLM-tag every menu
item by name at seed time) is unsafe for three reasons:

1. **Probabilistic.** "Chicken Satay" usually contains peanuts, but the
   model has no guarantee — and it can't see what the actual kitchen puts in.
2. **Drifts from truth.** Staff already maintain `ingredients.allergens` via
   the inventory UI. LLM tags create a parallel, inconsistent source.
3. **Not auditable.** Why did the model decide a dish was nut-free? No trace.

The right answer is **derivation from structured data** that staff already
maintain. The LLM never decides safety; it only formats results.

---

## 2. The schema is already correct

Backend Prisma already models the full graph
([backend/prisma/schema.prisma](../../backend/prisma/schema.prisma) lines 1291–1343):

```
ingredients (allergens String[])           ← staff-maintained truth
   └── dish_ingredients (junction)
         └── dishes
              └── menu_item_dishes (junction)
                    └── menu_items (allergens String[])  ← derived cache
```

`menu_items.allergens` already existed as a column. It was unused. We now
treat it as a **denormalized cache** populated only by derivation.

---

## 2a. Authoring policy (locked in)

- **Staff write allergens only at the ingredient level.** Inventory UI is
  the only place to enter or edit allergen tags.
- **Dishes have no allergens column.** Confirmed in schema — nothing to
  remove or hide.
- **Menu items never accept hand-entered allergens.** No runtime endpoint
  writes `menu_items.allergens`; it's a derived cache only.
- **Existing menu structure is preserved.** We do not delete menu items,
  categories, dishes, or links to "fix" anything. Gaps are filled by adding
  missing ingredient links in the inventory UI — not by reshaping the menu.
- **The seed script no longer hardcodes menu-item allergens.** It runs a
  derivation pass at the end (`deriveAllergens()` in `seed-menu.ts`) so
  the values come from the graph, not from guesses in the menu JSON.

## 3. Architectural truth

| Layer | Owns | Must NOT do |
|---|---|---|
| **Backend (NestJS)** | Ingredient truth, graph traversal, derivation, cache writes | Let any code outside the derivation service write `menu_items.allergens` |
| **ml-agent (Python)** | Filtering (`WHERE NOT (allergens && [...])`), response shaping | Traverse the graph at request time, reason about safety |
| **LLM** | Wording the response | Decide which dishes are safe |

This split has one consequence worth stating plainly: **the AI is not a
safety net.** If the DB is wrong, the AI is wrong. All correctness lives
in the backend derivation layer.

---

## 4. The five safeguards (locked in)

1. **Single writer rule.** Only `MenuAllergenDerivationService` writes
   `menu_items.allergens`. Enforced by convention + code review.
2. **Idempotent recompute.** Same input graph → same output. The service
   compares before writing and skips no-op updates.
3. **Fan-out correctness.** Every mutation that can affect derivation
   triggers a recompute. Mapped exhaustively in §5.
4. **Snapshot before deletes.** `ingredients.delete` cascades through
   `dish_ingredients`, destroying the path back to affected menu_items.
   The service captures affected IDs **before** the delete.
5. **Structured anomaly logs.** Every gap in the graph (menu_item with no
   dishes, dish with no ingredients, no allergens derived) emits a
   structured warn log with id + name. No silent failures.

---

## 5. Fan-out map (every path that can drift the cache)

| Mutation | File:Line | Recompute action |
|---|---|---|
| `ingredients.create` | inventory.service.ts:71 | None — ingredient not yet linked |
| `ingredients.update` (allergens changed) | inventory.service.ts:88 | `recomputeForIngredient(id)` |
| `ingredients.delete` | inventory.service.ts:106 | Snapshot affected → delete → `recomputeMany(ids)` |
| `dish_ingredients.upsert` | inventory.service.ts:157 | `recomputeForDish(dishId)` |
| `dish_ingredients.delete` | inventory.service.ts:178 | `recomputeForDish(dishId)` |
| `menu_item_dishes.create/deleteMany` | scripts/seed-menu.ts:445,479 | `deriveAllergens()` runs at end of seed |

There are no other write paths today. If new ones are added, the rule is:
**you must call the derivation service in the same transaction.**

---

## 6. The derivation service

[backend/src/inventory/menu-allergen-derivation.service.ts](../../backend/src/inventory/menu-allergen-derivation.service.ts)

Public surface:

| Method | Use case |
|---|---|
| `recomputeForMenuItem(id)` | Atomic primitive — updates one menu_item |
| `recomputeForDish(dishId)` | Fan-out from dish change |
| `recomputeForIngredient(id)` | Fan-out from ingredient change (post-mutation) |
| `findMenuItemsAffectedByIngredient(id)` | Snapshot before ingredient delete |
| `recomputeMany(ids)` | Batch primitive used by the fan-out methods |
| `recomputeAll()` | Backfill / drift recovery |
| `healthCheck()` | Returns counts + samples for the three known gap conditions |

Internals: walks the graph in a single Prisma query, unions allergen
strings (lowercased + trimmed), sorts deterministically, and writes only
when the result differs from the stored array.

---

## 7. Backfill / recovery

[backend/src/scripts/recompute-menu-allergens.ts](../../backend/src/scripts/recompute-menu-allergens.ts)

```bash
npx ts-node backend/src/scripts/recompute-menu-allergens.ts            # backfill
npx ts-node backend/src/scripts/recompute-menu-allergens.ts --health   # + data health probe
```

Idempotent. Safe to run anytime. Run it:

- After `seed-menu.ts` (which mass-rewrites `menu_item_dishes`).
- After any bulk ingredient import.
- Periodically (e.g. nightly) as a drift sentinel.
- Whenever data looks wrong — it's the "fix everything" button.

---

## 8. What's still TODO

### Slice 2 — ml-agent filter ✅ done

Implemented as a **post-fetch transform** rather than a Prisma `where` clause.
Reason: the menu is cached process-wide for 120s and shared across users. A
DB-side filter would either bust the cache per-session or require per-session
caches — both worse than filtering the small in-memory result.

What landed in [ml-agent/agent/menu_resolver.py](../../ml-agent/agent/menu_resolver.py):

- `filter_excluded_allergens(menu, excluded)` — hard exclusion (item disappears)
- `annotate_allergen_safety(items, excluded)` — soft annotation (`is_safe`,
  `unsafe_allergens` per item) for the S19 review path
- `load_main_dish_menu`, `load_appetizer_menu`, `load_dessert_menu_expanded`
  all accept optional `excluded_allergens=…`. Default behavior unchanged.

What landed in [ml-agent/agent/tools/menu_selection_tool.py](../../ml-agent/agent/tools/menu_selection_tool.py):

- `_user_excluded_allergens(slots)` reads `dietary_concerns` slot. Tolerant
  of both `list[str]` (post-Slice 3 schema) and legacy free-text.
- All 6 user-facing menu paths (3 resolution sites + 3 picker-display sites)
  now pass the user's exclusions through. Unsafe items never appear.

Still TODO inside Slice 2: review path. At S19, surface `is_safe`/
`unsafe_allergens` in the recap so the LLM reads a flag rather than
interpreting the array. Hook in `finalization_tool._render_review_recap`.

### Slice 2.5 — modification_tool wiring

[ml-agent/agent/tools/modification_tool.py](../../ml-agent/agent/tools/modification_tool.py)
also calls `load_*` (8 sites). Same one-line change per site — pass
`excluded_allergens=_user_excluded_allergens(slots)`. Defer until Slice 3
lands the structured slot type so we don't refactor twice.

### Slice 3 — collection UX

The `multi_select` checklist + `AllergenCategory` enum from the original
`Dietary Allergen Filtering plan.md`. Now wired to a real, deterministic filter
instead of an LLM heuristic.

### LLM-facing contract (where `is_safe` is mandatory)

The picker UI is hard-filtered, so by construction every item shown is safe
and the flag would be redundant. The contract — every item carries
`{ allergens, is_safe, unsafe_allergens }` — is **mandatory wherever items
reach the LLM as decision context**:

- S19 review recap (finalization_tool — Slice 3)
- conflict warnings when previously-selected items clash with newly-set
  dietary concerns (cross-target capture path)
- modification_tool surfaces (Slice 2.5)

In each of these the LLM must read a boolean; it must not interpret arrays.
Use `annotate_allergen_safety(items, excluded)` from menu_resolver — it
returns new dicts with the flags attached, no mutation.

### Three-state correctness (Slice 3 prerequisite)

`annotate_allergen_safety` today produces only two states:

- `unsafe_allergens` non-empty → `is_safe = false`
- `unsafe_allergens` empty → `is_safe = true`

The second branch silently absorbs the **unknown** case (item with `[]`
allergens because its graph is incomplete). That's tolerable for testing
but **not safe for production**. Slice 3 fixes this:

- `menu_items.allergen_confidence: 'derived' | 'incomplete'`
- `incomplete` items are excluded from `filter_excluded_allergens` whenever
  any dietary concern is set (fail-closed: unknown = unsafe)
- `annotate_allergen_safety` reads the flag and returns
  `{ is_safe: false, unsafe_allergens: ['unknown'] }` for `incomplete` items
  when the user has any concern

Slice 3 is **not optional**.

### Slice 4 — confidence flag (deferred)

Add `menu_items.allergen_confidence: 'derived' | 'incomplete'`:

- `derived` — at least one dish with at least one ingredient
- `incomplete` — menu_item has no dishes, or dishes have no ingredients

Requires:
1. Prisma schema migration (new column + enum).
2. Derivation service writes the flag alongside the array.
3. Strict mode in the filter: `incomplete` items are excluded when the user
   has any dietary restriction (fail-safe — unknown = unsafe).
4. Inventory UI surfaces the flag so staff can see what needs tagging.

Deferred to keep Slice 1 a pure backend change with no migration.

---

## 9. Why this generalizes

This isn't really about allergens. It's a **derived data system**. The same
pattern will later power:

- Dietary filters (vegan, halal, kosher) — same graph, different tags
- Pricing rollups — sum ingredient costs through the same path
- Nutrition summaries — sum macros through the same path
- Availability logic — propagate ingredient stockouts

Getting the derivation primitive right now means each future feature is a
small extension, not a re-architecture.

---

## 10. Pushback / things explicitly rejected

- ❌ LLM-tagging dish names at seed time. (Probabilistic, drifts, not auditable.)
- ❌ Computing the join at request time. (Expensive, not indexable, repeated work.)
- ❌ Using Qdrant / RAG for allergens. (This problem is structured, not semantic.)
- ❌ Letting the LLM interpret allergen arrays in tool output. (Subtle wording bugs.)
- ❌ Letting any code outside the derivation service write `menu_items.allergens`.

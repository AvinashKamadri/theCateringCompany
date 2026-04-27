# Allergen-Aware Menu Filtering — Implementation Reference

This document captures the end-to-end allergen-safety system in the
catering agent: how items get classified, how the chat surface filters
them, and how the fallback UX recovers when the strict filter leaves a
slot empty or the user requests something unsafe.

It supersedes the older slice-by-slice notes — read this if you're about
to touch any `load_*`, `resolve_*`, or modification "add" path.

---

## 1. Architectural rule (one-liner)

> Allergen safety is **derived from data**, **enforced at every menu
> entry point**, and **fails closed** when data is incomplete.

Three primitives carry the entire contract:

| Primitive | Lives in | Role |
|---|---|---|
| `menu_items.allergen_confidence` | Postgres enum (`derived` \| `incomplete`) | Per-item trust signal — written only by the derivation service |
| `_user_excluded_allergens(slots)` | `agent/tools/menu_selection_tool.py` | The single source of truth for "what is the user excluding right now" |
| `filter_excluded_allergens(menu, excluded)` | `agent/menu_resolver.py` | The single hard filter — applied post-fetch on every menu read |

Everything else (pickers, modification flows, review recap) is a caller
of these three.

---

## 2. Data layer — where allergens come from

### Schema

```
ingredients.allergens (TEXT[])      — source of truth, hand-curated
   │
   ▼
dish_ingredients   (M-N join)
   │
   ▼
dishes
   │
   ▼
menu_item_dishes   (M-N join)
   │
   ▼
menu_items.allergens               — DENORMALIZED CACHE
menu_items.allergen_confidence     — `derived` if every link in the
                                     graph above resolves; `incomplete`
                                     if any dish has no ingredients or
                                     any ingredient has null allergens
```

### Single writer

Only `MenuAllergenDerivationService`
(`backend/src/inventory/menu-allergen-derivation.service.ts`) writes
`menu_items.allergens` and `menu_items.allergen_confidence`. It runs:

- **On inventory mutations** — fanned out from any change that touches
  `ingredients`, `dish_ingredients`, or `menu_item_dishes`.
- **At seed time** — `prisma.menu_items.deriveAllergens()` after
  `seed:menu`.
- **On demand** — `recompute-menu-allergens.ts --health` for audits.

LLM tagging was rejected: it's probabilistic and non-auditable, and
allergen filtering is safety-critical.

### Three states

| Confidence | `allergens` | Meaning |
|---|---|---|
| `derived` | `[]` | Graph complete, no allergens — **safe** |
| `derived` | `['dairy', ...]` | Graph complete, has these allergens |
| `incomplete` | `[]` | Graph broken somewhere — **unknown, treat as unsafe** |

The `incomplete` state is the load-bearing one. Without it, "no
allergens listed" would be ambiguous between "safe" and "we don't know."

---

## 3. Filter contract

`filter_excluded_allergens(menu, excluded_allergens)` is the only place
where unsafe items are dropped. The rule:

```
keep item ⇔ (no excluded set)
          ∨ (item.confidence == 'derived' ∧ no overlap with excluded)
```

Equivalently — when the user has any concern set, **`incomplete` items
are dropped wholesale**. This is the fail-closed default: unknown is
treated as unsafe.

`annotate_allergen_safety(items, excluded)` is the soft variant for
review/recap surfaces. It returns three booleans per item so the LLM
reads truth values, not allergen arrays:

| State | `is_safe` | `unsafe_allergens` |
|---|---|---|
| `incomplete` + concerns set | `False` | `['unknown']` |
| `derived` + overlap | `False` | the overlapping allergens |
| `derived` + no overlap | `True` | `[]` |

---

## 4. The guard — fail-loud-in-dev / fail-CLOSED-in-prod

Lives at `agent/menu_resolver.py:38-58`. Wraps every public menu entry
point: `load_appetizer_menu`, `load_main_dish_menu`,
`load_dessert_menu_expanded`, `resolve_dessert_choices`,
`resolve_desserts`.

### Why a guard at all

A future caller might forget to thread `excluded_allergens` through —
that's a silent bypass. The guard turns the missing kwarg into a loud
crash in dev (caught in tests/PR review) and a logged + fail-closed
fallback in prod (no unsafe item served, even if a deploy ships with a
forgotten plumbing site).

### Mechanics

```python
_UNSET = object()  # distinguishes "default" from "explicit None/[]"

def _guard_excluded(arg, fn_name):
    if arg is _UNSET:
        env = os.getenv("ML_ENV", os.getenv("NODE_ENV", "production")).lower()
        if env != "production":
            raise ValueError(f"{fn_name}: excluded_allergens is required ...")
        # PROD: fail CLOSED — exclude the entire FALCPA set
        _logger.critical("ALLERGEN_GUARD_TRIGGERED ...", extra={...})
        return ALL_ALLERGENS
    return arg
```

### `ALL_ALLERGENS`

```python
ALL_ALLERGENS = (
    "dairy", "egg", "fish", "shellfish", "tree_nuts",
    "peanuts", "wheat", "gluten", "soy", "sesame",
)
```

Forcing this set means: when a caller forgets the kwarg in prod, the
strict filter drops every `incomplete` item AND every `derived` item
that has any allergen at all. Worst case the user sees an empty/sparse
menu plus a `CRITICAL` log — never an unsafe item.

### Env defaulting

Default is `"production"` because the realistic failure mode in prod is
a missing env var, not a missing kwarg. Dev opts in to the loud crash
via `ML_ENV=development` in `ml-agent/.env`.

### Logging

```
CRITICAL ALLERGEN_GUARD_TRIGGERED fn=load_dessert_menu_expanded
         caller=/app/agent/tools/X.py:42 in some_func — FAIL-CLOSED, ...
extra={event, fn, caller, action: "fail_closed_all_falcpa"}
```

The caller frame is walked one level up so the alert names the actual
offender, not the guarded function.

---

## 5. Wiring — every call site

### ml-agent (chat surface)

| Caller | File:line | Passes `excluded_allergens` |
|---|---|---|
| Menu picker (selection) | `agent/tools/menu_selection_tool.py:885,994,1389,1401` | ✓ via `_user_excluded_allergens(slots)` |
| Modification picker | `agent/tools/modification_tool.py:3680,3688,3697` (`_render_slot_menu`) | ✓ |
| Modification slot menu | `agent/tools/modification_tool.py:3708,3711,3714` (`_menu_for_slot`) | ✓ |
| Modification dessert add | `agent/tools/modification_tool.py:1515,2484` (`resolve_dessert_choices`) | ✓ |
| Modification dessert format | `agent/tools/modification_tool.py:1834,2500` | ✓ |
| Review recap (S19) | `agent/tools/finalization_tool.py:_collect_dietary_review` | ✓ (annotation, not filter) |
| Unfiltered fetch for blocked-detection | `agent/tools/modification_tool.py:_unfiltered_slot_items` | Explicit `[]` (only used to *detect* blocking, never to select) |

### backend (DB layer)

- `MenuAllergenDerivationService` — the only writer
- `recompute-menu-allergens.ts` — backfill / health-check entry point
- `seed-perfect-dataset.ts` — 10-item fixture exercising
  safe / single / multi / nuts / seafood buckets

---

## 6. Fallback UX — making safe feel helpful

The strict filter is correct but brittle — an empty menu reads as
"system broken." The fallback layer adds guided recovery without
relaxing safety.

### 6.1 Empty-state copy (picker)

`_render_slot_menu` (`modification_tool.py`): when the filtered menu
returns no items AND the user has dietary concerns, render
`_empty_slot_fallback(kind, excluded)` instead of an empty string:

> I couldn't find any nut-free desserts on the current menu. You can
> skip this course, or reply with a custom request and we'll check with
> the kitchen.

Logs `allergen_fallback_used kind=desserts excluded=['tree_nuts']
reason=empty_slot` for observability.

### 6.2 Blocked-add suggestions (modification)

When the user says **"add tiramisu"** with a nut allergy:

1. The strict filter blocks Tiramisu — `resolve_dessert_choices`
   returns no match.
2. `_unfiltered_slot_items(slot, slots)` re-fetches the same slot with
   `excluded_allergens=[]` — used **only** to distinguish "blocked by
   safety" from "doesn't exist on the menu."
3. `_match_blocked_for_safety(name, unfiltered, excluded)` substring-
   matches the requested name against the unfiltered set and returns
   `{name, unsafe_allergens}` if it's an allergen block (vs `None` for
   genuinely-unknown items).
4. `safe_alternatives_from_items(unfiltered, excluded, exclude_names=[name], limit=3)`
   re-applies `filter_excluded_allergens` and returns up to 3 safe
   items in the same slot.
5. The blocked + alternatives summary is prepended to the modification
   ack:

   > ⚠ Tiramisu isn't safe for your dietary preferences (nut-free).
   > Safe alternatives: Fruit Tart, Lemon Bars, Sorbet Trio.

6. `response_context.modification.blocked_for_safety` carries the
   structured payload for downstream consumers / analytics.
7. Logs `allergen_fallback_used kind=desserts excluded=[...]
   reason=blocked_add requested='Tiramisu' unsafe=['tree_nuts']
   n_alts=3`.

### 6.3 Safety re-applied at every fallback

`safe_alternatives_from_items` always re-runs
`filter_excluded_allergens` internally — even if a buggy caller hands
it an unfiltered item list, the helper cannot return an unsafe
suggestion. There is **no path that relaxes the filter** in fallback
code. This is the load-bearing invariant; the regression suite locks
it.

### 6.4 Display copy — `friendly_allergen_phrase`

Maps the user's exclusion set to readable copy:

| Input | Output |
|---|---|
| `['tree_nuts']` | `nut-free` |
| `['peanuts', 'tree_nuts']` | `nut-free` (collapsed) |
| `['dairy', 'tree_nuts']` | `dairy-free, nut-free` |

---

## 7. Things deliberately NOT done

These were considered and rejected — adding any of them would weaken
the safety story:

- ❌ **Surfacing `incomplete` items with a "needs verification"
  disclaimer.** Breaks the "system never shows unverified food under a
  restriction" guarantee.
- ❌ **Tag-based "fruit / GF / vegan" fallback that bypasses the
  derived filter.** Fallback ≠ loosen rules; it's a different *safe*
  subset, not a relaxed one.
- ❌ **LLM-derived allergen tagging.** Probabilistic, non-auditable.
- ❌ **Caller-supplied allergen overrides.** Only the derivation
  service writes `menu_items.allergens` / `allergen_confidence`.

---

## 8. Test surface

Regression suite: `ml-agent/tests/test_allergen_filter_regression.py`
(8 tests, all locked to the bug history).

| Test | What it locks |
|---|---|
| `test_load_dessert_menu_drops_nut_unsafe...` | Strict filter drops both nut-bearing AND incomplete items |
| `test_resolve_dessert_choices_refuses_to_match_unsafe_item` | The original bug: `add tiramisu` + nut allergy → no match |
| `test_annotate_allergen_safety_three_state` | Recap booleans match the three-state contract |
| `test_guard_fails_loud_in_dev` | `ML_ENV=development` + missing kwarg → `ValueError` |
| `test_guard_fails_closed_in_prod` | `ML_ENV=production` + missing kwarg → all FALCPA excluded + log |
| `test_friendly_allergen_phrase` | Display copy collapses peanuts+tree_nuts to "nut-free" |
| `test_safe_alternatives_re_filters_and_skips_blocked` | Fallback helper re-runs filter, drops blocked name and incomplete items |
| `test_safe_alternatives_caps_at_limit` | Fallback respects `limit` |

### Health check

```bash
cd backend
npx ts-node src/scripts/recompute-menu-allergens.ts --health
```

Reports counts of `derived` vs `incomplete` items, ingredients without
allergens, dishes without ingredients. After
`seed-perfect-dataset.ts` exactly 10 items should be `derived`, 68
`incomplete`, 0 failed.

### Reset → seed → verify

```bash
cd backend
npx prisma migrate reset            # applies seed_baseline_roles too
npm run seed:users
npm run seed:menu
npx ts-node src/scripts/seed-perfect-dataset.ts
npx ts-node src/scripts/recompute-menu-allergens.ts
```

DB user: `cateringco` (not `postgres`), port 5433.

---

## 9. Operational quick-reference

### Adding a new menu entry point

1. Add the kwarg with the sentinel default:
   `excluded_allergens=_UNSET`
2. First line: `excluded_allergens = _guard_excluded(excluded_allergens, "fn_name")`
3. After fetching items, return through `filter_excluded_allergens(menu, excluded_allergens)`
4. Caller: pass `_user_excluded_allergens(slots)` (use `[]` if you
   genuinely have no slots — this is rare and worth a comment)

### Debugging "why isn't this item showing up"

1. Check `menu_items.allergen_confidence` for that item — if
   `incomplete`, the filter dropped it by design when any concern is
   set.
2. Fix by adding ingredients to the item's dishes via the inventory UI
   — **not** by tagging the menu item directly.
3. Re-run the derivation service (it auto-runs on inventory mutations,
   but `recompute-menu-allergens.ts` is the manual hammer).

### Investigating a `ALLERGEN_GUARD_TRIGGERED` log

The `caller` field names the file:line that called a `load_*`/
`resolve_*` without the kwarg. That's the bypass — fix it by passing
`excluded_allergens=_user_excluded_allergens(slots)`.

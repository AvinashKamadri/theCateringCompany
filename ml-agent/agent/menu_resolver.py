"""
DB-backed menu resolution — the ONLY correct way to map user text to real
menu_items rows.

This is the preserved logic from the old `agent/nodes/menu.py::_resolve_to_db_items`,
extracted verbatim (minor cleanup) so MenuSelectionTool and ModificationTool
can share it.

Why this is separate from the Tools: the AGENT_SPEC.md Post-Mortem Rule says
every menu selection MUST go through DB resolution. Keeping this in one file
means there's exactly one correct implementation to audit.
"""

from __future__ import annotations

import re as _re
from typing import Iterable, Optional

from database.db_manager import load_menu_by_category


# ============================================================================
# Category classifiers
# ============================================================================

def is_appetizer_category(cat_name: str) -> bool:
    cat_lower = cat_name.lower()
    return any(kw in cat_lower for kw in (
        "appetizer", "starter", "hors d'oeuvre", "hors d'oeuvres",
        "canape", "canapes",
    ))


def is_non_dish_category(cat_name: str) -> bool:
    """Categories handled by dedicated flows or non-food."""
    cat_lower = cat_name.lower()
    return any(kw in cat_lower for kw in (
        "dessert", "cake", "floral", "flower", "bouquet", "boutonniere",
        "corsage", "arbor", "center piece", "centerpiece", "table runner",
        "coffee", "beverage", "drink", "bar setup",
        "utensil", "rental", "linen", "chair", "table",
        "bar supplies", "bar supply",
    ))


def is_dessert_category(cat_name: str) -> bool:
    return "dessert" in cat_name.lower()


# ============================================================================
# Scoped menu loaders
# ============================================================================

async def load_main_dish_menu() -> dict[str, list[dict]]:
    menu = await load_menu_by_category()
    return {
        cat: items for cat, items in menu.items()
        if not is_non_dish_category(cat) and not is_appetizer_category(cat)
    }


async def load_appetizer_menu() -> dict[str, list[dict]]:
    menu = await load_menu_by_category()
    return {cat: items for cat, items in menu.items() if is_appetizer_category(cat)}


async def load_dessert_menu_expanded(is_wedding: bool = False) -> list[dict]:
    """Flat list of desserts with mini-dessert bundle expanded into sub-items."""
    menu = await load_menu_by_category()
    out: list[dict] = []
    for cat_name, cat_items in menu.items():
        if not is_dessert_category(cat_name):
            continue
        if not is_wedding and "cake" in cat_name.lower() and "wedding" in cat_name.lower():
            continue
        for item in cat_items:
            name_lower = item["name"].lower()
            if "mini desserts" in name_lower and item.get("description"):
                for sub in _re.split(r",(?![^(]*\))", item["description"]):
                    sub = sub.strip()
                    if sub:
                        out.append({
                            "name": sub,
                            "unit_price": item.get("unit_price"),
                            "price_type": item.get("price_type", "per_person"),
                        })
            else:
                out.append(item)
    return out


# ============================================================================
# Resolver — the single source of truth
# ============================================================================

_STOP_WORDS = frozenset({"and", "w/", "with", "the", "a", "an", "&"})


def _split_items(text: str) -> list[str]:
    """Parentheses-aware split. 'Meatballs (BBQ, Swedish)' stays intact."""
    if not text:
        return []
    parts = _re.split(r",(?![^(]*\))", text)
    if len(parts) <= 1:
        parts = [p.strip() for p in text.split(" and ")]
    return [p.strip() for p in parts if p and p.strip()]


def _sig_words(name: str) -> set[str]:
    return {w for w in name.lower().split() if w not in _STOP_WORDS and len(w) > 2}


async def resolve_to_db_items(
    extraction: str | Iterable[str],
    *,
    menu: Optional[dict[str, list[dict]]] = None,
    existing_names: Optional[Iterable[str]] = None,
) -> tuple[list[dict], str]:
    """Match free text to real DB menu items.

    Returns (matched_items, formatted_slot_value) where formatted_slot_value
    is e.g. "Charcuterie Boards ($4.25/pp), Fruit Tarts ($5.25/pp)".

    Four-stage match per input token, first hit wins:
      1. Exact item name
      2. Full category name → expand all items in that category
      3. Category suffix / prefix ("chicken" → "Hors D'oeuvres - Chicken")
      4. Partial / significant-word-set overlap

    Dedup is seeded from `existing_names` so repeated tool calls never add
    the same item twice.
    """
    if menu is None:
        menu = await load_menu_by_category()

    if isinstance(extraction, str):
        raw_text = extraction
    else:
        raw_text = ", ".join(str(x) for x in extraction)

    if raw_text.strip().lower() in ("", "none", "no", "n/a"):
        return [], "none"

    # Build lookups
    items_by_name: dict[str, tuple[dict, str]] = {}
    cats_by_lower: dict[str, str] = {}
    for cat_name, items in menu.items():
        cats_by_lower[cat_name.lower()] = cat_name
        for item in items:
            items_by_name[item["name"].lower()] = (item, cat_name)

    raw_names = _split_items(raw_text)

    matched: list[dict] = []
    seen: set[str] = {n for n in (existing_names or [])}

    for name in raw_names:
        name_lower = name.lower().strip()

        # 1. Exact item name
        if name_lower in items_by_name:
            item, cat = items_by_name[name_lower]
            if item["name"] not in seen:
                matched.append({**item, "matched_category": cat})
                seen.add(item["name"])
            continue

        # 2. Full category name → expand
        matched_cat: Optional[str] = None
        for cat_lower, cat_original in cats_by_lower.items():
            if name_lower == cat_lower or name_lower in cat_lower or cat_lower in name_lower:
                matched_cat = cat_original
                break
        if matched_cat:
            for item in menu[matched_cat]:
                if item["name"] not in seen:
                    matched.append({**item, "matched_category": matched_cat})
                    seen.add(item["name"])
            continue

        # 3. Category suffix / prefix
        hit = False
        for cat_name in menu:
            for sep in (" - ", " / ", ": "):
                if sep in cat_name:
                    parts = cat_name.split(sep)
                    suffix = parts[-1].strip().lower()
                    prefix = parts[0].strip().lower()
                    if name_lower == suffix or name_lower == prefix:
                        for item in menu[cat_name]:
                            if item["name"] not in seen:
                                matched.append({**item, "matched_category": cat_name})
                                seen.add(item["name"])
                        hit = True
                        break
            if hit:
                break
        if hit:
            continue

        # 4. Partial / word-set match
        sig_input = _sig_words(name_lower)
        for db_name_lower, (item, cat) in items_by_name.items():
            if name_lower in db_name_lower or db_name_lower in name_lower:
                if item["name"] not in seen:
                    matched.append({**item, "matched_category": cat})
                    seen.add(item["name"])
                break
            if sig_input:
                sig_db = _sig_words(db_name_lower)
                if sig_db and sig_input == sig_db and item["name"] not in seen:
                    matched.append({**item, "matched_category": cat})
                    seen.add(item["name"])
                    break

    if not matched:
        return [], raw_text.strip()

    return matched, format_items(matched)


def format_items(items: Iterable[dict]) -> str:
    """Format resolved items as the user-facing slot value string."""
    parts: list[str] = []
    for item in items:
        price = item.get("unit_price")
        ptype = item.get("price_type", "per_person")
        if price:
            if ptype == "per_person":
                parts.append(f"{item['name']} (${price:.2f}/pp)")
            else:
                parts.append(f"{item['name']} (${price:.2f})")
        else:
            parts.append(item["name"])
    return ", ".join(parts)


def parse_slot_items(value: str | None) -> list[str]:
    """Inverse of `format_items` — extract clean item names from a slot value."""
    if not value:
        return []
    low = value.strip().lower()
    if low in ("none", "no", "n/a", ""):
        return []
    parts = _re.split(r",(?![^(]*\))", value)
    out: list[str] = []
    for part in parts:
        cleaned = _re.sub(r"\s*\(\$[\d.]+(?:/[\w_]+)?\)", "", part).strip()
        if cleaned:
            out.append(cleaned)
    return out


# ---- Dessert resolver uses the expanded list --------------------------------

async def resolve_desserts(
    raw_names: Iterable[str],
    *,
    is_wedding: bool = False,
    existing_names: Optional[Iterable[str]] = None,
) -> list[dict]:
    """Resolve dessert picks against the expanded dessert list."""
    expanded = await load_dessert_menu_expanded(is_wedding=is_wedding)
    lookup = {item["name"].lower(): item for item in expanded}
    seen = {n.lower() for n in (existing_names or [])}
    out: list[dict] = []

    for raw in raw_names:
        key = raw.strip().lower()
        if not key:
            continue
        hit = lookup.get(key)
        if not hit:
            for db_name, item in lookup.items():
                if key == db_name or key in db_name or db_name in key:
                    hit = item
                    break
                sig_input = _sig_words(key)
                sig_db = _sig_words(db_name)
                if sig_input and sig_db and sig_input == sig_db:
                    hit = item
                    break
        if hit and hit["name"].lower() not in seen:
            out.append(hit)
            seen.add(hit["name"].lower())
    return out


__all__ = [
    "is_appetizer_category",
    "is_non_dish_category",
    "is_dessert_category",
    "load_main_dish_menu",
    "load_appetizer_menu",
    "load_dessert_menu_expanded",
    "resolve_to_db_items",
    "resolve_desserts",
    "format_items",
    "parse_slot_items",
]

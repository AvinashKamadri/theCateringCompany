"""DB-backed menu resolution shared across menu selection and modifications."""

from __future__ import annotations

import re as _re
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from database.db_manager import load_menu_by_category

# ---------------------------------------------------------------------------
# Process-level menu cache — menu data is static within a deployment so we
# avoid hitting the DB on every tool call (3 callers per menu turn).
# TTL is intentionally short enough to pick up a menu republish within minutes.
# ---------------------------------------------------------------------------
_MENU_CACHE: dict | None = None
_MENU_CACHE_AT: float = 0.0
_MENU_CACHE_TTL: float = 120.0  # seconds


async def _load_cached_menu() -> dict:
    global _MENU_CACHE, _MENU_CACHE_AT
    now = time.monotonic()
    if _MENU_CACHE is not None and now - _MENU_CACHE_AT < _MENU_CACHE_TTL:
        return _MENU_CACHE
    fresh = await load_menu_by_category()
    _MENU_CACHE = fresh
    _MENU_CACHE_AT = now
    return fresh


def is_appetizer_category(cat_name: str) -> bool:
    cat_lower = cat_name.lower()
    return any(
        kw in cat_lower
        for kw in (
            "appetizer",
            "starter",
            "hors d'oeuvre",
            "hors d'oeuvres",
            "canape",
            "canapes",
        )
    )


def is_non_dish_category(cat_name: str) -> bool:
    """Categories handled by dedicated flows or non-food."""
    cat_lower = cat_name.lower()
    return any(
        kw in cat_lower
        for kw in (
            "dessert",
            "cake",
            "floral",
            "flower",
            "bouquet",
            "boutonniere",
            "corsage",
            "arbor",
            "center piece",
            "centerpiece",
            "table runner",
            "coffee",
            "beverage",
            "drink",
            "bar setup",
            "utensil",
            "rental",
            "linen",
            "chair",
            "table",
            "bar supplies",
            "bar supply",
        )
    )


def is_dessert_category(cat_name: str) -> bool:
    return "dessert" in cat_name.lower()


def _normalize_excluded(excluded_allergens: Optional[Iterable[str]]) -> set[str]:
    if not excluded_allergens:
        return set()
    return {a.lower().strip() for a in excluded_allergens if a and str(a).strip()}


def _item_unsafe_allergens(item: dict, excluded: set[str]) -> list[str]:
    """Return the subset of `item['allergens']` that overlap with `excluded`."""
    if not excluded:
        return []
    item_allergens = {
        str(a).lower().strip()
        for a in (item.get("allergens") or [])
        if a and str(a).strip()
    }
    return sorted(item_allergens & excluded)


def filter_excluded_allergens(
    menu: dict[str, list[dict]],
    excluded_allergens: Optional[Iterable[str]],
) -> dict[str, list[dict]]:
    """Hard-filter: drop any item whose allergens intersect with `excluded_allergens`.

    Pure post-fetch transform — preserves the cached menu for other callers.
    Item dicts are kept as-is (not mutated).
    """
    excluded = _normalize_excluded(excluded_allergens)
    if not excluded:
        return menu
    return {
        cat: [it for it in items if not _item_unsafe_allergens(it, excluded)]
        for cat, items in menu.items()
    }


def annotate_allergen_safety(
    items: Iterable[dict],
    excluded_allergens: Optional[Iterable[str]],
) -> list[dict]:
    """Soft annotate: attach `is_safe` + `unsafe_allergens` per item.

    Use for review/conflict-detection paths (e.g. S19 recap) where the AI
    must NOT decide safety from arrays — it reads a boolean.
    """
    excluded = _normalize_excluded(excluded_allergens)
    out: list[dict] = []
    for it in items or []:
        unsafe = _item_unsafe_allergens(it, excluded)
        out.append({**it, "is_safe": not unsafe, "unsafe_allergens": unsafe})
    return out


async def load_main_dish_menu(
    excluded_allergens: Optional[Iterable[str]] = None,
) -> dict[str, list[dict]]:
    menu = await _load_cached_menu()
    scoped = {
        cat: items
        for cat, items in menu.items()
        if not is_non_dish_category(cat) and not is_appetizer_category(cat)
    }
    return filter_excluded_allergens(scoped, excluded_allergens)


async def load_appetizer_menu(
    excluded_allergens: Optional[Iterable[str]] = None,
) -> dict[str, list[dict]]:
    menu = await _load_cached_menu()
    scoped = {cat: items for cat, items in menu.items() if is_appetizer_category(cat)}
    return filter_excluded_allergens(scoped, excluded_allergens)


async def load_dessert_menu_expanded(
    is_wedding: bool = False,
    excluded_allergens: Optional[Iterable[str]] = None,
) -> list[dict]:
    """Flat list of desserts with mini-dessert bundle expanded into sub-items."""
    menu = await _load_cached_menu()
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
                        # Mini-dessert sub-items inherit parent allergens (best
                        # available signal until the sub-items are seeded as
                        # their own menu_items with derived allergens). Copy
                        # the list — mutating a shared reference would leak
                        # across cache reads.
                        out.append(
                            {
                                "name": sub,
                                "unit_price": item.get("unit_price"),
                                "price_type": item.get("price_type", "per_person"),
                                "allergens": list(item.get("allergens") or []),
                            }
                        )
            else:
                out.append(item)
    excluded = _normalize_excluded(excluded_allergens)
    if excluded:
        out = [it for it in out if not _item_unsafe_allergens(it, excluded)]
    return out


@dataclass(slots=True)
class AmbiguousMenuChoice:
    query: str
    matches: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MenuResolution:
    matched_items: list[dict] = field(default_factory=list)
    formatted_value: str = "none"
    ambiguous_choices: list[AmbiguousMenuChoice] = field(default_factory=list)
    unmatched_queries: list[str] = field(default_factory=list)


_STOP_WORDS = frozenset({"and", "w", "with", "the", "a", "an", "&", "bar", "menu"})


def _loose(name: str) -> str:
    return _re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _sig_words(name: str) -> set[str]:
    return {
        word
        for word in _re.split(r"[^a-z0-9]+", name.lower())
        if word not in _STOP_WORDS and len(word) > 2
    }


def _flatten_menu(menu: dict[str, list[dict]]) -> list[tuple[dict, str]]:
    return [
        ({**item, "matched_category": cat_name}, cat_name)
        for cat_name, items in menu.items()
        for item in items
    ]


def _split_items(
    text: str,
    *,
    preserve_single_item: Callable[[str], bool],
) -> list[str]:
    if not text:
        return []

    parts = _re.split(r",(?![^(]*\))", text)
    if len(parts) > 1:
        return [part.strip() for part in parts if part and part.strip()]

    cleaned = text.strip()
    if not cleaned:
        return []
    if preserve_single_item(cleaned):
        return [cleaned]

    parts = [part.strip() for part in cleaned.split(" and ") if part and part.strip()]
    return parts or [cleaned]


def _dedupe_candidates(candidates: Iterable[dict]) -> list[dict]:
    unique: list[dict] = []
    seen: set[str] = set()
    for item in candidates:
        name = item["name"].lower()
        if name in seen:
            continue
        unique.append(item)
        seen.add(name)
    return unique


def _filter_unseen(candidates: list[dict], seen_names: set[str]) -> list[dict]:
    return [item for item in candidates if item["name"].lower() not in seen_names]


def _resolve_query(
    query: str,
    *,
    menu: dict[str, list[dict]],
    flat_items: list[tuple[dict, str]],
    items_by_name: dict[str, dict],
    items_by_loose: dict[str, dict],
    cats_by_lower: dict[str, str],
    cats_by_loose: dict[str, str],
    seen_names: set[str],
) -> tuple[list[dict], list[str]]:
    query_lower = query.lower().strip()
    query_loose = _loose(query_lower)

    exact_item = items_by_name.get(query_lower) or items_by_loose.get(query_loose)
    if exact_item:
        unseen = _filter_unseen([exact_item], seen_names)
        return unseen, []

    exact_category = cats_by_lower.get(query_lower) or cats_by_loose.get(query_loose)
    if exact_category:
        category_items = _filter_unseen(
            [{**item, "matched_category": exact_category} for item in menu[exact_category]],
            seen_names,
        )
        if len(category_items) <= 1:
            return category_items, []
        return [], [item["name"] for item in category_items]

    for cat_name, items in menu.items():
        for sep in (" - ", " / ", ": "):
            if sep not in cat_name:
                continue
            parts = cat_name.split(sep)
            if query_lower not in {parts[0].strip().lower(), parts[-1].strip().lower()}:
                continue
            category_items = _filter_unseen(
                [{**item, "matched_category": cat_name} for item in items],
                seen_names,
            )
            if len(category_items) <= 1:
                return category_items, []
            return [], [item["name"] for item in category_items]

    sig_input = _sig_words(query_lower)
    partial_candidates: list[dict] = []
    for item, _cat_name in flat_items:
        db_name_lower = item["name"].lower()
        db_loose = _loose(db_name_lower)
        if (
            query_lower in db_name_lower
            or db_name_lower in query_lower
            or (query_loose and query_loose in db_loose)
            or (db_loose and db_loose in query_loose)
        ):
            partial_candidates.append(item)
            continue
        if sig_input:
            sig_db = _sig_words(db_name_lower)
            if sig_db and (
                sig_input == sig_db or (len(sig_input) >= 2 and sig_input.issubset(sig_db))
            ):
                partial_candidates.append(item)

    unique_candidates = _filter_unseen(_dedupe_candidates(partial_candidates), seen_names)
    if len(unique_candidates) == 1:
        return unique_candidates, []
    if len(unique_candidates) > 1:
        return [], [item["name"] for item in unique_candidates]

    return [], []


async def resolve_menu_items(
    extraction: str | Iterable[str],
    *,
    menu: Optional[dict[str, list[dict]]] = None,
    existing_names: Optional[Iterable[str]] = None,
) -> MenuResolution:
    if menu is None:
        menu = await _load_cached_menu()

    if isinstance(extraction, str):
        raw_text = extraction
        flat_items = _flatten_menu(menu)
        items_by_name = {item["name"].lower(): item for item, _ in flat_items}
        items_by_loose = {_loose(item["name"]): item for item, _ in flat_items}
        cats_by_lower = {cat_name.lower(): cat_name for cat_name in menu}
        cats_by_loose = {_loose(cat_name): cat_name for cat_name in menu}
        raw_names = _split_items(
            raw_text,
            preserve_single_item=lambda text: (
                text.lower().strip() in items_by_name
                or _loose(text) in items_by_loose
                or text.lower().strip() in cats_by_lower
                or _loose(text) in cats_by_loose
                or any(_sig_words(text) == _sig_words(item["name"]) for item, _ in flat_items)
            ),
        )
    else:
        flat_items = _flatten_menu(menu)
        items_by_name = {item["name"].lower(): item for item, _ in flat_items}
        items_by_loose = {_loose(item["name"]): item for item, _ in flat_items}
        cats_by_lower = {cat_name.lower(): cat_name for cat_name in menu}
        cats_by_loose = {_loose(cat_name): cat_name for cat_name in menu}
        raw_names = []
        for item in extraction:
            text = str(item).strip()
            if not text:
                continue
            raw_names.extend(
                _split_items(
                    text,
                    preserve_single_item=lambda candidate: (
                        candidate.lower().strip() in items_by_name
                        or _loose(candidate) in items_by_loose
                        or candidate.lower().strip() in cats_by_lower
                        or _loose(candidate) in cats_by_loose
                        or any(_sig_words(candidate) == _sig_words(menu_item["name"]) for menu_item, _ in flat_items)
                    ),
                )
            )

    if not raw_names:
        return MenuResolution()

    if len(raw_names) == 1 and raw_names[0].strip().lower() in {"", "none", "no", "n/a"}:
        return MenuResolution(formatted_value="none")

    seen_names = {str(name).lower() for name in (existing_names or []) if str(name).strip()}
    matched_items: list[dict] = []
    ambiguous_choices: list[AmbiguousMenuChoice] = []
    unmatched_queries: list[str] = []

    for raw_name in raw_names:
        matches, ambiguous = _resolve_query(
            raw_name,
            menu=menu,
            flat_items=flat_items,
            items_by_name=items_by_name,
            items_by_loose=items_by_loose,
            cats_by_lower=cats_by_lower,
            cats_by_loose=cats_by_loose,
            seen_names=seen_names,
        )
        if matches:
            matched_items.extend(matches)
            seen_names.update(item["name"].lower() for item in matches)
            continue
        if ambiguous:
            ambiguous_choices.append(AmbiguousMenuChoice(query=raw_name, matches=ambiguous))
            continue
        unmatched_queries.append(raw_name)

    return MenuResolution(
        matched_items=matched_items,
        formatted_value=format_items(matched_items) if matched_items else "none",
        ambiguous_choices=ambiguous_choices,
        unmatched_queries=unmatched_queries,
    )


async def resolve_to_db_items(
    extraction: str | Iterable[str],
    *,
    menu: Optional[dict[str, list[dict]]] = None,
    existing_names: Optional[Iterable[str]] = None,
) -> tuple[list[dict], str]:
    resolution = await resolve_menu_items(
        extraction,
        menu=menu,
        existing_names=existing_names,
    )

    if resolution.matched_items:
        return resolution.matched_items, resolution.formatted_value

    if isinstance(extraction, str):
        raw_text = extraction.strip()
    else:
        raw_text = ", ".join(str(x).strip() for x in extraction if str(x).strip())
    return [], raw_text or "none"


def format_items(items: Iterable[dict]) -> str:
    parts: list[str] = []
    for item in items:
        price = item.get("unit_price")
        price_type = item.get("price_type", "per_person")
        if price:
            if price_type == "per_person":
                parts.append(f"{item['name']} (${price:.2f}/pp)")
            else:
                parts.append(f"{item['name']} (${price:.2f})")
        else:
            parts.append(item["name"])
    return ", ".join(parts)


def parse_slot_items(value: str | None) -> list[str]:
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


# ---------------------------------------------------------------------------
# Tagging helpers for bulk operations (veg/non-veg/seafood/egg/etc.)
# ---------------------------------------------------------------------------

_TAG_PATTERNS: dict[str, str] = {
    "egg": r"\begg\b",
    "seafood": r"\b(shrimp|salmon|tuna|crab|lobster|cod|scallop|scallops|mussel|mussels|clam|clams|fish)\b",
    "chicken": r"\bchicken\b",
    "pork": r"\b(pork|bacon|ham|chorizo)\b",
    "beef": r"\b(beef|steak|brisket|prime\s+rib|ribeye|filet)\b",
}


def menu_item_tags(item_name: str, category_name: str = "") -> set[str]:
    """Return coarse tags for a menu item for bulk selection/removal.

    Tags are deterministic heuristics (not nutrition facts). `non_veg` is only
    assigned when an animal-protein tag is detected, so vegetarian canapes are
    not misclassified as non-veg.
    """
    name = (item_name or "").strip()
    category = (category_name or "").strip()
    if not name and not category:
        return set()

    name_lower = name.lower()
    cat_lower = category.lower()
    tags: set[str] = set()

    if "vegetarian" in cat_lower or "veggie" in cat_lower:
        tags.add("veg")

    # Category hints
    if "seafood" in cat_lower:
        tags.add("seafood")
    if "chicken" in cat_lower:
        tags.add("chicken")
    if "pork" in cat_lower:
        tags.add("pork")
    if "beef" in cat_lower:
        tags.add("beef")

    # Name-based hints
    for tag, pattern in _TAG_PATTERNS.items():
        if _re.search(pattern, name_lower):
            tags.add(tag)

    animal = {"seafood", "chicken", "pork", "beef", "egg"}
    if "veg" not in tags and tags.intersection(animal):
        tags.add("non_veg")

    return tags


def filter_menu_items_by_tags(
    menu: dict[str, list[dict]],
    *,
    include_tags: set[str],
    exclude_tags: set[str] | None = None,
) -> list[dict]:
    """Return all menu items matching any include tag and no exclude tags."""
    if not include_tags:
        return []
    excluded = exclude_tags or set()
    out: list[dict] = []
    for cat, items in (menu or {}).items():
        for it in items or []:
            name = str(it.get("name") or "").strip()
            if not name:
                continue
            tags = menu_item_tags(name, cat)
            if not tags:
                continue
            if not any(t in tags for t in include_tags):
                continue
            if excluded and any(t in tags for t in excluded):
                continue
            out.append({**it, "matched_category": cat})
    return out


async def resolve_dessert_choices(
    raw_names: Iterable[str],
    *,
    is_wedding: bool = False,
    existing_names: Optional[Iterable[str]] = None,
) -> MenuResolution:
    expanded = await load_dessert_menu_expanded(is_wedding=is_wedding)
    return await resolve_menu_items(
        list(raw_names),
        menu={"Desserts": expanded},
        existing_names=existing_names,
    )


async def resolve_desserts(
    raw_names: Iterable[str],
    *,
    is_wedding: bool = False,
    existing_names: Optional[Iterable[str]] = None,
) -> list[dict]:
    resolution = await resolve_dessert_choices(
        raw_names,
        is_wedding=is_wedding,
        existing_names=existing_names,
    )
    return resolution.matched_items


__all__ = [
    "AmbiguousMenuChoice",
    "MenuResolution",
    "annotate_allergen_safety",
    "filter_excluded_allergens",
    "filter_menu_items_by_tags",
    "format_items",
    "is_appetizer_category",
    "is_dessert_category",
    "is_non_dish_category",
    "load_appetizer_menu",
    "load_dessert_menu_expanded",
    "load_main_dish_menu",
    "menu_item_tags",
    "parse_slot_items",
    "resolve_dessert_choices",
    "resolve_desserts",
    "resolve_menu_items",
    "resolve_to_db_items",
]

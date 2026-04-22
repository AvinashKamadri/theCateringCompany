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


async def load_main_dish_menu() -> dict[str, list[dict]]:
    menu = await _load_cached_menu()
    return {
        cat: items
        for cat, items in menu.items()
        if not is_non_dish_category(cat) and not is_appetizer_category(cat)
    }


async def load_appetizer_menu() -> dict[str, list[dict]]:
    menu = await _load_cached_menu()
    return {cat: items for cat, items in menu.items() if is_appetizer_category(cat)}


async def load_dessert_menu_expanded(is_wedding: bool = False) -> list[dict]:
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
                        out.append(
                            {
                                "name": sub,
                                "unit_price": item.get("unit_price"),
                                "price_type": item.get("price_type", "per_person"),
                            }
                        )
            else:
                out.append(item)
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


_STOP_WORDS = frozenset({"and", "w", "with", "the", "a", "an", "&"})


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
    "format_items",
    "is_appetizer_category",
    "is_dessert_category",
    "is_non_dish_category",
    "load_appetizer_menu",
    "load_dessert_menu_expanded",
    "load_main_dish_menu",
    "parse_slot_items",
    "resolve_dessert_choices",
    "resolve_desserts",
    "resolve_menu_items",
    "resolve_to_db_items",
]

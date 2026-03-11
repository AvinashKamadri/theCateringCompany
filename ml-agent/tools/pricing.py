"""
Pricing calculator — queries real menu items + pricing packages from DB.

Category matching is fully DB-driven:
  1. Exact item name
  2. Full category name match (e.g. "Hors D'oeuvres - Chicken")
  3. Category suffix match (e.g. "Chicken" matches "Hors D'oeuvres - Chicken")
  4. Fuzzy substring in category name
  5. Partial item name match (last resort)
"""

import logging
from database.db_manager import load_pricing_packages, load_menu_items
from config.business_rules import config

logger = logging.getLogger(__name__)


async def match_pricing_package(
    event_type: str,
    guest_count: int,
) -> dict | None:
    """Find the best pricing package for event type and guest count."""
    packages = await load_pricing_packages()
    if not packages:
        return None

    event_lower = event_type.lower() if event_type else ""

    # Try to match by category first
    candidates = []
    for pkg in packages:
        cat = (pkg["category"] or "").lower()
        name = (pkg["name"] or "").lower()

        if "wedding" in event_lower and "wedding" in (cat + name):
            candidates.append(pkg)
        elif "corporate" in event_lower and "premium" in cat:
            candidates.append(pkg)
        elif "standard" in cat and not candidates:
            candidates.append(pkg)

    if not candidates:
        candidates = packages  # fallback to all

    # For weddings / premium: pick deluxe for larger, basic for smaller
    if guest_count > config.PREMIUM_PACKAGE_GUEST_THRESHOLD:
        candidates.sort(key=lambda p: p["base_price"] or 0, reverse=True)
    else:
        candidates.sort(key=lambda p: p["base_price"] or 0)

    return candidates[0]


def _build_category_index(all_items: list[dict]) -> dict:
    """
    Build a generalized category index from whatever's in the DB.

    Returns a dict with multiple lookup layers:
    {
        "by_full_name": {"hors d'oeuvres - chicken": [items...]},
        "by_suffix": {"chicken": [items...], "seafood": [items...]},
        "by_keyword": {"chicken": [items...], "seafood": [items...]},
    }

    All keys are lowercased. Works with any category naming convention.
    """
    by_full_name: dict[str, list[dict]] = {}
    by_suffix: dict[str, list[dict]] = {}
    by_keyword: dict[str, list[dict]] = {}

    for item in all_items:
        cat = (item.get("category") or "").strip()
        cat_lower = cat.lower()

        # Full category name
        by_full_name.setdefault(cat_lower, []).append(item)

        # Split on common delimiters to get suffix/subcategory
        # Handles: "Hors D'oeuvres - Chicken", "Main Dishes / Beef", "Appetizers: Seafood"
        for sep in [" - ", " / ", ": ", " – "]:
            if sep in cat:
                parts = cat.split(sep)
                suffix = parts[-1].strip().lower()
                if suffix:
                    by_suffix.setdefault(suffix, []).append(item)
                # Also index the prefix for broad matches like "hors d'oeuvres"
                prefix = parts[0].strip().lower()
                if prefix:
                    by_suffix.setdefault(prefix, []).append(item)

        # Individual significant keywords from category name
        # Strip common noise words
        noise = {"and", "the", "of", "for", "with", "a", "an", "or", "d'oeuvres", "hors"}
        words = cat_lower.replace("-", " ").replace("/", " ").replace(":", " ").split()
        for word in words:
            word = word.strip("'\"(),.")
            if len(word) > 2 and word not in noise:
                by_keyword.setdefault(word, []).append(item)

    return {
        "by_full_name": by_full_name,
        "by_suffix": by_suffix,
        "by_keyword": by_keyword,
    }


async def calculate_event_pricing(
    guest_count: int,
    event_type: str,
    service_type: str,
    selected_dishes: list[str] | str | None = None,
    appetizers: list[str] | str | None = None,
    desserts: list[str] | str | None = None,
    utensils: str | None = None,
    rentals: str | None = None,
) -> dict:
    """
    Calculate full event pricing from DB data.

    Returns a breakdown dict with line items, subtotals, and grand total.
    """
    all_items = await load_menu_items()
    items_by_name = {item["name"].lower(): item for item in all_items}
    cat_index = _build_category_index(all_items)

    line_items = []
    seen_items = set()  # avoid duplicates

    def _add_item(item: dict, category_label: str):
        """Add a single menu item to line_items if not already added."""
        if item["name"] in seen_items:
            return
        seen_items.add(item["name"])
        price = item["unit_price"] or 0
        price_type = item["price_type"] or "per_person"
        if price_type == "per_person":
            total = price * guest_count
        else:
            total = price  # flat rate
        line_items.append({
            "name": item["name"],
            "description": item.get("description") or "",
            "category": category_label,
            "unit_price": price,
            "price_type": price_type,
            "quantity": guest_count if price_type == "per_person" else 1,
            "total": round(total, 2),
            "tags": item.get("tags") or [],
        })

    def _try_category_match(name_lower: str, category_label: str) -> bool:
        """Try all category-based matching layers. Returns True if matched."""
        # Layer 1: Full category name — "hors d'oeuvres - chicken"
        matches = cat_index["by_full_name"].get(name_lower, [])
        if matches:
            for m in matches:
                _add_item(m, category_label)
            return True

        # Layer 2: Category suffix — "chicken" matches "Hors D'oeuvres - Chicken"
        matches = cat_index["by_suffix"].get(name_lower, [])
        if matches:
            for m in matches:
                _add_item(m, category_label)
            return True

        # Layer 3: Keyword — "chicken" from category words
        matches = cat_index["by_keyword"].get(name_lower, [])
        if matches:
            for m in matches:
                _add_item(m, category_label)
            return True

        # Layer 4: Fuzzy substring in any category name
        found = False
        for cat_name, items in cat_index["by_full_name"].items():
            if name_lower in cat_name or cat_name in name_lower:
                for m in items:
                    _add_item(m, category_label)
                found = True
        return found

    def _resolve_selections(raw, category_label: str):
        """Parse a comma-separated string or list into matched menu items.

        Match priority (all DB-driven, no hardcoded categories):
        1. Exact item name
        2. Full category name
        3. Category suffix (part after delimiter)
        4. Category keyword
        5. Fuzzy category substring
        6. Partial item name match (last resort)
        """
        if not raw:
            return
        raw_str = str(raw).strip().lower()
        if raw_str in ("none", "no", "n/a", "not requested", "none selected"):
            return

        # Split on commas and "and"
        names = []
        for part in str(raw).split(","):
            for sub in part.split(" and "):
                cleaned = sub.strip()
                if cleaned:
                    names.append(cleaned)

        for name in names:
            name_lower = name.lower().strip()

            # 1. Try exact item name match
            matched = items_by_name.get(name_lower)
            if matched:
                _add_item(matched, category_label)
                continue

            # 2-5. Try category-based matching (all layers)
            if _try_category_match(name_lower, category_label):
                continue

            # 6. Partial item name match (last resort)
            partial_matches = []
            for db_name, item in items_by_name.items():
                if name_lower in db_name or db_name in name_lower:
                    partial_matches.append(item)
            if partial_matches:
                for m in partial_matches:
                    _add_item(m, category_label)
                continue

            logger.warning(f"Menu item not found in DB: {name}")

    # Resolve each selection category
    _resolve_selections(selected_dishes, "Main Dishes")
    _resolve_selections(appetizers, "Appetizers")
    _resolve_selections(desserts, "Desserts")

    # Add-ons (utensils, rentals) — estimate if not in menu_items
    if utensils and str(utensils).strip().lower() not in ("no", "none", "n/a", "not requested", "not provided"):
        _resolve_selections(utensils, "Utensils")
        # If nothing matched, add a flat estimate
        if not any(li["category"] == "Utensils" for li in line_items):
            line_items.append({
                "name": f"Utensil Package ({utensils})",
                "category": "Utensils",
                "unit_price": config.UTENSIL_PACKAGE_PER_PERSON,
                "price_type": "per_person",
                "quantity": guest_count,
                "total": round(config.UTENSIL_PACKAGE_PER_PERSON * guest_count, 2),
            })

    if rentals and str(rentals).strip().lower() not in ("no", "none", "n/a", "not requested", "not provided"):
        rental_items = [r.strip() for r in str(rentals).split(",")]
        for r in rental_items:
            r_lower = r.lower()
            for key, rate in config.RENTAL_RATES.items():
                if key in r_lower:
                    qty = config.get_rental_quantity(key, guest_count)
                    line_items.append({
                        "name": f"Rental - {key.title()}",
                        "category": "Rentals",
                        "unit_price": rate,
                        "price_type": "per_unit",
                        "quantity": qty,
                        "total": round(rate * qty, 2),
                    })
                    break

    # Pricing package (base rate)
    package = await match_pricing_package(event_type, guest_count)

    # Service surcharge for on-site
    service_surcharge = config.calculate_service_surcharge(guest_count, service_type)

    # Totals
    food_subtotal = sum(li["total"] for li in line_items)
    package_base = (package["base_price"] or 0) * guest_count if package else 0

    # Use the HIGHER of: package base vs item-level pricing
    menu_total = max(food_subtotal, package_base)

    # Tax & gratuity from business config
    subtotal_before_fees = menu_total + service_surcharge
    tax = subtotal_before_fees * config.TAX_RATE
    gratuity = subtotal_before_fees * config.GRATUITY_RATE
    grand_total = subtotal_before_fees + tax + gratuity

    # Deposit from business config
    deposit = grand_total * config.DEPOSIT_PERCENTAGE

    return {
        "line_items": line_items,
        "food_subtotal": round(food_subtotal, 2),
        "package": {
            "name": package["name"] if package else "Custom",
            "per_person_rate": package["base_price"] if package else None,
            "package_base_total": round(package_base, 2),
        } if package else None,
        "service_surcharge": round(service_surcharge, 2),
        "service_type": service_type,
        "guest_count": guest_count,
        "menu_total": round(menu_total, 2),
        "subtotal_before_fees": round(subtotal_before_fees, 2),
        "tax": round(tax, 2),
        "tax_rate": config.TAX_RATE,
        "gratuity": round(gratuity, 2),
        "gratuity_rate": config.GRATUITY_RATE,
        "grand_total": round(grand_total, 2),
        "deposit": round(deposit, 2),
        "balance": round(grand_total - deposit, 2),
        "currency": "USD",
    }

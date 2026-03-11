"""
Menu building nodes: dish selection, appetizers, menu design, menu changes.
Queries real menu data from the database instead of LLM-generated menus.

All selections are resolved to actual DB items with prices before storing
in slots, so pricing and contract generation work correctly.
"""

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_respond,
    is_affirmative, is_negative,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS
from database.db_manager import load_menu_by_category, load_dessert_items


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}


def _is_appetizer_category(cat_name: str) -> bool:
    """Check if a category name is appetizer-like (generalized for any DB naming)."""
    cat_lower = cat_name.lower()
    return any(kw in cat_lower for kw in [
        "appetizer", "starter", "hors d'oeuvre", "hors d'oeuvres",
        "canape", "canapes",
    ])


def _is_non_dish_category(cat_name: str) -> bool:
    """Check if a category is NOT a selectable food dish (desserts, floral, cakes, coffee, etc.).

    These categories are handled by their own dedicated nodes or are non-food items.
    """
    cat_lower = cat_name.lower()
    return any(kw in cat_lower for kw in [
        "dessert", "cake", "floral", "flower", "bouquet", "boutonniere",
        "corsage", "arbor", "center piece", "centerpiece", "table runner",
        "coffee", "beverage", "drink", "bar setup",
    ])


def _format_menu_for_prompt(
    menu_by_category: dict,
    exclude_categories: list[str] | None = None,
    highlight_tags: list[str] | None = None,
) -> str:
    """Format DB menu items into a numbered list for LLM context.

    Args:
        highlight_tags: If provided, items with matching tags get a star marker
                        (e.g. ["wedding", "vegetarian"]).
    """
    exclude = {c.lower() for c in (exclude_categories or [])}
    hl = {t.lower() for t in (highlight_tags or [])}
    lines = []
    item_num = 1
    for category, items in menu_by_category.items():
        if category.lower() in exclude:
            continue
        lines.append(f"\n**{category}**")
        for item in items:
            price_str = f" (${item['unit_price']:.2f}/{item['price_type']})" if item.get('unit_price') else ""
            desc_str = f" -- {item['description']}" if item.get('description') else ""
            allergen_str = f" [Allergens: {', '.join(item['allergens'])}]" if item.get('allergens') else ""
            # Tag-based highlights
            item_tags = {t.lower() for t in (item.get('tags') or [])}
            star = " *" if hl and hl & item_tags else ""
            tag_note = f" [{', '.join(sorted(hl & item_tags))}]" if hl and hl & item_tags else ""
            lines.append(f"  {item_num}. {item['name']}{price_str}{desc_str}{allergen_str}{star}{tag_note}")
            item_num += 1
    return "\n".join(lines) if lines else "No menu items available."


def _format_items_list(items: list[dict]) -> str:
    """Format a flat list of items into a numbered list."""
    lines = []
    for i, item in enumerate(items, 1):
        price_str = f" (${item['unit_price']:.2f})" if item.get('unit_price') else ""
        desc_str = f" -- {item['description']}" if item.get('description') else ""
        lines.append(f"  {i}. {item['name']}{price_str}{desc_str}")
    return "\n".join(lines) if lines else "No items available."


# ---------------------------------------------------------------------------
# DB item resolution — matches extracted text to actual menu items with prices
# ---------------------------------------------------------------------------

async def _resolve_to_db_items(extraction: str, menu: dict | None = None) -> tuple[list[dict], str]:
    """Match extracted selection text to actual DB items with prices.

    Returns:
        (matched_items, formatted_slot_value)
        - matched_items: list of dicts with name, unit_price, category, price_type
        - formatted_slot_value: string to store in slot, e.g.
          "Chicken Satay ($3.50/pp), Adobo Lime Chicken Bites ($3.50/pp)"
    """
    if menu is None:
        menu = await load_menu_by_category()

    extraction_lower = extraction.lower().strip()
    if extraction_lower in ("none", "no", "n/a", ""):
        return [], "none"

    # Build lookup structures
    items_by_name: dict[str, tuple[dict, str]] = {}  # name_lower -> (item, category)
    cats_by_lower: dict[str, str] = {}  # cat_lower -> original cat name

    for cat_name, items in menu.items():
        cats_by_lower[cat_name.lower()] = cat_name
        for item in items:
            items_by_name[item["name"].lower()] = (item, cat_name)

    # Parse comma / "and" separated selections
    raw_names = []
    for part in extraction.split(","):
        for sub in part.split(" and "):
            cleaned = sub.strip()
            if cleaned:
                raw_names.append(cleaned)

    matched = []
    seen = set()

    for name in raw_names:
        name_lower = name.lower().strip()

        # 1. Exact item name match
        if name_lower in items_by_name:
            item, cat = items_by_name[name_lower]
            if item["name"] not in seen:
                matched.append({**item, "matched_category": cat})
                seen.add(item["name"])
            continue

        # 2. Full category name match -> expand ALL items in that category
        matched_cat = None
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

        # 3. Category suffix match (e.g. "chicken" -> "Hors D'oeuvres - Chicken")
        for cat_name in menu:
            for sep in [" - ", " / ", ": "]:
                if sep in cat_name:
                    suffix = cat_name.split(sep)[-1].strip().lower()
                    prefix = cat_name.split(sep)[0].strip().lower()
                    if name_lower == suffix or name_lower == prefix:
                        for item in menu[cat_name]:
                            if item["name"] not in seen:
                                matched.append({**item, "matched_category": cat_name})
                                seen.add(item["name"])
                        break
            else:
                continue
            break

        # 4. Partial item name match (last resort)
        if name not in seen:
            for db_name_lower, (item, cat) in items_by_name.items():
                if name_lower in db_name_lower or db_name_lower in name_lower:
                    if item["name"] not in seen:
                        matched.append({**item, "matched_category": cat})
                        seen.add(item["name"])

    # Format as slot value with prices
    if not matched:
        return [], extraction.strip()

    parts = []
    for item in matched:
        price = item.get("unit_price")
        ptype = item.get("price_type", "per_person")
        if price:
            if ptype == "per_person":
                parts.append(f"{item['name']} (${price:.2f}/pp)")
            else:
                parts.append(f"{item['name']} (${price:.2f})")
        else:
            parts.append(item["name"])

    return matched, ", ".join(parts)


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------

async def get_main_dishes_context(state) -> str:
    """Fetch main dish menu items from DB and format for prompt."""
    menu = await load_menu_by_category()
    slots = _slots_context(state)

    highlight_tags = []
    event_type = (slots.get("event_type") or "").lower()
    if "wedding" in event_type:
        highlight_tags.append("wedding")
    if "premium" in event_type or "corporate" in event_type:
        highlight_tags.append("premium")

    dietary = (slots.get("dietary_concerns") or "").lower()
    if "vegetarian" in dietary:
        highlight_tags.append("vegetarian")
    if "vegan" in dietary:
        highlight_tags.append("vegan")

    # Exclude categories handled by their own dedicated nodes
    exclude = []
    for cat_name in menu.keys():
        if _is_non_dish_category(cat_name) or _is_appetizer_category(cat_name):
            exclude.append(cat_name)
    formatted = _format_menu_for_prompt(menu, exclude_categories=exclude, highlight_tags=highlight_tags)

    tag_note = ""
    if highlight_tags:
        tag_note = f"\nItems marked with * are recommended for {', '.join(highlight_tags)} events.\n"

    return (
        f"REAL MENU FROM DATABASE (present these exact items to the customer):\n"
        f"{formatted}\n{tag_note}\n"
        f"Event details: {slots}\n"
        f"Ask the customer to select 3 to 5 dishes from this menu."
    )


async def get_appetizer_context(state) -> str:
    """Fetch appetizer/hors d'oeuvres items from DB and format for prompt."""
    menu = await load_menu_by_category()
    appetizer_items = []
    for cat_name, items in menu.items():
        if _is_appetizer_category(cat_name):
            appetizer_items.extend(items)
    formatted = _format_items_list(appetizer_items) if appetizer_items else "No appetizer items in database."
    return (
        f"REAL APPETIZER MENU FROM DATABASE (present these exact items):\n"
        f"{formatted}\n\n"
        f"Event: {_slots_context(state)}"
    )


async def get_dessert_context(state) -> str:
    """Fetch dessert items from DB — includes Coffee and Desserts + Wedding Cakes for weddings."""
    menu = await load_menu_by_category()
    slots = _slots_context(state)
    event_type = (slots.get("event_type") or "").lower()
    is_wedding = "wedding" in event_type

    dessert_items = []
    for cat_name, items in menu.items():
        cat_lower = cat_name.lower()
        if any(kw in cat_lower for kw in ["dessert", "coffee"]):
            dessert_items.extend(items)
        elif is_wedding and "cake" in cat_lower:
            dessert_items.extend(items)

    formatted = _format_items_list(dessert_items) if dessert_items else "No dessert items available."
    return (
        f"REAL DESSERT MENU FROM DATABASE (present these exact items):\n"
        f"{formatted}\n\n"
        f"Event: {slots}"
    )


# ---------------------------------------------------------------------------
# Appetizer detection
# ---------------------------------------------------------------------------

async def _selections_include_appetizers(selections: str) -> bool:
    """Check if the selected dishes already include appetizer/hors d'oeuvres categories."""
    menu = await load_menu_by_category()
    sel_lower = selections.lower()

    appetizer_categories = []
    for cat_name in menu.keys():
        if _is_appetizer_category(cat_name):
            appetizer_categories.append(cat_name)

    if not appetizer_categories:
        return False

    for cat_name in appetizer_categories:
        cat_lower = cat_name.lower()
        # Full name match
        if cat_lower in sel_lower:
            return True
        # Suffix match
        for sep in [" - ", " / ", ": "]:
            if sep in cat_name:
                suffix = cat_name.split(sep)[-1].strip().lower()
                if suffix in sel_lower:
                    for item in menu[cat_name]:
                        if item["name"].lower() in sel_lower:
                            return True
                    if suffix in sel_lower.split(",") or suffix in [s.strip() for s in sel_lower.split(" and ")]:
                        return True

    return False


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

async def select_dishes_node(state: ConversationState) -> ConversationState:
    """Process the customer's dish selections (3-5 dishes).

    Resolves selections to actual DB items with prices before storing.
    """
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    menu = await load_menu_by_category()

    # Build a flat list of all available item and category names for the LLM
    available_names = []
    for cat_name, items in menu.items():
        available_names.append(f"Category: {cat_name}")
        for item in items:
            available_names.append(f"  Item: {item['name']}")

    # Use LLM to extract — instruct it to use exact DB names
    extraction = await llm_respond(
        "Extract the dish selections from this customer message. "
        "Match each selection to the EXACT item or category name from the menu below. "
        "Return them as a comma-separated list using the exact names. "
        "If the customer selected a whole category (e.g. 'Hors D'oeuvres - Chicken'), "
        "return the full category name.\n\n"
        f"Available menu:\n" + "\n".join(available_names),
        f"Customer message: {user_msg}"
    )

    # Resolve to actual DB items with prices
    matched_items, resolved_text = await _resolve_to_db_items(extraction, menu)

    if matched_items:
        fill_slot(state["slots"], "selected_dishes", resolved_text)
    else:
        # Fallback: store raw extraction if nothing matched
        fill_slot(state["slots"], "selected_dishes", extraction.strip())

    # Check if selected dishes already include appetizer categories
    includes_appetizers = await _selections_include_appetizers(resolved_text or extraction)

    if includes_appetizers:
        fill_slot(state["slots"], "appetizers", "included in dish selection")
        context = (f"Customer selected dishes (includes appetizers/hors d'oeuvres): {resolved_text}\n"
                   f"Slots: {_slots_context(state)}")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer selected their dishes, which already include "
            "appetizers/hors d'oeuvres. Confirm the selections with their prices. "
            "Present the complete menu beautifully with prices. "
            "Then ask: Would you like to make any changes?",
            context
        )
        state["current_node"] = "ask_menu_changes"
    else:
        context = (f"Customer selected dishes: {resolved_text}\n"
                   f"Slots: {_slots_context(state)}")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_dishes']}", context
        )
        state["current_node"] = "ask_appetizers"

    state["messages"] = add_ai_message(state, response)
    return state


async def ask_appetizers_node(state: ConversationState) -> ConversationState:
    """Handle yes/no response about appetizers."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_affirmative(user_msg):
        appetizer_context = await get_appetizer_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_appetizers']}\n\n"
            "IMPORTANT: Present the EXACT appetizer items from the database below. "
            "Do NOT make up items.",
            appetizer_context
        )
        state["current_node"] = "select_appetizers"
    else:
        fill_slot(state["slots"], "appetizers", "none")
        context = f"Customer doesn't want appetizers.\nSlots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer doesn't want appetizers. Acknowledge this. "
            "Now create a special, creative menu presentation based on their selections. "
            "Present the complete menu beautifully with prices and ask: Would you like to make any changes?",
            context
        )
        state["current_node"] = "ask_menu_changes"

    state["messages"] = add_ai_message(state, response)
    return state


async def select_appetizers_node(state: ConversationState) -> ConversationState:
    """Process appetizer selections — resolve to actual DB items with prices."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    menu = await load_menu_by_category()

    # Build appetizer-only name list for LLM
    appetizer_names = []
    for cat_name, items in menu.items():
        if _is_appetizer_category(cat_name):
            appetizer_names.append(f"Category: {cat_name}")
            for item in items:
                appetizer_names.append(f"  Item: {item['name']}")

    extraction = await llm_respond(
        "Extract the appetizer selections from this message. "
        "Match to EXACT names from the menu below. Return as comma-separated list.\n\n"
        f"Available appetizers:\n" + "\n".join(appetizer_names),
        f"Customer message: {user_msg}"
    )

    matched_items, resolved_text = await _resolve_to_db_items(extraction, menu)

    if matched_items:
        fill_slot(state["slots"], "appetizers", resolved_text)
    else:
        fill_slot(state["slots"], "appetizers", extraction.strip())

    context = (f"Appetizers selected: {resolved_text or extraction}\n"
               f"All selections: {_slots_context(state)}")
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['menu_design']}", context
    )

    state["current_node"] = "ask_menu_changes"
    state["messages"] = add_ai_message(state, response)
    return state


async def menu_design_node(state: ConversationState) -> ConversationState:
    """Present creative menu design with special touches."""
    state = dict(state)

    context = f"Full event details and selections: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['menu_design']}", context
    )

    state["current_node"] = "ask_menu_changes"
    state["messages"] = add_ai_message(state, response)
    return state


async def ask_menu_changes_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about menu changes."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_affirmative(user_msg):
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer wants to make changes to the menu. "
            "Ask them what they'd like to change.",
            f"Current menu: {_slots_context(state)}"
        )
        state["current_node"] = "collect_menu_changes"
    else:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe menu is finalized. Confirm it looks great. "
            "Ask: Would you like us to provide utensils?",
            f"Final menu: {_slots_context(state)}"
        )
        state["current_node"] = "ask_utensils"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_menu_changes_node(state: ConversationState) -> ConversationState:
    """Process menu change requests and re-present menu."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    existing_notes = get_slot_value(state["slots"], "menu_notes") or ""
    new_notes = f"{existing_notes}\nChange: {user_msg}".strip()
    fill_slot(state["slots"], "menu_notes", new_notes)

    context = (f"Customer wants these changes: {user_msg}\n"
               f"Full context: {_slots_context(state)}")
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_menu_changes']}", context
    )

    state["current_node"] = "ask_menu_changes"
    state["messages"] = add_ai_message(state, response)
    return state

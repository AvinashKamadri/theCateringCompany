"""
Menu building nodes: dish selection, appetizers, menu design, menu changes.
Queries real menu data from the database instead of LLM-generated menus.

All selections are resolved to actual DB items with prices before storing
in slots, so pricing and contract generation work correctly.
"""

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_respond, llm_extract,
    build_numbered_list,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS, EXTRACTION_PROMPTS
from database.db_manager import load_menu_by_category, load_dessert_items
from tools.modification_detection import _format_recent_messages


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled") and not k.startswith("__")}


def _recent_ctx(state, n: int = 6) -> str:
    msgs = list(state.get("messages", []))
    return _format_recent_messages(msgs, n=n) if msgs else ""


async def get_appetizer_items() -> list[dict]:
    """Get flat list of all appetizer items from DB."""
    menu = await load_menu_by_category()
    items = []
    for cat_name, cat_items in menu.items():
        if _is_appetizer_category(cat_name):
            items.extend(cat_items)
    return items


async def get_main_dish_items() -> tuple[list[dict], dict]:
    """Get flat list + categorized dict of main dish items from DB."""
    menu = await load_menu_by_category()
    flat = []
    categorized = {}
    for cat_name, cat_items in menu.items():
        if not _is_non_dish_category(cat_name) and not _is_appetizer_category(cat_name):
            categorized[cat_name] = cat_items
            flat.extend(cat_items)
    return flat, categorized


async def get_dessert_items(is_wedding: bool = False) -> list[dict]:
    """Get flat list of dessert items, expanding mini desserts bundle.

    Wedding cakes are intentionally excluded — they are collected via a
    dedicated flow ("Would you like a wedding cake?") in the frontend and
    should not appear inside the dessert picker.
    """
    menu = await load_menu_by_category()
    items = []
    for cat_name, cat_items in menu.items():
        cat_lower = cat_name.lower()
        if "dessert" in cat_lower:
            for item in cat_items:
                if "mini desserts" in item["name"].lower() and item.get("description"):
                    for sub in item["description"].split(","):
                        sub = sub.strip()
                        if sub:
                            items.append({"name": sub, "unit_price": item["unit_price"],
                                          "price_type": item["price_type"]})
                else:
                    items.append(item)
    return items


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
        "utensil", "rental", "linen", "chair", "table",
        "bar supplies", "bar supply",
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
    """Fetch appetizer/hors d'oeuvres items from DB, grouped by sub-category (Chicken, Pork, etc.)."""
    menu = await load_menu_by_category()

    # Collect only appetizer categories, preserving order
    appetizer_cats = {cat: items for cat, items in menu.items() if _is_appetizer_category(cat)}

    lines = []
    global_num = 1
    for cat_name, items in appetizer_cats.items():
        # Extract sub-category label after " - " (e.g. "Hors D'oeuvres - Chicken" → "Chicken")
        if " - " in cat_name:
            label = cat_name.split(" - ", 1)[1].strip()
        else:
            label = cat_name

        # Determine if all items share the same flat price (e.g. all $3.50)
        prices = [item.get("unit_price") for item in items if item.get("unit_price")]
        if prices and len(set(prices)) == 1:
            price_note = f" (${prices[0]:.2f} pp/option)"
        else:
            price_note = ""

        lines.append(f"\n**{label}**{price_note}")
        for item in items:
            # Per-item price only when it differs from the group price
            if not price_note and item.get("unit_price"):
                price_str = f" (${item['unit_price']:.2f})"
            elif price_note:
                price_str = ""  # already shown on header
            else:
                price_str = ""
            # Show individual price regardless of group price so LLM can relay it when needed
            item_price = item.get("unit_price")
            p_str = f" (${item_price:.2f})" if item_price and not price_note else ""
            lines.append(f"  {global_num}. {item['name']}{p_str}")
            global_num += 1

    formatted = "\n".join(lines) if lines else "No appetizer items in database."
    return (
        f"REAL APPETIZER MENU FROM DATABASE — grouped by type, global sequential numbers:\n"
        f"{formatted}\n\n"
        f"Event: {_slots_context(state)}"
    )


async def get_dessert_context(state) -> str:
    """Fetch dessert items from DB — Desserts only.

    Wedding cakes are collected via a dedicated frontend flow and must not
    appear in the dessert picker.
    """
    menu = await load_menu_by_category()
    slots = _slots_context(state)

    dessert_items = []
    for cat_name, items in menu.items():
        cat_lower = cat_name.lower()
        if any(kw in cat_lower for kw in ["dessert"]):
            for item in items:
                # Expand mini dessert bundle into individual items
                if "mini desserts" in item["name"].lower() and item.get("description"):
                    for sub in item["description"].split(","):
                        sub = sub.strip()
                        if sub:
                            dessert_items.append({"name": sub, "unit_price": item["unit_price"],
                                                  "price_type": item["price_type"]})
                else:
                    dessert_items.append(item)

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

async def collect_meal_style_node(state: ConversationState) -> ConversationState:
    """Wedding only — ask plated or buffet before main menu."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    choice = await llm_extract(
        "The customer was asked if they want plated or buffet style. "
        "This is a REQUIRED choice — they must pick one. 'no', 'neither', 'skip' are NOT valid. "
        "Return ONLY: plated, buffet, or unclear.",
        user_msg
    )
    choice = choice.strip().lower()
    if choice == "unclear":
        # Keep asking — do NOT silently default. LLM has phrasing authority only.
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer didn't pick between plated or buffet — this is required. "
            "Warmly explain that plated is served to guests at their seats while buffet lets guests "
            "serve themselves, and we need to know which to plan staffing and setup. Then re-ask: plated or buffet?",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    fill_slot(state["slots"], "meal_style", choice.capitalize())

    # Python builds the main menu list — deterministic intro so LLM can't skip main menu.
    _, categorized = await get_main_dish_items()
    menu_list = build_numbered_list([], categories=categorized, category_headers=True)

    if "plated" in choice:
        intro = (
            "Plated it is — all plated packages come with china, we'll add that to your quote. "
            "Here's the main menu (items shown buffet-style — just pick what's closest, we'll fine-tune on a call):"
        )
    else:
        intro = "Buffet it is — here's the main menu:"

    response = f"{intro}\n\n{menu_list}\n\nThink of this as a starting point — we can customize later. Pick 3 to 5 dishes!"
    state["current_node"] = "select_dishes"
    state["messages"] = add_ai_message(state, response)
    return state


async def select_dishes_node(state: ConversationState) -> ConversationState:
    """Process the customer's dish selections (3-5 dishes).

    Resolves selections to actual DB items with prices before storing.
    """
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # If user sent a vague/short reply and hasn't selected any dishes yet, re-show the menu.
    # Do NOT run the custom check on these — "ok", "yes", "main menu", "show me" etc. all
    # mean the user is confused or waiting to see the menu again, not requesting custom.
    _VAGUE_REPLIES = {"ok", "okay", "yes", "sure", "alright", "yep", "yeah",
                      "main menu", "show me", "show menu", "the menu", "menu", "go ahead"}
    dishes_filled = state["slots"].get("selected_dishes", {}).get("filled", False)
    if not dishes_filled and user_msg.strip().lower() in _VAGUE_REPLIES:
        _, categorized = await get_main_dish_items()
        menu_list = build_numbered_list([], categories=categorized, category_headers=True)
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nRe-present the main dish menu in one casual line. Do NOT list any items.",
            f"Slots: {_slots_context(state)}"
        )
        state["messages"] = add_ai_message(
            state, f"{intro}\n\n{menu_list}\n\nPick 3 to 5 dishes!"
        )
        return state

    # Custom menu escape hatch — LLM detects if user wants something not on the menu.
    # Only run this check if user sent a substantial message (not a vague filler).
    custom_check = await llm_extract(
        "The customer was shown a menu of dishes to choose from. "
        "Are they requesting a CUSTOM menu or saying nothing on the list works for them? "
        "Or are they picking items from the menu?\n\n"
        "Return ONLY: custom or picking",
        user_msg
    )
    if custom_check.strip().lower() == "custom":
        fill_slot(state["slots"], "menu_notes", "Custom menu requested — schedule call")
        fill_slot(state["slots"], "selected_dishes", "Custom menu — to be finalized on call")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer wants a custom menu. Respond: "
            "'No problem — we can set up a quick call and design a custom menu just for you. "
            "We'll note that for the team. Let's keep going with the rest of the details.'",
            f"Slots: {_slots_context(state)}"
        )
        state["current_node"] = "ask_desserts"
        state["messages"] = add_ai_message(state, response)
        return state

    menu = await load_menu_by_category()

    # Build the same numbered list the user saw (excluding appetizers/desserts)
    exclude_cats = set()
    for cat_name in menu.keys():
        if _is_non_dish_category(cat_name) or _is_appetizer_category(cat_name):
            exclude_cats.add(cat_name.lower())

    number_to_name: dict[str, str] = {}
    numbered_lines: list[str] = []
    item_num = 1
    for cat_name, items in menu.items():
        if cat_name.lower() in exclude_cats:
            continue
        numbered_lines.append(f"\n{cat_name}")
        for item in items:
            price_str = f" (${item['unit_price']:.2f}/pp)" if item.get("unit_price") else ""
            numbered_lines.append(f"  {item_num}. {item['name']}{price_str}")
            number_to_name[str(item_num)] = item["name"]
            item_num += 1

    numbered_str = "\n".join(numbered_lines)

    # Fast path: user typed numbers → resolve directly without LLM
    bare_numbers = _re.findall(r"\b(\d+)\b", user_msg)
    if bare_numbers and all(n in number_to_name for n in bare_numbers):
        extraction = ", ".join(number_to_name[n] for n in bare_numbers)
    else:
        extraction = await llm_extract(
            "Extract the dish selections from this customer message. "
            "The customer may refer to items by number or by name. "
            "Use the numbered list below to map numbers to exact item names. "
            "Return ONLY a comma-separated list of item names (no numbers, no extra text). "
            "If the customer selected a whole category, return all item names in that category.\n\n"
            f"Numbered menu:\n{numbered_str}",
            user_msg
        )

    # Build a MAIN-DISHES-ONLY menu so appetizer items can't accidentally be selected here
    main_dishes_menu = {
        cat: items for cat, items in menu.items()
        if cat.lower() not in exclude_cats
    }

    # Check if user is trying to skip — main dishes are mandatory
    skip_check = await llm_extract(
        "The customer was shown a main dish menu and asked to pick 3-5 dishes. "
        "Are they trying to SKIP or decline the menu entirely, or are they making selections?\n\n"
        "Return ONLY: skip or selecting",
        user_msg
    )
    is_trying_to_skip = skip_check.strip().lower() == "skip" and not bare_numbers

    # Resolve ONLY against main-dish categories (prevents appetizer items sneaking in)
    matched_items, resolved_text = await _resolve_to_db_items(extraction, main_dishes_menu)

    if matched_items:
        fill_slot(state["slots"], "selected_dishes", resolved_text)
    else:
        # Nothing matched — re-present the menu with mandatory notice
        menu_context = await get_main_dishes_context(state)
        if is_trying_to_skip:
            instruction = (
                "The customer is trying to skip the main dish selection, but it is REQUIRED. "
                "Politely but firmly let them know that selecting main dishes is mandatory — "
                "they must choose at least 1 dish (ideally 3–5) to proceed. "
                "Re-present the menu below and ask them to make a selection."
            )
        else:
            instruction = (
                "The customer mentioned items that are NOT available as main dishes. "
                "Politely re-present the main dishes menu and ask them to choose 3 to 5 dishes."
            )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{instruction}",
            menu_context
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Resume-after-mod: mid-conv @AI edit just updates the slot and returns.
    resume_slot = state["slots"].pop("__resume_after_mod__", None)
    resume_node = resume_slot["value"] if resume_slot and resume_slot.get("filled") else None
    if resume_node:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer just updated their main dishes to: {resolved_text}. "
            "Briefly confirm the update in ONE short line. Do NOT ask any new question.",
            f"Dishes: {resolved_text}"
        )
        state["current_node"] = resume_node
        state["messages"] = add_ai_message(state, response)
        return state

    context = (f"Customer selected dishes: {resolved_text}\n"
               f"Slots: {_slots_context(state)}")
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_dishes']}", context
    )
    state["current_node"] = "ask_menu_changes"

    state["messages"] = add_ai_message(state, response)
    return state


async def ask_appetizers_node(state: ConversationState) -> ConversationState:
    """Present appetizer menu directly — always show the full menu on first entry."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Only skip if user EXPLICITLY says "no appetizers" or "skip appetizers"
    # Note: on first entry the user_msg is their answer to guest count/service style, NOT about appetizers
    skip_check = await llm_extract(
        "The customer just answered a question (about guest count or service style). "
        "Their response is being checked: did they EXPLICITLY say they want to skip appetizers? "
        "Only return 'skip' if they clearly say 'no appetizers', 'skip appetizers', etc. "
        "If they're just answering the previous question normally, return 'continue'.\n\n"
        "Return ONLY: skip or continue",
        user_msg
    )
    if skip_check.strip().lower() == "skip":
        fill_slot(state["slots"], "appetizers", "none")
        # Skip appetizers — go straight to main menu
        menu_context = await get_main_dishes_context(state)
        event_slots = {
            k: v["value"] for k, v in state["slots"].items()
            if v.get("filled") and k in ("name", "event_type", "event_date", "guest_count", "venue")
        }
        context = (
            f"Customer skipped appetizers.\n"
            f"Event details: {event_slots}\n\n"
            f"{menu_context}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['present_menu']}\n\n"
            "Briefly acknowledge they've skipped appetizers (one sentence), then present the menu. "
            "CRITICAL: Use ONLY the exact items listed in the database context. "
            "DO NOT invent, rename, or add any item not in that list.",
            context
        )
        state["current_node"] = "select_dishes"
    else:
        # Default: show the FULL appetizer menu directly — don't ask, just present
        appetizer_context = await get_appetizer_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_appetizers']}\n\n"
            "Present ALL appetizer items from the database using this EXACT grouped format:\n"
            "- Use the group headers as bold section labels (e.g. **Chicken**, **Pork**, **Seafood**, etc.)\n"
            "- Keep the global sequential numbering from the database context (numbers continue across groups)\n"
            "- Show the group price on the header line when all items share the same price (e.g. '$3.50 pp/option')\n"
            "- For Seafood, Canapes, and Vegetarian show individual prices per item since they vary\n"
            "- Show EVERY item — do not skip or summarize any group\n"
            "- End with: 'You can mix and match from any category — just let me know which ones you'd like!'\n"
            "CRITICAL: Use ONLY the exact item names from the database context below.",
            appetizer_context
        )
        state["current_node"] = "select_appetizers"

    state["messages"] = add_ai_message(state, response)
    return state


async def select_appetizers_node(state: ConversationState) -> ConversationState:
    """Process appetizer selections — resolve to actual DB items with prices."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    menu = await load_menu_by_category()

    # Build flat numbered list matching what the user sees (numbered 1..N)
    appetizer_items_flat = []
    for cat_name, items in menu.items():
        if _is_appetizer_category(cat_name):
            appetizer_items_flat.extend(items)

    number_to_name: dict[str, str] = {}
    numbered_lines: list[str] = []
    for i, item in enumerate(appetizer_items_flat, 1):
        price_str = f" (${item['unit_price']:.2f}/pp)" if item.get("unit_price") else ""
        numbered_lines.append(f"  {i}. {item['name']}{price_str}")
        number_to_name[str(i)] = item["name"]

    numbered_str = "\n".join(numbered_lines)

    # Fast path: user typed numbers → resolve directly without LLM
    bare_numbers = _re.findall(r"\b(\d+)\b", user_msg)
    if bare_numbers and all(n in number_to_name for n in bare_numbers):
        extraction = ", ".join(number_to_name[n] for n in bare_numbers)
    else:
        extraction = await llm_extract(
            "Extract the appetizer selections from this customer message. "
            "The customer may refer to items by number or by name. "
            "Use the numbered list below to map numbers to exact item names. "
            "Return ONLY a comma-separated list of item names (no numbers).\n\n"
            f"Numbered appetizer menu:\n{numbered_str}",
            user_msg
        )

    matched_items, resolved_text = await _resolve_to_db_items(extraction, menu)

    if matched_items:
        fill_slot(state["slots"], "appetizers", resolved_text)
    else:
        # Nothing matched — re-present appetizer menu
        appetizer_context = await get_appetizer_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer mentioned appetizers that are not on our menu. "
            "Politely let them know those items are not available and re-present the appetizer list. "
            "Ask them to choose from the items listed below.",
            appetizer_context
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Resume-after-mod: mid-conv @AI edit just updates the slot and returns.
    resume_slot = state["slots"].pop("__resume_after_mod__", None)
    resume_node = resume_slot["value"] if resume_slot and resume_slot.get("filled") else None
    if resume_node:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer just updated their appetizers to: {resolved_text}. "
            "Briefly confirm the update in ONE short line. Do NOT ask any new question.",
            f"Appetizers: {resolved_text}"
        )
        state["current_node"] = resume_node
        state["messages"] = add_ai_message(state, response)
        return state

    # Confirm appetizers + ask passed/station. Hardcoded so the LLM cannot
    # drift into "anything else?" affirmations or re-present the menu.
    response = (
        f"Got it — noted: {resolved_text}. "
        "Would you like the appetizers passed around by servers, or set up at a station?"
    )
    state["current_node"] = "collect_appetizer_style"
    state["messages"] = add_ai_message(state, response)
    return state


async def collect_appetizer_style_node(state: ConversationState) -> ConversationState:
    """Collect passed vs station for appetizers, then route to main menu."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    style = await llm_extract(
        "The customer was asked if they want appetizers passed around or at a station. "
        "This is a REQUIRED choice — they must pick one. 'no', 'neither', 'skip' are NOT valid. "
        "Return ONLY: passed, station, or unclear.",
        user_msg
    )
    style_val = style.strip().lower()
    if style_val == "unclear":
        # Keep asking — do NOT silently default. LLM has phrasing authority only.
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer didn't pick between passed or station — this is required. "
            "Warmly explain that passed means servers walk around offering bites, while a station "
            "is a set spot where guests help themselves. We need to know which so we can plan staffing "
            "and setup. Then re-ask: passed around or set up at a station?",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    fill_slot(state["slots"], "appetizer_style", style_val.capitalize())

    # Always ask plated vs buffet next — Python controls flow, hardcoded question
    # so the LLM cannot drift past the meal-style step.
    response = (
        f"{style_val.capitalize()} style — got it. "
        "For the main course, are you thinking plated (served to guests at their seats) "
        "or buffet (guests serve themselves)?"
    )
    state["current_node"] = "collect_meal_style"
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


def _count_slot_revisions(slots: dict, *slot_names: str) -> int:
    """Count total modification_history entries across the given slots."""
    total = 0
    for name in slot_names:
        total += len(slots.get(name, {}).get("modification_history", []))
    return total


def _parse_slot_items(value: str) -> list[str]:
    """Parse a slot value like 'Item A ($3.50/pp), Item B' into ['Item A', 'Item B']."""
    import re as _re
    if not value or value.strip().lower() in ("none", "no", "n/a", ""):
        return []
    # Strip price annotations: ($3.50/pp) or ($3.50)
    cleaned = _re.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', value)
    return [name.strip() for name in cleaned.split(',') if name.strip()]


async def ask_menu_changes_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about menu changes, allowing up to 3 revisions per menu."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    MAX_REVISIONS = 3
    total_revisions = state["slots"].get("_menu_revision_count", {}).get("value", 0)

    user_lower = user_msg.lower()

    # Detect if the user is directly requesting a change with specific details
    direct_change_check = await llm_extract(
        "The customer was asked if they want to make changes to their menu selections. "
        "Are they naming a SPECIFIC ITEM to add, remove, swap, or replace (e.g. 'remove Crab Cakes', 'add BBQ Chicken')? "
        "Return 'direct_change' ONLY if a specific menu item name is mentioned. "
        "Vague phrases like 'make changes', 'yes changes', 'no make changes', 'want to change' "
        "do NOT count — return 'response' for those.\n\n"
        "Return ONLY: direct_change or response",
        user_msg
    )
    directly_requesting_change = direct_change_check.strip().lower() == "direct_change"

    # If the user directly requested a change WITH details already in the message,
    # forward immediately to collect_menu_changes_node — no need to ask what they want.
    if directly_requesting_change:
        if total_revisions >= MAX_REVISIONS:
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n"
                "The customer wants more changes but the menu has already been revised several times. "
                "Politely let them know we'll go with the current selections and move on.",
                f"Current menu: {_slots_context(state)}"
            )
            state["current_node"] = "ask_desserts"
            state["messages"] = add_ai_message(state, response)
            return state
        return await collect_menu_changes_node(state)

    # Find the last AI message to understand the exact question framing
    last_ai_msg = ""
    from langchain_core.messages import AIMessage
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg.content
            break

    # Use LLM to determine: happy with selections (finalize) vs want to redo (re-show menu)
    # IMPORTANT: Pass the exact AI question so classifier understands framing direction.
    # "Everything good?" + "no" = change. "Any changes?" + "no" = keep. Framing matters.
    ctx = _recent_ctx(state)
    intent = await llm_extract(
        "Below is the exact question the AI asked the customer, followed by the customer's reply. "
        "Based on what the CUSTOMER ACTUALLY WANTS (not just yes/no word), determine if they want to "
        "CHANGE / redo / modify their menu, or KEEP it as-is and move on.\n\n"
        "Rules:\n"
        "- 'Everything good?' + 'yes/ok/sure/looks good' → keep\n"
        "- 'Everything good?' + 'no/not really/nah' → change\n"
        "- 'Any changes?' + 'no/nope/nothing' → keep\n"
        "- 'Any changes?' + 'yes/yeah' → change\n"
        "- If they name a specific dish to add/remove → change\n\n"
        f"Recent conversation:\n{ctx}\n\n"
        f"AI asked: {last_ai_msg}\n"
        f"Customer replied: {user_msg}\n\n"
        "Return ONLY: change or keep",
        user_msg
    )

    intent_val = intent.strip().lower()
    # Accept legacy "done" as equivalent to "keep"
    if intent_val == "done":
        intent_val = "keep"
    if intent_val == "change":
        if total_revisions >= MAX_REVISIONS:
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n"
                "Menu revised several times already. Let them know we'll finalize and move on.",
                f"Current menu: {_slots_context(state)}"
            )
            state["current_node"] = "ask_desserts"
        else:
            # Show the menu WITH current selection highlighted — route to collect_menu_changes
            # so picking an item does add/remove rather than wiping the full selection.
            current_dishes = get_slot_value(state["slots"], "selected_dishes") or ""
            current_note = f"**Your current selection:** {current_dishes}\n\n" if current_dishes else ""
            _, categorized = await get_main_dish_items()
            menu_list = build_numbered_list([], categories=categorized, category_headers=True)
            intro = await llm_respond(
                f"{SYSTEM_PROMPT}\n\nCustomer wants to change their dish selection. "
                "Write a casual 1-line transition telling them to tell you what to add, remove, or swap. Do NOT list items.",
                f"Current menu: {_slots_context(state)}"
            )
            response = f"{intro}\n\n{current_note}{menu_list}\n\nTell me what to add, remove, or swap!"
            state["current_node"] = "collect_menu_changes"
    else:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The menu is finalized. Confirm it looks great. "
            "Ask: Would you like to add desserts to your event?",
            f"Final menu: {_slots_context(state)}"
        )
        state["current_node"] = "ask_desserts"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_menu_changes_node(state: ConversationState) -> ConversationState:
    """Process menu change requests — actually updates the relevant slot (add/remove/replace)."""
    import re as _re
    import json as _json
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    menu = await load_menu_by_category()

    # --- Step 1: Use LLM to parse intent, items, and target slot ---
    extraction = await llm_extract(
        "You are a menu change parser. Analyze the customer's change request and return a JSON object with:\n"
        '- "action": one of "add", "remove", "replace"\n'
        '- "items": comma-separated names of items to add or remove\n'
        '- "replace_with": (only for replace action) comma-separated new item names\n'
        '- "slot": "dishes" if they are changing main dishes/entrees, "appetizers" if changing appetizers/hors d\'oeuvres\n'
        "Return ONLY valid JSON with no markdown, no explanation.",
        user_msg
    )

    try:
        raw = _re.sub(r"```(?:json)?|```", "", extraction).strip()
        change_data = _json.loads(raw)
        action = change_data.get("action", "add").lower()
        items_text = change_data.get("items", "").strip()
        replace_with = change_data.get("replace_with", "").strip()
        slot_target = change_data.get("slot", "dishes")
    except Exception:
        # Fallback: treat the whole message as "add to dishes"
        action = "add"
        items_text = user_msg
        replace_with = ""
        slot_target = "dishes"

    slot_name = "appetizers" if slot_target == "appetizers" else "selected_dishes"
    current_value = get_slot_value(state["slots"], slot_name) or ""
    current_items = _parse_slot_items(current_value)

    # --- Step 2: Apply the change ---
    if action == "remove" and items_text:
        matched_remove, _ = await _resolve_to_db_items(items_text, menu)
        remove_names = {item["name"].lower() for item in matched_remove}
        # Also do a loose keyword match for partial name removal
        remove_keywords = [p.strip().lower() for p in items_text.split(',') if p.strip()]
        updated_items = [
            name for name in current_items
            if name.lower() not in remove_names
            and not any(kw and kw in name.lower() for kw in remove_keywords)
        ]
        if updated_items:
            _, resolved_text = await _resolve_to_db_items(", ".join(updated_items), menu)
        else:
            resolved_text = current_value  # nothing matched to remove — keep original

    elif action == "replace":
        new_items_text = replace_with if replace_with else items_text
        matched_new, resolved_text = await _resolve_to_db_items(new_items_text, menu)
        if not matched_new:
            resolved_text = current_value  # nothing resolved — keep original

    else:  # add (default)
        if items_text:
            matched_new, _ = await _resolve_to_db_items(items_text, menu)
            existing_lower = {name.lower() for name in current_items}
            new_names = [item["name"] for item in matched_new if item["name"].lower() not in existing_lower]
            merged = current_items + new_names
            if merged:
                _, resolved_text = await _resolve_to_db_items(", ".join(merged), menu)
            else:
                resolved_text = current_value
        else:
            resolved_text = current_value

    # --- Step 3: Persist updated slot ---
    if resolved_text and resolved_text != current_value:
        fill_slot(state["slots"], slot_name, resolved_text)

    # Increment revision counter (used by ask_menu_changes_node cap check)
    rev_count = state["slots"].get("_menu_revision_count", {}).get("value", 0)
    state["slots"]["_menu_revision_count"] = {
        "value": rev_count + 1, "filled": True, "modified_at": None, "modification_history": []
    }

    # Always log the request in menu_notes for traceability
    existing_notes = get_slot_value(state["slots"], "menu_notes") or ""
    fill_slot(state["slots"], "menu_notes", f"{existing_notes}\nChange: {user_msg}".strip())

    context = (
        f"Customer requested: {user_msg}\n"
        f"Action taken: {action} on {slot_name}\n"
        f"Updated {slot_name}: {resolved_text}\n"
        f"All current selections: {_slots_context(state)}"
    )
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n"
        "The customer just made a change to their menu. "
        "Confirm exactly what was changed (what was added, removed, or replaced) "
        "and show their updated full selection clearly. "
        "Then ask: 'Would you like any other changes, or are you happy with this?'",
        context
    )

    state["current_node"] = "ask_menu_changes"
    state["messages"] = add_ai_message(state, response)
    return state

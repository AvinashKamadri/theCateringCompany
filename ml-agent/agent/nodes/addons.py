"""
Add-on nodes: utensils, desserts, rentals, florals.
"""

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_respond, llm_extract,
    is_affirmative, is_negative,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS
from agent.nodes.menu import get_dessert_context, _resolve_to_db_items
from database.db_manager import load_menu_by_category


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}


async def ask_utensils_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about utensils."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    mentions_utensils = bool(_re.search(r'\butensils?\b', user_msg, _re.IGNORECASE))
    if is_affirmative(user_msg) or (mentions_utensils and not is_negative(user_msg)):
        context = f"Customer wants utensils. Event: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_utensils']}", context
        )
        state["current_node"] = "select_utensils"
    else:
        fill_slot(state["slots"], "utensils", "no")
        context = f"Customer doesn't need utensils.\nSlots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer doesn't need utensils. Acknowledge. "
            "Ask: What type of service do you prefer? "
            "Options: Drop-off, Full-Service Buffet, or Full-Service On-site.",
            context
        )
        state["current_node"] = "select_service_type"

    state["messages"] = add_ai_message(state, response)
    return state


async def select_utensils_node(state: ConversationState) -> ConversationState:
    """Process utensil selection."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extraction = await llm_extract(
        "Extract the utensil type from the customer's message. "
        "Return ONLY the utensil type (e.g. 'eco-friendly', 'plastic', 'standard', 'biodegradable', 'bamboo'). "
        "Return NONE if no clear selection is made.",
        user_msg
    )
    utensil_value = extraction.strip() if extraction.strip().upper() != "NONE" else user_msg.strip()
    fill_slot(state["slots"], "utensils", utensil_value)

    context = f"Utensils selected: {extraction}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_utensils']}", context
    )

    state["current_node"] = "select_service_type"
    state["messages"] = add_ai_message(state, response)
    return state


async def ask_desserts_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about desserts — present real dessert items from DB."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Treat as affirmative if: standard yes-word OR user explicitly mentions "dessert"
    # (e.g. "lets go to desserts", "looks good, desserts please")
    mentions_dessert = bool(_re.search(r'\bdesserts?\b', user_msg, _re.IGNORECASE))
    wants_desserts = is_affirmative(user_msg) or (mentions_dessert and not is_negative(user_msg))

    if wants_desserts:
        # Fetch real dessert data from DB
        dessert_ctx = await get_dessert_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_desserts']}\n\n"
            "CRITICAL: Present ONLY the dessert items listed in the database context above. "
            "Copy item names verbatim. DO NOT add, rename, or invent any items.",
            dessert_ctx
        )
        state["current_node"] = "select_desserts"
    else:
        fill_slot(state["slots"], "desserts", "no")
        context = f"No desserts. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer doesn't want desserts. Acknowledge. "
            "Ask: Would you like us to provide utensils for your event?",
            context
        )
        state["current_node"] = "ask_utensils"

    state["messages"] = add_ai_message(state, response)
    return state


async def select_desserts_node(state: ConversationState) -> ConversationState:
    """Process dessert selections — resolve to actual DB items with prices."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # If user wants to skip, move on
    skip_patterns = r'\b(skip|no|none|pass|no desserts?|skip desserts?|not?\s+want|forget it|move on)\b'
    if is_negative(user_msg) or _re.search(skip_patterns, user_msg, _re.IGNORECASE):
        fill_slot(state["slots"], "desserts", "no")
        context = f"No desserts. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer skipped desserts. Acknowledge and move on.",
            context
        )
        state["current_node"] = "ask_utensils"
        state["messages"] = add_ai_message(state, response)
        return state

    # Load dessert-only menu for resolution (so "Coffee Bar" etc. match correctly)
    menu = await load_menu_by_category()
    dessert_menu = {}
    for cat_name, items in menu.items():
        cat_lower = cat_name.lower()
        if any(kw in cat_lower for kw in ["dessert", "coffee", "cake"]):
            dessert_menu[cat_name] = items

    # Build numbered list so LLM knows exact item names
    numbered_lines = []
    item_num = 1
    for items in dessert_menu.values():
        for item in items:
            numbered_lines.append(f"{item_num}. {item['name']}")
            item_num += 1
    numbered_str = "\n".join(numbered_lines)

    extraction = await llm_respond(
        "Extract the dessert selections from this customer message. "
        "Use the numbered list below to map references to exact item names. "
        "Return ONLY a comma-separated list of exact item names, nothing else.\n\n"
        f"Available desserts:\n{numbered_str}",
        f"Customer message: {user_msg}"
    )

    # Resolve against dessert-only menu
    matched_items, resolved_text = await _resolve_to_db_items(extraction, dessert_menu)

    if not matched_items:
        # Nothing matched — re-present dessert menu
        dessert_ctx = await get_dessert_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer mentioned desserts that are not on our menu. "
            "Politely let them know and re-present the dessert list. "
            "CRITICAL: Copy item names verbatim from the list below. No additions.",
            dessert_ctx
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Append to existing desserts if any
    existing = get_slot_value(state["slots"], "desserts")
    if existing and existing != "no":
        new_val = f"{existing}, {resolved_text}"
    else:
        new_val = resolved_text
    fill_slot(state["slots"], "desserts", new_val)

    context = f"Desserts selected: {new_val}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_desserts']}", context
    )

    state["current_node"] = "ask_more_desserts"
    state["messages"] = add_ai_message(state, response)
    return state


async def ask_more_desserts_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about more desserts."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_affirmative(user_msg):
        dessert_ctx = await get_dessert_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_more_desserts']}\n\n"
            "CRITICAL: Present ONLY the dessert items listed in the database context above. "
            "Copy item names verbatim. DO NOT add or invent. Customer already has: "
            f"{get_slot_value(state['slots'], 'desserts')}",
            dessert_ctx
        )
        state["current_node"] = "select_desserts"
    else:
        context = f"Desserts finalized. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nDessert selections are finalized. "
            "Ask: Would you like us to provide utensils for your event?",
            context
        )
        state["current_node"] = "ask_utensils"

    state["messages"] = add_ai_message(state, response)
    return state


async def ask_rentals_node(state: ConversationState) -> ConversationState:
    """Process rental selections (linen/table/chair/no)."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_negative(user_msg):
        fill_slot(state["slots"], "rentals", "no")
    else:
        extraction = await llm_extract(
            "Extract rental items from the customer's message. Options: linens, tables, chairs. "
            "Return ONLY a comma-separated list of what they chose (e.g. 'linens, tables'). "
            "Return NONE if none selected.",
            user_msg
        )
        fill_slot(state["slots"], "rentals", extraction.strip())

    # Route to florals for weddings, otherwise skip to special requests
    event_type = get_slot_value(state["slots"], "event_type")
    is_wedding = event_type and "wedding" in str(event_type).lower()

    if is_wedding:
        # Fetch floral items from DB to present
        floral_ctx = await _get_floral_context(state)
        context = f"Rentals: {get_slot_value(state['slots'], 'rentals')}\n{floral_ctx}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_florals']}",
            context
        )
        state["current_node"] = "ask_florals"
    else:
        fill_slot(state["slots"], "florals", "no")
        context = f"Rentals: {get_slot_value(state['slots'], 'rentals')}\nSlots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_special_requests']}", context
        )
        state["current_node"] = "ask_special_requests"

    state["messages"] = add_ai_message(state, response)
    return state


async def _get_floral_context(state) -> str:
    """Fetch floral arrangement items from DB and format for prompt."""
    menu = await load_menu_by_category()
    floral_items = []
    for cat_name, items in menu.items():
        if any(kw in cat_name.lower() for kw in ["floral", "flower", "bouquet", "arrangement"]):
            floral_items.extend(items)

    from agent.nodes.menu import _format_items_list
    formatted = _format_items_list(floral_items) if floral_items else "No floral items available."
    return (
        f"FLORAL ARRANGEMENTS FROM DATABASE (present these exact items):\n"
        f"{formatted}\n\n"
        f"Event: {_slots_context(state)}"
    )


async def ask_florals_node(state: ConversationState) -> ConversationState:
    """Process floral arrangement selections (wedding only)."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_negative(user_msg):
        fill_slot(state["slots"], "florals", "no")
    else:
        extraction = await llm_respond(
            "Extract the floral arrangement selections from this message. "
            "Return as a comma-separated list using the exact item names from the menu.",
            f"Customer message: {user_msg}"
        )
        matched_items, resolved_text = await _resolve_to_db_items(extraction)
        fill_slot(state["slots"], "florals", resolved_text if matched_items else extraction.strip())

    context = f"Florals: {get_slot_value(state['slots'], 'florals')}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_special_requests']}", context
    )

    state["current_node"] = "ask_special_requests"
    state["messages"] = add_ai_message(state, response)
    return state

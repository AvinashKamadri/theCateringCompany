"""
Add-on nodes: cocktail hour, buffet/plated, desserts, drinks, bar service,
tableware, rentals, labor services.
"""

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_respond, llm_extract,
    is_affirmative, is_negative, is_null_extraction,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS, EXTRACTION_PROMPTS
from agent.nodes.menu import (
    get_dessert_context, get_drink_context, get_appetizer_context,
    get_main_dishes_context, _resolve_to_db_items,
)
from database.db_manager import load_menu_by_category


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}


# ---------------------------------------------------------------------------
# Cocktail Hour
# ---------------------------------------------------------------------------

async def ask_cocktail_hour_node(state: ConversationState) -> ConversationState:
    """Ask about cocktail hour style (passed/station/both) and flow into appetizers."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Extract service style
    extracted = await llm_extract(
        EXTRACTION_PROMPTS["service_style"], user_msg
    )
    extracted = extracted.strip()

    if not is_null_extraction(extracted):
        fill_slot(state["slots"], "service_style", extracted)

    # Present appetizer menu
    appetizer_context = await get_appetizer_context(state)
    slots = _slots_context(state)
    context = (
        f"Cocktail hour style: {extracted}\n"
        f"Event details: {slots}\n\n"
        f"{appetizer_context}"
    )
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_cocktail_hour']}\n\n"
        "The customer chose their cocktail hour style. Confirm briefly. "
        "Now present the appetizer items from the database below. "
        "Ask them to pick as many as they'd like. "
        "CRITICAL: Use ONLY the exact items from the database context.",
        context
    )

    state["current_node"] = "select_appetizers"
    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Buffet or Plated
# ---------------------------------------------------------------------------

async def ask_buffet_or_plated_node(state: ConversationState) -> ConversationState:
    """Ask buffet vs plated for main course, then present the menu."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(
        EXTRACTION_PROMPTS["buffet_or_plated"], user_msg
    )
    extracted = extracted.strip()

    if not is_null_extraction(extracted):
        fill_slot(state["slots"], "buffet_or_plated", extracted)
        # Present main menu
        menu_context = await get_main_dishes_context(state)
        slots = _slots_context(state)
        plated_note = ""
        if "plated" in extracted.lower():
            plated_note = (
                "\nNote to include: 'Plated service is great — we'll fine-tune "
                "the details on a follow-up call.'"
            )
        context = (
            f"Service style: {extracted}{plated_note}\n"
            f"Event details: {slots}\n\n"
            f"{menu_context}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['present_menu']}\n\n"
            "Confirm their choice briefly. Then present the main menu from the database. "
            "Add: 'Think of this as a starting point — we can customize as your vision comes together.' "
            "CRITICAL: Use ONLY items from the database context. DO NOT invent items.",
            context
        )
        state["current_node"] = "select_dishes"
    else:
        # Unclear — re-ask
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_buffet_or_plated']}",
            f"Customer said: {user_msg}\nSlots: {_slots_context(state)}"
        )
        # Stay on same node

    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Desserts
# ---------------------------------------------------------------------------

async def ask_desserts_node(state: ConversationState) -> ConversationState:
    """Handle dessert question — detect item names before yes/no check."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Bug fix: detect specific dessert item names BEFORE yes/no check
    # so "lets do cookies" isn't interpreted as "no desserts"
    menu = await load_menu_by_category()
    dessert_menu = {}
    for cat_name, items in menu.items():
        cat_lower = cat_name.lower()
        if "dessert" in cat_lower or "cake" in cat_lower:
            dessert_menu[cat_name] = items

    # Check if user named specific dessert items
    all_dessert_names = []
    for items in dessert_menu.values():
        for item in items:
            all_dessert_names.append(item["name"].lower())

    user_lower = user_msg.lower()
    # Check for partial matches against dessert item keywords
    dessert_keywords = ["cookie", "brownie", "cheesecake", "lemon bar", "mousse",
                        "fruit tart", "blondie", "7-layer", "cake", "cupcake",
                        "mini dessert"]
    names_specific_item = any(kw in user_lower for kw in dessert_keywords)

    if names_specific_item:
        # Direct selection — skip yes/no, go straight to select_desserts
        return await select_desserts_node(state)

    mentions_dessert = bool(_re.search(r'\bdesserts?\b', user_msg, _re.IGNORECASE))
    wants_desserts = is_affirmative(user_msg) or (mentions_dessert and not is_negative(user_msg))

    if wants_desserts:
        dessert_ctx = await get_dessert_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_desserts']}\n\n"
            "CRITICAL: Present ONLY the dessert items listed in the database context. "
            "Copy item names verbatim. DO NOT add, rename, or invent any items.",
            dessert_ctx
        )
        state["current_node"] = "select_desserts"
    else:
        fill_slot(state["slots"], "desserts", "no")
        context = f"No desserts. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "Customer doesn't want desserts. Acknowledge briefly. "
            "Transition to drinks: 'Water, iced tea, and lemonade are included. "
            "Want to add coffee service or bar service?'",
            context
        )
        state["current_node"] = "ask_drinks"

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
            f"{SYSTEM_PROMPT}\n\nCustomer skipped desserts. Acknowledge. "
            "Transition to drinks.",
            context
        )
        state["current_node"] = "ask_drinks"
        state["messages"] = add_ai_message(state, response)
        return state

    # Load dessert-only menu for resolution (exclude coffee/drinks)
    menu = await load_menu_by_category()
    dessert_menu = {}
    event_type = (get_slot_value(state["slots"], "event_type") or "").lower()
    is_wedding = "wedding" in event_type
    for cat_name, items in menu.items():
        cat_lower = cat_name.lower()
        if "dessert" in cat_lower:
            dessert_menu[cat_name] = items
        elif is_wedding and "cake" in cat_lower:
            dessert_menu[cat_name] = items

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

    matched_items, resolved_text = await _resolve_to_db_items(extraction, dessert_menu)

    if not matched_items:
        dessert_ctx = await get_dessert_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer mentioned desserts not on our menu. "
            "Politely re-present the dessert list. "
            "CRITICAL: Copy item names verbatim. No additions.",
            dessert_ctx
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Deduplicate before storing
    existing = get_slot_value(state["slots"], "desserts")
    if existing and existing != "no":
        combined = f"{existing}, {resolved_text}"
    else:
        combined = resolved_text

    # Deduplicate the combined string
    import re as _re2
    parts = [_re2.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', p).strip()
             for p in combined.split(',') if p.strip()]
    seen: set[str] = set()
    deduped: list[str] = []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            deduped.append(p)
    if deduped:
        _, deduped_resolved = await _resolve_to_db_items(", ".join(deduped), dessert_menu)
        fill_slot(state["slots"], "desserts", deduped_resolved)
    else:
        fill_slot(state["slots"], "desserts", resolved_text)

    context = f"Desserts selected: {get_slot_value(state['slots'], 'desserts')}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_desserts']}\n\n"
        "Confirm dessert selections briefly. Move on to drinks.",
        context
    )

    state["current_node"] = "ask_drinks"
    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Drinks
# ---------------------------------------------------------------------------

async def ask_drinks_node(state: ConversationState) -> ConversationState:
    """Handle drink selections — coffee, bar service, or skip."""
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Check for bar-related keywords
    wants_bar = bool(_re.search(r'\b(bar|cocktail|beer|wine|liquor|open bar|full bar)\b',
                                user_msg, _re.IGNORECASE))

    # Check for coffee
    wants_coffee = bool(_re.search(r'\bcoffee\b', user_msg, _re.IGNORECASE))

    if wants_coffee:
        # Resolve coffee bar from DB
        menu = await load_menu_by_category()
        drink_menu = {cat: items for cat, items in menu.items()
                      if any(kw in cat.lower() for kw in ["drink", "coffee", "beverage"])}
        matched, resolved = await _resolve_to_db_items("Coffee Bar", drink_menu)
        if matched:
            fill_slot(state["slots"], "drinks", resolved)
        else:
            fill_slot(state["slots"], "drinks", "Coffee Bar")

    if wants_bar:
        # Route to bar service node
        context = f"Customer wants bar service. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_bar_service']}",
            context
        )
        state["current_node"] = "ask_bar_service"
    elif is_negative(user_msg):
        fill_slot(state["slots"], "drinks", get_slot_value(state["slots"], "drinks") or "no")
        context = f"No extra drinks. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer doesn't want extra drinks. Acknowledge. "
            "Move to tableware.",
            context
        )
        state["current_node"] = "ask_tableware"
    else:
        # Coffee only or just "yes" — check if they also want bar
        drink_ctx = await get_drink_context(state)
        if wants_coffee:
            context = (
                f"Customer added coffee. Drinks so far: {get_slot_value(state['slots'], 'drinks')}\n"
                f"{drink_ctx}\nSlots: {_slots_context(state)}"
            )
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n"
                "Customer added coffee. Confirm briefly. "
                "Ask if they'd also like bar service.",
                context
            )
            # Stay to catch bar response — but route to tableware if they say no
            state["current_node"] = "ask_bar_service"
        else:
            # Generic affirmative — show drink options
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_drinks']}",
                f"{drink_ctx}\nSlots: {_slots_context(state)}"
            )
            # Stay on ask_drinks to get specific selection

    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Bar Service
# ---------------------------------------------------------------------------

async def ask_bar_service_node(state: ConversationState) -> ConversationState:
    """Handle bar service package selection."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_negative(user_msg):
        fill_slot(state["slots"], "bar_service", "no")
        context = f"No bar service. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer doesn't want bar service. Acknowledge. "
            "Move to tableware.",
            context
        )
        state["current_node"] = "ask_tableware"
    else:
        # Extract bar package selection
        extraction = await llm_extract(
            "Extract the bar package selection. Options: "
            "'Beer & Wine' ($15/pp), 'Beer, Wine & Signature Cocktails' ($22/pp), "
            "'Full Open Bar' ($30/pp). "
            "Return the exact package name. If unclear, return NONE.",
            user_msg
        )
        if not is_null_extraction(extraction.strip()):
            fill_slot(state["slots"], "bar_service", extraction.strip())
            context = f"Bar package: {extraction.strip()}\nSlots: {_slots_context(state)}"
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n"
                f"Customer chose '{extraction.strip()}' bar package. "
                "Confirm briefly. Note bartender service is $50/hr (5-hr min). "
                "Move to tableware.",
                context
            )
            state["current_node"] = "ask_tableware"
        else:
            # Re-present options
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_bar_service']}",
                f"Customer said: {user_msg}\nSlots: {_slots_context(state)}"
            )
            # Stay on same node

    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Tableware
# ---------------------------------------------------------------------------

async def ask_tableware_node(state: ConversationState) -> ConversationState:
    """Handle tableware selection — standard/premium/china."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extraction = await llm_extract(EXTRACTION_PROMPTS["tableware"], user_msg)
    extracted = extraction.strip()

    if not is_null_extraction(extracted):
        fill_slot(state["slots"], "tableware", extracted)
    else:
        fill_slot(state["slots"], "tableware", "Standard")

    context = f"Tableware: {get_slot_value(state['slots'], 'tableware')}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n"
        "Confirm the tableware choice briefly. "
        "Ask about rentals: 'Do you need any rentals? We offer linens, tables, and chairs.'",
        context
    )

    state["current_node"] = "ask_rentals"
    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Rentals
# ---------------------------------------------------------------------------

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
        if not is_null_extraction(extraction.strip()):
            fill_slot(state["slots"], "rentals", extraction.strip())
        else:
            fill_slot(state["slots"], "rentals", "no")

    context = f"Rentals: {get_slot_value(state['slots'], 'rentals')}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_special_requests']}",
        context
    )

    state["current_node"] = "ask_special_requests"
    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Labor Services
# ---------------------------------------------------------------------------

async def ask_labor_services_node(state: ConversationState) -> ConversationState:
    """Present labor service options and collect selections."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_negative(user_msg):
        fill_slot(state["slots"], "labor_services", "no")
    else:
        extraction = await llm_extract(
            "Extract labor service selections from the customer's message. Options include: "
            "ceremony setup, table & chair setup, table preset, reception cleanup, "
            "trash removal, travel fee. "
            "Return a comma-separated list of selected services. "
            "Return NONE if none selected.",
            user_msg
        )
        if not is_null_extraction(extraction.strip()):
            fill_slot(state["slots"], "labor_services", extraction.strip())
        else:
            fill_slot(state["slots"], "labor_services", "no")

    context = f"Labor services: {get_slot_value(state['slots'], 'labor_services')}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_dietary']}",
        context
    )

    state["current_node"] = "collect_dietary"
    state["messages"] = add_ai_message(state, response)
    return state

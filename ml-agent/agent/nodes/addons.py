"""
Add-on nodes: utensils, desserts, rentals.
"""

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_respond, llm_extract,
    is_affirmative, is_negative, build_numbered_list,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS
from agent.nodes.menu import get_dessert_context, _resolve_to_db_items
from database.db_manager import load_menu_by_category


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}


async def ask_utensils_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about utensils."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_affirmative(user_msg):
        utensil_list = "1. Standard Plastic\n2. Eco-friendly / Biodegradable\n3. Bamboo"
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer wants utensils. Write one casual line asking which type. "
            "Do NOT list the options.",
            f"Event: {_slots_context(state)}"
        )
        response = f"{intro}\n\n{utensil_list}"
        state["current_node"] = "select_utensils"
    else:
        fill_slot(state["slots"], "utensils", "no")
        tableware_list = "1. Standard Disposable (included)\n2. Premium Disposable (gold or silver) — $1 per person\n3. Full China — pricing based on guest count"
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nNo utensils needed. Acknowledge briefly, then ask about tableware. "
            "Do NOT list the options.",
            f"Slots: {_slots_context(state)}"
        )
        response = f"{intro}\n\n{tableware_list}"
        state["current_node"] = "collect_tableware"

    state["messages"] = add_ai_message(state, response)
    return state


async def select_utensils_node(state: ConversationState) -> ConversationState:
    """Process utensil selection."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extraction = await llm_extract(
        "Extract the utensil type from the customer's message. "
        "Valid options: plastic, eco-friendly, biodegradable, bamboo. "
        "Return ONLY the type, or unclear if no clear selection.",
        user_msg
    )
    if extraction.strip().lower() == "unclear":
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer's answer didn't match a utensil type. "
            "Briefly clarify, then re-ask: plastic, eco-friendly, or bamboo?",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    fill_slot(state["slots"], "utensils", extraction.strip())

    tableware_list = "1. Standard Disposable (included)\n2. Premium Disposable (gold or silver) — $1 per person\n3. Full China — pricing based on guest count"
    intro = await llm_respond(
        f"{SYSTEM_PROMPT}\n\nUtensils confirmed. Now transition to tableware — "
        "write one casual line. Do NOT list the options.",
        f"Utensils: {extraction}"
    )
    response = f"{intro}\n\n{tableware_list}"

    state["current_node"] = "collect_tableware"
    state["messages"] = add_ai_message(state, response)
    return state


async def ask_desserts_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about desserts — present real dessert items from DB."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Use LLM to detect intent — handles slang, hype, enthusiasm naturally
    intent = await llm_extract(
        "Does this message mean the person wants desserts, or are they declining/skipping desserts? "
        "Consider any form of enthusiasm, excitement, or affirmation as 'yes'. "
        "Only return 'no' if they clearly decline (e.g. 'no thanks', 'skip', 'pass', 'none'). "
        "Return ONLY: yes or no",
        user_msg
    )
    wants_desserts = intent.strip().lower() != "no"

    if wants_desserts:
        # Python builds the dessert list — LLM only generates intro
        from agent.nodes.menu import get_dessert_items
        event_type = (get_slot_value(state["slots"], "event_type") or "").lower()
        dessert_items = await get_dessert_items(is_wedding="wedding" in event_type)
        dessert_list = build_numbered_list(dessert_items, show_price=True)

        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_desserts']}\n\n"
            "Write a brief casual intro for the dessert options. "
            "Do NOT list any items — the list will be appended automatically.",
            f"Event: {_slots_context(state)}"
        )
        response = f"{intro}\n\n{dessert_list}\n\nPick up to 4 mini desserts!"
        state["current_node"] = "select_desserts"
    else:
        fill_slot(state["slots"], "desserts", "no")
        context = f"No desserts. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_drinks']}",
            context
        )
        state["current_node"] = "collect_drinks"

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
            f"{SYSTEM_PROMPT}\n\nCustomer skipped desserts. Acknowledge briefly.\n\n{NODE_PROMPTS['collect_drinks']}",
            context
        )
        state["current_node"] = "collect_drinks"
        state["messages"] = add_ai_message(state, response)
        return state

    # Load dessert-only menu for resolution (so "Coffee Bar" etc. match correctly)
    menu = await load_menu_by_category()
    dessert_menu = {}
    for cat_name, items in menu.items():
        cat_lower = cat_name.lower()
        if any(kw in cat_lower for kw in ["dessert", "cake"]):
            dessert_menu[cat_name] = items

    # Build numbered list — expand mini dessert bundle into individual items from description
    numbered_lines = []
    item_num = 1
    for items in dessert_menu.values():
        for item in items:
            if "mini desserts" in item["name"].lower() and item.get("description"):
                # Expand bundle: show each sub-item individually
                for sub in item["description"].split(","):
                    sub = sub.strip()
                    if sub:
                        numbered_lines.append(f"{item_num}. {sub}")
                        item_num += 1
            else:
                numbered_lines.append(f"{item_num}. {item['name']}")
                item_num += 1
    numbered_str = "\n".join(numbered_lines)

    extraction = await llm_extract(
        "Extract the dessert selections from this customer message. "
        "The customer may refer to items by number or by name. "
        "Use the numbered list below to map numbers to exact item names. "
        "Return ONLY a comma-separated list of exact item names (no numbers, no extra text).\n\n"
        f"Available desserts:\n{numbered_str}",
        user_msg
    )

    # Try DB resolution first
    matched_items, resolved_text = await _resolve_to_db_items(extraction, dessert_menu)

    # Check if extraction matches mini dessert sub-items (from description, not standalone DB items)
    _BUNDLE_NAMES = {"mini desserts - select 4", "mini desserts"}
    _MINI_OPTIONS = set()
    for items in dessert_menu.values():
        for item in items:
            if item["name"].lower() in _BUNDLE_NAMES:
                for part in (item.get("description") or "").split(","):
                    part = part.strip().lower()
                    if part:
                        _MINI_OPTIONS.add(part)

    extraction_lower = extraction.strip().lower()

    # Case 1: user said just the package name → ask which 4
    if extraction_lower in _BUNDLE_NAMES:
        desc = ", ".join(sorted(_MINI_OPTIONS)).title()
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer chose Mini Desserts but didn't specify which items. "
            f"Ask them to pick up to 4 from: {desc}. Present as numbered list.",
            f"Available: {desc}"
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Case 2: user named individual mini dessert items → store directly
    extracted_items = [i.strip() for i in extraction.split(",") if i.strip()]
    mini_matches = [i for i in extracted_items if i.lower() in _MINI_OPTIONS]

    if mini_matches:
        resolved_text = f"Mini Desserts: {', '.join(mini_matches)}"
    elif matched_items and len(matched_items) == 1 and matched_items[0]["name"].lower() in _BUNDLE_NAMES:
        # DB resolved to bundle but extraction has specific items → use extraction
        resolved_text = f"Mini Desserts: {extraction.strip()}"

    if not resolved_text or resolved_text.upper() == "NONE":
        # Nothing extracted — re-present dessert menu
        dessert_ctx = await get_dessert_context(state)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "Couldn't catch those selections. Re-present the dessert list casually. "
            "CRITICAL: Copy item names verbatim from the list below. No additions.",
            dessert_ctx
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Append to existing desserts (deduplicate, cap at 4 for mini desserts)
    existing = get_slot_value(state["slots"], "desserts")

    # Parse existing items — strip "Mini Desserts: " prefix if present
    def _parse_dessert_items(val):
        if not val or val == "no":
            return []
        # Strip prefix like "Mini Desserts: "
        for prefix in ["Mini Desserts: ", "Mini Desserts:"]:
            if val.startswith(prefix):
                val = val[len(prefix):]
                break
        return [i.strip() for i in val.split(",") if i.strip()]

    existing_items = _parse_dessert_items(existing)
    new_raw = resolved_text
    for prefix in ["Mini Desserts: ", "Mini Desserts:"]:
        if new_raw.startswith(prefix):
            new_raw = new_raw[len(prefix):]
            break
    new_items_list = [i.strip() for i in new_raw.split(",") if i.strip()]

    existing_lower = {i.lower() for i in existing_items}
    deduped_new = [i for i in new_items_list if i.lower() not in existing_lower]
    combined = existing_items + deduped_new

    # Enforce 4-item max for mini desserts
    is_mini = "mini desserts" in resolved_text.lower() or (existing and "mini desserts" in existing.lower())
    max_items = 4 if is_mini else 20

    if len(combined) > max_items:
        # Too many — CLEAR previous selections and start fresh
        fill_slot(state["slots"], "desserts", None)
        state["slots"]["desserts"]["filled"] = False
        # Python-render the dessert options
        sorted_options = sorted(_MINI_OPTIONS, key=str.lower)
        dessert_reask_list = "\n".join(f"{i+1}. {opt.title()}" for i, opt in enumerate(sorted_options))
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer picked {len(combined)} but the limit is 4. "
            "Write one casual line explaining. Do NOT list the options.",
            f"Customer tried: {', '.join(combined)}"
        )
        response = f"{intro}\n\n{dessert_reask_list}\n\nPick up to 4 mini desserts!"
        # Stay on select_desserts — loop back with clean slate
        state["messages"] = add_ai_message(state, response)
        return state

    new_val = f"Mini Desserts: {', '.join(combined)}" if is_mini else ", ".join(combined)
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

    intent = await llm_extract(
        "The customer was asked 'Want to add anything else to the dessert lineup, or is that it?' "
        "Does their reply mean they are DONE with desserts, or do they want to ADD more? "
        "Phrases like 'that is all', 'that's it', 'this is all', 'nope', 'done', 'no', 'no more', "
        "'move on', 'looks good', 'we good', 'perfect' = done. "
        "Phrases like 'add', 'also', 'more', 'yes', or naming specific items = more. "
        "Return ONLY: done or more",
        user_msg
    )
    if intent.strip().lower() != "more":
        context = f"Desserts finalized. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nDessert selections are finalized.\n\n{NODE_PROMPTS['collect_drinks']}",
            context
        )
        state["current_node"] = "collect_drinks"
    else:
        # Python-render the dessert options for "add more"
        from agent.nodes.menu import get_dessert_items
        event_type = (get_slot_value(state["slots"], "event_type") or "").lower()
        d_items = await get_dessert_items(is_wedding="wedding" in event_type)
        d_list = build_numbered_list(d_items, show_price=True)
        current = get_slot_value(state["slots"], "desserts") or "none"
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer wants more desserts. Already has: {current}. "
            "Write one casual line. Do NOT list items.",
            f"Current: {current}"
        )
        response = f"{intro}\n\n{d_list}\n\nPick up to 4 mini desserts!"
        state["current_node"] = "select_desserts"

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
            "The customer was asked about rentals. Available options: 1=Linens, 2=Tables, 3=Chairs. "
            "The customer may type numbers, names, or both. "
            "Map: 1/linens → Linens, 2/tables → Tables, 3/chairs → Chairs. "
            "Return ONLY a comma-separated list (e.g. 'Linens, Tables'). "
            "If they said 'yes' or 'sure' WITHOUT specifying which ones, return 'ask'. "
            "Return NONE if they clearly don't want any.",
            user_msg
        )
        if extraction.strip().lower() == "ask":
            rental_list = "1. Linens\n2. Tables\n3. Chairs"
            intro = await llm_respond(
                f"{SYSTEM_PROMPT}\n\nCustomer wants rentals but didn't say which. "
                "Write one casual line asking which ones. Do NOT list them.",
                f"Customer said: {user_msg}"
            )
            response = f"{intro}\n\n{rental_list}\n\nPick one, multiple, or all!"
            state["messages"] = add_ai_message(state, response)
            return state
        fill_slot(state["slots"], "rentals", extraction.strip())

    # Route to labor (Onsite only) or special requests (Drop-off)
    service_type = get_slot_value(state["slots"], "service_type")
    is_onsite = service_type and "onsite" in str(service_type).lower()

    context = f"Rentals: {get_slot_value(state['slots'], 'rentals')}\nSlots: {_slots_context(state)}"
    if is_onsite:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_labor']}", context
        )
        state["current_node"] = "collect_labor"
    else:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_special_requests']}", context
        )
        state["current_node"] = "ask_special_requests"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_tableware_node(state: ConversationState) -> ConversationState:
    """Collect tableware choice — disposable, premium, or china."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    choice = await llm_extract(
        "The customer was shown tableware options: 1=Standard Disposable, 2=Premium Disposable ($1pp), 3=Full China. "
        "They may type a number or name. Extract their choice. "
        "Return ONLY: Standard Disposable, Premium Disposable, China, or unclear.",
        user_msg
    )
    if choice.strip().lower() == "unclear":
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer's answer didn't match the tableware options. "
            "Briefly explain you need to clarify, then re-ask with the 3 options: "
            "1. Standard Disposable (included), 2. Premium Disposable ($1pp), 3. Full China. "
            "Keep it casual.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    fill_slot(state["slots"], "tableware", choice.strip())

    # Check if plated was selected — auto-note china
    meal_style = get_slot_value(state["slots"], "meal_style") or ""
    china_note = ""
    if "plated" in meal_style.lower() and "china" not in choice.lower():
        china_note = " Note: plated packages include china automatically — we'll factor that in."

    service_list = "1. Drop-off (we deliver, no staff)\n2. Onsite (our team is there with you)"
    intro = await llm_respond(
        f"{SYSTEM_PROMPT}\n\nTableware: {choice.strip()}.{china_note} Confirm briefly, then ask about service type. "
        "Do NOT list the options.",
        f"Tableware: {choice}"
    )
    response = f"{intro}\n\n{service_list}"
    state["current_node"] = "select_service_type"
    state["messages"] = add_ai_message(state, response)
    return state


async def collect_labor_node(state: ConversationState) -> ConversationState:
    """Collect labor services — Onsite events only."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_negative(user_msg):
        fill_slot(state["slots"], "labor", "no")
    else:
        extraction = await llm_extract(
            "The customer was shown labor options: "
            "1=Ceremony Setup/Cleanup, 2=Table & Chair Setup, 3=Table Preset, "
            "4=Reception Cleanup, 5=Trash Removal, 6=Travel Fee. "
            "They may type numbers, names, or both. "
            "Return ONLY a comma-separated list of service names. "
            "If they said 'yes' or 'all', return all 6 services. "
            "Return NONE if they don't want any.",
            user_msg
        )
        fill_slot(state["slots"], "labor", extraction.strip() if extraction.strip().upper() != "NONE" else "no")

    context = f"Labor: {get_slot_value(state['slots'], 'labor')}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_special_requests']}", context
    )
    state["current_node"] = "ask_special_requests"
    state["messages"] = add_ai_message(state, response)
    return state


async def collect_drinks_node(state: ConversationState) -> ConversationState:
    """Collect drink preferences — water/tea/lemonade included, coffee/bar upsell."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    intent = await llm_extract(
        "The customer was told water/tea/lemonade are included, then asked if they want coffee or bar service. "
        "Does their reply mean: coffee, bar, both, or none? "
        "If they said 'yes' or something vague without specifying coffee or bar, return 'ask'. "
        "Return ONLY one of: coffee, bar, both, none, ask",
        user_msg
    )
    choice = intent.strip().lower()

    if choice == "ask":
        drink_options = "1. Coffee Service\n2. Bar Service\n3. Both"
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer said yes but didn't specify. Acknowledge briefly, then ask which. "
            "Do NOT list the options.",
            f"Customer said: {user_msg}"
        )
        response = f"{intro}\n\n{drink_options}"
        # Stay on this node
        state["messages"] = add_ai_message(state, response)
        return state

    if choice == "bar" or choice == "both":
        # Route to bar service sub-flow
        drinks_so_far = "Water, Iced Tea, Lemonade (included)"
        if choice == "both":
            drinks_so_far += ", Coffee Bar"
        fill_slot(state["slots"], "drinks", drinks_so_far)
        bar_list = "1. Beer & Wine\n2. Beer & Wine + Two Signature Drinks\n3. Full Open Bar"
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nMention bar back items ($8.50pp) or simple ice/coolers ($1.75pp). "
            "Then transition to bar packages. Do NOT list the packages.",
            f"Current drinks: {drinks_so_far}"
        )
        response = f"{intro}\n\n{bar_list}\n\nAll bar services include professional bartenders — $50/hr, 5-hour minimum."
        state["current_node"] = "collect_bar_service"
    elif choice == "coffee":
        fill_slot(state["slots"], "drinks", "Water, Iced Tea, Lemonade (included), Coffee Bar")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCoffee service added. Confirm briefly. "
            "Ask: Would you like us to provide utensils for your event?",
            f"Drinks: Coffee Bar added\nSlots: {_slots_context(state)}"
        )
        state["current_node"] = "ask_utensils"
    else:
        fill_slot(state["slots"], "drinks", "Water, Iced Tea, Lemonade (included)")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nNo extra drinks needed. Confirm briefly. "
            "Ask: Would you like us to provide utensils for your event?",
            f"Drinks: standard (included)\nSlots: {_slots_context(state)}"
        )
        state["current_node"] = "ask_utensils"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_bar_service_node(state: ConversationState) -> ConversationState:
    """Bar service sub-flow — Beer & Wine, Signature, Full Open Bar."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    bar_choice = await llm_extract(
        "The customer was shown bar options: 1=Beer & Wine, 2=Beer & Wine + Two Signature Drinks, 3=Full Open Bar. "
        "They may type a number or name. Extract their selection. "
        "Return ONLY: Beer & Wine, Beer & Wine + Two Signature Drinks, Full Open Bar, or unclear.",
        user_msg
    )
    bar_choice = bar_choice.strip()
    if bar_choice.lower() == "unclear":
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer's answer didn't match the bar options. "
            "Briefly explain you need to clarify, then re-ask with the 3 options: "
            "1. Beer & Wine, 2. Beer & Wine + Two Signature Drinks, 3. Full Open Bar.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Append bar choice to existing drinks
    existing = get_slot_value(state["slots"], "drinks") or ""
    new_val = f"{existing}, Bar Service: {bar_choice}" if existing else f"Bar Service: {bar_choice}"
    fill_slot(state["slots"], "drinks", new_val)

    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\nBar service selected: {bar_choice}. Confirm it. "
        "Note: 'All bar services include professional bartenders — $50/hr, 5-hour minimum.' "
        "Then ask: Would you like us to provide utensils for your event?",
        f"Drinks: {new_val}\nSlots: {_slots_context(state)}"
    )
    state["current_node"] = "ask_utensils"
    state["messages"] = add_ai_message(state, response)
    return state



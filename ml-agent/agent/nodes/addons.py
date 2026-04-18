"""
Add-on nodes: utensils, desserts, rentals.
"""

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_respond, llm_extract,
    build_numbered_list, norm_llm,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS
from agent.nodes.menu import get_dessert_context, _resolve_to_db_items
from database.db_manager import load_menu_by_category
from tools.modification_detection import _format_recent_messages


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled") and not k.startswith("__")}


def _recent_ctx(state, n: int = 6) -> str:
    """Compact recent conversation block for injecting into LLM classifier prompts."""
    msgs = list(state.get("messages", []))
    return _format_recent_messages(msgs, n=n) if msgs else ""


async def ask_utensils_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about utensils."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    wants_utensils = await llm_extract(
        "The customer was asked if they want utensils for their event. "
        "Classify their answer. 'unclear' is for ambiguous like 'maybe', 'not sure', 'idk', "
        "'what do you recommend'.\n\nReturn ONLY: yes, no, or unclear",
        user_msg
    )
    intent_norm = norm_llm(wants_utensils)
    if intent_norm == "unclear":
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer gave an ambiguous answer about utensils. "
            "Briefly explain: utensils = forks/knives/spoons for guests. Ask them warmly "
            "to decide yes or no. One short line.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    if intent_norm == "yes":
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
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Fast path: numeric choice (1=Plastic, 2=Eco-friendly, 3=Bamboo)
    _NUM_MAP = {"1": "Standard Plastic", "2": "Eco-friendly", "3": "Bamboo"}
    bare_num = _re.fullmatch(r'\s*([123])\s*\.?\s*', user_msg.strip())
    if bare_num:
        extraction = _NUM_MAP[bare_num.group(1)]
    else:
        extraction = await llm_extract(
            "Extract the utensil type from the customer's message. "
            "Options shown: 1=Standard Plastic, 2=Eco-friendly/Biodegradable, 3=Bamboo. "
            "Map numbers: 1→Standard Plastic, 2→Eco-friendly, 3→Bamboo. "
            "Return ONLY: Standard Plastic, Eco-friendly, Bamboo, or unclear.",
            user_msg
        )
    if norm_llm(extraction) == "unclear":
        retry_slot = state["slots"].get("_retry_utensils", {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"]["_retry_utensils"] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer's answer didn't match a utensil type. "
            "Acknowledge warmly, briefly clarify, then re-ask: plastic, eco-friendly, or bamboo? "
            "One short line. DO NOT pick one for them.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    else:
        state["slots"].pop("_retry_utensils", None)
    chosen = extraction.strip()
    fill_slot(state["slots"], "utensils", chosen)

    tableware_list = "1. Standard Disposable (included)\n2. Premium Disposable (gold or silver) — $1 per person\n3. Full China — pricing based on guest count"
    intro = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n"
        f"The customer picked '{chosen}' utensils — confirm that specific choice briefly "
        f"(e.g. '{chosen.capitalize()} it is!' or 'Going with {chosen} — nice.'). "
        "Then ask what tableware they want. One casual line total. "
        "Do NOT say 'no utensils' — they ARE getting utensils. Do NOT list tableware options.",
        f"Utensils chosen: {chosen}"
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
    wants_desserts = norm_llm(intent) != "no"

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
        response = f"{intro}\n\n{dessert_list}\n\nPick up to 4 items total!"
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
    ctx = _recent_ctx(state)
    skip_check = await llm_extract(
        "The customer was shown a dessert menu and asked to pick items. "
        "Are they skipping/declining desserts, or making selections?\n\n"
        f"Recent conversation:\n{ctx}\n\n"
        "Return ONLY: skip or selecting",
        user_msg
    )
    if norm_llm(skip_check) == "skip":
        fill_slot(state["slots"], "desserts", "no")
        context = f"No desserts. Slots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer skipped desserts. Acknowledge briefly.\n\n{NODE_PROMPTS['collect_drinks']}",
            context
        )
        state["current_node"] = "collect_drinks"
        state["messages"] = add_ai_message(state, response)
        return state

    # Use get_dessert_items() which expands bundle sub-items into individual named items.
    # This ensures "Lemon Bars", "Fruit Tarts" etc. are resolvable even though they live
    # in a bundle description in the DB rather than as standalone rows.
    from agent.nodes.menu import get_dessert_items as _get_dessert_items
    event_type_val = (get_slot_value(state["slots"], "event_type") or "").lower()
    expanded_items = await _get_dessert_items(is_wedding="wedding" in event_type_val)

    # Build numbered list from expanded items for extraction context
    numbered_lines = [f"{i+1}. {item['name']}" for i, item in enumerate(expanded_items)]
    numbered_str = "\n".join(numbered_lines)

    # Build a flat lookup: name_lower → item dict (for resolution)
    expanded_lookup = {item["name"].lower(): item for item in expanded_items}

    # Also keep the raw dessert_menu for DB-resolution fallback
    menu = await load_menu_by_category()
    dessert_menu = {k: v for k, v in menu.items() if any(kw in k.lower() for kw in ["dessert", "cake"])}

    extraction = await llm_extract(
        "Extract the dessert selections from this customer message. "
        "The customer may refer to items by number or by name. "
        "Use the numbered list below to map numbers to exact item names. "
        "Return ONLY a comma-separated list of exact item names (no numbers, no extra text).\n\n"
        f"Available desserts:\n{numbered_str}",
        user_msg
    )

    # Resolve against expanded items first (handles sub-items like Lemon Bars, Fruit Tarts),
    # then fall back to raw DB resolution for bundle-level items.
    extracted_names = [n.strip() for n in extraction.split(",") if n.strip()]
    matched_items = []
    resolved_names = []
    for name in extracted_names:
        name_lower = name.lower()
        if name_lower in expanded_lookup:
            matched_items.append(expanded_lookup[name_lower])
            resolved_names.append(expanded_lookup[name_lower]["name"])
        else:
            # Partial match fallback
            for key, item in expanded_lookup.items():
                if name_lower in key or key in name_lower:
                    if item["name"] not in resolved_names:
                        matched_items.append(item)
                        resolved_names.append(item["name"])
                    break

    if resolved_names:
        # Format with prices for display
        parts = []
        for item in matched_items:
            if item.get("unit_price"):
                parts.append(f"{item['name']} (${item['unit_price']:.2f}/{item.get('price_type','pp')})")
            else:
                parts.append(item["name"])
        resolved_text = ", ".join(p.split(" ($")[0] for p in parts)  # store names only, prices added by build
        # Store as plain names for slot value
        resolved_text = ", ".join(resolved_names)
    else:
        # Fall back to original DB resolution for bundle-level names
        matched_items, resolved_text = await _resolve_to_db_items(extraction, dessert_menu)

    # Check if extraction matches mini dessert sub-items (from description, not standalone DB items).
    # Robust detection: any dessert item whose NAME contains "mini" contributes its description
    # entries as valid sub-options. Also accept common exact bundle names as fallback.
    _BUNDLE_NAMES = {"mini desserts - select 4", "mini desserts"}
    _MINI_OPTIONS = set()
    _DETECTED_BUNDLE_NAMES = set()
    for items in dessert_menu.values():
        for item in items:
            name_lower = item["name"].lower()
            is_bundle = name_lower in _BUNDLE_NAMES or "mini" in name_lower
            if is_bundle and item.get("description"):
                _DETECTED_BUNDLE_NAMES.add(name_lower)
                for part in item["description"].split(","):
                    part = part.strip().lower()
                    if part:
                        _MINI_OPTIONS.add(part)
    # Merge detected bundle names into canonical set so downstream checks work uniformly
    _BUNDLE_NAMES = _BUNDLE_NAMES | _DETECTED_BUNDLE_NAMES

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
        # Also keep non-mini DB items the user selected (e.g. Barback Package, Coffee Bar)
        mini_lower = {m.lower() for m in mini_matches}
        db_non_mini = [item["name"] for item in matched_items if item["name"].lower() not in mini_lower and item["name"].lower() not in _BUNDLE_NAMES]
        if db_non_mini:
            resolved_text = f"Mini Desserts: {', '.join(mini_matches)}, {', '.join(db_non_mini)}"
        else:
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

    # Enforce 4-item cap for mini desserts — count only mini items (not cakes/cupcakes/coffee).
    # Normalize names for matching (lowercase + collapse whitespace) so capitalization
    # and punctuation variants don't slip through the cap.
    def _norm(s: str) -> str:
        return _re.sub(r'\s+', ' ', s.strip().lower())
    mini_options_norm = {_norm(o) for o in _MINI_OPTIONS} if _MINI_OPTIONS else set()
    mini_in_combined = [i for i in combined if _norm(i) in mini_options_norm] if mini_options_norm else []
    # Fallback: if _MINI_OPTIONS is empty, treat ALL selected items as mini if resolved_text had the prefix
    has_mini_prefix = "mini desserts" in resolved_text.lower() or (existing and "mini desserts" in (existing or "").lower())
    if not mini_options_norm and has_mini_prefix:
        mini_in_combined = combined  # treat all as mini

    # Absolute total cap: max 4 dessert items total (mini + non-mini combined)
    MINI_CAP = 4
    TOTAL_CAP = 4
    over_mini = len(mini_in_combined) > MINI_CAP
    over_total = len(combined) > TOTAL_CAP

    if over_mini or over_total:
        # Cap exceeded — clear the selection and re-present the dessert menu so the customer re-picks.
        state["slots"]["desserts"] = {
            "value": None, "filled": False,
            "modified_at": None, "modification_history": [],
        }
        from agent.nodes.menu import get_dessert_items
        event_type = (get_slot_value(state["slots"], "event_type") or "").lower()
        d_items = await get_dessert_items(is_wedding="wedding" in event_type)
        dessert_list = build_numbered_list(d_items, show_price=True)
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer tried to pick {len(combined)} desserts but the cap is {TOTAL_CAP}. "
            "Tell them warmly, in ONE short line, that we can't keep more than 4 items and ask them to re-pick up to 4. "
            "Do NOT list any items — the list is appended automatically.",
            f"Customer tried: {', '.join(combined)}"
        )
        response = f"{intro}\n\n{dessert_list}\n\nPick up to 4 items total!"
        state["current_node"] = "select_desserts"
        state["messages"] = add_ai_message(state, response)
        return state

    # Combine mini and non-mini into final slot value
    non_mini_in_combined = [i for i in combined if _norm(i) not in mini_options_norm] if mini_options_norm else []
    has_any_mini = bool(mini_in_combined) or has_mini_prefix
    if has_any_mini and mini_in_combined:
        mini_part = f"Mini Desserts: {', '.join(mini_in_combined)}"
        new_val = f"{mini_part}, {', '.join(non_mini_in_combined)}" if non_mini_in_combined else mini_part
    else:
        new_val = ", ".join(combined)
    fill_slot(state["slots"], "desserts", new_val)

    # Resume-after-mod: if we entered here via a mid-conversation @AI edit,
    # just acknowledge and jump back to where the user was — don't run ask_more_desserts.
    resume_slot = state["slots"].pop("__resume_after_mod__", None)
    resume_node = resume_slot["value"] if resume_slot and resume_slot.get("filled") else None
    if resume_node:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer just updated desserts to: {new_val}. "
            "Briefly confirm the update in ONE short line. Do NOT ask any new question.",
            f"Desserts: {new_val}"
        )
        state["current_node"] = resume_node
        state["messages"] = add_ai_message(state, response)
        return state

    # No affirmation — go straight to the drinks step. If the user wants to
    # change desserts later they'll do it via a natural correction which routes
    # to check_modifications.
    context = f"Desserts selected: {new_val}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\nCustomer just finalized desserts: {new_val}. "
        "Briefly confirm the selection in ONE short line (no follow-up question about adding more), "
        "then immediately ask the drinks question.\n\n"
        f"{NODE_PROMPTS['collect_drinks']}",
        context
    )

    state["current_node"] = "collect_drinks"
    state["messages"] = add_ai_message(state, response)
    return state


async def ask_more_desserts_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about more desserts."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Look at the last AI message to understand exact question framing
    last_ai_msg = ""
    from langchain_core.messages import AIMessage
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, AIMessage):
            last_ai_msg = msg.content
            break

    ctx = _recent_ctx(state)
    intent = await llm_extract(
        "The AI just asked the customer if they want to add more desserts or if they're done. "
        "Based on the exact question + customer reply, determine their intent.\n\n"
        "Rules:\n"
        "- 'yes', 'yeah', 'yep', 'sure' → more (they want to add more)\n"
        "- 'no', 'nope', 'that's it', 'nothing else', 'all good', 'done' → done\n"
        "- Naming specific dessert items → more\n"
        "- Ambiguous one-word replies → lean 'more' if question was 'anything else?' (positive framing)\n\n"
        f"Recent conversation:\n{ctx}\n\n"
        f"AI asked: {last_ai_msg}\n"
        f"Customer replied: {user_msg}\n\n"
        "Return ONLY: more or done",
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

    extraction = await llm_extract(
        "The customer was asked about rentals. Available options: 1=Linens, 2=Tables, 3=Chairs. "
        "The customer may type numbers, names, or both. "
        "Map: 1/linens → Linens, 2/tables → Tables, 3/chairs → Chairs. "
        "Return ONLY a comma-separated list (e.g. 'Linens, Tables'). "
        "If they gave a vague answer like 'yes', 'sure', 'okay' WITHOUT specifying which ones, return ASK. "
        "Return NONE if they clearly don't want any.",
        user_msg
    )
    if extraction.strip().upper() == "NONE":
        fill_slot(state["slots"], "rentals", "no")
    elif extraction.strip().upper() == "ASK":
        rental_list = "1. Linens\n2. Tables\n3. Chairs"
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer wants rentals but didn't say which. "
            "Write one casual line asking which ones. Do NOT list them.",
            f"Customer said: {user_msg}"
        )
        response = f"{intro}\n\n{rental_list}\n\nPick one, multiple, or all!"
        state["messages"] = add_ai_message(state, response)
        return state
    else:
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
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Fast path: numeric choice
    _NUM_MAP = {"1": "Standard Disposable", "2": "Premium Disposable", "3": "China"}
    bare_num = _re.fullmatch(r'\s*([123])\s*\.?\s*', user_msg.strip())
    if bare_num:
        choice = _NUM_MAP[bare_num.group(1)]
    else:
        choice = await llm_extract(
            "The customer was shown tableware options: 1=Standard Disposable, 2=Premium Disposable ($1pp), 3=Full China. "
            "Map numbers: 1→Standard Disposable, 2→Premium Disposable, 3→China. "
            "Return ONLY: Standard Disposable, Premium Disposable, China, or unclear.",
            user_msg
        )
    if norm_llm(choice) == "unclear":
        retry_slot = state["slots"].get("_retry_tableware", {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"]["_retry_tableware"] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer's answer didn't match the tableware options. "
            "Acknowledge warmly, briefly clarify, then re-ask with the 3 options: "
            "1. Standard Disposable (included), 2. Premium Disposable ($1pp), 3. Full China. "
            "One short line. DO NOT pick one for them.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    else:
        state["slots"].pop("_retry_tableware", None)
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

    extraction = await llm_extract(
        "The customer was shown labor options: "
        "1=Ceremony Setup/Cleanup, 2=Table & Chair Setup, 3=Table Preset, "
        "4=Reception Cleanup, 5=Trash Removal, 6=Travel Fee. "
        "They may type numbers, names, or both. "
        "Return ONLY a comma-separated list of service names. "
        "If they said 'yes' or 'all', return all 6 services. "
        "If they gave a vague answer like 'okay', 'sure', 'yes' WITHOUT specifying which ones, return ASK. "
        "Return NONE if they don't want any.",
        user_msg
    )
    if extraction.strip().upper() == "ASK":
        labor_list = (
            "1. Ceremony Setup/Cleanup — $1.50 per person\n"
            "2. Table & Chair Setup — $2.00 per person\n"
            "3. Table Preset (plates, napkins, cutlery) — $1.75 per person\n"
            "4. Reception Cleanup — $3.75 per person\n"
            "5. Trash Removal — $175 flat\n"
            "6. Travel Fee — $150 (30 min) / $250 (1 hr) / $375+ (extended)"
        )
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer wants labor services but didn't specify which. "
            "Write one casual line asking which ones they need. Do NOT list them.",
            f"Customer said: {user_msg}"
        )
        response = f"{intro}\n\n{labor_list}\n\nFeel free to pick multiple or none!"
        state["messages"] = add_ai_message(state, response)
        return state
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
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Fast path: numeric choice (1=Coffee, 2=Bar, 3=Both) — skip LLM
    _NUM_MAP = {"1": "coffee", "2": "bar", "3": "both"}
    stripped = user_msg.strip()
    bare_num_match = _re.fullmatch(r'\s*([123])\s*\.?\s*', stripped)
    if bare_num_match:
        choice = _NUM_MAP[bare_num_match.group(1)]
    else:
        intent = await llm_extract(
            "The customer was told water/tea/lemonade are included, then asked if they want coffee or bar service. "
            "The options shown were: 1=Coffee Service, 2=Bar Service, 3=Both. "
            "Map their reply to: coffee, bar, both, or none. "
            "Number mapping: '1' → coffee, '2' → bar, '3' → both. "
            "If they clearly decline (no/skip/nothing) → none. "
            "If they said 'yes' or vague without specifying → 'ask'. "
            "Return ONLY one of: coffee, bar, both, none, ask",
            user_msg
        )
        choice = intent.strip().lower()

    if choice == "ask":
        retry_slot = state["slots"].get("_retry_drinks", {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"]["_retry_drinks"] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        drink_options = "1. Coffee Service\n2. Bar Service\n3. Both"
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer said yes but didn't specify which drink service. "
            "Acknowledge warmly, then ask which (coffee, bar, or both). Do NOT list the options. "
            "One short line. DO NOT pick one for them.",
            f"Customer said: {user_msg}"
        )
        response = f"{intro}\n\n{drink_options}"
        state["messages"] = add_ai_message(state, response)
        return state
    else:
        state["slots"].pop("_retry_drinks", None)

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
    import re as _re
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Fast path: numeric choice
    _NUM_MAP = {
        "1": "Beer & Wine",
        "2": "Beer & Wine + Two Signature Drinks",
        "3": "Full Open Bar",
    }
    bare_num = _re.fullmatch(r'\s*([123])\s*\.?\s*', user_msg.strip())
    if bare_num:
        bar_choice = _NUM_MAP[bare_num.group(1)]
    else:
        bar_choice = await llm_extract(
            "The customer was shown bar options: 1=Beer & Wine, 2=Beer & Wine + Two Signature Drinks, 3=Full Open Bar. "
            "Map numbers: 1→Beer & Wine, 2→Beer & Wine + Two Signature Drinks, 3→Full Open Bar. "
            "Return ONLY: Beer & Wine, Beer & Wine + Two Signature Drinks, Full Open Bar, or unclear.",
            user_msg
        )
    bar_choice = bar_choice.strip()
    if bar_choice.lower() == "unclear":
        retry_slot = state["slots"].get("_retry_bar", {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"]["_retry_bar"] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer's answer didn't match the bar options. "
            "Acknowledge warmly, briefly clarify, then re-ask with the 3 options: "
            "1. Beer & Wine, 2. Beer & Wine + Two Signature Drinks, 3. Full Open Bar. "
            "One short line. DO NOT pick one for them.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    else:
        state["slots"].pop("_retry_bar", None)

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



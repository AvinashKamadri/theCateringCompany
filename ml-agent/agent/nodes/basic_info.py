"""
Basic info collection nodes: name, date, service type, event type, venue,
guest count, service style.
"""

from datetime import datetime

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_extract, llm_respond,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS, EXTRACTION_PROMPTS
from agent.nodes.menu import get_main_dishes_context


async def _extract_and_respond(state, slot_name, next_node, node_key):
    """Common pattern: extract a slot value, generate response, advance node.

    Ambiguity handling: if extraction fails (returns NONE), stay on the same
    node and ask the user to clarify — do NOT advance to next_node.
    """
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Extract slot value (format prompt with today's date if needed)
    prompt = EXTRACTION_PROMPTS[slot_name]
    if "{today}" in prompt:
        prompt = prompt.format(today=datetime.now().strftime("%Y-%m-%d"))
    extracted = await llm_extract(prompt, user_msg)
    extracted = extracted.strip()

    extraction_succeeded = extracted and extracted.upper() != "NONE"

    if extraction_succeeded:
        # Normalize guest_count to int
        if slot_name == "guest_count":
            try:
                extracted = int("".join(c for c in extracted if c.isdigit()))
            except ValueError:
                extracted = extracted

        fill_slot(state["slots"], slot_name, extracted)

    # Build context for response
    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    if extraction_succeeded:
        # Success — confirm and move to next node
        context = (
            f"Customer said: {user_msg}\nExtracted {slot_name}: {extracted}\n"
            f"CURRENT slot values (use THESE, not earlier conversation): {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS[node_key]}",
            context,
        )
        state["current_node"] = next_node
    else:
        # Ambiguous — stay on the same node and ask for clarification
        context = (
            f"Customer said: {user_msg}\n"
            f"Could NOT extract a clear value for '{slot_name}'. "
            f"The response was ambiguous or unrelated.\n"
            f"Slots so far: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            f"The customer's response was unclear for the '{slot_name}' field. "
            f"Politely acknowledge what they said, then re-ask the question for {slot_name}. "
            f"Give an example of what a good answer looks like.",
            context,
        )
        # Stay on the CURRENT node (don't advance)
        # current_node is already correct from state

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_name_node(state: ConversationState) -> ConversationState:
    return await _extract_and_respond(state, "name", "select_event_type", "collect_name")


async def collect_event_date_node(state: ConversationState) -> ConversationState:
    return await _extract_and_respond(state, "event_date", "collect_venue", "collect_event_date")


async def select_service_type_node(state: ConversationState) -> ConversationState:
    """Extract service type and move on. Custom handling to prevent re-asking loop."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["service_type"], user_msg)
    extracted = extracted.strip()

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "service_type", extracted)
        slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
        # Directly confirm and ask about rentals — do NOT mention service type options
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            f"The customer selected '{extracted}' as their service type. "
            "Confirm this in ONE short sentence. "
            "Then ask: Do you need any rentals for your event? "
            "We offer linens, tables, and chairs — you can select multiple or none. "
            "CRITICAL: Do NOT ask about service type again. It is already set.",
            f"Service type: {extracted}\nSlots: {slots_summary}",
        )
        state["current_node"] = "ask_rentals"
    else:
        slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer's response was unclear for service type. "
            "Ask them to choose one: Drop-off, Full-Service Buffet, or Full-Service On-site. "
            "Briefly explain: Drop-off means we deliver and set up, "
            "Full-Service Buffet means staff serves buffet-style, "
            "Full-Service On-site means full plated/attended service.",
            f"Customer said: {user_msg}\nSlots: {slots_summary}",
        )
        # Stay on same node

    state["messages"] = add_ai_message(state, response)
    return state


async def select_event_type_node(state: ConversationState) -> ConversationState:
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["event_type"], user_msg)
    extracted = extracted.strip()

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    # If the customer said "Custom" but hasn't described their event yet,
    # stay on this node and ask what kind of event it is.
    is_bare_custom = extracted.lower() == "custom"
    already_asking_custom = get_slot_value(state["slots"], "event_type") == "Custom - pending description"

    if is_bare_custom and not already_asking_custom:
        # Mark that we're waiting for a custom description, then ask
        fill_slot(state["slots"], "event_type", "Custom - pending description")
        context = f"Customer said: {user_msg}\nSlots: {slots_summary}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer said 'custom event'. Acknowledge that warmly, then ask: "
            "'That sounds exciting! Could you tell me a bit more about what kind of event you have in mind?'",
            context,
        )
        # Stay on select_event_type
        state["messages"] = add_ai_message(state, response)
        return state

    # If we were waiting for a custom description, use the full message as the event type
    if already_asking_custom:
        event_description = await llm_extract(
            "The customer is describing their custom event type. "
            "Extract a concise event name/description (e.g. 'Charity Gala', 'Product Launch', 'Retirement Party'). "
            "Return ONLY the event description, max 5 words.",
            user_msg,
        )
        extracted = event_description.strip() if event_description.strip().upper() != "NONE" else user_msg.strip()

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "event_type", extracted)

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
    context = (
        f"Customer said: {user_msg}\nEvent type: {extracted}\n"
        f"CURRENT slot values: {slots_summary}"
    )

    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_event_type']}",
        context,
    )

    state["current_node"] = "collect_event_date"
    state["messages"] = add_ai_message(state, response)
    return state


async def wedding_message_node(state: ConversationState) -> ConversationState:
    """Special heartfelt message for weddings, then collect venue.

    Defensive: if event_type was changed away from Wedding (via @AI),
    falls back to a generic venue collection prompt.
    """
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Try to extract venue if they gave it along with event type
    extracted = await llm_extract(EXTRACTION_PROMPTS["venue"], user_msg)
    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "venue", extracted.strip())
        next_node = "collect_guest_count"
    else:
        next_node = "collect_venue"

    # Check if event_type is still a wedding (may have changed via @AI)
    event_type = get_slot_value(state["slots"], "event_type")
    is_wedding = event_type and "wedding" in str(event_type).lower()

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    if is_wedding:
        context = f"Customer said: {user_msg}\nThis is a WEDDING.\nCURRENT slot values: {slots_summary}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['wedding_message']}",
            context,
        )
    else:
        # Event type changed — use generic venue prompt instead
        context = (
            f"Customer said: {user_msg}\n"
            f"Event type: {event_type}\nCURRENT slot values: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_venue']}",
            context,
        )

    state["current_node"] = next_node
    state["messages"] = add_ai_message(state, response)
    return state


async def collect_venue_node(state: ConversationState) -> ConversationState:
    """Collect venue — requires a proper venue name or address.

    Informal/vague answers like 'my home', 'my backyard' are NOT accepted.
    The bot asks for clarification with a specific address or venue name.
    """
    import re as _re
    from prompts.system_prompts import EXTRACTION_PROMPTS
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    t = user_msg.strip().lower()

    # --- Vague venue detection ---
    # Category 1: Informal/personal places (my home, backyard, etc.)
    _VAGUE_PERSONAL = [
        r'\b(my\s+)?(home|house|place|gome|hme|apartment|flat|condo)\b',
        r'\b(my\s+)?(backyard|garden|yard|patio|garage|driveway|rooftop)\b',
        r'\b(my\s+)?(office|workplace|work)\b',
        r'\b(here|there|somewhere|tbd|not sure|undecided|idk|dunno)\b',
    ]
    # Category 2: Generic place TYPES without a specific name/address
    # e.g. "public school", "a church", "the park" — need to know WHICH one
    _GENERIC_PLACE_TYPES = [
        r'\b(school|church|mosque|temple|synagogue)\b',
        r'\b(park|beach|lake|field|playground|community center)\b',
        r'\b(restaurant|hotel|motel|inn|lodge|resort)\b',
        r'\b(hall|banquet|club|bar|pub|cafe|cafeteria)\b',
        r'\b(library|museum|gallery|theater|theatre|stadium|arena)\b',
    ]

    is_vague_personal = any(_re.search(p, t) for p in _VAGUE_PERSONAL)
    is_generic_type = any(_re.search(p, t) for p in _GENERIC_PLACE_TYPES)

    # Check if user included a specific name or address detail that makes it acceptable
    # e.g. "Lincoln Public School", "the park on 5th Ave", "Hilton Hotel, downtown"
    has_address_detail = bool(_re.search(
        r'(\d+\s+\w+\s+(st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|ln|lane|way|ct|court|pl|place))'
        r'|(\b\d{5}\b)'  # zip code
        r'|(\w+,\s*\w+)'  # City, State pattern
        , t, _re.IGNORECASE
    ))
    # A proper name before the generic type (e.g. "Lincoln School", "Riverside Park")
    # Excludes generic qualifiers like "public", "local", "the", "a", "my", "nearby"
    _GENERIC_QUALIFIERS = r'^(a|an|the|my|our|some|local|public|private|nearby|big|small|old|new)\s+'
    venue_stripped = _re.sub(_GENERIC_QUALIFIERS, '', user_msg.strip(), flags=_re.IGNORECASE).strip()
    # After stripping qualifiers, if it's JUST the place type word, it's generic
    _PLACE_TYPE_WORDS = {'school', 'church', 'mosque', 'temple', 'park', 'beach', 'lake',
                         'field', 'restaurant', 'hotel', 'motel', 'hall', 'banquet', 'club',
                         'bar', 'pub', 'cafe', 'library', 'museum', 'gallery', 'theater',
                         'theatre', 'stadium', 'arena', 'resort', 'inn', 'lodge', 'cafeteria',
                         'playground', 'synagogue', 'community center'}
    has_proper_name = (
        is_generic_type
        and venue_stripped.lower() not in _PLACE_TYPE_WORDS
        and len(venue_stripped.split()) >= 2
    )
    # More than 3 words usually means it's specific enough (e.g. "the public school near downtown")
    is_descriptive_enough = len(user_msg.strip().split()) > 3

    needs_clarification = False
    clarification_reason = ""

    if is_vague_personal and not has_address_detail:
        needs_clarification = True
        clarification_reason = "personal"
    elif is_generic_type and not has_address_detail and not has_proper_name and not is_descriptive_enough:
        needs_clarification = True
        clarification_reason = "generic"

    if needs_clarification:
        slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
        context = (
            f"Customer said: {user_msg}\n"
            f"This is too vague for a venue (reason: {clarification_reason}). Slots: {slots_summary}"
        )
        if clarification_reason == "personal":
            prompt_detail = (
                "The customer gave a vague personal venue like 'my home' or 'my backyard'. "
                "We need a proper address for the catering contract. "
                "Politely ask: 'I appreciate that! For the catering contract, "
                "could you provide the full address? "
                "For example: \"123 Oak Street, Springfield\" or \"The Grand Ballroom at Hilton Downtown\".'"
            )
        else:
            prompt_detail = (
                f"The customer said '{user_msg}' which is a type of place but not a specific venue. "
                "We need to know exactly which one — the name and/or address. "
                "Politely ask: 'That sounds great! Could you tell me the specific name or address "
                "of the venue? For example: \"Springfield Community Center, 456 Elm Road\" "
                "or \"St. Mary\\'s Church on 3rd Avenue\".'"
            )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{prompt_detail}",
            context,
        )
        state["current_node"] = "collect_venue"
        state["messages"] = add_ai_message(state, response)
        return state

    # Try LLM extraction for proper venues
    extracted = (await llm_extract(EXTRACTION_PROMPTS["venue"], user_msg)).strip()

    # Final fallback: if still NONE but message is short (1-5 words) and not a question,
    # treat the message itself as the venue
    if not extracted or extracted.upper() == "NONE":
        words = user_msg.strip().split()
        if 1 <= len(words) <= 8 and not user_msg.strip().endswith("?"):
            extracted = user_msg.strip().title()

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "venue", extracted)
        state["current_node"] = "collect_guest_count"
        context = (
            f"Customer said: {user_msg}\n"
            f"Venue set to: {extracted}\nSlots: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_venue']}",
            context,
        )
    else:
        state["current_node"] = "collect_venue"
        context = (
            f"Customer said: {user_msg}\n"
            f"Could not extract a venue. Slots: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer's response was unclear for the 'venue' field. "
            "Politely ask them to provide a specific venue name or full address. "
            "For example: '123 Oak Street, Springfield' or 'The Grand Ballroom at Hilton Downtown'.",
            context,
        )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_guest_count_node(state: ConversationState) -> ConversationState:
    """Collect guest count only. Route to present_menu (non-wedding) or select_service_style (wedding)."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["guest_count"], user_msg)
    extracted = extracted.strip()

    guest_extracted = False
    if extracted and extracted.upper() != "NONE":
        try:
            extracted = int("".join(c for c in extracted if c.isdigit()))
        except ValueError:
            pass
        fill_slot(state["slots"], "guest_count", extracted)
        guest_extracted = True

    event_type = get_slot_value(state["slots"], "event_type")
    is_wedding = event_type and "wedding" in str(event_type).lower()

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
    context = (
        f"Customer said: {user_msg}\nExtracted guest_count: {extracted}\n"
        f"Event type: {event_type}\nCURRENT slot values: {slots_summary}"
    )

    if guest_extracted:
        next_node = "select_service_style" if is_wedding else "ask_appetizers"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_guest_count']}",
            context,
        )
    else:
        # No number found — stay on this node and re-ask
        next_node = "collect_guest_count"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer's response did not include a number of guests. "
            "Politely re-ask: Approximately how many guests are you expecting?",
            context,
        )

    state["current_node"] = next_node
    state["messages"] = add_ai_message(state, response)
    return state


async def present_menu_node(state: ConversationState) -> ConversationState:
    """Fetch DB menu items and present them. Route to select_dishes."""
    state = dict(state)

    menu_context = await get_main_dishes_context(state)
    # Only pass event context (NOT user message or appetizers slot) to avoid LLM confusion
    event_slots = {
        k: v["value"] for k, v in state["slots"].items()
        if v.get("filled") and k in ("name", "event_type", "event_date", "guest_count", "venue")
    }

    context = (
        f"Event details: {event_slots}\n\n"
        f"{menu_context}"
    )
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['present_menu']}\n\n"
        "CRITICAL INSTRUCTION: The database menu is listed above in the context. "
        "You MUST present ONLY those exact items as a bullet list (use •, NOT numbers). "
        "DO NOT add, rename, substitute, or invent any item not in that list. "
        "DO NOT show appetizers — those have already been selected. "
        "Copy the item names verbatim from the database list.",
        context,
    )

    state["current_node"] = "select_dishes"
    state["messages"] = add_ai_message(state, response)
    return state


async def select_service_style_node(state: ConversationState) -> ConversationState:
    """Extract service style (wedding only). Route to present_menu."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["service_style"], user_msg)
    extracted = extracted.strip()

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "service_style", extracted)

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
    context = (
        f"Customer said: {user_msg}\nExtracted service_style: {extracted}\n"
        f"CURRENT slot values: {slots_summary}"
    )
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_service_style']}",
        context,
    )

    state["current_node"] = "ask_appetizers"
    state["messages"] = add_ai_message(state, response)
    return state

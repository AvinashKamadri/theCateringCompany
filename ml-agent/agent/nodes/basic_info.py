"""
Basic info collection nodes: name, date, service type, event type, venue,
guest count, service style.
"""

from datetime import datetime

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_extract, llm_respond,
    llm_extract_enum, llm_extract_integer, is_null_extraction,
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

    extraction_succeeded = not is_null_extraction(extracted)

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
    """Collect event date with past-date rejection.

    Extraction uses today's date injected at runtime so the LLM normalises
    relative phrases ("next Saturday", "in June") correctly.  After extraction
    we do a hard Python-side check — if the resolved date is today or earlier
    we stay on the node and tell the customer why instead of silently accepting
    a booking that is already in the past.
    """
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    prompt = EXTRACTION_PROMPTS["event_date"].format(today=today_str)
    extracted = (await llm_extract(prompt, user_msg)).strip()

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    # -- Validate extracted date --
    is_past_date = False
    extraction_succeeded = not is_null_extraction(extracted)

    if extraction_succeeded:
        try:
            event_date = datetime.strptime(extracted, "%Y-%m-%d")
            if event_date.date() <= today.date():
                is_past_date = True
                extraction_succeeded = False
        except ValueError:
            # LLM returned something that isn't a valid YYYY-MM-DD date
            extraction_succeeded = False

    if is_past_date:
        context = (
            f"Customer said: {user_msg}\n"
            f"Extracted date: {extracted} — this date is in the past.\n"
            f"Today: {today_str}\nSlots: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer provided an event date that has already passed. "
            "Politely explain that we can only book events for future dates. "
            "Acknowledge the date they mentioned, then ask them to provide a future date. "
            "Keep it warm and brief — do not lecture.",
            context,
        )
        # Stay on collect_event_date
    elif extraction_succeeded:
        fill_slot(state["slots"], "event_date", extracted)
        slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
        context = (
            f"Customer said: {user_msg}\nExtracted event_date: {extracted}\n"
            f"CURRENT slot values (use THESE): {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_event_date']}",
            context,
        )
        state["current_node"] = "collect_venue"
    else:
        context = (
            f"Customer said: {user_msg}\n"
            f"Could not extract a valid date. Today: {today_str}\nSlots: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer's response did not include a clear event date. "
            "Politely re-ask for the date of their event. "
            "Give an example of a valid answer, e.g. 'June 15th, 2026'.",
            context,
        )
        # Stay on collect_event_date

    state["messages"] = add_ai_message(state, response)
    return state


async def select_service_type_node(state: ConversationState) -> ConversationState:
    """Extract service type and move on. Custom handling to prevent re-asking loop."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract_enum(
        EXTRACTION_PROMPTS["service_type"], user_msg,
        ["Drop-off", "Full-Service Buffet", "Full-Service On-site"],
    )
    extracted = extracted.strip()

    if not is_null_extraction(extracted):
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

    extracted = await llm_extract_enum(
        EXTRACTION_PROMPTS["event_type"], user_msg,
        ["Wedding", "Corporate", "Birthday", "Social", "Custom"],
    )
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
        extracted = event_description.strip() if not is_null_extraction(event_description.strip()) else user_msg.strip()

    if not is_null_extraction(extracted):
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
    if not is_null_extraction(extracted.strip()):
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

    - Inappropriate venues (airport, bus stand, etc.) get a polite "not suitable" message.
    - Informal/vague answers (my home, the park) trigger a followup echoing the word back:
      "Could you please specify where your home is located?"
    """
    import re as _re
    from prompts.system_prompts import EXTRACTION_PROMPTS
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    t = user_msg.strip().lower()

    # --- 1. Inappropriate venue detection ---
    _INAPPROPRIATE_VENUES = [
        r'\b(airport|airfield|airstrip|air\s*port)\b',
        r'\b(bus\s*(stand|station|stop|terminal|depot))\b',
        r'\b(train\s*(station|terminal|depot)|railway\s*station|railroad)\b',
        r'\b(subway\s*station|metro\s*station|underground\s*station)\b',
        r'\b(highway|freeway|motorway|expressway|overpass|underpass)\b',
        r'\b(gas\s*station|petrol\s*station|fuel\s*station|rest\s*stop|truck\s*stop)\b',
    ]
    is_inappropriate = any(_re.search(p, t) for p in _INAPPROPRIATE_VENUES)

    if is_inappropriate:
        slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            f"The customer suggested '{user_msg}' as their event venue. "
            "This is not a suitable location for a catering event. "
            "Politely explain that unfortunately we are unable to cater at that type of location. "
            "Then kindly ask them to share a more appropriate venue — such as a home, "
            "banquet hall, restaurant, park, event space, or any private/semi-private location. "
            "Keep it warm and brief.",
            f"Customer said: {user_msg}\nSlots: {slots_summary}",
        )
        state["current_node"] = "collect_venue"
        state["messages"] = add_ai_message(state, response)
        return state

    # --- 2. Vague venue detection ---
    # Category A: Informal/personal places (my home, backyard, etc.)
    _VAGUE_PERSONAL = [
        r'\b(my\s+)?(home|house|place|gome|hme|apartment|flat|condo)\b',
        r'\b(my\s+)?(backyard|garden|yard|patio|garage|driveway|rooftop)\b',
        r'\b(my\s+)?(office|workplace|work)\b',
        r'\b(here|there|somewhere|tbd|not sure|undecided|idk|dunno)\b',
    ]
    # Category B: Generic place TYPES without a specific name/address
    _GENERIC_PLACE_TYPES = [
        r'\b(school|church|mosque|temple|synagogue)\b',
        r'\b(park|beach|lake|field|playground|community center)\b',
        r'\b(restaurant|hotel|motel|inn|lodge|resort)\b',
        r'\b(hall|banquet|club|bar|pub|cafe|cafeteria)\b',
        r'\b(library|museum|gallery|theater|theatre|stadium|arena)\b',
    ]

    is_vague_personal = any(_re.search(p, t) for p in _VAGUE_PERSONAL)
    is_generic_type = any(_re.search(p, t) for p in _GENERIC_PLACE_TYPES)

    has_address_detail = bool(_re.search(
        r'(\d+\s+\w+\s+(st|street|ave|avenue|blvd|boulevard|rd|road|dr|drive|ln|lane|way|ct|court|pl|place))'
        r'|(\b\d{5}\b)'
        r'|(\w+,\s*\w+)',
        t, _re.IGNORECASE
    ))
    _GENERIC_QUALIFIERS = r'^(a|an|the|my|our|some|local|public|private|nearby|big|small|old|new)\s+'
    venue_stripped = _re.sub(_GENERIC_QUALIFIERS, '', user_msg.strip(), flags=_re.IGNORECASE).strip()
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
            f"Venue is too vague (reason: {clarification_reason}). Slots: {slots_summary}"
        )
        if clarification_reason == "personal":
            prompt_detail = (
                f"The customer said '{user_msg}' as their venue. "
                "Find the exact informal word they used (e.g. 'home', 'backyard', 'office', 'place'). "
                "Ask a short, warm follow-up question echoing that word back — for example: "
                "'Could you please specify where your home is located? Could you share the address or city?' "
                "Use the customer's exact word in the question (not a synonym). "
                "Do NOT ask for a 'full address' in formal language — keep it conversational."
            )
        else:
            prompt_detail = (
                f"The customer said '{user_msg}' as their venue — it names a type of place but not a specific one. "
                "Find the exact place word they used (e.g. 'park', 'church', 'restaurant', 'hall'). "
                "Ask a short follow-up echoing that word: "
                "'Could you please specify where the park is located? What\\'s the name or address?' "
                "Use their exact word. Keep it brief and friendly."
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

    if not is_null_extraction(extracted):
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

    extracted = await llm_extract_integer(EXTRACTION_PROMPTS["guest_count"], user_msg)
    extracted = extracted.strip()

    # llm_extract_integer guarantees the value is a valid integer string or "NONE".
    # The digit-scraping fallback is no longer needed — a plain int() is safe here.
    guest_extracted = False
    invalid_count = False
    if not is_null_extraction(extracted):
        try:
            count = int(extracted)
            if count > 0:
                extracted = count
                fill_slot(state["slots"], "guest_count", extracted)
                guest_extracted = True
            else:
                invalid_count = True
        except ValueError:
            pass

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
    elif invalid_count:
        # Extracted a number but it was zero or negative — stay and re-ask
        next_node = "collect_guest_count"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer provided a guest count that is not valid (must be at least 1). "
            "Politely ask them to confirm how many guests they are expecting.",
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

    extracted = await llm_extract_enum(
        EXTRACTION_PROMPTS["service_style"], user_msg,
        ["cocktail hour", "reception", "both"],
    )
    extracted = extracted.strip()

    if not is_null_extraction(extracted):
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

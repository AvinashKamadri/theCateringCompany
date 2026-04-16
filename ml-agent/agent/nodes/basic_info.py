"""
Basic info collection nodes: name, date, service type, event type, venue,
guest count, service style.
"""

import re as _re
from datetime import datetime, timedelta

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_extract, llm_respond,
    build_numbered_list,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS, EXTRACTION_PROMPTS
from agent.nodes.menu import get_main_dishes_context, get_appetizer_context, get_appetizer_items, get_main_dish_items, get_dessert_items


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
        # Two-strike rule: after 2 failed extractions, accept raw input and move on
        retry_key = f"_retry_{slot_name}"
        retry_slot = state["slots"].get(retry_key, {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0

        if retries >= 1:
            fill_slot(state["slots"], slot_name, user_msg.strip())
            context = (
                f"Customer said: {user_msg}\nAccepted as {slot_name} (best effort).\n"
                f"Slots so far: {slots_summary}"
            )
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS[node_key]}",
                context,
            )
            state["current_node"] = next_node
            state["slots"].pop(retry_key, None)
        else:
            state["slots"][retry_key] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
            context = (
                f"Customer said: {user_msg}\n"
                f"Could NOT extract a clear value for '{slot_name}'.\n"
                f"Slots so far: {slots_summary}"
            )
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n"
                f"Couldn't catch a clear answer for '{slot_name}'. "
                f"First briefly explain why you're re-asking (e.g. 'I didn't quite catch that' or 'Just need to clarify'). "
                f"Then re-ask the question in a different way. Keep it casual, one or two lines.",
                context,
            )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_name_node(state: ConversationState) -> ConversationState:
    return await _extract_and_respond(state, "name", "collect_contact", "collect_name")


async def collect_contact_node(state: ConversationState) -> ConversationState:
    """Collect email and phone in one message."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Check what's already captured from previous turns
    existing_email = get_slot_value(state["slots"], "email")
    existing_phone = get_slot_value(state["slots"], "phone")

    email = await llm_extract(EXTRACTION_PROMPTS["email"], user_msg)
    phone = await llm_extract(EXTRACTION_PROMPTS["phone"], user_msg)
    email = email.strip()
    phone = phone.strip()

    got_email = (email and email.upper() != "NONE") or existing_email
    got_phone = (phone and phone.upper() != "NONE") or existing_phone

    if email and email.upper() != "NONE":
        fill_slot(state["slots"], "email", email)
    if phone and phone.upper() != "NONE":
        fill_slot(state["slots"], "phone", phone)

    # Use existing values if current extraction didn't find them
    final_email = get_slot_value(state["slots"], "email")
    final_phone = get_slot_value(state["slots"], "phone")

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    event_type_list = "1. Wedding\n2. Birthday\n3. Corporate\n4. Social\n5. Custom"

    if final_email and final_phone:
        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nGot email and phone. Confirm briefly, then ask what kind of event they're planning. "
            "Do NOT list the event types — the list will be appended automatically.",
            f"Email: {final_email}, Phone: {final_phone}\nSlots: {slots_summary}"
        )
        response = f"{intro}\n\n{event_type_list}"
        state["current_node"] = "select_event_type"
    elif final_email and not final_phone:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nGot the email ({final_email}). Just need the phone number now.",
            f"Email: {final_email}\nSlots: {slots_summary}"
        )
    elif final_phone and not final_email:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nGot the phone ({final_phone}). Just need the email now.",
            f"Phone: {final_phone}\nSlots: {slots_summary}"
        )
    else:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_contact']}",
            f"Couldn't extract email or phone from: {user_msg}"
        )
        # Stay on this node

    state["messages"] = add_ai_message(state, response)
    return state


_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}

def _resolve_day_of_week(text: str, today: datetime) -> str | None:
    """Resolve 'this saturday', 'next friday', etc. to YYYY-MM-DD in Python (no LLM)."""
    m = _re.search(
        r'\b(?:this\s+|next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        text, _re.IGNORECASE
    )
    if not m:
        return None
    target = _WEEKDAYS[m.group(1).lower()]
    days_ahead = (target - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # "this X" when today IS X → next week
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


async def collect_fiance_name_node(state: ConversationState) -> ConversationState:
    """Wedding only — collect partner/fiancé name."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["partner_name"], user_msg)
    extracted = extracted.strip()

    retry_slot = state["slots"].get("_retry_partner", {})
    retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "partner_name", extracted)
        state["slots"].pop("_retry_partner", None)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_fiance_name']}\n\n"
            f"Name captured: {extracted}. Confirm it casually, then ask: 'When's the big day?' "
            "End with: 'Tip: type @AI anytime to update a previous answer.'",
            f"Partner name captured: {extracted}",
        )
        state["current_node"] = "collect_event_date"
    elif retries >= 1:
        fill_slot(state["slots"], "partner_name", user_msg.strip())
        state["slots"].pop("_retry_partner", None)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nPartner name: {user_msg.strip()}. Confirm, then ask: 'When's the big day?' "
            "End with: 'Tip: type @AI anytime to update a previous answer.'",
            f"Partner name: {user_msg.strip()}",
        )
        state["current_node"] = "collect_event_date"
    else:
        state["slots"]["_retry_partner"] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_fiance_name']}",
            f"Need partner name. Customer said: {user_msg}",
        )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_birthday_person_node(state: ConversationState) -> ConversationState:
    """Birthday only — collect whose birthday it is."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["honoree_name"], user_msg)
    extracted = extracted.strip()

    if extracted.lower() == "self":
        full_name = get_slot_value(state["slots"], "name") or ""
        extracted = full_name.split()[0] if full_name else "you"

    retry_slot = state["slots"].get("_retry_honoree", {})
    retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "honoree_name", extracted)
        state["slots"].pop("_retry_honoree", None)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nBirthday person is {extracted}. Confirm warmly, then ask: 'When's the big day?'",
            f"Birthday person: {extracted}",
        )
        state["current_node"] = "collect_event_date"
    elif retries >= 1:
        fill_slot(state["slots"], "honoree_name", user_msg.strip())
        state["slots"].pop("_retry_honoree", None)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nBirthday person: {user_msg.strip()}. Confirm, then ask: 'When's the big day?'",
            f"Birthday person: {user_msg.strip()}",
        )
        state["current_node"] = "collect_event_date"
    else:
        state["slots"]["_retry_honoree"] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_birthday_person']}",
            f"Need to know whose birthday. Customer said: {user_msg}",
        )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_company_name_node(state: ConversationState) -> ConversationState:
    """Corporate only — collect company name."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["company_name"], user_msg)
    extracted = extracted.strip()

    # Two-strike: accept raw input on second try (store counter in slots to persist)
    retry_slot = state["slots"].get("_retry_company", {})
    retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "company_name", extracted)
        state["slots"].pop("_retry_company", None)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCompany is {extracted}. Confirm it, then ask: 'What date are you planning for?'",
            f"Company name: {extracted}",
        )
        state["current_node"] = "collect_event_date"
    elif retries >= 1:
        fill_slot(state["slots"], "company_name", user_msg.strip())
        state["slots"].pop("_retry_company", None)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCompany is {user_msg.strip()}. Confirm it, then ask: 'What date are you planning for?'",
            f"Company name: {user_msg.strip()}",
        )
        state["current_node"] = "collect_event_date"
    else:
        state["slots"]["_retry_company"] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_company_name']}",
            f"Need company name. Customer said: {user_msg}",
        )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_event_date_node(state: ConversationState) -> ConversationState:
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    today = datetime.now()

    # Try Python-level day-of-week resolution first (100% accurate)
    resolved = _resolve_day_of_week(user_msg, today)

    if not resolved:
        # Fall back to LLM for all other date formats
        prompt = EXTRACTION_PROMPTS["event_date"].format(today=today.strftime("%Y-%m-%d"))
        resolved = (await llm_extract(prompt, user_msg)).strip()

    if resolved and resolved.upper() != "NONE":
        try:
            parsed = datetime.strptime(resolved, "%Y-%m-%d")
            if parsed.date() <= today.date():
                # Past date — re-ask casually
                from agent.nodes.helpers import add_ai_message
                response = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nThat date has already passed. Re-ask for the event date casually in one line.",
                    f"Customer said: {user_msg}\nResolved date: {resolved}"
                )
                state["messages"] = add_ai_message(state, response)
                return state
            fill_slot(state["slots"], "event_date", resolved)
        except ValueError:
            resolved = "NONE"

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
    from agent.nodes.helpers import add_ai_message
    from prompts.system_prompts import NODE_PROMPTS

    if resolved and resolved.upper() != "NONE":
        context = f"Customer said: {user_msg}\nEVENT DATE = {resolved} — confirm THIS date exactly, do not recalculate.\nSlots: {slots_summary}"
        response = await llm_respond(f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_event_date']}", context)
        state["current_node"] = "collect_venue"
    else:
        context = f"Customer said: {user_msg}\nCouldn't extract a date.\nSlots: {slots_summary}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCouldn't catch the date. Re-ask casually in one short line — no examples, no formality.",
            context
        )

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

    # Route to event-specific context node before date collection
    event_lower = (extracted or "").lower()
    if "wedding" in event_lower:
        state["current_node"] = "collect_fiance_name"
        confirmation = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCongrats on the wedding — one short warm line, "
            "then immediately ask for the fiancé/partner's name in the SAME message. "
            "Example: 'Congrats on the wedding! Who's the other half of this day?'",
            f"Event type: Wedding. Customer name: {get_slot_value(state['slots'], 'name')}"
        )
    elif "birthday" in event_lower:
        state["current_node"] = "collect_birthday_person"
        confirmation = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nConfirm the birthday event with one upbeat line, "
            "then immediately ask whose birthday it is in the SAME message. "
            "Example: 'Awesome, a birthday celebration! Whose big day is it?'",
            f"Event type: Birthday. Customer name: {get_slot_value(state['slots'], 'name')}"
        )
    elif "corporate" in event_lower:
        state["current_node"] = "collect_company_name"
        confirmation = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nConfirm the corporate event with one short line, "
            "then immediately ask for the company/organization name in the SAME message. "
            "Example: 'Nice — corporate event it is. What company is this for?'",
            f"Event type: Corporate. Customer name: {get_slot_value(state['slots'], 'name')}"
        )
    else:
        state["current_node"] = "collect_event_date"
        confirmation = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nConfirm the event type in one line, then ask: 'When's the event?'",
            f"Event type: {extracted}"
        )

    state["messages"] = add_ai_message(state, confirmation)
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

    if is_wedding:
        # Wedding: ask service style (cocktail hour/reception/both)
        context = (
            f"Customer said: {user_msg}\nExtracted guest_count: {extracted}\n"
            f"Event type: {event_type}\nCURRENT slot values: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_guest_count']}",
            context,
        )
        state["current_node"] = "select_service_style"
    else:
        # Non-wedding: confirm guest count AND show appetizer menu directly (no wait)
        # Python builds the list — LLM only generates the intro
        app_items = await get_appetizer_items()
        app_list = build_numbered_list(app_items, show_price=True)
        favorites = ", ".join(i["name"] for i in app_items[:3])

        intro = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nConfirm {extracted} guests in one brief line. "
            f"Then write a casual 1-line intro for the appetizer menu. "
            f"Mention these crowd favorites: {favorites}. "
            "Do NOT list any items — the list will be appended automatically.",
            f"Guest count: {extracted}, Event: {event_type}"
        )
        response = f"{intro}\n\n{app_list}\n\nPick as many as you'd like! If you don't want appetizers, just say skip."
        state["current_node"] = "select_appetizers"

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
        "Present the main dish menu using the EXACT grouped format from the database context:\n"
        "- Use section headers exactly as named (Signature Combinations, BBQ Menus, Tasty & Casual, Global Inspirations, Soup / Salad / Sandwich)\n"
        "- Keep the global sequential numbering — numbers continue across sections\n"
        "- Show the price per item\n"
        "- Do NOT collapse sections or merge categories\n"
        "- DO NOT show appetizers — those have already been selected\n"
        "CRITICAL: Copy item names verbatim from the database list. DO NOT add or rename any item.",
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
    # Confirm service style AND show appetizer menu directly (no wait)
    # Python builds the list — LLM only generates the intro
    app_items = await get_appetizer_items()
    app_list = build_numbered_list(app_items, show_price=True)
    favorites = ", ".join(i["name"] for i in app_items[:3])

    intro = await llm_respond(
        f"{SYSTEM_PROMPT}\n\nConfirm {extracted} service style in one brief line. "
        f"Then write a casual 1-line intro for the cocktail hour appetizers. "
        f"Mention these crowd favorites: {favorites}. "
        "Do NOT list any items — the list will be appended automatically.",
        f"Service style: {extracted}"
    )
    response = f"{intro}\n\n{app_list}\n\nPick as many as you'd like!"

    state["current_node"] = "select_appetizers"
    state["messages"] = add_ai_message(state, response)
    return state

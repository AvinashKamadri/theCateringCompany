"""
Basic info collection nodes: name, date, service type, event type, venue,
guest count, service style.
"""

import re as _re
from datetime import datetime, timedelta

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_extract, llm_respond,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS, EXTRACTION_PROMPTS
from agent.nodes.menu import get_main_dishes_context, get_appetizer_context


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

    if final_email and final_phone:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nGot email and phone. Confirm briefly, then ask what kind of event they're planning. "
            "Show numbered options:\n1. Wedding\n2. Birthday\n3. Corporate\n4. Social\n5. Custom",
            f"Email: {final_email}, Phone: {final_phone}\nSlots: {slots_summary}"
        )
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
    return await _extract_and_respond(state, "service_type", "ask_rentals", "select_service_type")


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
    return await _extract_and_respond(state, "venue", "collect_guest_count", "collect_venue")


async def collect_guest_count_node(state: ConversationState) -> ConversationState:
    """Collect guest count only. Route to present_menu (non-wedding) or select_service_style (wedding)."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["guest_count"], user_msg)
    extracted = extracted.strip()

    if extracted and extracted.upper() != "NONE":
        try:
            extracted = int("".join(c for c in extracted if c.isdigit()))
        except ValueError:
            pass
        fill_slot(state["slots"], "guest_count", extracted)

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
        appetizer_context = await get_appetizer_context(state)
        context = (
            f"Guest count confirmed: {extracted}\n"
            f"Event type: {event_type}\n\n"
            f"{appetizer_context}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nConfirm the guest count in one brief line. "
            "Then immediately present the FULL appetizer menu from the database below as a numbered list. "
            "Use a casual intro mentioning crowd favorites from the list. "
            "Say: 'pick as many as you'd like' or 'if you don't want appetizers, just say skip'. "
            "CRITICAL: Only list items from the database. Show ALL items.",
            context,
        )
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
        "CRITICAL INSTRUCTION: The database menu is listed above in the context. "
        "You MUST present ONLY those exact items — numbered exactly as they appear. "
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
    # Confirm service style AND show appetizer menu directly (no wait)
    appetizer_context = await get_appetizer_context(state)
    combined_context = (
        f"Service style confirmed: {extracted}\n"
        f"Slots: {slots_summary}\n\n"
        f"{appetizer_context}"
    )
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\nConfirm the service style briefly. "
        "Then immediately present the FULL appetizer menu from the database below as a numbered list. "
        "Mention crowd favorites from the list. Say 'pick as many as you'd like'. "
        "CRITICAL: Only list items from the database. Show ALL items.",
        combined_context,
    )

    state["current_node"] = "select_appetizers"
    state["messages"] = add_ai_message(state, response)
    return state

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
        # Never accept raw text as a constrained-enum slot — keep re-asking instead.
        retry_key = f"_retry_{slot_name}"
        retry_slot = state["slots"].get(retry_key, {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"][retry_key] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        context = (
            f"Customer said: {user_msg}\n"
            f"Could NOT extract a clear value for '{slot_name}'.\n"
            f"Slots so far: {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            f"Couldn't catch a clear answer for '{slot_name}'. "
            f"Acknowledge warmly, briefly explain you need a clear pick, then re-ask. "
            f"One or two short lines. DO NOT move on without a valid answer.",
            context,
        )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_name_node(state: ConversationState) -> ConversationState:
    """Collect name, then go straight to event type (email/phone collected elsewhere)."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = (await llm_extract(EXTRACTION_PROMPTS["name"], user_msg)).strip()
    extraction_succeeded = extracted and extracted.upper() != "NONE"

    retry_key = "_retry_name"
    retry_slot = state["slots"].get(retry_key, {})
    retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0

    if extraction_succeeded:
        fill_slot(state["slots"], "name", extracted)
        state["slots"].pop(retry_key, None)
    else:
        state["slots"][retry_key] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer didn't give a usable name (they said something like "
            "'dunno' or 'idk'). Acknowledge warmly, then gently explain we need their name so our team "
            "knows who the event is for. Sound natural, not robotic. One short line. "
            "DO NOT move on without a name.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state

    # Successfully got name — confirm briefly AND ask event type (with list appended)
    event_type_list = "1. Wedding\n2. Birthday\n3. Corporate\n4. Social\n5. Custom"
    intro = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_name']}",
        f"Name captured: {extracted}"
    )
    response = f"{intro}\n\n{event_type_list}"
    state["current_node"] = "select_event_type"
    state["messages"] = add_ai_message(state, response)
    return state


# Phrases that mean "I don't know — decide later". Trigger deferral of
# date/venue/guest_count to the end of the flow rather than blocking.
_UNSURE_PHRASES = frozenset({
    "idk", "i dont know", "i don't know", "dunno", "dont know", "don't know",
    "not sure", "unsure", "no idea", "no clue", "have no clue", "not yet",
    "tbd", "tba", "to be decided", "to be determined", "not decided",
    "havent decided", "haven't decided", "will decide later", "decide later",
    "later", "ask later", "ask me later", "skip for now", "skip",
    "pata nahi", "pata nai", "nai malum", "nahi malum",
})


def _is_unsure(user_msg: str) -> bool:
    """True when the user gave a stand-alone 'I don't know / decide later' reply."""
    cleaned = user_msg.strip().lower().rstrip(".!?,")
    return cleaned in _UNSURE_PHRASES


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
            f"Name captured: {extracted}. Confirm it casually, then ask: 'When's your wedding?'",
            f"Partner name captured: {extracted}",
        )
        state["current_node"] = "collect_event_date"
    else:
        state["slots"]["_retry_partner"] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer didn't give a partner/fiancé name. Acknowledge warmly, "
            "then gently explain we need the partner's name for the wedding contract. Sound natural. "
            "One short line. DO NOT move on without a name.",
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
            f"{SYSTEM_PROMPT}\n\nBirthday person is {extracted}. Confirm warmly, then ask: 'When's the birthday?'",
            f"Birthday person: {extracted}",
        )
        state["current_node"] = "collect_event_date"
    else:
        state["slots"]["_retry_honoree"] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer didn't tell us whose birthday it is. Acknowledge warmly, "
            "then gently explain we need a name so the team knows who we're celebrating. Sound natural. "
            "One short line. DO NOT move on without a name.",
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
            f"{SYSTEM_PROMPT}\n\nCompany is {extracted}. Confirm it, then ask: 'When is the corporate event?'",
            f"Company name: {extracted}",
        )
        state["current_node"] = "collect_event_date"
    else:
        state["slots"]["_retry_company"] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer didn't give a company name. Acknowledge warmly, then "
            "gently explain we need the company name for the corporate event contract. Sound natural. "
            "One short line. DO NOT move on without it.",
            f"Need company name. Customer said: {user_msg}",
        )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_event_date_node(state: ConversationState) -> ConversationState:
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    today = datetime.now()

    # Defer path — user explicitly says they don't know yet. Mark TBD and move on;
    # we'll circle back at the end of the flow via collect_pending_details_node.
    if _is_unsure(user_msg):
        fill_slot(state["slots"], "event_date", "TBD")
        state["slots"].pop("_retry_event_date", None)
        from agent.nodes.helpers import add_ai_message
        response = (
            "No worries — we'll circle back to the date at the end. "
            "For now, where are you thinking of hosting the event?"
        )
        state["current_node"] = "collect_venue"
        state["messages"] = add_ai_message(state, response)
        return state

    # Try Python-level day-of-week resolution first (100% accurate)
    resolved = _resolve_day_of_week(user_msg, today)

    if not resolved:
        # Fall back to LLM for all other date formats
        prompt = EXTRACTION_PROMPTS["event_date"].format(today=today.strftime("%Y-%m-%d"))
        resolved = (await llm_extract(prompt, user_msg)).strip()

    if resolved and resolved.upper() != "NONE":
        try:
            parsed = datetime.strptime(resolved, "%Y-%m-%d")
            max_date = today + timedelta(days=213)  # ~7 months booking window
            if parsed.date() <= today.date():
                from agent.nodes.helpers import add_ai_message
                response = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nSorry, that date is in the past. "
                    "Re-ask for the event date casually in one line — mention we book events within the next 6-7 months.",
                    f"Customer said: {user_msg}\nResolved date: {resolved}\nToday: {today.strftime('%Y-%m-%d')}"
                )
                state["messages"] = add_ai_message(state, response)
                return state
            if parsed.date() > max_date.date():
                from agent.nodes.helpers import add_ai_message
                response = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nThat date is too far out — we only book events within the next 6-7 months. "
                    f"Apologize briefly and ask for a date between {today.strftime('%b %d, %Y')} and {max_date.strftime('%b %d, %Y')}. One line.",
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
        state["slots"].pop("_retry_event_date", None)
        context = f"Customer said: {user_msg}\nEVENT DATE = {resolved} — confirm THIS date exactly, do not recalculate.\nSlots: {slots_summary}"
        response = await llm_respond(f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_event_date']}", context)
        state["current_node"] = "collect_venue"
    else:
        # Date is mandatory — never accept vague input. Keep re-asking until we get a real date.
        retry_slot = state["slots"].get("_retry_event_date", {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"]["_retry_event_date"] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        context = f"Customer said: {user_msg}\nCouldn't extract a date.\nSlots: {slots_summary}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer didn't give a real date (they said something like "
            "'idk' or 'no idea'). Acknowledge warmly, then gently explain we NEED an event date to "
            "confirm our team's availability — even a rough date works (e.g. 'next Saturday', "
            "'May 15', 'end of June'). Sound natural, not robotic. One short, warm line. "
            "DO NOT move on without a date. DO NOT ask any other question.",
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
    else:
        # Can't extract a valid event type — re-ask (two-strike rule)
        retry_key = "_retry_event_type"
        retry_slot = state["slots"].get(retry_key, {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0

        state["slots"][retry_key] = {"value": retries + 1, "filled": True, "modified_at": None, "modification_history": []}
        event_type_list = "1. Wedding\n2. Birthday\n3. Corporate\n4. Social\n5. Custom"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCouldn't catch the event type. Ask them warmly to pick one "
            "(number or name). Do NOT list the options — the list is appended automatically. "
            "DO NOT move on without a clear pick.",
            f"Customer said: {user_msg}"
        )
        response = f"{response}\n\n{event_type_list}"
        state["messages"] = add_ai_message(state, response)
        return state

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
            "then immediately ask for the fiancé(e)'s name in the SAME message. "
            "IMPORTANT: you MUST use the word 'fiancé' or 'fiancée' explicitly — do NOT say "
            "'other half', 'partner', 'spouse', or anything else. "
            "Example: 'Congrats on the wedding! Who's the lucky fiancé(e)?'",
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


# Venues too vague to use for catering logistics — need a real address or city+venue
_VAGUE_VENUES = frozenset({
    # Non-answers / ignorance phrasing
    "idk", "dunno", "no idea", "i dont know", "i don't know", "dont know",
    "don't know", "not sure", "unsure", "tbd", "tba", "to be decided",
    "to be determined", "nai malum", "nahi malum", "pata nahi", "pata nai",
    "nothing", "n/a", "na", "none", "no",
    # Generic words
    "home", "backyard", "my backyard", "my home", "house", "my house",
    "my place", "place", "yard", "garden", "my garden", "somewhere",
    "anywhere", "everywhere", "tbh idk",
    # Country names
    "india", "usa", "united states", "us", "uk", "united kingdom", "canada",
    "australia", "germany", "france", "spain", "italy", "china", "japan",
    "mexico", "brazil", "russia", "nigeria", "south africa", "egypt",
    "pakistan", "bangladesh", "indonesia", "philippines", "vietnam",
    "thailand", "malaysia", "singapore", "saudi arabia", "uae", "turkey",
    "argentina", "colombia", "chile", "peru", "the us", "the uk", "the usa",
    # Continents/regions
    "africa", "europe", "asia", "america", "north america", "south america",
    "middle east", "southeast asia",
})


async def collect_venue_node(state: ConversationState) -> ConversationState:
    """Collect venue — rejects bare country names and vague words like 'home'/'backyard'."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Defer path — explicit "idk / decide later" marks venue TBD and moves on.
    if _is_unsure(user_msg):
        fill_slot(state["slots"], "venue", "TBD")
        state["slots"].pop("_retry_venue", None)
        response = (
            "Totally fine — we'll sort the venue at the end. "
            "Roughly how many guests are you expecting?"
        )
        state["current_node"] = "collect_guest_count"
        state["messages"] = add_ai_message(state, response)
        return state

    extracted = (await llm_extract(EXTRACTION_PROMPTS["venue"], user_msg)).strip()
    extraction_succeeded = extracted and extracted.upper() not in ("NONE",)

    # Reject venues that are too vague to schedule a catering delivery
    if extraction_succeeded and extracted.lower() in _VAGUE_VENUES:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer gave a venue that's too vague for catering logistics. "
            "Ask them for something more specific — a street address, city + venue name, or the name of the hall/hotel/restaurant. "
            "Keep it friendly and brief, one line.",
            f"Customer said: {user_msg}\nVague venue given: {extracted}"
        )
        state["messages"] = add_ai_message(state, response)
        return state

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    if extraction_succeeded:
        fill_slot(state["slots"], "venue", extracted)
        context = (
            f"Customer said: {user_msg}\nExtracted venue: {extracted}\n"
            f"CURRENT slot values (use THESE): {slots_summary}"
        )
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_venue']}", context
        )
        state["current_node"] = "collect_guest_count"
    else:
        retry_key = "_retry_venue"
        retry_slot = state["slots"].get(retry_key, {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"][retry_key] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        context = f"Customer said: {user_msg}\nCouldn't extract a usable venue.\nSlots: {slots_summary}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer hasn't given a real venue yet (they said something vague like 'i dont know' "
            "or 'not sure'). Acknowledge them warmly, then gently explain we NEED a venue to plan catering logistics — "
            "even a rough one works (street address, venue/hall name, or city + neighborhood). "
            "Sound natural and human, not robotic. Example tone: 'okay — but we do need a venue to serve you. "
            "even a rough location works (city + hall name, or an address). share what you've got?' "
            "One short, warm message.",
            context
        )

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_guest_count_node(state: ConversationState) -> ConversationState:
    """Collect guest count only. Route to present_menu (non-wedding) or select_service_style (wedding)."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Defer path — explicit "idk / decide later" marks guest count TBD and moves on.
    if _is_unsure(user_msg):
        fill_slot(state["slots"], "guest_count", "TBD")
        state["slots"].pop("_retry_guest_count", None)
        event_type = get_slot_value(state["slots"], "event_type")
        is_wedding = event_type and "wedding" in str(event_type).lower()
        if is_wedding:
            response = (
                "No problem — we'll nail down the final count later. "
                "For now, are you thinking cocktail hour only, full reception, or both?"
            )
            state["current_node"] = "select_service_style"
        else:
            app_items = await get_appetizer_items()
            app_list = build_numbered_list(app_items, show_price=True)
            response = (
                "No problem — we'll lock the guest count in at the end. "
                "Meanwhile, let's pick some appetizers:\n\n"
                f"{app_list}\n\nPick as many as you'd like! If you don't want appetizers, just say skip."
            )
            state["current_node"] = "select_appetizers"
        state["messages"] = add_ai_message(state, response)
        return state

    extracted = await llm_extract(EXTRACTION_PROMPTS["guest_count"], user_msg)
    extracted = extracted.strip()

    extraction_succeeded = extracted and extracted.upper() != "NONE"

    if extraction_succeeded:
        digits = "".join(c for c in str(extracted) if c.isdigit())
        if not digits:
            extraction_succeeded = False
        else:
            try:
                extracted = int(digits)
            except ValueError:
                extraction_succeeded = False

    if extraction_succeeded:
        # Range check: 10-10000 guests
        if isinstance(extracted, int) and (extracted < 10 or extracted > 10000):
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\n"
                f"Customer gave {extracted} guests — that's outside our range (10 to 10,000). "
                "Politely explain our minimum is 10 and ask them for a revised guest count. One line.",
                f"Customer said: {user_msg}"
            )
            state["messages"] = add_ai_message(state, response)
            return state
        fill_slot(state["slots"], "guest_count", extracted)
        state["slots"].pop("_retry_guest_count", None)
    else:
        # Two-strike rule: after 2 failed extractions, accept raw input and move on
        retry_slot = state["slots"].get("_retry_guest_count", {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"]["_retry_guest_count"] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer didn't give a usable number (they said something like "
            "'i dont know' or gave non-numeric text). Acknowledge warmly, then gently explain we need "
            "an APPROXIMATE GUEST COUNT — a number like 50, 100, 200 — so we can plan portions, pricing, "
            "and staffing. Even a rough estimate is fine. Sound natural and human, not robotic. "
            "One short, friendly line. DO NOT move on without a number.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state

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

    extracted = await llm_extract(EXTRACTION_PROMPTS["service_style"], user_msg)
    extracted = extracted.strip()

    # Ambiguous / unclear response — keep re-asking; never silently default.
    if not extracted or extracted.upper() == "NONE":
        retry_slot = state["slots"].get("_retry_service_style", {})
        retries = retry_slot.get("value", 0) if retry_slot.get("filled") else 0
        state["slots"]["_retry_service_style"] = {
            "value": retries + 1, "filled": True,
            "modified_at": None, "modification_history": [],
        }
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer's answer wasn't clear — need to know the service style. "
            "Acknowledge warmly, then ask again: cocktail hour only, full reception, or both? "
            "One short line. DO NOT move on without a pick.",
            f"Customer said: {user_msg}"
        )
        state["messages"] = add_ai_message(state, response)
        return state
    else:
        fill_slot(state["slots"], "service_style", extracted)
        state["slots"].pop("_retry_service_style", None)

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


_PENDING_SLOT_ORDER = ("event_date", "venue", "guest_count")
_PENDING_SLOT_PROMPTS = {
    "event_date": (
        "Before we wrap up — do you have a date now, even a rough one? "
        "(Day of the week or month works. Or say 'confirm on call' if you still need time.)"
    ),
    "venue": (
        "Any venue update? Even a city or rough location helps. "
        "(Or say 'confirm on call' if still undecided.)"
    ),
    "guest_count": (
        "Any update on the guest count — even a rough number works. "
        "(Or say 'confirm on call' if still undecided.)"
    ),
}


def _find_next_pending(slots: dict) -> str | None:
    """Return the first TBD slot name among date/venue/guest_count, or None."""
    for name in _PENDING_SLOT_ORDER:
        if get_slot_value(slots, name) == "TBD":
            return name
    return None


async def collect_pending_details_node(state: ConversationState) -> ConversationState:
    """Final-stage collection for date/venue/guest_count deferred earlier.

    - On first entry (no `_pending_asking` set): ask the first TBD slot.
    - On follow-up: try to parse the answer for the slot we just asked about.
      * Valid input → fill the slot, advance to next TBD (or offer_followup).
      * Still unsure / says "confirm on call" → mark as 'TBD — confirm on call', advance.
      * Unparseable → re-ask the same slot.
    """
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    asking = state.get("_pending_asking")
    today = datetime.now()

    # --- Process the answer for whatever we asked last turn ---
    if asking:
        msg_lower = user_msg.strip().lower()
        wants_confirm_on_call = (
            "confirm on call" in msg_lower
            or "on a call" in msg_lower
            or "on call" in msg_lower
            or _is_unsure(user_msg)
        )

        resolved_ok = False

        if asking == "event_date" and not wants_confirm_on_call:
            resolved = _resolve_day_of_week(user_msg, today)
            if not resolved:
                prompt = EXTRACTION_PROMPTS["event_date"].format(today=today.strftime("%Y-%m-%d"))
                resolved = (await llm_extract(prompt, user_msg)).strip()
            if resolved and resolved.upper() != "NONE":
                try:
                    parsed = datetime.strptime(resolved, "%Y-%m-%d")
                    max_date = today + timedelta(days=213)
                    if today.date() < parsed.date() <= max_date.date():
                        fill_slot(state["slots"], "event_date", resolved)
                        resolved_ok = True
                except ValueError:
                    pass

        elif asking == "venue" and not wants_confirm_on_call:
            extracted = (await llm_extract(EXTRACTION_PROMPTS["venue"], user_msg)).strip()
            if (
                extracted and extracted.upper() != "NONE"
                and extracted.lower() not in _VAGUE_VENUES
            ):
                fill_slot(state["slots"], "venue", extracted)
                resolved_ok = True

        elif asking == "guest_count" and not wants_confirm_on_call:
            extracted = (await llm_extract(EXTRACTION_PROMPTS["guest_count"], user_msg)).strip()
            digits = "".join(c for c in extracted if c.isdigit())
            if digits:
                try:
                    count = int(digits)
                    if 10 <= count <= 10000:
                        fill_slot(state["slots"], "guest_count", count)
                        resolved_ok = True
                except ValueError:
                    pass

        if resolved_ok:
            state.pop("_pending_asking", None)
        elif wants_confirm_on_call:
            fill_slot(state["slots"], asking, "TBD — confirm on call")
            state.pop("_pending_asking", None)
        else:
            # Couldn't parse — re-ask the same slot, keep _pending_asking set.
            response = (
                f"Sorry, I didn't catch that. {_PENDING_SLOT_PROMPTS[asking]}"
            )
            state["current_node"] = "collect_pending_details"
            state["messages"] = add_ai_message(state, response)
            return state

    # --- Find the next TBD slot to ask about ---
    next_slot = _find_next_pending(state["slots"])
    if next_slot:
        state["_pending_asking"] = next_slot
        state["current_node"] = "collect_pending_details"
        state["messages"] = add_ai_message(state, _PENDING_SLOT_PROMPTS[next_slot])
        return state

    # Nothing left pending — go straight to contract generation.
    state.pop("_pending_asking", None)
    response = (
        "Perfect — we've got everything we need. "
        "Your summary is being prepared and our team will review it shortly. Thanks!"
    )
    state["current_node"] = "generate_contract"
    state["messages"] = add_ai_message(state, response)
    return state

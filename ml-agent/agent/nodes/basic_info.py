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
    return await _extract_and_respond(state, "name", "collect_event_date", "collect_name")


async def collect_event_date_node(state: ConversationState) -> ConversationState:
    return await _extract_and_respond(state, "event_date", "select_service_type", "collect_event_date")


async def select_service_type_node(state: ConversationState) -> ConversationState:
    return await _extract_and_respond(state, "service_type", "select_event_type", "select_service_type")


async def select_event_type_node(state: ConversationState) -> ConversationState:
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["event_type"], user_msg)
    extracted = extracted.strip()

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "event_type", extracted)

    # If wedding, go to wedding_message; otherwise go to collect_venue
    event_type = get_slot_value(state["slots"], "event_type")
    is_wedding = event_type and "wedding" in str(event_type).lower()

    if is_wedding:
        next_node = "wedding_message"
    else:
        next_node = "collect_venue"

    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
    context = (
        f"Customer said: {user_msg}\nEvent type: {extracted}\n"
        f"CURRENT slot values: {slots_summary}"
    )

    prompt_key = "select_event_type"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS[prompt_key]}",
        context,
    )

    state["current_node"] = next_node
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
    return await _extract_and_respond(state, "venue", "collect_guest_count", "collect_venue")


async def collect_guest_count_node(state: ConversationState) -> ConversationState:
    """Collect guest count and route based on event type."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Extract guest count
    extracted = await llm_extract(EXTRACTION_PROMPTS["guest_count"], user_msg)
    extracted = extracted.strip()

    if extracted and extracted.upper() != "NONE":
        # Normalize guest_count to int
        try:
            extracted = int("".join(c for c in extracted if c.isdigit()))
        except ValueError:
            pass
        fill_slot(state["slots"], "guest_count", extracted)

    # Check event type to determine next node
    event_type = get_slot_value(state["slots"], "event_type")
    is_wedding = event_type and "wedding" in str(event_type).lower()

    # For weddings, ask about service style (Cocktail Hour, Reception, Both)
    # For other events, skip service style and go directly to menu selection
    next_node = "select_service_style" if is_wedding else "select_dishes"

    # Build context for response — include real menu data for non-wedding events
    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    if not is_wedding:
        # Non-wedding: present real menu items from DB
        menu_context = await get_main_dishes_context(state)
        context = (
            f"Customer said: {user_msg}\nExtracted guest_count: {extracted}\n"
            f"Event type: {event_type}\nCURRENT slot values: {slots_summary}\n\n"
            f"{menu_context}"
        )
        prompt = (
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_guest_count']}\n\n"
            "IMPORTANT: Present the EXACT menu items from the database below. "
            "Do NOT invent or hallucinate menu items. Use the real items provided."
        )
    else:
        context = (
            f"Customer said: {user_msg}\nExtracted guest_count: {extracted}\n"
            f"Event type: {event_type}\nCURRENT slot values: {slots_summary}"
        )
        prompt = f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_guest_count']}"

    response = await llm_respond(prompt, context)

    state["current_node"] = next_node
    state["messages"] = add_ai_message(state, response)
    return state


async def select_service_style_node(state: ConversationState) -> ConversationState:
    """Extract service style and present real menu items from DB."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    extracted = await llm_extract(EXTRACTION_PROMPTS["service_style"], user_msg)
    extracted = extracted.strip()

    if extracted and extracted.upper() != "NONE":
        fill_slot(state["slots"], "service_style", extracted)

    # Fetch real menu items from DB
    menu_context = await get_main_dishes_context(state)
    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}

    context = (
        f"Customer said: {user_msg}\nExtracted service_style: {extracted}\n"
        f"CURRENT slot values: {slots_summary}\n\n{menu_context}"
    )
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['select_service_style']}\n\n"
        "IMPORTANT: Present the EXACT menu items from the database below. "
        "Do NOT invent or hallucinate menu items. Use the real items provided.",
        context,
    )

    state["current_node"] = "select_dishes"
    state["messages"] = add_ai_message(state, response)
    return state

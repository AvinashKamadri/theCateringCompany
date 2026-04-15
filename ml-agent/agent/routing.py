"""
Routing logic for the catering intake conversation graph.

Two-layer routing:
1. Check for modification request (explicit @AI tag) → check_modifications
2. LLM classifies if message is a correction targeting a different slot → check_modifications
3. Otherwise route to current_node (set by previous node)
"""

import re
from langchain_core.messages import HumanMessage
from agent.state import ConversationState

# Maps each node to the slot it is currently collecting.
_NODE_COLLECTS: dict[str, str | None] = {
    "collect_name": "name",
    "collect_event_date": "event_date",
    "select_service_type": "service_type",
    "select_event_type": "event_type",
    "wedding_message": None,
    "collect_fiance_name": "partner_name",
    "collect_birthday_person": "honoree_name",
    "collect_company_name": "company_name",
    "collect_contact": "email",
    "collect_venue": "venue",
    "collect_guest_count": "guest_count",
    "select_service_style": "service_style",
    "ask_appetizers": "appetizers",
    "select_appetizers": "appetizers",
    "collect_meal_style": "meal_style",
    "collect_appetizer_style": "appetizer_style",
    "present_menu": "selected_dishes",
    "select_dishes": "selected_dishes",
    "menu_design": None,
    "ask_menu_changes": "selected_dishes",
    "collect_menu_changes": "selected_dishes",
    "collect_tableware": "tableware",
    "collect_drinks": "drinks",
    "collect_bar_service": "drinks",
    "collect_labor": "labor",
    "offer_followup": "followup_call",
    "ask_utensils": "utensils",
    "select_utensils": "utensils",
    "ask_desserts": "desserts",
    "select_desserts": "desserts",
    "ask_more_desserts": "desserts",
    "ask_rentals": "rentals",
    "ask_special_requests": "special_requests",
    "collect_special_requests": "special_requests",
    "collect_dietary": "dietary_concerns",
    "ask_anything_else": "additional_notes",
    "collect_anything_else": "additional_notes",
    "generate_contract": None,
}


async def route_message(state: ConversationState) -> str:
    """
    Route to the correct node based on state.

    Priority:
    1. If user message contains @AI tag → check_modifications
    2. LLM detects natural correction for a different slot → check_modifications
    3. Otherwise → current_node from state
    """
    last_user_msg = ""
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    # 1. Explicit @AI tag
    if re.search(r'@\w*ai\b', last_user_msg, re.IGNORECASE):
        return "check_modifications"

    current = state.get("current_node", "start")

    # 2. LLM-based correction detection — is the user trying to fix a previous answer?
    current_slot = _NODE_COLLECTS.get(current)
    filled_slots = {
        name for name, data in state.get("slots", {}).items()
        if data.get("filled")
    }
    if filled_slots and current_slot:
        from agent.nodes.helpers import llm_extract
        correction_check = await llm_extract(
            f"The chatbot is currently asking about '{current_slot}'. "
            f"Already filled slots: {', '.join(filled_slots)}.\n\n"
            "Is the customer answering the current question normally, "
            "or are they trying to CORRECT/CHANGE a previously filled answer "
            "(e.g. 'actually change my date', 'wait, add more appetizers', "
            "'scratch that, make it 50 guests')?\n\n"
            "Return ONLY: normal or correction",
            last_user_msg
        )
        if correction_check.strip().lower() == "correction":
            return "check_modifications"

    from agent.nodes import NODE_MAP
    if current in NODE_MAP:
        return current

    return "start"

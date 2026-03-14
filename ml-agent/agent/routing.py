"""
Routing logic for the catering intake conversation graph.

Two-layer routing:
1. Check for @AI modification request → route to check_modifications
2. Otherwise route to current_node (set by previous node)
"""

from langchain_core.messages import HumanMessage
from agent.state import ConversationState


def route_message(state: ConversationState) -> str:
    """
    Route to the correct node based on state.

    Priority:
    1. If user message contains @AI or @ai → check_modifications
    2. Otherwise → current_node from state
    """
    # Check last user message for @AI tag
    last_user_msg = ""
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    # Match @AI, @ai, @cateringAI, @catering_ai, @CateringAI, etc.
    import re
    if re.search(r'@\w*ai\b', last_user_msg, re.IGNORECASE):
        return "check_modifications"

    current = state.get("current_node", "start")

    valid_nodes = {
        "start", "collect_name", "collect_event_date", "select_service_type",
        "select_event_type", "wedding_message", "collect_venue",
        "collect_guest_count", "present_menu", "select_service_style",
        "select_dishes", "ask_appetizers", "select_appetizers",
        "menu_design", "ask_menu_changes", "collect_menu_changes",
        "ask_utensils", "select_utensils",
        "ask_desserts", "select_desserts", "ask_more_desserts",
        "ask_rentals", "ask_florals",
        "ask_special_requests", "collect_special_requests",
        "collect_dietary", "ask_anything_else", "collect_anything_else",
        "generate_contract", "check_modifications",
    }

    if current in valid_nodes:
        return current

    return "start"

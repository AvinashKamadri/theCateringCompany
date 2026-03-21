"""
Routing logic for the catering intake conversation graph.

Two-layer routing:
1. Check for modification request (explicit @AI tag OR natural correction phrase) → check_modifications
2. Otherwise route to current_node (set by previous node)
"""

import re
from langchain_core.messages import HumanMessage
from agent.state import ConversationState

# Maps each node to the slot it is currently collecting.
# Used to detect when the user is talking about a DIFFERENT slot than the current one.
_NODE_COLLECTS: dict[str, str | None] = {
    "collect_name": "name",
    "collect_event_date": "event_date",
    "select_service_type": "service_type",
    "select_event_type": "event_type",
    "wedding_message": None,
    "collect_venue": "venue",
    "collect_guest_count": "guest_count",
    "select_service_style": "service_style",
    "ask_appetizers": "appetizers",
    "select_appetizers": "appetizers",
    "present_menu": "selected_dishes",
    "select_dishes": "selected_dishes",
    "menu_design": None,
    "ask_menu_changes": "selected_dishes",
    "collect_menu_changes": "selected_dishes",
    "ask_utensils": "utensils",
    "select_utensils": "utensils",
    "ask_desserts": "desserts",
    "select_desserts": "desserts",
    "ask_more_desserts": "desserts",
    "ask_rentals": "rentals",
    "ask_florals": "florals",
    "ask_special_requests": "special_requests",
    "collect_special_requests": "special_requests",
    "collect_dietary": "dietary_concerns",
    "ask_anything_else": "additional_notes",
    "collect_anything_else": "additional_notes",
    "generate_contract": None,
}

# Words/phrases that clearly signal the user wants to correct a PREVIOUS answer.
_CORRECTION_SIGNALS = re.compile(
    r'\b(actually|wait|i meant|let me change|can you (change|update|fix)|'
    r'change (my|the)|update (my|the)|i want to (change|update)|'
    r'correction|oh wait|no wait|sorry,?\s+i|i made a mistake|'
    r'i forgot to|i need to (change|update|fix)|'
    r'make that|scratch that)\b',
    re.IGNORECASE,
)

# Keyword sets per slot for detecting which slot the user is talking about.
_SLOT_KEYWORDS: dict[str, list[str]] = {
    "name":          [r'\bmy name\b', r'\bname is\b', r'\bcall me\b'],
    "event_date":    [r'\bthe date\b', r'\bmy date\b', r'\bevent date\b', r'\bdate is\b', r'\bdate to\b'],
    "guest_count":   [r'\bguests?\b', r'\bguest count\b', r'\bpeople\b', r'\battendees?\b'],
    "venue":         [r'\bvenue\b', r'\blocation\b', r'\bplace\b', r'\baddress\b', r'\bheld at\b'],
    "service_type":  [r'\bdrop.?off\b', r'\bon.?site\b', r'\bservice type\b'],
    "event_type":    [r'\bwedding\b', r'\bcorporate\b', r'\bbirthday\b', r'\bevent type\b'],
    "dietary_concerns": [r'\bdiet\b', r'\ballerg\b', r'\bvegan\b', r'\bvegetarian\b', r'\bhalal\b', r'\bkosher\b'],
    "special_requests": [r'\bspecial request\b', r'\bnote\b'],
    "appetizers":       [r'appetizers?', r'hors\s*d\'?oeuvres?', r'starters?'],
    "selected_dishes":  [r'\bdishes?\b', r'\bentr[eé]es?\b', r'\bmain\s+courses?\b', r'\bfood\s+selection\b'],
}


_ADD_TO_PREV_PATTERN = re.compile(
    r'\b(also\s+add|let me (also\s+)?add|i (also\s+)?want to add|add .+ to (the|my))\b',
    re.IGNORECASE,
)


def _detect_off_topic_correction(msg: str, current_slot: str | None, filled_slots: set[str]) -> bool:
    """Return True if the message looks like a correction targeting a slot OTHER than the current one.

    Criteria (either A or B):
    A) Contains a correction signal + a slot keyword for a different slot
    B) Contains a correction signal + an explicit "add to previous" phrase
       (e.g. "wait let me also add X to the appetizers" — even if slot keyword is missing)
    """
    if not _CORRECTION_SIGNALS.search(msg):
        return False

    msg_lower = msg.lower()

    # B) "wait/actually" + "also add / let me add / add X to the" — route to check_modifications
    #    so it can figure out which slot the item belongs to
    if _ADD_TO_PREV_PATTERN.search(msg_lower):
        return True

    # A) Correction signal + explicit slot keyword for a different slot
    for slot, patterns in _SLOT_KEYWORDS.items():
        if slot == current_slot:
            continue  # Talking about the current slot is normal, not an off-topic correction
        for pattern in patterns:
            if re.search(pattern, msg_lower):
                return True
    return False


def route_message(state: ConversationState) -> str:
    """
    Route to the correct node based on state.

    Priority:
    1. If user message contains @AI tag → check_modifications
    2. If message is a natural correction for a different slot → check_modifications
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

    # 2. Natural correction for a slot different from what we're currently asking
    current_slot = _NODE_COLLECTS.get(current)
    filled_slots = {
        name for name, data in state.get("slots", {}).items()
        if data.get("filled")
    }
    if _detect_off_topic_correction(last_user_msg, current_slot, filled_slots):
        return "check_modifications"

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

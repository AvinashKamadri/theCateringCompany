"""
Routing logic for the catering intake conversation graph.

Two-layer routing:
1. Check for natural modification intent (correction/additive phrases + slot keywords) → check_modifications
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
    "collect_fiance_name": "partner_name",
    "collect_birthday_person": "honoree_name",
    "collect_company_name": "company_name",
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
    "collect_pending_details": None,  # dynamic — node chooses the TBD slot itself
    "generate_contract": None,
}

# Words/phrases that clearly signal the user wants to correct a PREVIOUS answer.
_CORRECTION_SIGNALS = re.compile(
    r'\b(actually|wait|i meant|let me change|can you (change|update|fix|edit|add|remove|delete)|'
    r'change (my|the)|update (my|the)|edit (my|the)|add (to|in|on)|remove|delete|'
    r'i want to (change|update|edit|add|remove|delete)|'
    r'correction|oh wait|no wait|sorry,?\s+i|i made a mistake|'
    r'i forgot to|i need to (change|update|fix|edit|add|remove|delete)|'
    r'make that|scratch that|instead of|rather than|replace .+ with|'
    r'revise|modify|clear|wipe|drop)\b',
    re.IGNORECASE,
)

# Bare modify/action verbs — no leading "actually/wait" needed, since users can't rely on @AI.
# Pair this with a slot keyword to be safe. Covers: change, update, edit, fix, modify, revise,
# correct, switch, add, remove, delete, append, insert, drop, clear, wipe.
_MODIFY_VERB = re.compile(
    r'\b(change|update|edit|fix|modify|revise|correct|switch|add|remove|delete|'
    r'append|insert|drop|clear|wipe)\b',
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
    r'\b(also\s+add|let me (also\s+)?add|i (also\s+)?want to add|add .+ to (the|my)|i also need)\b',
    re.IGNORECASE,
)

# Phrases that signal the user wants to add/append/insert to a PREVIOUS slot.
# Unlike correction signals, these don't need a correction signal — they are
# additive-only and always route to check_modifications.
_ADDITIVE_SIGNALS = re.compile(
    r'\b(i also need|also need|i need to add|please also add|also (add|include|put)|'
    r'plus|and also|throw in|toss in|include|add in|add on|add more)\b',
    re.IGNORECASE,
)


def _detect_off_topic_correction(msg: str, current_slot: str | None, filled_slots: set[str]) -> bool:
    """Return True if the message looks like a correction targeting a slot OTHER than the current one.

    Criteria (A, B, or C):
    A) Contains a correction signal + a slot keyword for a different slot
    B) Contains a correction signal + an explicit "add to previous" phrase
       (e.g. "wait let me also add X to the appetizers" — even if slot keyword is missing)
    C) Contains an additive signal ("i also need", "also need") — always routes to check_modifications
       so the agent can figure out which slot to append to
    """
    msg_lower = msg.lower()

    # C) Pure additive — no correction signal needed
    if _ADDITIVE_SIGNALS.search(msg_lower):
        return True

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


def _detect_modify_intent(msg: str, current_slot: str | None) -> bool:
    """Return True when the user uses a modify verb (change/update/edit/fix/modify/revise/switch)
    alongside a slot keyword for a DIFFERENT slot than the current one.

    This replaces explicit @AI tagging — we infer edit intent from keywords instead.
    """
    if not _MODIFY_VERB.search(msg):
        return False
    msg_lower = msg.lower()
    for slot, patterns in _SLOT_KEYWORDS.items():
        if slot == current_slot:
            continue
        for pattern in patterns:
            if re.search(pattern, msg_lower):
                return True
    return False


def route_message(state: ConversationState) -> str:
    """
    Route to the correct node based on state.

    Priority:
    1. If message is a natural correction/addition targeting a DIFFERENT slot → check_modifications
    2. Otherwise → current_node from state
    """
    last_user_msg = ""
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, HumanMessage):
            last_user_msg = msg.content
            break

    current = state.get("current_node", "start")

    # 1. Natural correction/addition for a slot different from what we're currently asking
    current_slot = _NODE_COLLECTS.get(current)
    filled_slots = {
        name for name, data in state.get("slots", {}).items()
        if data.get("filled")
    }
    if _detect_off_topic_correction(last_user_msg, current_slot, filled_slots):
        return "check_modifications"

    # 2. Natural "modify/change/update" intent combined with a slot keyword — route to check_modifications.
    if _detect_modify_intent(last_user_msg, current_slot):
        return "check_modifications"

    from agent.nodes import NODE_MAP
    if current in NODE_MAP:
        return current

    return "start"

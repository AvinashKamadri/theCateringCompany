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
    "select_event_type": "event_type",
    "collect_event_type_followup": "event_type",
    "collect_event_date": "event_date",
    "collect_venue": "venue",
    "collect_guest_count": "guest_count",
    "select_service_type": "service_type",
    "ask_cocktail_hour": "service_style",
    "select_appetizers": "appetizers",
    "ask_buffet_or_plated": "buffet_or_plated",
    "present_menu": "selected_dishes",
    "select_dishes": "selected_dishes",
    "ask_menu_changes": "selected_dishes",
    "collect_menu_changes": "selected_dishes",
    "ask_desserts": "desserts",
    "select_desserts": "desserts",
    "ask_drinks": "drinks",
    "ask_bar_service": "bar_service",
    "ask_tableware": "tableware",
    "ask_rentals": "rentals",
    "ask_special_requests": "special_requests",
    "collect_special_requests": "special_requests",
    "ask_labor_services": "labor_services",
    "collect_dietary": "dietary_concerns",
    "generate_summary": None,
    "offer_followup_call": None,
}

# Words/phrases that clearly signal the user wants to correct a PREVIOUS answer.
_CORRECTION_SIGNALS = re.compile(
    r'\b(actually|wait|i meant|let me change|can you (change|update|fix)|'
    r'change (my|the|guest|event|venue|date|name|service|rental|dessert|drink|bar|tableware)|'
    r'update (my|the|guest|event|venue|date|name|service|drink|bar)|'
    r'i want to (change|update)|'
    r'correction|oh wait|no wait|sorry,?\s+i|i made a mistake|'
    r'i forgot to|i need to (change|update|fix)|'
    r'make that|scratch that|'
    r'set (my|the|guest|event|venue|date)|'
    r'the (guest count|venue|date|name|service type|event type) (is|should be|was|needs to be)|'
    r'is (the\s+)?\d+(st|nd|rd|th)?\s+not|'  # "is 4th not 2nd"
    r'not\s+\d+(st|nd|rd|th)?|'  # "not 2nd", "not the 2nd"
    r'\bwrong\s+(date|day|venue|name|number|count)\b)\b',
    re.IGNORECASE,
)

# Keyword sets per slot for detecting which slot the user is talking about.
_SLOT_KEYWORDS: dict[str, list[str]] = {
    "name":             [r'\bmy name\b', r'\bname is\b', r'\bcall me\b'],
    "event_date":       [r'\bthe date\b', r'\bmy date\b', r'\bevent date\b', r'\bdate is\b', r'\bdate to\b',
                         r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
                         r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
                         r'\bnext\s+(week|month|saturday|sunday|monday|friday)\b'],
    "guest_count":      [r'\bguests?\b', r'\bguest count\b', r'\bpeople\b', r'\battendees?\b'],
    "venue":            [r'\bvenue\b', r'\blocation\b', r'\bplace\b', r'\baddress\b', r'\bheld at\b'],
    "service_type":     [r'\bdrop.?off\b', r'\bonsite\b', r'\bservice type\b'],
    "event_type":       [r'\bwedding\b', r'\bcorporate\b', r'\bbirthday\b', r'\bevent type\b'],
    "fiance_name":      [r'\bfianc[eé]\b', r'\bpartner\b', r'\bspouse\b'],
    "buffet_or_plated": [r'\bbuffet\b', r'\bplated\b'],
    "dietary_concerns": [r'\bdiet\b', r'\ballerg\b', r'\bvegan\b', r'\bvegetarian\b', r'\bhalal\b', r'\bkosher\b'],
    "special_requests": [r'\bspecial request\b', r'\bnote\b'],
    "appetizers":       [r'appetizers?', r'hors\s*d\'?oeuvres?', r'starters?'],
    "selected_dishes":  [r'\bdishes?\b', r'\bentr[eé]es?\b', r'\bmain\s+courses?\b', r'\bfood\s+selection\b'],
    "desserts":         [r'\bdesserts?\b', r'\bcake\b', r'\bcupcakes?\b', r'\bcookies?\b', r'\bsweets?\b'],
    "drinks":           [r'\bdrinks?\b', r'\bcoffee\b', r'\bbeverage\b'],
    "bar_service":      [r'\bbar\b', r'\bcocktails?\b', r'\bbeer\b', r'\bwine\b', r'\bliquor\b'],
    "tableware":        [r'\btableware\b', r'\bchina\b', r'\bdisposable\b', r'\bplates?\b', r'\bsilverware\b'],
    "labor_services":   [r'\bsetup\b', r'\bcleanup\b', r'\btravel\b', r'\blabor\b'],
}


_ADD_TO_PREV_PATTERN = re.compile(
    r'\b(also\s+add|let me (also\s+)?add|i (also\s+)?want to add|add .+ to (the|my))\b',
    re.IGNORECASE,
)

# Remove/delete intent on any previously-collected item → always route to check_modifications
# Note: "drop" alone is excluded because "drop off" / "drop-off" is a valid service type selection
_REMOVE_INTENT_PATTERN = re.compile(
    r'\b(remove|delete|take out|drop\s+(?!off)(?!-off)\w+|i (added|selected|chose|picked).+by mistake|by mistake.+(remove|delete|take out))\b',
    re.IGNORECASE,
)


def _detect_off_topic_correction(msg: str, current_slot: str | None, filled_slots: set[str]) -> bool:
    """Return True if the message looks like a correction targeting a slot OTHER than the current one.

    Criteria (A, B, or C):
    A) Contains a correction signal + a slot keyword for a different slot
    B) Contains a correction signal + an explicit "add to previous" phrase
       (e.g. "wait let me also add X to the appetizers" — even if slot keyword is missing)
    C) Starts with "no" + references a different slot (e.g. "no the venue is my home")
       — user is rejecting the current question and redirecting to a different slot
    """
    msg_lower = msg.lower()

    # B) "wait/actually" + "also add / let me add / add X to the" — route to check_modifications
    if _CORRECTION_SIGNALS.search(msg) and _ADD_TO_PREV_PATTERN.search(msg_lower):
        return True

    # A) Correction signal + explicit slot keyword for a different slot
    if _CORRECTION_SIGNALS.search(msg):
        for slot, patterns in _SLOT_KEYWORDS.items():
            if slot == current_slot:
                continue
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    return True

    # C) "no [the/my/...] <slot-keyword>" — user correcting/redirecting mid-flow
    if re.match(r'^no[\s,]', msg_lower):
        for slot, patterns in _SLOT_KEYWORDS.items():
            if slot == current_slot:
                continue
            for pattern in patterns:
                if re.search(pattern, msg_lower):
                    return True

    # D) Message contains "not [number]" or "is [date] not" → date correction without signal word
    #    e.g. "next saturday is 4th not 2nd", "its the 4th not the 2nd"
    if re.search(r'\bnot\s+\d+|\bis\s+\w*\d+\w*\s+not\b', msg_lower):
        if current_slot != "event_date":
            for pattern in _SLOT_KEYWORDS.get("event_date", []):
                if re.search(pattern, msg_lower):
                    return True
            # Also catch plain number corrections at date collection stage when a date is already filled
            if "event_date" in filled_slots:
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

    # 2. Remove/delete intent on any item → always route to check_modifications
    if _REMOVE_INTENT_PATTERN.search(last_user_msg):
        return "check_modifications"

    # 3. Natural correction for a slot different from what we're currently asking
    current_slot = _NODE_COLLECTS.get(current)
    filled_slots = {
        name for name, data in state.get("slots", {}).items()
        if data.get("filled")
    }
    if _detect_off_topic_correction(last_user_msg, current_slot, filled_slots):
        return "check_modifications"


    valid_nodes = {
        "start", "collect_name", "select_event_type", "collect_event_type_followup",
        "collect_event_date", "collect_venue", "collect_guest_count",
        "select_service_type",
        "ask_cocktail_hour", "select_appetizers",
        "ask_buffet_or_plated", "present_menu", "select_dishes",
        "ask_menu_changes", "collect_menu_changes",
        "ask_desserts", "select_desserts",
        "ask_drinks", "ask_bar_service",
        "ask_tableware", "ask_rentals",
        "ask_special_requests", "collect_special_requests",
        "ask_labor_services", "collect_dietary",
        "generate_summary", "offer_followup_call",
        "check_modifications",
    }

    # "complete" means summary was already generated — stay at offer_followup_call
    # so post-summary messages don't restart the flow
    if current == "complete":
        return "offer_followup_call"

    if current in valid_nodes:
        return current

    return "start"

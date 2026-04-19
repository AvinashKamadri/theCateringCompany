"""
Routing logic for the catering intake conversation graph.

Two-layer routing:
1. Check for natural modification intent (correction/additive phrases + slot keywords) → check_modifications
2. Otherwise route to current_node (set by previous node)
"""

import re
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import ConversationState
from agent.llm import llm_cold

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
    "collect_dietary_details": "dietary_concerns",
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
    r'revise|modify|clear|wipe|drop(?!.?off)|skip)\b',
    re.IGNORECASE,
)

# Bare modify/action verbs — no leading "actually/wait" needed, since users can't rely on @AI.
# Pair this with a slot keyword to be safe. Covers: change, update, edit, fix, modify, revise,
# correct, switch, add, remove, delete, append, insert, drop, clear, wipe, skip.
_MODIFY_VERB = re.compile(
    r'\b(change|update|edit|fix|modify|revise|correct|switch|add|remove|delete|'
    r'append|insert|drop|clear|wipe|skip)\b',
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
    "special_requests": [r'\bspecial requests?\b', r'\bdietary\b', r'\bnote\b', r'\brestriction\b', r'\bintoleranc\b', r'\ballerg\b'],
    "additional_notes": [r'\binstructions?\b', r'\badditional (note|info|detail)\b', r'\bnote for\b', r'\bleave (a )?note\b', r'\banything else\b', r'\bremind\b'],
    "appetizer_style":  [r'\bpassed\s+around\b', r'\bpassing\b', r'\bset\s+up\s+at\s+(a\s+)?station\b', r'\bappetizer\s+style\b', r'\bserved\s+(by\s+)?servers?\b'],
    "meal_style":       [r'\bplated\b', r'\bbuffet\b', r'\bmeal\s+style\b', r'\bserving\s+style\b'],
    "service_style":    [r'\bcocktail\s+hour\b', r'\bfull\s+reception\b', r'\bservice\s+style\b'],
    "appetizers":       [r'appetizers?', r'hors\s*d\'?oeuvres?', r'starters?'],
    "selected_dishes":  [r'\bdishes?\b', r'\bentr[eé]es?\b', r'\bmain\s+courses?\b', r'\bfood\s+selection\b', r'\bthe menu\b', r'\bmain menu\b'],
    "desserts":         [r'\bdesserts?\b', r'\bcakes?\b', r'\bcupcakes?\b', r'\bbrownie\b', r'\bmousse\b', r'\bcheesecake\b'],
    "drinks":           [r'\bdrinks?\b', r'\bbeverages?\b', r'\bcoffee\s+service\b', r'\bbar\s+(service|package|setup)\b', r'\bopen\s+bar\b', r'\bbeer\b', r'\bwine\b'],
    "utensils":         [r'\butensils?\b', r'\bflatware\b', r'\bsilverware\b', r'\bbamboo\b', r'\bplastic\b', r'\beco.?friendly\b'],
    "rentals":          [r'\brentals?\b', r'\blinens?\b', r'\btable\s+rental\b', r'\bchair\s+rental\b'],
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


_REMOVE_ADD_VERB = re.compile(r'\b(remove|delete|drop|add|include)\b', re.IGNORECASE)
_MENU_SLOTS = {"appetizers", "selected_dishes", "desserts", "drinks"}


def _detect_off_topic_correction(msg: str, current_slot: str | None, filled_slots: set[str], slots: dict | None = None) -> bool:
    """Return True if the message looks like a correction targeting a slot OTHER than the current one.

    Criteria (A, B, C, D):
    A) Contains a correction signal + a slot keyword for a different slot
    B) Contains a correction signal + an explicit "add to previous" phrase
    C) Contains an additive signal ("i also need", "also need")
    D) Contains remove/add verb + a substring that appears in any filled menu slot value
       (catches "remove Crab Dip" without requiring the word "appetizers")
    """
    msg_lower = msg.lower()

    # C) Pure additive — no correction signal needed
    if _ADDITIVE_SIGNALS.search(msg_lower):
        return True

    # D) remove/add + item name found in a filled menu slot value
    if _REMOVE_ADD_VERB.search(msg) and slots:
        for slot_name in _MENU_SLOTS:
            if slot_name == current_slot:
                continue
            data = slots.get(slot_name, {})
            if not data.get("filled"):
                continue
            slot_val = str(data.get("value") or "").lower()
            if not slot_val or slot_val in ("no", "none", ""):
                continue
            # Check if any word sequence from the message (3+ chars) appears in the slot value
            words = msg_lower.split()
            for i in range(len(words)):
                for j in range(i + 1, min(i + 5, len(words) + 1)):
                    phrase = " ".join(words[i:j])
                    if len(phrase) >= 3 and phrase in slot_val:
                        return True

    if not _CORRECTION_SIGNALS.search(msg):
        return False

    msg_lower = msg.lower()

    # B) "wait/actually" + "also add / let me add / add X to the"
    if _ADD_TO_PREV_PATTERN.search(msg_lower):
        return True

    # A) Correction signal + explicit slot keyword for a different slot
    for slot, patterns in _SLOT_KEYWORDS.items():
        if slot == current_slot:
            continue
        for pattern in patterns:
            if re.search(pattern, msg_lower):
                return True
    return False


# "replace X with Y" / "change X to Y" / "swap X for Y" — anchored by value, not slot name.
# Even without a slot keyword, if X matches a currently-filled slot value we should route
# to check_modifications.
_REPLACE_BY_VALUE_PATTERN = re.compile(
    r'\b(replace|swap|switch)\s+(.+?)\s+(with|for|to)\s+(.+)$|'
    r'\bchange\s+(.+?)\s+to\s+(.+)$',
    re.IGNORECASE,
)


def _detect_replace_by_value(msg: str, slots: dict) -> bool:
    """Return True if the message says 'replace X with Y' and X appears inside any filled slot's value.

    This catches cases where the user names the OLD value (e.g. 'replace algunoor karimnagar
    with peddapeli') instead of naming the slot ('replace the venue ...').
    """
    m = _REPLACE_BY_VALUE_PATTERN.search(msg)
    if not m:
        return False
    # Group layout: 'replace/swap/switch X with/for/to Y' → groups 2 & 4 ; 'change X to Y' → groups 5 & 6
    old_val = (m.group(2) or m.group(5) or "").strip().lower()
    if not old_val or len(old_val) < 2:
        return False
    for _, data in slots.items():
        if not data.get("filled"):
            continue
        cur = str(data.get("value") or "").lower()
        if not cur or cur in ("no", "none", ""):
            continue
        # Substring match (either direction) — robust against partial phrasings like
        # 'replace algunoor with X' when value is 'algunoor karimnagar'
        if old_val in cur or cur in old_val:
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


# ── Section-jump shortcuts ────────────────────────────────────────────────────
# When the user names a section ("add desserts", "go to appetizers", "skip to
# utensils"), route directly to the node that handles that section instead of
# leaking into whatever node was current. The trigger verbs are loose on
# purpose so we catch natural phrasings like "want desserts" or "more desserts"
# alongside explicit "add/go to/pick" forms. Each entry is (pattern, node).
_SECTION_JUMP: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(add|more|pick|choose|select|want|show|go to|back to|skip to|jump to|do)\b.*?\bdesserts?\b', re.IGNORECASE), "ask_desserts"),
    (re.compile(r'\b(add|more|pick|choose|select|want|show|go to|back to|skip to|jump to|do)\b.*?\b(appetizers?|hors\s*d\'?oeuvres?|starters?)\b', re.IGNORECASE), "ask_appetizers"),
    (re.compile(r'\b(add|pick|choose|select|want|show|go to|back to|skip to|jump to|do)\b.*?\b(main\s+(dish(es)?|courses?)|entr[eé]es?|dishes?|menu\s+items?)\b', re.IGNORECASE), "select_dishes"),
    (re.compile(r'\b(add|pick|choose|select|want|show|go to|back to|skip to|jump to|do)\b.*?\butensils?\b', re.IGNORECASE), "ask_utensils"),
    (re.compile(r'\b(add|pick|choose|select|want|show|go to|back to|skip to|jump to|do)\b.*?\brentals?\b', re.IGNORECASE), "ask_rentals"),
    (re.compile(r'\b(add|pick|choose|select|want|show|go to|back to|skip to|jump to|do)\b.*?\b(bar(\s+service)?|drinks?|beverages?)\b', re.IGNORECASE), "collect_bar_service"),
]


def _detect_section_jump(msg: str, current: str) -> str | None:
    """If the user asks for a section by name, return that section's node.

    Skips the match when the user is already IN that section's ask/select pair
    (e.g. "add desserts" while current_node is ask_desserts/select_desserts —
    the current node will handle it naturally).
    """
    # Map: current node → nodes we should NOT jump TO (already here)
    stay_put = {
        "ask_desserts": {"ask_desserts", "select_desserts", "ask_more_desserts"},
        "select_desserts": {"ask_desserts", "select_desserts", "ask_more_desserts"},
        "ask_more_desserts": {"ask_desserts", "select_desserts", "ask_more_desserts"},
        "ask_appetizers": {"ask_appetizers", "select_appetizers"},
        "select_appetizers": {"ask_appetizers", "select_appetizers"},
        "select_dishes": {"select_dishes", "present_menu", "ask_menu_changes", "collect_menu_changes"},
        "ask_utensils": {"ask_utensils", "select_utensils"},
        "select_utensils": {"ask_utensils", "select_utensils"},
        "ask_rentals": {"ask_rentals"},
        "collect_bar_service": {"collect_bar_service", "collect_drinks"},
    }
    blocked = stay_put.get(current, set())
    for pattern, node in _SECTION_JUMP:
        if node in blocked:
            continue
        if pattern.search(msg):
            return node
    return None


async def _llm_fallback_is_modification(last_ai_msg: str, last_user_msg: str) -> bool:
    """Ask the LLM whether the user is modifying a previous answer or answering normally.

    Only called when all regex checks have failed AND there are filled menu slots.
    Returns True if the LLM says "modification".
    """
    prompt = (
        f'The agent just asked the customer a question. Determine if the customer is:\n'
        f'(A) answering the agent\'s question normally, OR\n'
        f'(B) trying to change/remove/add something from a PREVIOUS answer (not what\'s being asked right now)\n\n'
        f'Agent\'s question: "{last_ai_msg[:300]}"\n'
        f'Customer\'s reply: "{last_user_msg}"\n\n'
        f'IMPORTANT: Only return "modification" if the customer is clearly changing a PREVIOUSLY GIVEN answer,\n'
        f'not if they are answering the current question. For example:\n'
        f'- Agent asks "how many guests?" + customer says "remove Crab Dip" \u2192 modification\n'
        f'- Agent asks "any dietary restrictions?" + customer says "no dietary restrictions" \u2192 normal\n'
        f'- Agent asks "passed or station?" + customer says "remove Crab Dip from appetizers" \u2192 modification\n\n'
        f'Return ONLY: normal or modification'
    )
    response = await llm_cold.ainvoke([{"role": "user", "content": prompt}])
    result = (response.content or "").strip().lower()
    return result == "modification"


async def route_message(state: ConversationState) -> str:
    """
    Route to the correct node based on state.

    Priority:
    0. Section-jump shortcut ("add desserts", "go to appetizers", …)
    1. If message is a natural correction/addition targeting a DIFFERENT slot → check_modifications
    2. Otherwise → current_node from state
    3. LLM fallback when all regex checks fail and menu slots are filled
    """
    last_user_msg = ""
    last_ai_msg = ""
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, HumanMessage) and not last_user_msg:
            last_user_msg = msg.content
        elif isinstance(msg, AIMessage) and not last_ai_msg:
            last_ai_msg = msg.content
        if last_user_msg and last_ai_msg:
            break

    current = state.get("current_node", "start")

    # 0. Section-jump shortcut — route directly to the named section.
    jump = _detect_section_jump(last_user_msg, current)
    if jump is not None:
        state["current_node"] = jump
        return jump

    # 1. Natural correction/addition for a slot different from what we're currently asking
    current_slot = _NODE_COLLECTS.get(current)
    filled_slots = {
        name for name, data in state.get("slots", {}).items()
        if data.get("filled")
    }
    if _detect_off_topic_correction(last_user_msg, current_slot, filled_slots, slots=state.get("slots", {})):
        return "check_modifications"

    # 2. Natural "modify/change/update" intent combined with a slot keyword — route to check_modifications.
    if _detect_modify_intent(last_user_msg, current_slot):
        return "check_modifications"

    # 3. "replace X with Y" / "change X to Y" — if X matches any filled slot value, route to modify.
    if _detect_replace_by_value(last_user_msg, state.get("slots", {})):
        return "check_modifications"

    # 4. If menu slots are filled and the message contains a bare add/remove verb with at least
    #    one other word, it is deterministically a modification — no LLM needed.
    slots = state.get("slots", {})
    has_filled_menu_slots = any(
        slots.get(s, {}).get("filled") for s in _MENU_SLOTS
    )
    if has_filled_menu_slots and last_user_msg:
        word_count = len(last_user_msg.split())
        has_remove_add = bool(_REMOVE_ADD_VERB.search(last_user_msg))
        if has_remove_add and word_count >= 2:
            return "check_modifications"

    # 5. LLM fallback — only for longer ambiguous messages where no regex matched.
    #    Skip when current node is a pure selection node — the user is always answering
    #    the menu prompt there, never making a modification.
    _SELECTION_NODES = {
        "select_desserts", "select_appetizers", "select_dishes",
        "select_utensils", "present_menu",
    }
    if has_filled_menu_slots and last_ai_msg and last_user_msg and current not in _SELECTION_NODES:
        word_count = len(last_user_msg.split())
        has_correction = bool(_CORRECTION_SIGNALS.search(last_user_msg))
        if word_count > 3 or has_correction:
            if await _llm_fallback_is_modification(last_ai_msg, last_user_msg):
                return "check_modifications"

    from agent.nodes import NODE_MAP
    if current in NODE_MAP:
        return current

    return "start"

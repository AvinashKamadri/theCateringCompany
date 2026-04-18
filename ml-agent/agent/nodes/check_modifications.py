"""
Check modifications node — Handle @AI slot modifications.

Generalized behavior:
- Detects which slot the user wants to change via keyword + LLM layers
- Validates and applies the change
- ALWAYS stays on the same current_node (never jumps ahead)
- Re-asks the pending question by extracting it from the last AI message
  (no LLM call, no NODE_PROMPTS — bulletproof against node jumping)
"""

import re
import logging
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage
from agent.state import ConversationState
from tools.modification_detection import detect_slot_modification
from tools.slot_validation import validate_slot, _contains_relative_date, _resolve_relative_date
from agent.nodes.helpers import add_ai_message

logger = logging.getLogger(__name__)
_MOD_VERSION = "v12"  # Bump to verify this code is running


_MENU_BUCKET_DEFS = {
    "appetizers":      {"reentry": "select_appetizers"},
    "selected_dishes": {"reentry": "select_dishes"},
    "desserts":        {"reentry": "select_desserts"},
    "drinks":          {"reentry": "collect_drinks"},
}


def _name_similar(a: str, b: str) -> bool:
    """Return True if two item names are close enough to be the same item.

    Handles typos and British/American spelling variants (e.g. "Flavoured" vs "Flavored")
    by comparing word-by-word and allowing ≤1 word to differ by ≤2 characters.
    """
    a, b = a.lower().strip(), b.lower().strip()
    if a == b or a in b or b in a:
        return True
    words_a, words_b = a.split(), b.split()
    if len(words_a) != len(words_b):
        return False
    mismatches = 0
    for wa, wb in zip(words_a, words_b):
        if wa != wb:
            if abs(len(wa) - len(wb)) > 2:
                return False
            mismatches += 1
    return mismatches <= 1


async def _find_item_in_any_menu(items_text: str, menu_context: dict, exclude_slot: str | None = None) -> tuple[str | None, list, dict]:
    """Search all menu buckets for items_text. Returns (slot_name, matched_items, filtered_menu).

    Checks appetizers, selected_dishes, desserts (via get_dessert_items expansion), and drinks.
    Skips exclude_slot (the slot that already failed). Returns (None, [], {}) if not found anywhere.
    """
    from agent.nodes.menu import (
        _resolve_to_db_items, _is_appetizer_category, _is_non_dish_category,
        get_dessert_items,
    )

    buckets: list[tuple[str, dict]] = []

    appetizer_menu = {k: v for k, v in menu_context.items() if _is_appetizer_category(k)}
    dishes_menu = {k: v for k, v in menu_context.items()
                   if not _is_non_dish_category(k) and not _is_appetizer_category(k)}
    drinks_menu = {k: v for k, v in menu_context.items()
                   if any(kw in k.lower() for kw in ["coffee", "beverage", "drink", "bar setup", "bar supplies"])}

    if exclude_slot != "appetizers":
        buckets.append(("appetizers", appetizer_menu))
    if exclude_slot != "selected_dishes":
        buckets.append(("selected_dishes", dishes_menu))
    if exclude_slot != "drinks":
        buckets.append(("drinks", drinks_menu))

    # Check appetizers, dishes, drinks via standard DB resolution
    for slot_name, bucket_menu in buckets:
        matched, _ = await _resolve_to_db_items(items_text, bucket_menu)
        if matched:
            return slot_name, matched, bucket_menu

    # Check desserts via expanded item list (sub-items live in bundle descriptions)
    if exclude_slot != "desserts":
        dessert_items = await get_dessert_items()
        dessert_lookup = {item["name"].lower(): item for item in dessert_items}
        query_names = [n.strip().lower() for n in items_text.split(",") if n.strip()]
        dessert_matched = []
        for qname in query_names:
            if qname in dessert_lookup:
                dessert_matched.append(dessert_lookup[qname])
            else:
                for key, item in dessert_lookup.items():
                    if qname in key or key in qname or _name_similar(qname, key):
                        dessert_matched.append(item)
                        break
        if dessert_matched:
            dessert_menu = {k: v for k, v in menu_context.items()
                            if any(kw in k.lower() for kw in ["dessert", "cake"])}
            return "desserts", dessert_matched, dessert_menu

    return None, [], {}


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled") and not k.startswith("__")}


# Conditional nodes: mapping of node_name → (slot_name, valid_condition_fn, fallback_node)
# If the slot no longer satisfies the condition, reroute to fallback_node.
_CONDITIONAL_NODES = {
    "wedding_message":        ("event_type", lambda v: v and "wedding" in str(v).lower(), "collect_venue"),
    "collect_fiance_name":    ("event_type", lambda v: v and "wedding" in str(v).lower(), "collect_event_date"),
    "collect_birthday_person":("event_type", lambda v: v and "birthday" in str(v).lower(), "collect_event_date"),
    "collect_company_name":   ("event_type", lambda v: v and "corporate" in str(v).lower(), "collect_event_date"),
    "select_service_style":   ("event_type", lambda v: v and "wedding" in str(v).lower(), "select_dishes"),
}


def _event_type_context_node(event_type_value) -> str | None:
    """Return the context-collection node required for the given event type, or None.

    Wedding → collect_fiance_name, Birthday → collect_birthday_person,
    Corporate → collect_company_name. Anything else has no context slot.
    """
    if not event_type_value:
        return None
    val = str(event_type_value).lower()
    if "wedding" in val:
        return "collect_fiance_name"
    if "birthday" in val:
        return "collect_birthday_person"
    if "corporate" in val:
        return "collect_company_name"
    return None


def _adjust_node_for_slot_change(node: str, slots: dict) -> str:
    """Re-route conditional nodes when the underlying slot no longer matches.

    For example, if event_type changed from Corporate to Wedding,
    'collect_company_name' should become 'collect_fiance_name' instead.
    """
    # If dishes are already filled, don't send back to the menu-browsing nodes —
    # go to ask_menu_changes so the user can confirm rather than re-pick.
    if node in ("present_menu", "select_dishes", "collect_menu_changes", "menu_design") and \
            slots.get("selected_dishes", {}).get("filled"):
        return "ask_menu_changes"

    # If desserts are already filled, don't loop back into dessert selection nodes.
    if node in ("ask_desserts", "select_desserts", "ask_more_desserts") and \
            slots.get("desserts", {}).get("filled"):
        return "ask_rentals"

    rule = _CONDITIONAL_NODES.get(node)
    if not rule:
        return node  # Not a conditional node — keep as-is

    slot_name, condition_fn, fallback = rule
    slot_data = slots.get(slot_name, {})
    current_value = slot_data.get("value")

    if not condition_fn(current_value):
        # For event_type changes, route to the NEW event type's context node
        if slot_name == "event_type" and current_value:
            val = str(current_value).lower()
            if "wedding" in val:
                fallback = "collect_fiance_name"
            elif "birthday" in val:
                fallback = "collect_birthday_person"
            elif "corporate" in val:
                fallback = "collect_company_name"
            else:
                fallback = "collect_event_date"
        print(f"[CHECK_MODIFICATIONS] Rerouting {node} -> {fallback} (slot '{slot_name}' = '{current_value}')")
        return fallback

    return node


def _get_slot_label(slot_name: str) -> str:
    """Convert slot key to human-readable label."""
    return slot_name.replace("_", " ")


_NO_QUESTION_NODES = {
    "generate_contract", "start", "menu_design", "wedding_message",
}


_REPLACE_BY_VALUE_RE = re.compile(
    r'\b(replace|swap|switch)\s+(.+?)\s+(?:with|for|to)\s+(.+)$|'
    r'\bchange\s+(.+?)\s+to\s+(.+)$',
    re.IGNORECASE,
)

# Strips price info like "($23.99/per_person)" or "($3.50/pp)" before name-matching.
_PRICE_RE = re.compile(r'\s*\([^)]*\)')


def _resolve_replace_by_value(message: str, slots: dict) -> tuple[str | None, str | None, str | None]:
    """If message is 'replace X with Y' / 'change X to Y' and X matches a filled slot value,
    return (slot_name, old_value_text, new_value). Otherwise (None, None, None).
    Normalizes price info before comparing so 'Pork & Chicken ($23.99/per_person)' matches
    the stored value 'Pork & Chicken ($23.99/pp)'.
    """
    m = _REPLACE_BY_VALUE_RE.search(message)
    if not m:
        return None, None, None
    old_val = (m.group(2) or m.group(4) or "").strip()
    new_val = (m.group(3) or m.group(5) or "").strip()
    if not old_val or not new_val:
        return None, None, None
    old_lower = old_val.lower()
    old_norm = _PRICE_RE.sub("", old_lower).strip()
    for slot_name, data in slots.items():
        if not data.get("filled"):
            continue
        cur = str(data.get("value") or "").lower()
        if not cur or cur in ("no", "none", ""):
            continue
        cur_norm = _PRICE_RE.sub("", cur).strip()
        if old_lower in cur or cur in old_lower or old_norm in cur_norm or cur_norm in old_norm:
            return slot_name, old_val, new_val
    return None, None, None


async def _extract_all_swap_pairs(message: str) -> list[tuple[str, str]]:
    """Extract all (old, new) swap pairs from a message that may contain N replacements.
    e.g. 'replace A with B and C with D' → [('A', 'B'), ('C', 'D')]
    """
    from agent.nodes.helpers import llm_extract as _le
    raw = await _le(
        'List every "replace/swap X with Y" pair in this message.\n'
        'Write one pair per line as:  OLD -> NEW\n'
        'Item names only, no prices or extra text.\n'
        'If none found, return "none".',
        message
    )
    if raw.strip().lower().startswith("none"):
        return []
    pairs = []
    for line in raw.strip().split('\n'):
        if '->' in line:
            left, _, right = line.partition('->')
            old = left.strip().strip('*').strip()
            new = right.strip().strip('*').strip()
            if old and new:
                pairs.append((old, new))
    return pairs


async def _extract_mixed_ops(message: str) -> dict:
    """Extract remove and add item lists from a message that does both in one go.
    Returns {"remove": [...], "add": [...]}
    """
    from agent.nodes.helpers import llm_extract as _le
    raw = await _le(
        "Extract items to REMOVE and items to ADD from this message.\n"
        "Format (one line each):\n"
        "REMOVE: item1, item2\n"
        "ADD: item3, item4\n"
        "If none for a category write 'none'. Item names only, no prices.",
        message
    )
    result: dict = {"remove": [], "add": []}
    for line in raw.strip().split("\n"):
        upper = line.upper()
        if upper.startswith("REMOVE:"):
            val = line.split(":", 1)[1].strip()
            if val.lower() != "none":
                result["remove"] = [v.strip() for v in val.split(",") if v.strip()]
        elif upper.startswith("ADD:"):
            val = line.split(":", 1)[1].strip()
            if val.lower() != "none":
                result["add"] = [v.strip() for v in val.split(",") if v.strip()]
    return result


_REMOVE_FROM_TEXT_RE = re.compile(
    r'\b(remove|delete|drop|clear|wipe|take out)\s+(.+)$',
    re.IGNORECASE,
)


def _looks_like_remove(message: str) -> tuple[bool, str]:
    """Return (is_remove, item_text). Only fires on messages that START with a remove verb
    or clearly express removal, so we don't mistake a sentence mentioning 'remove' elsewhere.
    """
    stripped = message.strip()
    m = _REMOVE_FROM_TEXT_RE.match(stripped)
    if not m:
        return False, ""
    return True, m.group(2).strip()

# Maps collection nodes to the slot they collect.
# Used to detect mid-collection @AI interrupts (slot not filled yet).
_NODE_SLOT_MAP = {
    "select_event_type":    "event_type",
    "collect_event_date":   "event_date",
    "collect_venue":        "venue",
    "collect_guest_count":  "guest_count",
    "select_service_type":  "service_type",
    "select_service_style": "service_style",
    "collect_meal_style":   "meal_style",
    "collect_fiance_name":  "partner_name",
    "collect_birthday_person": "honoree_name",
    "collect_company_name": "company_name",
    "collect_name":         "name",
    "collect_appetizer_style": "appetizer_style",
    "ask_utensils":          "utensils",
    "select_utensils":       "utensils",
    "collect_tableware":     "tableware",
    "collect_drinks":        "drinks",
    "collect_bar_service":   "drinks",
    "collect_labor":         "labor",
    "ask_rentals":           "rentals",
    "ask_appetizers":        "appetizers",
    "ask_desserts":          "desserts",
    "present_menu":          "selected_dishes",
    "select_appetizers":     "appetizers",
    "select_dishes":         "selected_dishes",
    "select_desserts":       "desserts",
    "ask_more_desserts":     "desserts",
}

# Plain re-ask prompts used when the slot for a node is not yet filled.
# These replace NODE_PROMPTS to avoid the LLM "confirming" an unknown value.
# Keep these to ONE casual line — static lists are appended separately via _PENDING_LIST_SUFFIXES.
_PENDING_PROMPTS = {
    "select_event_type":    "Re-ask what kind of event they're planning in one casual line. Do NOT list the options.",
    "collect_event_date":   "Re-ask what date they have in mind for the event. One short question.",
    "collect_venue":        "Re-ask where the event will be held — venue name, address, or city. One casual line.",
    "collect_guest_count":  "Re-ask how many guests they're expecting. One short question.",
    "select_service_type":  "Re-ask whether they want Drop-off or Onsite service. One casual line. Do NOT list the options.",
    "select_service_style": "Re-ask the wedding service style: cocktail hour, full reception, or both. One casual line.",
    "collect_meal_style":   "Re-ask whether they prefer plated or buffet for the main course. One casual line.",
    "collect_fiance_name":  "Re-ask for their partner's or fiancé's name. One warm question.",
    "collect_birthday_person": "Re-ask whose birthday this celebration is for. One upbeat line.",
    "collect_company_name": "Re-ask for the company or organization name. One brief line.",
    "collect_name":         "Re-ask for their first and last name. One friendly line.",
    "collect_appetizer_style": "Re-ask: passed around or set up at a station for the appetizers? One short line.",
    "ask_utensils":          "Re-ask what kind of utensils they'd like. One brief question. Do NOT list the options.",
    "select_utensils":       "Re-ask what kind of utensils they'd like. One brief question. Do NOT list the options.",
    "collect_tableware":     "Re-ask what tableware they'd like. One brief question. Do NOT list the options.",
    "collect_drinks":        "Re-ask if they want coffee service, bar service, or both. One casual line. Do NOT list the options.",
    "collect_bar_service":   "Re-ask which bar package they'd like. One casual line. Do NOT list the options.",
    "collect_labor":         "Re-ask which labor services they need. One casual line. Do NOT list the options.",
    "ask_rentals":           "Re-ask about rentals — linens, tables, chairs, or none. One casual line. Do NOT list the options.",
}

# Static numbered lists to append after the LLM re-ask intro for selection nodes.
# This ensures the frontend can render them as clickable options after an @AI mid-flow update.
# NOTE: DB-driven menus (appetizers, main dishes, desserts) are NOT listed here — those nodes
# return "" when slot is filled, and the node's own logic re-presents the menu when needed.
_PENDING_LIST_SUFFIXES = {
    "select_event_type":  "1. Wedding\n2. Birthday\n3. Corporate\n4. Social\n5. Custom",
    "select_service_type": "1. Drop-off (we deliver, no staff)\n2. Onsite (our team is there with you)",
    "ask_utensils":       "1. Standard Plastic\n2. Eco-friendly / Biodegradable\n3. Bamboo",
    "select_utensils":    "1. Standard Plastic\n2. Eco-friendly / Biodegradable\n3. Bamboo",
    "collect_tableware":  (
        "1. Standard Disposable (included)\n"
        "2. Premium Disposable (gold or silver) — $1 per person\n"
        "3. Full China — pricing based on guest count"
    ),
    "collect_drinks":     "1. Coffee Service\n2. Bar Service\n3. Both",
    "collect_bar_service": (
        "1. Beer & Wine\n"
        "2. Beer & Wine + Two Signature Drinks\n"
        "3. Full Open Bar\n"
        "All bar services include professional bartenders — $50/hr, 5-hour minimum."
    ),
    "collect_labor": (
        "1. Ceremony Setup/Cleanup — $1.50 per person\n"
        "2. Table & Chair Setup — $2.00 per person\n"
        "3. Table Preset (plates, napkins, cutlery) — $1.75 per person\n"
        "4. Reception Cleanup — $3.75 per person\n"
        "5. Trash Removal — $175 flat\n"
        "6. Travel Fee — $150 (30 min) / $250 (1 hr) / $375+ (extended)\n"
        "Feel free to pick multiple or none!"
    ),
    "ask_rentals":        "1. Linens\n2. Tables\n3. Chairs\nPick one, multiple, or all!",
}


async def _generate_fresh_question(node: str, state: dict) -> str:
    """Generate a fresh contextual question for the given node using current slot state.

    Always generated fresh via LLM — never extracted from stale conversation history.
    This ensures the re-asked question reflects CURRENT slot values after any modification.

    If the node's target slot is not yet filled (mid-collection @AI interrupt), uses a
    plain re-ask prompt instead of NODE_PROMPTS to prevent the LLM hallucinating a value.
    """
    if node in _NO_QUESTION_NODES:
        return ""
    from agent.nodes.helpers import llm_respond
    from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS

    # Check if this is a node whose primary slot we know
    pending_slot = _NODE_SLOT_MAP.get(node)
    if pending_slot:
        slot_filled = state["slots"].get(pending_slot, {}).get("filled", False)
        if not slot_filled:
            # DB-driven menu nodes: re-fetch and re-present the full menu inline.
            # NOTE: collect_meal_style is NOT here — it's a plated/buffet question,
            # not a menu. It uses _PENDING_PROMPTS instead.
            if node in ("select_dishes", "present_menu"):
                from agent.nodes.menu import get_main_dish_items
                from agent.nodes.helpers import build_numbered_list
                _, categorized = await get_main_dish_items()
                item_list = build_numbered_list([], categories=categorized, category_headers=True)
                intro = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nRe-present the main dish menu briefly in one casual line. Do NOT list any items.",
                    f"Current event info: {_slots_context(state)}"
                )
                return f"{intro}\n\n{item_list}\n\nPick 3 to 5 dishes!"

            if node in ("select_appetizers", "ask_appetizers"):
                from agent.nodes.menu import get_appetizer_items
                from agent.nodes.helpers import build_numbered_list
                items = await get_appetizer_items()
                item_list = build_numbered_list(items, show_price=True)
                intro = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nRe-present the appetizer menu briefly in one casual line. Do NOT list any items.",
                    f"Current event info: {_slots_context(state)}"
                )
                return f"{intro}\n\n{item_list}\n\nPick as many as you'd like! If you don't want appetizers, just say skip."

            if node in ("ask_desserts", "select_desserts", "ask_more_desserts"):
                from agent.nodes.menu import get_dessert_items
                from agent.nodes.helpers import build_numbered_list
                event_type = (state["slots"].get("event_type", {}).get("value") or "").lower()
                items = await get_dessert_items(is_wedding="wedding" in event_type)
                item_list = build_numbered_list(items, show_price=True)
                intro = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nRe-present the dessert menu briefly in one casual line. Do NOT list any items.",
                    f"Current event info: {_slots_context(state)}"
                )
                return f"{intro}\n\n{item_list}\n\nPick up to 4 items total!"

            # Slot not collected yet — re-ask with a plain prompt to avoid hallucination
            pending_prompt = _PENDING_PROMPTS.get(node)
            if pending_prompt:
                intro = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\n{pending_prompt}",
                    f"Current event info: {_slots_context(state)}"
                )
                static_list = _PENDING_LIST_SUFFIXES.get(node)
                return f"{intro}\n\n{static_list}" if static_list else intro
            # No pending prompt defined — stay silent; the previous question is still visible
            return ""
        else:
            # Slot already filled — don't generate a transition message.
            # The confirmation above is enough; the normal flow continues on the user's next reply.
            return ""

    node_prompt = NODE_PROMPTS.get(node, "")
    if not node_prompt:
        return ""
    return await llm_respond(
        f"{SYSTEM_PROMPT}\n\n"
        f"The customer just updated something in their order mid-conversation. "
        f"Acknowledge the change was made (it's already confirmed above), then naturally move to the next question — "
        f"like a waiter smoothly continuing service after handling a request. "
        f"ONE short question only, no preamble.\n\n"
        f"Step instruction: {node_prompt}",
        f"Current event info: {_slots_context(state)}"
    )


async def check_modifications_node(state: ConversationState) -> ConversationState:
    """
    Handle @AI slot modification requests.

    After processing, current_node is ALWAYS restored to previous_node
    so the conversation never jumps ahead.
    """
    from agent.nodes.helpers import llm_extract
    state = dict(state)
    print(f"\n[CHECK_MODIFICATIONS {_MOD_VERSION}] Entered check_modifications_node")

    # Remember where we were before the @AI interrupt
    previous_node = state.get("current_node", "start")
    print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] previous_node = {previous_node}")

    # We'll generate the fresh follow-up question AFTER processing (uses updated state)

    # Get last user message
    last_message = ""
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, HumanMessage):
            last_message = msg.content
            break

    # Load full menu from DB once — passed to detect_slot_modification so the LLM
    # can map any item name to its correct slot without post-processing overrides.
    from database.db_manager import load_menu_by_category
    menu_context = await load_menu_by_category()

    # ── Pre-pass: 'replace X with Y' resolved by matching X against filled slot values ──
    rbv_slot, rbv_old, rbv_new = _resolve_replace_by_value(last_message, state["slots"])

    # Detect which slot to modify — LLM has full menu context so no overrides needed
    detection_result = await detect_slot_modification.ainvoke({
        "message": last_message,
        "current_slots": state["slots"],
        "recent_messages": list(state.get("messages", [])),
        "menu_context": menu_context,
    })

    # replace-by-value regex is deterministic — prefer it when it matches
    if rbv_slot:
        detection_result = {
            "detected": True,
            "target_slot": rbv_slot,
            "new_value": rbv_new,
            "clarification_needed": False,
        }

    # confirm holds just the acknowledgment text — fresh follow-up question appended at end
    confirm = ""
    # final_response is set for paths that return early or need custom responses
    final_response = None

    if detection_result.get("clarification_needed"):
        # Ambiguous — ask user to clarify (no follow-up question needed, just re-ask)
        possible_slots = detection_result.get("possible_slots", [])
        if possible_slots:
            labels = [_get_slot_label(s) for s in possible_slots]
            if len(labels) == 1:
                final_response = f"I want to make sure I update the right information. Did you want to change {labels[0]}?"
            elif len(labels) == 2:
                final_response = f"I want to make sure I update the right information. Did you want to change {labels[0]} or {labels[1]}?"
            else:
                options_str = ", ".join(labels[:-1]) + f", or {labels[-1]}"
                final_response = f"I want to make sure I update the right information. Did you want to change {options_str}?"
        else:
            final_response = ("I'm not sure which information you'd like to change. Could you be more specific? "
                              "For example: 'change guest count to 200' or 'update the date to May 1st'.")

    elif detection_result.get("detected"):
        target_slot = detection_result.get("target_slot")
        new_value = detection_result.get("new_value")

        # ── Text note slots: special_requests, dietary_concerns, additional_notes ──
        # Support add/append/remove/replace on these free-text fields
        if target_slot in ("special_requests", "dietary_concerns", "additional_notes"):
            slot_label = _get_slot_label(target_slot)
            existing = state["slots"].get(target_slot, {}).get("value") or ""
            now = datetime.now().isoformat()

            # Remove path: user said "remove X" / "delete X"
            is_remove, remove_text = _looks_like_remove(last_message)
            if is_remove and existing and existing.lower() not in ("none", "no", ""):
                # Strip matching fragments from the stored value. Items are stored
                # separated by '; ' so split, filter, rejoin.
                parts = [p.strip() for p in re.split(r';|,', existing) if p.strip()]
                remove_lower = remove_text.lower()
                kept = [p for p in parts if remove_lower not in p.lower() and p.lower() not in remove_lower]
                removed = len(parts) - len(kept)
                if removed > 0:
                    merged = "; ".join(kept) if kept else ""
                    history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                    history.append({"old_value": existing, "new_value": merged, "timestamp": now})
                    state["slots"][target_slot] = {
                        "value": merged if merged else "no",
                        "filled": True,
                        "modified_at": now,
                        "modification_history": history,
                    }
                    if merged:
                        confirm = f"Removed. Your {slot_label}: '{merged}'."
                    else:
                        confirm = f"Removed — your {slot_label} is now cleared."
                else:
                    confirm = (
                        f"Hmm, don't see '{remove_text}' in your current {slot_label}: "
                        f"'{existing}'. Nothing changed."
                    )
            else:
                append_intent = await llm_extract(
                    f"The customer is updating their '{slot_label}'. "
                    "Are they ADDING something new (append to existing), or REPLACING everything?\n\n"
                    "Return ONLY: add or replace",
                    last_message
                )
                if append_intent.strip().lower() == "add" and existing and existing.lower() not in ("none", "no", ""):
                    merged = f"{existing}; {new_value}"
                else:
                    merged = str(new_value)

                history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                history.append({"old_value": existing, "new_value": merged, "timestamp": now})
                state["slots"][target_slot] = {
                    "value": merged, "filled": True, "modified_at": now, "modification_history": history,
                }
                confirm = f"Done! I've noted that for your {slot_label}: '{merged}'."

        # ── Rentals / utensils — simple string slots, not menu items ──
        elif target_slot in ("rentals", "utensils"):
            slot_label = _get_slot_label(target_slot)
            old_value = state["slots"].get(target_slot, {}).get("value")
            now = datetime.now().isoformat()
            history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
            history.append({"old_value": old_value, "new_value": new_value, "timestamp": now})
            state["slots"][target_slot] = {
                "value": new_value, "filled": True, "modified_at": now, "modification_history": history,
            }
            confirm = f"Done! I've updated your {slot_label} to '{new_value}'."

        # ── Appetizers / Main Dishes: comprehensive 5-way intent handler ──
        elif target_slot in ("appetizers", "selected_dishes"):
            from agent.nodes.menu import (
                _resolve_to_db_items, _parse_slot_items,
                _is_appetizer_category, _is_non_dish_category,
                get_appetizer_items, get_main_dish_items,
            )
            from agent.nodes.helpers import llm_respond, build_numbered_list
            from prompts.system_prompts import SYSTEM_PROMPT
            from database.db_manager import load_menu_by_category
            slot_label = _get_slot_label(target_slot)

            # ── 1. Detect clear-all intent ──
            skip_check = await llm_extract(
                f"The customer is modifying their '{slot_label}'. "
                "Decide: are they expressing a BLANKET intent to wipe/skip the entire category with no specific items named = clear, "
                "or do they name one or more SPECIFIC ITEMS to add, remove, or swap = change?\n"
                "Rule: if ANY specific item name appears in the message, always return 'change'.\n"
                "Return ONLY: clear or change",
                last_message
            )
            if skip_check.strip().lower() == "clear":
                now = datetime.now().isoformat()
                old_val = state["slots"].get(target_slot, {}).get("value")
                state["slots"][target_slot] = {
                    "value": "no", "filled": True, "modified_at": now,
                    "modification_history": [{"old_value": old_val, "new_value": "no", "timestamp": now}],
                }
                confirm = f"Done! Cleared your {slot_label}."
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state

            current_value = state["slots"].get(target_slot, {}).get("value") or ""
            current_items = _parse_slot_items(current_value)
            slot_is_declined = current_value.lower() in ("no", "none", "") or not current_value

            # Build category-filtered menu for accurate resolution (reuse already-loaded menu_context)
            menu = menu_context
            if target_slot == "appetizers":
                filtered_menu = {k: v for k, v in menu.items() if _is_appetizer_category(k)}
                reentry_node = "select_appetizers"
            else:
                filtered_menu = {
                    k: v for k, v in menu.items()
                    if not _is_non_dish_category(k) and not _is_appetizer_category(k)
                }
                reentry_node = "select_dishes"

            # ── 1b. Replace-by-value swap(s): handles "replace A with B and C with D" (N pairs) ──
            if rbv_old and rbv_slot == target_slot:
                swap_pairs = await _extract_all_swap_pairs(last_message)
                if not swap_pairs:
                    swap_pairs = [(_PRICE_RE.sub("", rbv_old).strip(), rbv_new.strip())]

                working_items = list(current_items)
                swap_lines = []

                for pair_old, pair_new in swap_pairs:
                    pair_old_norm = pair_old.lower()
                    # Remove old item (fuzzy match on normalized name)
                    after_remove = [
                        n for n in working_items
                        if pair_old_norm not in n.lower() and n.lower() not in pair_old_norm
                    ]
                    # Resolve new item against this slot's menu, then cross-slot
                    matched_new, _ = await _resolve_to_db_items(pair_new, filtered_menu)
                    if not matched_new:
                        _, matched_new, _ = await _find_item_in_any_menu(pair_new, menu_context)
                    if matched_new:
                        existing_lower = {n.lower() for n in after_remove}
                        added = [i["name"] for i in matched_new if i["name"].lower() not in existing_lower]
                        working_items = after_remove + added
                        swap_lines.append(f"**{pair_old}** → **{', '.join(added)}**" if added else f"**{pair_old}** removed")
                    else:
                        # New item not on menu — remove old anyway, note the miss
                        working_items = after_remove
                        swap_lines.append(f"**{pair_old}** removed (**{pair_new}** not on menu — added to special requests)")
                        sr_existing = state["slots"].get("special_requests", {}).get("value") or ""
                        sr_merged = f"{sr_existing}; {pair_new}" if sr_existing and sr_existing.lower() not in ("none", "no", "") else pair_new
                        now_sr = datetime.now().isoformat()
                        history_sr = list(state["slots"].get("special_requests", {}).get("modification_history") or [])
                        history_sr.append({"old_value": sr_existing, "new_value": sr_merged, "timestamp": now_sr})
                        state["slots"]["special_requests"] = {
                            "value": sr_merged, "filled": True, "modified_at": now_sr, "modification_history": history_sr,
                        }

                if swap_lines:
                    _, resolved = await _resolve_to_db_items(", ".join(working_items), filtered_menu) if working_items else ([], "")
                    now = datetime.now().isoformat()
                    history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                    history.append({"old_value": current_value, "new_value": resolved, "timestamp": now})
                    state["slots"][target_slot] = {
                        "value": resolved, "filled": bool(resolved), "modified_at": now, "modification_history": history,
                    }
                    confirm = "Swapped: " + " | ".join(swap_lines) + f". Your current {slot_label}: **{resolved or 'none'}**"
                    restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                    state["current_node"] = restored_node
                    fresh_q = await _generate_fresh_question(restored_node, state)
                    state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                    return state
                # All new items not found — fall through to 5-way classifier

            # ── 2. Classify intent (5-way) ──
            # Build recent conversation context so the classifier can tell
            # "Add X" after a menu browse apart from a cold replace request
            from tools.modification_detection import _format_recent_messages
            _recent_ctx = _format_recent_messages(state.get("messages", []))
            intent = await llm_extract(
                f"Customer is modifying their '{slot_label}' "
                f"(current selection: '{current_value or 'none'}').\n\n"
                f"Recent conversation context:\n{_recent_ctx}\n\n"
                f"Latest message: {last_message}\n\n"
                "Classify their intent as exactly one of:\n"
                "- 'add_specific': naming SPECIFIC items to ADD only\n"
                "- 'remove': naming items to REMOVE only\n"
                "- 'mixed': BOTH removing specific items AND adding specific items in the same message\n"
                "- 'replace': wants to REPLACE / START OVER entire selection "
                "(e.g. 'change everything', 'start fresh', 'redo the menu')\n"
                "- 'browse': wants to SEE / BROWSE the menu — no specific item named "
                "(e.g. 'show me options', 'add some food', 'change my appetizers')\n"
                "- 'unclear': genuinely ambiguous, can't determine\n"
                "IMPORTANT: if the agent just showed a menu list and the user is now naming items, "
                "that is 'add_specific' not 'replace'.\n"
                "Return ONLY: add_specific, remove, mixed, replace, browse, or unclear",
                last_message
            )
            intent = intent.strip().lower()
            if intent not in ("add_specific", "remove", "mixed", "replace", "browse", "unclear"):
                intent = "unclear"

            # ── 3a. Browse / Unclear → show menu, preserve existing selection ──
            if intent in ("browse", "unclear"):
                current_note = f"Your current {slot_label}: **{current_value}**\n\n" if not slot_is_declined else ""
                if target_slot == "appetizers":
                    items = await get_appetizer_items()
                    item_list = build_numbered_list(items, show_price=True)
                    intro = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\nCustomer wants to browse appetizers. "
                        "Write a casual 1-line intro. Do NOT list any items.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{current_note}{item_list}\n\nPick as many as you'd like!"
                else:
                    _, categorized = await get_main_dish_items()
                    item_list = build_numbered_list([], categories=categorized, category_headers=True)
                    intro = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\nCustomer wants to browse main dishes. "
                        "Write a casual 1-line intro. Do NOT list any items.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{current_note}{item_list}\n\nPick 3 to 5 dishes!"
                state["current_node"] = reentry_node
                state["messages"] = add_ai_message(state, response)
                return state

            # ── 3b. Replace → clear slot and show fresh menu ──
            if intent == "replace":
                now = datetime.now().isoformat()
                history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                history.append({"old_value": current_value, "new_value": None, "timestamp": now})
                state["slots"][target_slot] = {
                    "value": None, "filled": False, "modified_at": now, "modification_history": history,
                }
                if target_slot == "appetizers":
                    items = await get_appetizer_items()
                    item_list = build_numbered_list(items, show_price=True)
                    intro = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\nCustomer is starting fresh with appetizers — cleared old selection. "
                        "Write a casual 1-line intro for the appetizer menu. Do NOT list any items.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{item_list}\n\nPick as many as you'd like!"
                else:
                    _, categorized = await get_main_dish_items()
                    item_list = build_numbered_list([], categories=categorized, category_headers=True)
                    intro = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\nCustomer is starting fresh with main dishes — cleared old selection. "
                        "Write a casual 1-line intro for the main dish menu. Do NOT list any items.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{item_list}\n\nPick 3 to 5 dishes!"
                state["current_node"] = reentry_node
                state["messages"] = add_ai_message(state, response)
                return state

            # ── 3c-mixed. Mixed remove+add in one message ──
            if intent == "mixed":
                ops = await _extract_mixed_ops(last_message)
                working = list(current_items)

                removed_names, added_names = [], []

                # Removes first
                for item_name in ops.get("remove", []):
                    item_lower = item_name.lower()
                    before = list(working)
                    working = [
                        n for n in working
                        if item_lower not in n.lower() and n.lower() not in item_lower
                    ]
                    if len(working) < len(before):
                        removed_names.append(item_name)

                # Then adds
                for item_name in ops.get("add", []):
                    matched, _ = await _resolve_to_db_items(item_name, filtered_menu)
                    if not matched:
                        _, matched, _ = await _find_item_in_any_menu(item_name, menu_context)
                    if matched:
                        existing_lower = {n.lower() for n in working}
                        for m in matched:
                            if m["name"].lower() not in existing_lower:
                                working.append(m["name"])
                                added_names.append(m["name"])
                    else:
                        sr_existing = state["slots"].get("special_requests", {}).get("value") or ""
                        sr_merged = f"{sr_existing}; {item_name}" if sr_existing and sr_existing.lower() not in ("none", "no", "") else item_name
                        now_sr = datetime.now().isoformat()
                        history_sr = list(state["slots"].get("special_requests", {}).get("modification_history") or [])
                        history_sr.append({"old_value": sr_existing, "new_value": sr_merged, "timestamp": now_sr})
                        state["slots"]["special_requests"] = {
                            "value": sr_merged, "filled": True, "modified_at": now_sr, "modification_history": history_sr,
                        }
                        added_names.append(f"{item_name} (added to special requests)")

                _, resolved = await _resolve_to_db_items(", ".join(working), filtered_menu) if working else ([], "")
                now = datetime.now().isoformat()
                history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                history.append({"old_value": current_value, "new_value": resolved, "timestamp": now})
                state["slots"][target_slot] = {
                    "value": resolved, "filled": bool(resolved), "modified_at": now, "modification_history": history,
                }
                parts = []
                if removed_names:
                    parts.append(f"Removed **{', '.join(removed_names)}**")
                if added_names:
                    parts.append(f"added **{', '.join(added_names)}**")
                summary = " | ".join(parts) if parts else "No changes made"
                confirm = f"{summary}. Your {slot_label}: **{resolved or 'none'}**"
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state

            # ── 3c. Remove → keyword match against current items ──
            if intent == "remove":
                items_text = str(new_value).strip()
                matched_remove, _ = await _resolve_to_db_items(items_text, filtered_menu)
                remove_names = {i["name"].lower() for i in matched_remove}
                remove_kws = [p.strip().lower() for p in items_text.split(",") if p.strip()]
                updated = [
                    n for n in current_items
                    if n.lower() not in remove_names
                    and not any(kw and kw in n.lower() for kw in remove_kws)
                ]
                removed_count = len(current_items) - len(updated)
                now = datetime.now().isoformat()

                if removed_count > 0 and updated:
                    _, resolved = await _resolve_to_db_items(", ".join(updated), filtered_menu)
                    history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                    history.append({"old_value": current_value, "new_value": resolved, "timestamp": now})
                    state["slots"][target_slot] = {
                        "value": resolved, "filled": True, "modified_at": now, "modification_history": history,
                    }
                    confirm = f"Removed **{items_text}**. Your current {slot_label}: **{resolved}**"
                elif removed_count > 0 and not updated:
                    history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                    history.append({"old_value": current_value, "new_value": None, "timestamp": now})
                    state["slots"][target_slot] = {
                        "value": None, "filled": False, "modified_at": now, "modification_history": history,
                    }
                    confirm = f"Removed **{items_text}** — your {slot_label} is now empty."
                else:
                    confirm = (
                        f"**{items_text}** wasn't in your {slot_label} — nothing changed. "
                        f"Your current {slot_label}: **{current_value or 'none'}**"
                    )
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state

            # ── 3d. Add specific items → resolve against filtered menu ──
            # intent == "add_specific"
            items_text = str(new_value).strip()
            matched_add, _ = await _resolve_to_db_items(items_text, filtered_menu)

            if matched_add:
                # Found in DB — append (deduplicated)
                existing_lower = {n.lower() for n in current_items}
                new_names = [i["name"] for i in matched_add if i["name"].lower() not in existing_lower]
                already_have = [i["name"] for i in matched_add if i["name"].lower() in existing_lower]
                merged = current_items + new_names
                _, resolved = await _resolve_to_db_items(", ".join(merged), filtered_menu) if merged else ([], current_value)
                now = datetime.now().isoformat()
                history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                history.append({"old_value": current_value, "new_value": resolved, "timestamp": now})
                state["slots"][target_slot] = {
                    "value": resolved, "filled": True, "modified_at": now, "modification_history": history,
                }
                parts = []
                if new_names:
                    parts.append(f"Added **{', '.join(new_names)}**")
                if already_have:
                    parts.append(f"you already had **{', '.join(already_have)}**")
                confirm = f"{' — '.join(parts)}. Your {slot_label}: **{resolved}**"
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state
            else:
                # Item not found in identified slot — search all other buckets
                # (covers appetizers, selected_dishes, desserts, and drinks)
                found_slot, cross_matched, cross_menu = await _find_item_in_any_menu(
                    items_text, menu_context, exclude_slot=target_slot
                )
                if cross_matched:
                    # Silently correct the slot and apply the add
                    target_slot = found_slot
                    slot_label = _get_slot_label(target_slot)
                    filtered_menu = cross_menu
                    reentry_node = _MENU_BUCKET_DEFS[target_slot]["reentry"]
                    current_value = state["slots"].get(target_slot, {}).get("value") or ""
                    current_items = _parse_slot_items(current_value)
                    existing_lower = {n.lower() for n in current_items}
                    new_names = [i["name"] for i in cross_matched if i["name"].lower() not in existing_lower]
                    already_have = [i["name"] for i in cross_matched if i["name"].lower() in existing_lower]
                    merged = current_items + new_names
                    if target_slot == "desserts":
                        resolved = ", ".join(merged) if merged else current_value
                    else:
                        _, resolved = await _resolve_to_db_items(", ".join(merged), filtered_menu) if merged else ([], current_value)
                    now = datetime.now().isoformat()
                    history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                    history.append({"old_value": current_value, "new_value": resolved, "timestamp": now})
                    state["slots"][target_slot] = {
                        "value": resolved, "filled": True, "modified_at": now, "modification_history": history,
                    }
                    parts = []
                    if new_names:
                        parts.append(f"Added **{', '.join(new_names)}**")
                    if already_have:
                        parts.append(f"you already had **{', '.join(already_have)}**")
                    confirm = f"{' — '.join(parts)}. Your {slot_label}: **{resolved}**"
                    restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                    state["current_node"] = restored_node
                    fresh_q = await _generate_fresh_question(restored_node, state)
                    state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                    return state

                # Not on menu — add to special_requests and confirm
                sr_existing = state["slots"].get("special_requests", {}).get("value") or ""
                now = datetime.now().isoformat()
                sr_merged = f"{sr_existing}; {items_text}" if sr_existing and sr_existing.lower() not in ("none", "no", "") else items_text
                history_sr = list(state["slots"].get("special_requests", {}).get("modification_history") or [])
                history_sr.append({"old_value": sr_existing, "new_value": sr_merged, "timestamp": now})
                state["slots"]["special_requests"] = {
                    "value": sr_merged, "filled": True, "modified_at": now, "modification_history": history_sr,
                }
                confirm = (
                    f"**{items_text}** isn't on our standard menu, so I've added it to your special requests. "
                    f"If you meant a specific menu item, just let me know!"
                )
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state

        # ── Desserts + Drinks: reentry / item-merge logic ──
        elif target_slot in ("desserts", "drinks"):
            from agent.nodes.menu import _resolve_to_db_items, _parse_slot_items
            slot_label = _get_slot_label(target_slot)

            # Detect clear-all intent
            skip_check = await llm_extract(
                f"The customer is modifying their '{slot_label}'. "
                "Decide: are they expressing a BLANKET intent to wipe/skip the entire category with no specific items named = clear, "
                "or do they name one or more SPECIFIC ITEMS to add, remove, or swap = change?\n"
                "Rule: if ANY specific item name appears in the message, always return 'change'.\n"
                "Return ONLY: clear or change",
                last_message
            )
            if skip_check.strip().lower() == "clear":
                now = datetime.now().isoformat()
                old_val = state["slots"].get(target_slot, {}).get("value")
                state["slots"][target_slot] = {
                    "value": "no", "filled": True, "modified_at": now,
                    "modification_history": [{"old_value": old_val, "new_value": "no", "timestamp": now}],
                }
                confirm = f"Done! Cleared your {slot_label}."
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state

            current_value = state["slots"].get(target_slot, {}).get("value") or ""
            current_items = _parse_slot_items(current_value)
            slot_is_declined = current_value.lower() in ("no", "none", "") or not current_value

            # ── Replace-by-value swap for desserts/drinks ──
            if rbv_old and rbv_slot == target_slot:
                now = datetime.now().isoformat()
                old_norm = _PRICE_RE.sub("", rbv_old).strip().lower()
                updated = [n for n in current_items if old_norm not in n.lower() and n.lower() not in old_norm]

                if target_slot == "desserts":
                    from agent.nodes.menu import get_dessert_items
                    event_type = (state["slots"].get("event_type", {}).get("value") or "").lower()
                    dessert_expanded = await get_dessert_items(is_wedding="wedding" in event_type)
                    dessert_lookup = {item["name"].lower(): item for item in dessert_expanded}
                    new_norm = rbv_new.strip().lower()
                    matched_new_item = next(
                        (item for key, item in dessert_lookup.items()
                         if new_norm == key or new_norm in key or key in new_norm or _name_similar(new_norm, key)),
                        None
                    )
                    if matched_new_item:
                        if matched_new_item["name"].lower() not in {n.lower() for n in updated}:
                            updated.append(matched_new_item["name"])
                        resolved_rbv = ", ".join(updated)
                        history = list(state["slots"].get("desserts", {}).get("modification_history") or [])
                        history.append({"old_value": current_value, "new_value": resolved_rbv, "timestamp": now})
                        state["slots"]["desserts"] = {
                            "value": resolved_rbv, "filled": True, "modified_at": now, "modification_history": history,
                        }
                        old_display = _PRICE_RE.sub("", rbv_old).strip()
                        confirm = f"Swapped **{old_display}** → **{matched_new_item['name']}**. Your current {slot_label}: **{resolved_rbv}**"
                        restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                        state["current_node"] = restored_node
                        fresh_q = await _generate_fresh_question(restored_node, state)
                        state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                        return state
                    # New dessert not found — fall through to reentry (shows menu)

                else:  # drinks
                    matched_add, _ = await _resolve_to_db_items(rbv_new.strip())
                    if matched_add:
                        existing_lower = {n.lower() for n in updated}
                        new_names = [i["name"] for i in matched_add if i["name"].lower() not in existing_lower]
                        merged = updated + new_names
                        _, resolved_rbv = await _resolve_to_db_items(", ".join(merged)) if merged else ([], current_value)
                        history = list(state["slots"].get("drinks", {}).get("modification_history") or [])
                        history.append({"old_value": current_value, "new_value": resolved_rbv, "timestamp": now})
                        state["slots"]["drinks"] = {
                            "value": resolved_rbv, "filled": True, "modified_at": now, "modification_history": history,
                        }
                        old_display = _PRICE_RE.sub("", rbv_old).strip()
                        confirm = f"Swapped **{old_display}** → **{', '.join(new_names)}**. Your current {slot_label}: **{resolved_rbv}**"
                        restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                        state["current_node"] = restored_node
                        fresh_q = await _generate_fresh_question(restored_node, state)
                        state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                        return state
                    # New drink not found — fall through to reentry

            _DESSERT_DRINK_REENTRY = {"desserts": "select_desserts", "drinks": "collect_drinks"}

            # ── Mixed remove+add for drinks (desserts show menu for adds anyway) ──
            mixed_check = await llm_extract(
                "Does this message BOTH remove specific items AND add specific items?\n"
                "Return ONLY: yes or no",
                last_message
            )
            if mixed_check.strip().lower() == "yes" and target_slot == "drinks":
                ops = await _extract_mixed_ops(last_message)
                working = list(current_items)
                removed_names, added_names = [], []

                for item_name in ops.get("remove", []):
                    item_lower = item_name.lower()
                    before = list(working)
                    working = [n for n in working if item_lower not in n.lower() and n.lower() not in item_lower]
                    if len(working) < len(before):
                        removed_names.append(item_name)

                for item_name in ops.get("add", []):
                    matched, _ = await _resolve_to_db_items(item_name)
                    if matched:
                        existing_lower = {n.lower() for n in working}
                        for m in matched:
                            if m["name"].lower() not in existing_lower:
                                working.append(m["name"])
                                added_names.append(m["name"])

                _, resolved = await _resolve_to_db_items(", ".join(working)) if working else ([], "")
                now = datetime.now().isoformat()
                history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                history.append({"old_value": current_value, "new_value": resolved, "timestamp": now})
                state["slots"][target_slot] = {
                    "value": resolved, "filled": bool(resolved), "modified_at": now, "modification_history": history,
                }
                parts = []
                if removed_names:
                    parts.append(f"Removed **{', '.join(removed_names)}**")
                if added_names:
                    parts.append(f"added **{', '.join(added_names)}**")
                summary = " | ".join(parts) if parts else "No changes made"
                confirm = f"{summary}. Your {slot_label}: **{resolved or 'none'}**"
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state

            if mixed_check.strip().lower() == "yes" and target_slot == "desserts":
                ops = await _extract_mixed_ops(last_message)
                from agent.nodes.menu import get_dessert_items
                from agent.nodes.helpers import build_numbered_list
                event_type = (state["slots"].get("event_type", {}).get("value") or "").lower()
                dessert_expanded = await get_dessert_items(is_wedding="wedding" in event_type)
                dessert_lookup = {item["name"].lower(): item for item in dessert_expanded}

                working = list(current_items)
                removed_names, added_names, not_found = [], [], []

                for item_name in ops.get("remove", []):
                    item_lower = item_name.lower()
                    before = list(working)
                    working = [n for n in working if item_lower not in n.lower() and n.lower() not in item_lower]
                    if len(working) < len(before):
                        removed_names.append(item_name)

                for item_name in ops.get("add", []):
                    item_norm = _PRICE_RE.sub("", item_name).strip().lower()
                    matched_item = next(
                        (item for key, item in dessert_lookup.items()
                         if item_norm == key or item_norm in key or key in item_norm or _name_similar(item_norm, key)),
                        None
                    )
                    if matched_item:
                        if matched_item["name"].lower() not in {n.lower() for n in working}:
                            working.append(matched_item["name"])
                            added_names.append(matched_item["name"])
                    else:
                        not_found.append(item_name)

                resolved_desserts = ", ".join(working)
                now = datetime.now().isoformat()
                history = list(state["slots"].get("desserts", {}).get("modification_history") or [])
                history.append({"old_value": current_value, "new_value": resolved_desserts, "timestamp": now})
                state["slots"]["desserts"] = {
                    "value": resolved_desserts, "filled": bool(resolved_desserts), "modified_at": now, "modification_history": history,
                }

                parts = []
                if removed_names:
                    parts.append(f"Removed **{', '.join(removed_names)}**")
                if added_names:
                    parts.append(f"added **{', '.join(added_names)}**")
                summary = " | ".join(parts) if parts else "No changes made"
                confirm = f"{summary}. Your desserts: **{resolved_desserts or 'none'}**"

                if not_found:
                    item_list = build_numbered_list(dessert_expanded, show_price=True)
                    confirm += f"\n\n**{', '.join(not_found)}** wasn't found on the dessert menu. Here's the full list:\n\n{item_list}"

                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q and not not_found else confirm)
                return state

            reentry_intent = await llm_extract(
                f"Customer is modifying '{target_slot}' (current: '{current_value}').\n"
                "Are they asking to SEE THE MENU / RE-OPEN this category, "
                "or naming SPECIFIC ITEMS to add/remove?\n"
                "Return ONLY: reopen or specific",
                last_message
            )
            is_reentry = reentry_intent.strip().lower() == "reopen"

            # Desserts always show menu for add/change — mini items aren't standalone DB items
            if target_slot == "desserts" and not is_reentry:
                dessert_op = await llm_extract(
                    "Is the customer asking to REMOVE specific items from their desserts, "
                    "or ADD / CHANGE / MODIFY / SEE the dessert menu?\n"
                    f"Message: {last_message}\nReturn ONLY: remove or add",
                    last_message
                )
                if dessert_op.strip().lower() != "remove":
                    is_reentry = True

            if is_reentry:
                if slot_is_declined:
                    state["slots"][target_slot] = {
                        "value": None, "filled": False, "modified_at": None, "modification_history": [],
                    }
                reentry_node = _DESSERT_DRINK_REENTRY.get(target_slot, "collect_drinks")
                state["current_node"] = reentry_node
                # Remember where to resume once this one slot is filled — so we don't
                # re-run the whole mini-flow (ask_more_desserts etc.) after a mid-conv edit.
                # Persisted inside slots so it survives DB round-trips.
                _resume_target = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["slots"]["__resume_after_mod__"] = {
                    "value": _resume_target,
                    "filled": True,
                    "modified_at": None,
                    "modification_history": [],
                }
                from agent.nodes.helpers import llm_respond, build_numbered_list
                from prompts.system_prompts import SYSTEM_PROMPT

                if target_slot == "desserts":
                    from agent.nodes.menu import get_dessert_items
                    event_type = (state["slots"].get("event_type", {}).get("value") or "").lower()
                    dessert_items = await get_dessert_items(is_wedding="wedding" in event_type)
                    item_list = build_numbered_list(dessert_items, show_price=True)
                    current_note = f"Your current desserts: **{current_value}**\n\n" if not slot_is_declined else ""
                    intro = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\nCustomer wants to {'add' if slot_is_declined else 'change'} desserts. "
                        "Write a brief casual intro. Do NOT list any items.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{current_note}{item_list}\n\nPick up to 4 items total!"
                else:
                    from prompts.system_prompts import NODE_PROMPTS
                    response = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_drinks']}\n\n"
                        "Customer wants to discuss drinks/coffee/bar. Re-ask about coffee or bar setup.",
                        f"Slots: {_slots_context(state)}"
                    )
                state["messages"] = add_ai_message(state, response)
                return state

            # Not reentry (dessert remove, or drinks specific): item-merge path
            items_text = str(new_value).strip()
            action_intent = await llm_extract(
                "Is the customer REMOVING or ADDING items?\n"
                f"Message: {last_message}\nReturn ONLY: remove or add",
                last_message
            )
            remove_intent = action_intent.strip().lower() == "remove"

            if remove_intent:
                matched, _ = await _resolve_to_db_items(items_text)
                remove_names = {i["name"].lower() for i in matched}
                remove_kws = [p.strip().lower() for p in items_text.split(",") if p.strip()]
                updated = [
                    n for n in current_items
                    if n.lower() not in remove_names
                    and not any(kw and kw in n.lower() for kw in remove_kws)
                ]
                _, resolved = await _resolve_to_db_items(", ".join(updated)) if updated else ([], current_value)
                action_word = "removed from"
            else:
                matched, _ = await _resolve_to_db_items(items_text)
                existing_lower = {n.lower() for n in current_items}
                new_names = [i["name"] for i in matched if i["name"].lower() not in existing_lower]
                merged = current_items + new_names
                _, resolved = await _resolve_to_db_items(", ".join(merged)) if merged else ([], current_value)
                action_word = "added to"

            if resolved and resolved != current_value:
                old_val = current_value
                now = datetime.now().isoformat()
                history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                history.append({"old_value": old_val, "new_value": resolved, "timestamp": now})
                state["slots"][target_slot] = {
                    "value": resolved, "filled": True, "modified_at": now, "modification_history": history,
                }
                if remove_intent:
                    confirm = f"Removed **{items_text}**. Your current {slot_label}: **{resolved}**"
                else:
                    confirm = f"Added **{items_text}**. Your current {slot_label}: **{resolved}**"
            elif not remove_intent:
                # Item not found in this slot — search all other buckets before giving up
                found_slot, cross_matched, cross_menu = await _find_item_in_any_menu(
                    items_text, menu_context, exclude_slot=target_slot
                )
                if cross_matched:
                    x_slot_label = _get_slot_label(found_slot)
                    x_current_value = state["slots"].get(found_slot, {}).get("value") or ""
                    x_current_items = _parse_slot_items(x_current_value)
                    existing_lower = {n.lower() for n in x_current_items}
                    new_names = [i["name"] for i in cross_matched if i["name"].lower() not in existing_lower]
                    already_have = [i["name"] for i in cross_matched if i["name"].lower() in existing_lower]
                    merged = x_current_items + new_names
                    if found_slot == "desserts":
                        x_resolved = ", ".join(merged) if merged else x_current_value
                    else:
                        _, x_resolved = await _resolve_to_db_items(", ".join(merged), cross_menu) if merged else ([], x_current_value)
                    now = datetime.now().isoformat()
                    history = list(state["slots"].get(found_slot, {}).get("modification_history") or [])
                    history.append({"old_value": x_current_value, "new_value": x_resolved, "timestamp": now})
                    state["slots"][found_slot] = {
                        "value": x_resolved, "filled": True, "modified_at": now, "modification_history": history,
                    }
                    parts = []
                    if new_names:
                        parts.append(f"Added **{', '.join(new_names)}**")
                    if already_have:
                        parts.append(f"you already had **{', '.join(already_have)}**")
                    confirm = f"{' — '.join(parts)}. Your {x_slot_label}: **{x_resolved}**"
                else:
                    # Not on menu — add to special_requests
                    sr_existing = state["slots"].get("special_requests", {}).get("value") or ""
                    now_sr = datetime.now().isoformat()
                    sr_merged = f"{sr_existing}; {items_text}" if sr_existing and sr_existing.lower() not in ("none", "no", "") else items_text
                    history_sr = list(state["slots"].get("special_requests", {}).get("modification_history") or [])
                    history_sr.append({"old_value": sr_existing, "new_value": sr_merged, "timestamp": now_sr})
                    state["slots"]["special_requests"] = {
                        "value": sr_merged, "filled": True, "modified_at": now_sr, "modification_history": history_sr,
                    }
                    confirm = (
                        f"**{items_text}** isn't on our standard menu, so I've noted it in your special requests. "
                        f"If you meant a specific item, just let me know!"
                    )
            else:
                confirm = f"Couldn't find **{items_text}** in your current {slot_label} selection — nothing changed."

        else:
            # ── Scalar slots: use standard date-resolve + validate path ──
            resolved_value = str(new_value)
            print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] target_slot={target_slot}, raw new_value={new_value}")
            if target_slot == "event_date" and _contains_relative_date(resolved_value):
                print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] Resolving relative date: {resolved_value}")
                resolved_value = _resolve_relative_date(resolved_value)
                print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] Resolved to: {resolved_value}")

            validation_result = await validate_slot.ainvoke({
                "slot_name": target_slot,
                "value": resolved_value
            })

            if validation_result.get("valid"):
                old_value = state["slots"][target_slot].get("value")
                normalized_value = validation_result.get("normalized_value")

                if state["slots"][target_slot].get("modification_history") is None:
                    state["slots"][target_slot]["modification_history"] = []

                state["slots"][target_slot]["modification_history"].append({
                    "old_value": old_value,
                    "new_value": normalized_value,
                    "timestamp": datetime.now().isoformat()
                })

                state["slots"][target_slot]["value"] = normalized_value
                state["slots"][target_slot]["filled"] = True
                state["slots"][target_slot]["modified_at"] = datetime.now().isoformat()

                # Clear stale context slots when event_type changes
                if target_slot == "event_type":
                    _CONTEXT_SLOTS = ["partner_name", "company_name", "honoree_name"]
                    for stale in _CONTEXT_SLOTS:
                        if stale in state["slots"] and state["slots"][stale].get("filled"):
                            state["slots"][stale] = {
                                "value": None, "filled": False,
                                "modified_at": None, "modification_history": [],
                            }

                slot_label = _get_slot_label(target_slot)

                if old_value:
                    confirm = f"I've updated your {slot_label} from '{old_value}' to '{normalized_value}'."
                else:
                    confirm = f"I've set your {slot_label} to '{normalized_value}'."
            else:
                error_message = validation_result.get("error_message", "Invalid value")
                final_response = f"I couldn't update that: {error_message}"
    else:
        final_response = ("I'm not sure which information you'd like to change. Could you be more specific? "
                          "For example: 'change guest count to 200' or 'update the date to May 1st'.")

    # CRITICAL: Stay on the same node — never jump ahead
    # EXCEPT: reroute conditional nodes when their condition no longer holds
    restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])

    # If event_type just changed and the new event type needs a context slot
    # (partner_name / honoree_name / company_name) that isn't filled, route to
    # that collection node — regardless of where the user was in the flow.
    # Prevents the "event_type changed but context never collected" gap.
    if detection_result.get("detected") and detection_result.get("target_slot") == "event_type":
        new_event_value = state["slots"].get("event_type", {}).get("value")
        ctx_node = _event_type_context_node(new_event_value)
        if ctx_node:
            ctx_slot_map = {
                "collect_fiance_name": "partner_name",
                "collect_birthday_person": "honoree_name",
                "collect_company_name": "company_name",
            }
            ctx_slot = ctx_slot_map.get(ctx_node)
            if ctx_slot and not state["slots"].get(ctx_slot, {}).get("filled"):
                restored_node = ctx_node

    state["current_node"] = restored_node
    print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] Exiting. current_node: {restored_node} (previous: {previous_node})")

    # Build the final message and add to state
    if final_response:
        # Error / clarification / not-detected paths — no follow-up question needed
        state["messages"] = add_ai_message(state, final_response)
    elif confirm:
        # Successful modification — append a fresh context-aware follow-up question
        fresh_q = await _generate_fresh_question(restored_node, state)
        state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
    return state

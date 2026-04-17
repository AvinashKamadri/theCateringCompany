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
_MOD_VERSION = "v7"  # Bump to verify this code is running


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}


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

    # Detect which slot to modify
    detection_result = await detect_slot_modification.ainvoke({
        "message": last_message,
        "current_slots": state["slots"]
    })

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

        # ── Force desserts slot if message mentions a known dessert sub-item ──
        # Mini dessert options live in description fields, not as standalone DB items,
        # so detect_slot_modification guesses the wrong slot. Resolve from DB instead.
        from database.db_manager import load_menu_by_category
        menu = await load_menu_by_category()
        dessert_sub_items = set()
        for cat_name, items in menu.items():
            if "dessert" in cat_name.lower() or "cake" in cat_name.lower():
                for item in items:
                    desc = item.get("description") or ""
                    for part in desc.split(","):
                        part = part.strip().lower()
                        if part:
                            dessert_sub_items.add(part)
        msg_lower = last_message.lower()
        if any(sub in msg_lower for sub in dessert_sub_items):
            target_slot = "desserts"

        # ── Text note slots: special_requests, dietary_concerns, additional_notes ──
        # Support @AI add/append to these free-text fields
        if target_slot in ("special_requests", "dietary_concerns", "additional_notes"):
            slot_label = _get_slot_label(target_slot)
            existing = state["slots"].get(target_slot, {}).get("value") or ""
            now = datetime.now().isoformat()

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
                "Are they trying to CLEAR / REMOVE ALL items entirely, or making a specific change?\n"
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

            # Build category-filtered menu for accurate resolution
            menu = await load_menu_by_category()
            if target_slot == "appetizers":
                filtered_menu = {k: v for k, v in menu.items() if _is_appetizer_category(k)}
                reentry_node = "select_appetizers"
            else:
                filtered_menu = {
                    k: v for k, v in menu.items()
                    if not _is_non_dish_category(k) and not _is_appetizer_category(k)
                }
                reentry_node = "select_dishes"

            # ── 2. Classify intent (5-way) ──
            intent = await llm_extract(
                f"Customer is modifying their '{slot_label}' "
                f"(current selection: '{current_value or 'none'}').\n"
                f"Message: {last_message}\n\n"
                "Classify their intent as exactly one of:\n"
                "- 'add_specific': naming SPECIFIC items to ADD (e.g. 'add Chicken Satay and Crab Cakes')\n"
                "- 'remove': naming items to REMOVE from current selection\n"
                "- 'replace': wants to REPLACE / START OVER entire selection "
                "(e.g. 'change everything', 'start fresh', 'redo the menu')\n"
                "- 'browse': wants to SEE / BROWSE the menu — no specific item named "
                "(e.g. 'show me options', 'add some food', 'change my appetizers')\n"
                "- 'unclear': genuinely ambiguous, can't determine\n"
                "Return ONLY: add_specific, remove, replace, browse, or unclear",
                last_message
            )
            intent = intent.strip().lower()
            if intent not in ("add_specific", "remove", "replace", "browse", "unclear"):
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
                    confirm = f"Removed! Updated your {slot_label}: **{resolved}**"
                elif removed_count > 0 and not updated:
                    history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                    history.append({"old_value": current_value, "new_value": None, "timestamp": now})
                    state["slots"][target_slot] = {
                        "value": None, "filled": False, "modified_at": now, "modification_history": history,
                    }
                    confirm = f"Removed all items from your {slot_label}."
                else:
                    confirm = (
                        f"Hmm, don't see those in your current {slot_label}: "
                        f"**{current_value or 'none'}**. Nothing changed."
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
                # Not in DB — warm apology, reassure signature items, show menu
                apology = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nCustomer asked for '{items_text}' which is NOT on our menu. "
                    "Write one warm casual line: apologize we don't have that specific item, "
                    "then reassure them we've got signature picks they'll love — "
                    "something like 'Sorry, we don't have X on our menu, but we've got some seriously good signature items you'll love — take a look:'. "
                    "Do NOT list any items — the menu is appended automatically.",
                    f"Requested: {items_text}\nSlots: {_slots_context(state)}"
                )
                current_note = f"Your current {slot_label}: **{current_value}**\n\n" if not slot_is_declined else ""
                if target_slot == "appetizers":
                    items = await get_appetizer_items()
                    item_list = build_numbered_list(items, show_price=True)
                    response = f"{apology}\n\n{current_note}{item_list}\n\nPick as many as you'd like!"
                else:
                    _, categorized = await get_main_dish_items()
                    item_list = build_numbered_list([], categories=categorized, category_headers=True)
                    response = f"{apology}\n\n{current_note}{item_list}\n\nPick 3 to 5 dishes!"
                state["current_node"] = reentry_node
                state["messages"] = add_ai_message(state, response)
                return state

        # ── Desserts + Drinks: reentry / item-merge logic ──
        elif target_slot in ("desserts", "drinks"):
            from agent.nodes.menu import _resolve_to_db_items, _parse_slot_items
            from database.db_manager import load_menu_by_category
            slot_label = _get_slot_label(target_slot)

            # Detect clear-all intent
            skip_check = await llm_extract(
                f"The customer is modifying their '{slot_label}'. "
                "Are they trying to CLEAR/SKIP/REMOVE ALL items from this category entirely, "
                "or making a specific change?\nReturn ONLY: clear or change",
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

            _DESSERT_DRINK_REENTRY = {"desserts": "select_desserts", "drinks": "collect_drinks"}

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
                state["_resume_after_mod"] = _adjust_node_for_slot_change(previous_node, state["slots"])
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
                confirm = f"Done! {action_word.capitalize()} your {slot_label}: **{resolved}**"
            else:
                confirm = f"Couldn't find those on the menu. Your {slot_label}: {current_value or 'none selected'}."

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

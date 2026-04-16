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


async def _generate_fresh_question(node: str, state: dict) -> str:
    """Generate a fresh contextual question for the given node using current slot state.

    Always generated fresh via LLM — never extracted from stale conversation history.
    This ensures the re-asked question reflects CURRENT slot values after any modification.
    """
    if node in _NO_QUESTION_NODES:
        return ""
    from agent.nodes.helpers import llm_respond
    from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS
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
    logger.debug("[CHECK_MODIFICATIONS %s] Entered check_modifications_node", _MOD_VERSION)

    # Remember where we were before the @AI interrupt
    previous_node = state.get("current_node", "start")
    logger.debug("[CHECK_MODIFICATIONS %s] previous_node = %s", _MOD_VERSION, previous_node)

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
                              "For example: '@AI change guest count to 200' or '@AI update the date to May 1st'.")

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

        # ── Menu slots: appetizers / selected_dishes / desserts — use item merge logic ──
        elif target_slot in ("appetizers", "selected_dishes", "desserts", "drinks"):
            from agent.nodes.menu import _resolve_to_db_items, _parse_slot_items
            from database.db_manager import load_menu_by_category
            slot_label = _get_slot_label(target_slot)

            # Detect skip/clear/remove-all intent via LLM
            skip_check = await llm_extract(
                f"The customer is modifying their '{target_slot}' slot. "
                "Are they trying to CLEAR/SKIP/REMOVE ALL items from this category entirely, "
                "or are they making a specific change (add, remove, swap individual items)?\n\n"
                "Return ONLY: clear or change",
                last_message
            )
            skip_intent = skip_check.strip().lower() == "clear"
            if skip_intent:
                now = datetime.now().isoformat()
                old_value = state["slots"].get(target_slot, {}).get("value")
                state["slots"][target_slot] = {
                    "value": "no", "filled": True, "modified_at": now,
                    "modification_history": [{"old_value": old_value, "new_value": "no", "timestamp": now}],
                }
                confirm = f"Done! I've cleared your {slot_label}."
                restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
                state["current_node"] = restored_node
                fresh_q = await _generate_fresh_question(restored_node, state)
                state["messages"] = add_ai_message(state, f"{confirm}\n\n{fresh_q}" if fresh_q else confirm)
                return state

            current_value = state["slots"].get(target_slot, {}).get("value") or ""
            current_items = _parse_slot_items(current_value)

            # ── Re-entry: user wants to re-open a previously declined slot ──
            # e.g. "@ai lets add desserts" when desserts = "no"
            # → re-route to the selection node so they see the menu again
            _SLOT_REENTRY_NODE = {
                "desserts": "ask_desserts",
                "appetizers": "select_appetizers",
                "selected_dishes": "select_dishes",
                "drinks": "collect_drinks",
            }
            # ── LLM-based intent classification ──
            # Is the user requesting to see/reopen a menu category (e.g. "add desserts",
            # "change the menu", "I want coffee") vs naming specific items to add/remove?
            slot_is_declined = current_value.lower() in ("no", "none", "") or not current_value
            reentry_intent = await llm_extract(
                "A customer is modifying their catering order. They are changing the "
                f"'{target_slot}' slot (current value: '{current_value}').\n\n"
                "Is the customer asking to SEE THE MENU / RE-OPEN this category "
                "(e.g. 'add desserts', 'lets add coffee', 'change the menu', 'redo appetizers') "
                "or are they naming SPECIFIC ITEMS to add/remove "
                "(e.g. 'add Crab Cakes and Chicken Satay', 'remove the burger bar')?\n\n"
                "Return ONLY: reopen or specific",
                last_message
            )
            is_reentry = reentry_intent.strip().lower() == "reopen"

            if is_reentry and target_slot in _SLOT_REENTRY_NODE:
                if slot_is_declined:
                    # Clear the "no" completely
                    state["slots"][target_slot] = {
                        "value": None, "filled": False,
                        "modified_at": None, "modification_history": [],
                    }
                reentry_node = _SLOT_REENTRY_NODE[target_slot]
                state["current_node"] = reentry_node
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
                        "Write a brief casual intro for the dessert options. "
                        "Do NOT list any items — the list will be appended automatically.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{current_note}{item_list}\n\nPick up to 4 mini desserts!"

                elif target_slot == "drinks":
                    from prompts.system_prompts import NODE_PROMPTS
                    response = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_drinks']}\n\n"
                        "Customer wants to discuss drinks/coffee/bar. "
                        "Re-ask about coffee service or bar setup.",
                        f"Slots: {_slots_context(state)}"
                    )

                elif target_slot == "appetizers":
                    from agent.nodes.menu import get_appetizer_items
                    app_items = await get_appetizer_items()
                    item_list = build_numbered_list(app_items, show_price=True)
                    current_note = f"Your current appetizers: **{current_value}**\n\n" if not slot_is_declined else ""
                    intro = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\nCustomer wants to {'add' if slot_is_declined else 'change'} appetizers. "
                        "Write a brief casual intro. Do NOT list any items.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{current_note}{item_list}\n\nPick as many as you'd like!"

                elif target_slot == "selected_dishes":
                    from agent.nodes.menu import get_main_dish_items
                    _, categorized = await get_main_dish_items()
                    item_list = build_numbered_list([], categories=categorized, category_headers=True)
                    current_note = f"Your current dishes: **{current_value}**\n\n" if not slot_is_declined else ""
                    intro = await llm_respond(
                        f"{SYSTEM_PROMPT}\n\nCustomer wants to {'pick' if slot_is_declined else 'change'} their main dishes. "
                        "Write a brief casual intro. Do NOT list any items.",
                        f"Event: {_slots_context(state)}"
                    )
                    response = f"{intro}\n\n{current_note}{item_list}\n\nPick 3 to 5 dishes!"

                state["messages"] = add_ai_message(state, response)
                return state

            # Detect remove vs. add intent via LLM
            items_text = str(new_value).strip()
            action_intent = await llm_extract(
                "Is the customer trying to REMOVE items from their order, or ADD items?\n"
                f"Message: {last_message}\n\n"
                "Return ONLY: remove or add",
                last_message
            )
            remove_intent = action_intent.strip().lower() == "remove"

            # ── Extract remove-items and add-items separately when both appear ──
            # Pattern: "remove X and add Y" or "remove X, add Y"
            remove_text = items_text
            add_text = ""
            if remove_intent and add_intent:
                # Try to split the message on "and add" or ", add"
                split_match = re.split(r'(?:,?\s+and\s+add\b|\badd\b)', last_message, maxsplit=1, flags=re.IGNORECASE)
                if len(split_match) == 2:
                    add_text = split_match[1].strip()
                    # remove_text: everything before "add" in the LLM's new_value, or use remove section
                    remove_section = re.split(r'\b(?:and\s+)?add\b', items_text, maxsplit=1, flags=re.IGNORECASE)[0].strip()
                    remove_text = remove_section if remove_section else items_text

            if remove_intent:
                matched, _ = await _resolve_to_db_items(remove_text)
                remove_names = {i["name"].lower() for i in matched}
                remove_kws = [p.strip().lower() for p in remove_text.split(",") if p.strip()]
                updated = [
                    n for n in current_items
                    if n.lower() not in remove_names
                    and not any(kw and kw in n.lower() for kw in remove_kws)
                ]
                removed_items = [n for n in current_items if n not in updated]

                # Also process add if combined
                added_items = []
                if add_intent and add_text:
                    add_matched, _ = await _resolve_to_db_items(add_text)
                    existing_lower = {n.lower() for n in updated}
                    new_names = [i["name"] for i in add_matched if i["name"].lower() not in existing_lower]
                    updated = updated + new_names
                    added_items = new_names

                _, resolved = await _resolve_to_db_items(", ".join(updated)) if updated else ([], "")
                action_word = "removed"
            else:
                matched, _ = await _resolve_to_db_items(items_text)
                existing_lower = {n.lower() for n in current_items}
                new_names = [i["name"] for i in matched if i["name"].lower() not in existing_lower]
                merged = current_items + new_names
                _, resolved = await _resolve_to_db_items(", ".join(merged)) if merged else ([], current_value)
                action_word = "added to"

            if remove_intent:
                actually_resolved = resolved if resolved else ""
                value_changed = set(updated) != set(current_items)
                if value_changed and (removed_items or (add_intent and add_text)):
                    old_value = current_value
                    now = datetime.now().isoformat()
                    history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                    history.append({"old_value": old_value, "new_value": actually_resolved, "timestamp": now})
                    state["slots"][target_slot] = {
                        "value": actually_resolved,
                        "filled": bool(updated),
                        "modified_at": now,
                        "modification_history": history,
                    }
                    parts = []
                    if removed_items:
                        parts.append(f"Removed **{', '.join(removed_items)}**")
                    if add_intent and 'added_items' in dir() and added_items:
                        parts.append(f"Added **{', '.join(added_items)}**")
                    action_summary = " and ".join(parts) if parts else "Updated"
                    remaining_str = actually_resolved if actually_resolved else "none"
                    confirm = f"Done! {action_summary} from your {slot_label}. Updated {slot_label}: {remaining_str}"
                else:
                    confirm = f"I couldn't find that item in your {slot_label}. Current {slot_label}: {current_value or 'none selected'}."
            elif resolved and resolved != current_value:
                old_value = current_value
                now = datetime.now().isoformat()
                history = list(state["slots"].get(target_slot, {}).get("modification_history") or [])
                history.append({"old_value": old_value, "new_value": resolved, "timestamp": now})
                state["slots"][target_slot] = {
                    "value": resolved,
                    "filled": True,
                    "modified_at": now,
                    "modification_history": history,
                }
                confirm = f"Done! Updated your {slot_label}: **{resolved}**"
            else:
                confirm = f"I couldn't find those items on the menu. Your {slot_label} remain: {current_value or 'none selected'}."

        else:
            # ── Scalar slots: use standard date-resolve + validate path ──
            resolved_value = str(new_value)
            logger.debug("[CHECK_MODIFICATIONS %s] target_slot=%s, raw new_value=%s", _MOD_VERSION, target_slot, new_value)
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
                          "For example: '@AI change guest count to 200' or '@AI update the date to May 1st'.")

    # CRITICAL: Stay on the same node — never jump ahead
    # EXCEPT: reroute conditional nodes when their condition no longer holds
    # EXCEPT: after processing a menu change from collect_menu_changes → go to ask_menu_changes
    #         so user gets "are you happy with this?" not "what would you like to change?"
    if previous_node == "collect_menu_changes" and detection_result.get("detected"):
        restored_node = "ask_menu_changes"
    else:
        restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
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

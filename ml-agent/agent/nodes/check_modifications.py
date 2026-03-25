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
_MOD_VERSION = "v6"  # Bump to verify this code is running


# Conditional nodes: mapping of node_name → (slot_name, valid_condition_fn, fallback_node)
# If the slot no longer satisfies the condition, reroute to fallback_node.
_CONDITIONAL_NODES = {
    "wedding_message": ("event_type", lambda v: v and "wedding" in str(v).lower(), "collect_venue"),
    "select_service_style": ("event_type", lambda v: v and "wedding" in str(v).lower(), "select_dishes"),
    "ask_florals": ("event_type", lambda v: v and "wedding" in str(v).lower(), "ask_special_requests"),
}


def _adjust_node_for_slot_change(node: str, slots: dict) -> str:
    """Re-route conditional nodes when the underlying slot no longer matches.

    For example, if event_type changed from Wedding to Birthday,
    'wedding_message' should become 'collect_venue' instead.
    """
    rule = _CONDITIONAL_NODES.get(node)
    if not rule:
        return node  # Not a conditional node — keep as-is

    slot_name, condition_fn, fallback = rule
    slot_data = slots.get(slot_name, {})
    current_value = slot_data.get("value")

    if not condition_fn(current_value):
        print(f"[CHECK_MODIFICATIONS] Rerouting {node} -> {fallback} (slot '{slot_name}' = '{current_value}')")
        return fallback

    return node


def _get_slot_label(slot_name: str) -> str:
    """Convert slot key to human-readable label."""
    return slot_name.replace("_", " ")


def _extract_pending_question(state: ConversationState) -> str:
    """
    Extract the last question the bot asked from conversation history.

    This is the question the user was supposed to answer before they
    sent the @AI modification. We re-ask it so the flow stays in place.
    Fully generalized — works for any node, any point in the conversation.
    """
    # Walk backwards: skip the last HumanMessage (@AI msg), find the AI message before it
    found_human = False
    for msg in reversed(list(state.get("messages", []))):
        if isinstance(msg, HumanMessage):
            found_human = True
            continue
        if found_human and isinstance(msg, AIMessage):
            content = msg.content
            # Extract all sentences ending with "?"
            questions = re.findall(r'[^.!?\n]*\?', content)
            if questions:
                # Return the last question asked
                return questions[-1].strip()
            break

    return ""


async def check_modifications_node(state: ConversationState) -> ConversationState:
    """
    Handle @AI slot modification requests.

    After processing, current_node is ALWAYS restored to previous_node
    so the conversation never jumps ahead.
    """
    state = dict(state)
    print(f"\n[CHECK_MODIFICATIONS {_MOD_VERSION}] Entered check_modifications_node")

    # Remember where we were before the @AI interrupt
    previous_node = state.get("current_node", "start")
    print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] previous_node = {previous_node}")

    # Extract the pending question BEFORE we process (from the last AI message)
    pending_question = _extract_pending_question(state)

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

    if detection_result.get("clarification_needed"):
        # Ambiguous — ask user to clarify
        possible_slots = detection_result.get("possible_slots", [])

        if possible_slots:
            labels = [_get_slot_label(s) for s in possible_slots]
            if len(labels) == 1:
                response = f"I want to make sure I update the right information. Did you want to change {labels[0]}?"
            elif len(labels) == 2:
                response = f"I want to make sure I update the right information. Did you want to change {labels[0]} or {labels[1]}?"
            else:
                options_str = ", ".join(labels[:-1]) + f", or {labels[-1]}"
                response = f"I want to make sure I update the right information. Did you want to change {options_str}?"
        else:
            response = ("I'm not sure which information you'd like to change. Could you be more specific? "
                        "For example: '@AI change guest count to 200' or '@AI update the date to May 1st'.")

        state["messages"] = add_ai_message(state, response)

    elif detection_result.get("detected"):
        target_slot = detection_result.get("target_slot")
        new_value = detection_result.get("new_value")

        # ── Menu slots: appetizers / selected_dishes — use item merge logic ──
        if target_slot in ("appetizers", "selected_dishes"):
            from agent.nodes.menu import _resolve_to_db_items, _parse_slot_items
            slot_label = _get_slot_label(target_slot)
            current_value = state["slots"].get(target_slot, {}).get("value") or ""
            current_items = _parse_slot_items(current_value)

            # Detect remove / add intent from the raw user message
            remove_intent = bool(re.search(r'\b(remove|delete|take out|drop)\b', last_message, re.IGNORECASE))
            add_intent = bool(re.search(r'\badd\b', last_message, re.IGNORECASE))
            items_text = str(new_value).strip()

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

            response = f"{confirm}\n\n{pending_question}" if pending_question else f"{confirm}\n\nPlease continue where we left off."
            state["messages"] = add_ai_message(state, response)

        else:
            # ── Scalar slots: use standard date-resolve + validate path ──
            resolved_value = str(new_value)
            print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] target_slot={target_slot}, raw new_value={new_value}")
            if target_slot == "event_date" and _contains_relative_date(resolved_value):
                print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] Resolving relative date: {resolved_value}")
                resolved_value = await _resolve_relative_date(resolved_value)
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

                slot_label = _get_slot_label(target_slot)

                if old_value:
                    confirm = f"I've updated your {slot_label} from '{old_value}' to '{normalized_value}'."
                else:
                    confirm = f"I've set your {slot_label} to '{normalized_value}'."

                response = f"{confirm}\n\n{pending_question}" if pending_question else f"{confirm}\n\nPlease continue where we left off."
                state["messages"] = add_ai_message(state, response)
            else:
                error_message = validation_result.get("error_message", "Invalid value")
                response = f"I couldn't update that: {error_message}"
                state["messages"] = add_ai_message(state, response)
    else:
        response = ("I'm not sure which information you'd like to change. Could you be more specific? "
                    "For example: '@AI change guest count to 200' or '@AI update the date to May 1st'.")
        state["messages"] = add_ai_message(state, response)

    # CRITICAL: Stay on the same node — never jump ahead
    # EXCEPT: reroute conditional nodes when their condition no longer holds
    restored_node = _adjust_node_for_slot_change(previous_node, state["slots"])
    state["current_node"] = restored_node
    print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] Exiting. current_node: {restored_node} (previous: {previous_node})")
    return state

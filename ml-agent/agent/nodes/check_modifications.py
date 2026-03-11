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

        # For date slots, resolve relative dates BEFORE validation
        # (dateutil.parser can't handle "next month", "this week", etc.)
        resolved_value = str(new_value)
        print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] target_slot={target_slot}, raw new_value={new_value}")
        if target_slot == "event_date" and _contains_relative_date(resolved_value):
            print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] Resolving relative date: {resolved_value}")
            resolved_value = await _resolve_relative_date(resolved_value)
            print(f"[CHECK_MODIFICATIONS {_MOD_VERSION}] Resolved to: {resolved_value}")

        # Validate new value
        validation_result = await validate_slot.ainvoke({
            "slot_name": target_slot,
            "value": resolved_value
        })

        if validation_result.get("valid"):
            old_value = state["slots"][target_slot].get("value")
            normalized_value = validation_result.get("normalized_value")

            # Update slot with modification history
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

            # Build confirmation
            if old_value:
                confirm = f"I've updated your {slot_label} from '{old_value}' to '{normalized_value}'."
            else:
                confirm = f"I've set your {slot_label} to '{normalized_value}'."

            # Re-ask the pending question from conversation history
            # NO LLM call, NO NODE_PROMPTS — just replay the question the bot already asked
            if pending_question:
                response = f"{confirm}\n\n{pending_question}"
            else:
                response = f"{confirm}\n\nPlease continue where we left off."

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

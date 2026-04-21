"""
Response generator for tool outputs.

Tools return structured facts in `response_context`. This module turns those
facts into user-facing text while keeping deterministic paths for UI-critical
turns such as direct menu renders, forced follow-up prompts, and modification
confirmations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from agent.instructor_client import MODEL_RESPONSE, extract, generate_text
from agent.prompt_registry import RESPONSE_SYSTEM_PROMPT, fallback_prompt_for_target
from agent.state import filled_slot_summary, get_slot_value, unfilled_required
from agent.tools.base import ToolResult

logger = logging.getLogger(__name__)

_RESPONSE_MAX_TOKENS = 1400
_SYSTEM_PROMPT = RESPONSE_SYSTEM_PROMPT

class GeneratedReply(BaseModel):
    """Structured user-facing reply for the next assistant turn."""

    reply_text: str = Field(
        ...,
        description=(
            "The complete assistant reply to send to the user. Keep it natural, "
            "short, and grounded in the provided context. Respect any widget "
            "keyword constraints implied by next_question_target."
        ),
    )


async def render(
    *,
    tool_result: ToolResult,
    user_message: str,
    history: list[BaseMessage],
) -> str:
    """Render the assistant reply for a tool result."""
    if tool_result.direct_response:
        ctx = tool_result.response_context or {}
        logger.info(
            "render_source=direct_response tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return tool_result.direct_response

    ctx = tool_result.response_context or {}

    if _should_force_modification_render(ctx):
        logger.info(
            "render_source=deterministic_modification tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return _modification_prompt(ctx, tool_result.state)

    if _should_force_menu_progress_render(ctx):
        logger.info(
            "render_source=deterministic_menu_progress tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return str(ctx.get("menu_progress") or _fallback(ctx, tool_result.state))

    if _should_force_direct_prompt(ctx):
        logger.info(
            "render_source=deterministic_prompt tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return _direct_prompt_text(ctx, tool_result.state) or _fallback(ctx, tool_result.state)

    user_block = _build_user_block(
        tool_result=tool_result,
        user_message=user_message,
        history=history,
    )

    structured = await extract(
        schema=GeneratedReply,
        system=_SYSTEM_PROMPT,
        user_message=user_block,
        model=MODEL_RESPONSE,
        max_tokens=_RESPONSE_MAX_TOKENS,
    )
    text = (structured.reply_text or "").strip() if structured else ""

    if not text:
        text = await generate_text(
            system=_SYSTEM_PROMPT,
            user=user_block,
            model=MODEL_RESPONSE,
            max_tokens=_RESPONSE_MAX_TOKENS,
            temperature=0.85,
        )

    if not text:
        logger.warning(
            "render_source=fallback tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return _fallback(ctx, tool_result.state)

    logger.info(
        "render_source=%s tool=%s target=%s",
        "llm_structured" if structured else "llm_text_fallback",
        ctx.get("tool", "-"),
        ctx.get("next_question_target", "-"),
    )
    return text


def _build_user_block(
    *,
    tool_result: ToolResult,
    user_message: str,
    history: list[BaseMessage],
) -> str:
    state = tool_result.state
    slots = state.get("slots", {})

    name = get_slot_value(slots, "name")
    filled_slots = filled_slot_summary(slots)
    filled_compact = {
        key: (value if len(str(value)) < 200 else f"{str(value)[:200]}...")
        for key, value in filled_slots.items()
    }

    payload = {
        "user_message": user_message,
        "context": _sanitize(tool_result.response_context or {}),
        "conversation": {
            "phase": state.get("conversation_phase"),
            "status": get_slot_value(slots, "conversation_status") or "active",
            "turn_count": len(state.get("messages", [])),
        },
        "filled_slots": filled_compact,
        "missing_required": unfilled_required(slots),
        "key_slots": {
            "name": name,
            "event_type": get_slot_value(slots, "event_type"),
            "event_date": get_slot_value(slots, "event_date"),
            "venue": get_slot_value(slots, "venue"),
            "guest_count": get_slot_value(slots, "guest_count"),
            "service_type": get_slot_value(slots, "service_type"),
        },
        "next_question_target": (tool_result.response_context or {}).get("next_question_target"),
        "customer_name": name,
        "recent_assistant_replies": _recent_assistant_replies(history),
    }
    return json.dumps(payload, default=str)


def _sanitize(ctx: dict[str, Any]) -> dict[str, Any]:
    """Strip fields that should not reach the response model."""
    safe: dict[str, Any] = {}
    for key, value in ctx.items():
        if key == "pricing":
            continue
        safe[key] = value
    return safe


def _recent_assistant_replies(history: list[BaseMessage]) -> list[str]:
    replies: list[str] = []
    for msg in history[-8:]:
        if getattr(msg, "type", "") != "ai":
            continue
        content = str(getattr(msg, "content", "")).strip()
        if not content:
            continue
        first_line = content.splitlines()[0].strip()
        if first_line:
            replies.append(first_line[:140])
    return replies[-4:]


def _should_force_modification_render(ctx: dict[str, Any]) -> bool:
    return bool(
        ctx.get("tool") == "modification_tool"
        and ctx.get("modification")
        and not ctx.get("error")
    )


def _should_force_menu_progress_render(ctx: dict[str, Any]) -> bool:
    return bool(
        ctx.get("tool") == "menu_selection_tool"
        and ctx.get("menu_progress")
    )


def _should_force_direct_prompt(ctx: dict[str, Any]) -> bool:
    return str(ctx.get("next_question_target") or "") == "ask_service_style"


def _direct_prompt_text(ctx: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    target = str(ctx.get("next_question_target") or "")
    if target == "ask_service_style":
        return (
            "For the wedding, would you like to have a cocktail hour before the main meal, "
            "a reception for the main meal, or both?"
        )
    return _next_prompt(ctx, state)


def _fallback(ctx: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    tool = str(ctx.get("tool") or "")

    if ctx.get("error") in {"could_not_parse", "could_not_route"}:
        return "Sorry, I didn't quite catch that - could you say it another way?"
    if ctx.get("error") == "invalid_new_value":
        return "That value didn't look right - could you try again?"
    if ctx.get("error") == "locked_slot":
        return (
            "That's set automatically based on your bar service selection - "
            "to change it, update your bar service choice."
        )

    if ctx.get("awaiting_confirm"):
        return "Here's the summary so far - does everything look correct?"
    if ctx.get("status") == "pending_staff_review":
        return "All set! One of our coordinators will review your request and reach out shortly."

    if tool == "modification_tool":
        return _modification_prompt(ctx, state)

    next_prompt = _next_prompt(ctx, state)
    if next_prompt:
        return next_prompt

    return "Got it - what would you like to do next?"


def _next_prompt(ctx: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    return fallback_prompt_for_target(
        str(ctx.get("tool") or ""),
        ctx.get("next_question_target"),
        _prompt_variant_seed(ctx, state),
    )


def _modification_prompt(ctx: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    mod = ctx.get("modification") or {}
    target = str(mod.get("target_slot") or "selection")
    label = _modification_label(target)
    action = str(mod.get("action") or "replace")
    removed = [str(v) for v in (mod.get("removed") or []) if str(v).strip()]
    added = [str(v) for v in (mod.get("added") or []) if str(v).strip()]
    remaining = [str(v) for v in (mod.get("remaining_items") or []) if str(v).strip()]
    new_value = mod.get("new_value")

    if action == "reopen":
        return f"Let's revisit your {label}. What would you like to pick?"

    follow_up = _next_prompt(ctx, state)

    if removed or added:
        parts: list[str] = []
        if removed:
            parts.append(f"removed {', '.join(removed)} from your {label}")
        if added:
            parts.append(f"added {', '.join(added)} to your {label}")

        sentences = ["I " + " and ".join(parts) + "."]
        current_state = _modification_current_state_sentence(
            target=target,
            label=label,
            new_value=new_value,
            remaining_items=remaining,
        )
        if current_state:
            sentences.append(current_state)
        sentences.extend(_additional_modification_sentences(mod.get("additional_changes")))
        if follow_up:
            sentences.append(follow_up)
        return " ".join(sentences).strip()

    if action == "remove" or new_value in (None, ""):
        text = f"I removed your {label}."
    else:
        pretty_value = _modification_value_text(target, new_value)
        if action == "add":
            text = f"I added {pretty_value} to your {label}."
        else:
            text = f"I updated your {label} to {pretty_value}."

    current_state = _modification_current_state_sentence(
        target=target,
        label=label,
        new_value=new_value,
        remaining_items=remaining,
    )

    parts = [text]
    if current_state and current_state != text:
        parts.append(current_state)
    parts.extend(_additional_modification_sentences(mod.get("additional_changes")))
    if follow_up:
        parts.append(follow_up)
    return " ".join(parts).strip()


def _modification_label(target: str) -> str:
    return {
        "selected_dishes": "main dishes",
        "special_requests": "special requests",
        "dietary_concerns": "dietary concerns",
        "additional_notes": "notes",
        "guest_count": "guest count",
        "event_date": "event date",
        "service_type": "service type",
    }.get(target, target.replace("_", " "))


def _modification_value_text(target: str, value: Any) -> str:
    if value in (None, ""):
        return "nothing"
    if isinstance(value, bool):
        return "yes" if value else "no"

    text = str(value).strip()
    if not text:
        return "nothing"

    if target == "service_type" and text.lower() == "dropoff":
        return "drop-off"
    if target == "tableware":
        return {
            "standard_disposable": "standard disposable",
            "silver_disposable": "silver disposable",
            "gold_disposable": "gold disposable",
            "china": "full china",
            "no_tableware": "no tableware",
        }.get(text.lower(), text)
    if target == "utensils":
        return {
            "standard_plastic": "standard plastic",
            "eco_biodegradable": "eco / biodegradable",
            "bamboo": "bamboo",
        }.get(text.lower(), text)
    return text


def _modification_current_state_sentence(
    *,
    target: str,
    label: str,
    new_value: Any,
    remaining_items: list[str],
) -> str:
    if remaining_items:
        return f"Your {label} are now: {', '.join(remaining_items)}."

    if new_value in (None, "", "none"):
        if target in {"appetizers", "selected_dishes", "desserts", "rentals"}:
            return f"Your {label} list is empty now."
        return ""

    pretty_value = _modification_value_text(target, new_value)
    if target in {"special_requests", "dietary_concerns", "additional_notes"}:
        return f"Your {label} now read: {pretty_value}."
    return f"Your {label} is now {pretty_value}."


def _additional_modification_sentences(changes: Any) -> list[str]:
    if not isinstance(changes, list):
        return []

    sentences: list[str] = []
    for change in changes:
        if not isinstance(change, dict):
            continue

        target = str(change.get("target_slot") or "selection")
        label = _modification_label(target)
        added = [str(v) for v in (change.get("added") or []) if str(v).strip()]
        removed = [str(v) for v in (change.get("removed") or []) if str(v).strip()]
        remaining = [str(v) for v in (change.get("remaining_items") or []) if str(v).strip()]
        new_value = change.get("new_value")

        pieces: list[str] = []
        if removed:
            pieces.append(f"removed {', '.join(removed)} from your {label}")
        if added:
            pieces.append(f"added {', '.join(added)} to your {label}")
        if pieces:
            sentences.append("I also " + " and ".join(pieces) + ".")

        current_state = _modification_current_state_sentence(
            target=target,
            label=label,
            new_value=new_value,
            remaining_items=remaining,
        )
        if current_state:
            sentences.append(current_state)

    return sentences


def _prompt_variant_seed(ctx: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    phase = ""
    turn_count = 0
    if state:
        phase = str(state.get("conversation_phase") or "")
        turn_count = len(state.get("messages", []))

    tool = str(ctx.get("tool") or "")
    target = str(ctx.get("next_question_target") or "")
    filled = ",".join(sorted(str(item) for item in (ctx.get("filled_this_turn") or [])))
    return f"{tool}|{target}|{phase}|{turn_count}|{filled}"


__all__ = ["render"]

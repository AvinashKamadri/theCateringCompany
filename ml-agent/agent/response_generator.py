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
import hashlib
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from agent.instructor_client import MODEL_RESPONSE, extract, generate_text
from agent.prompt_registry import RESPONSE_SYSTEM_PROMPT, fallback_prompt_for_target
from agent.state import filled_slot_summary, get_slot_value, unfilled_required
from agent.tone_detector import detect_tone, guidance_for_tone
from agent.tools.base import ToolResult

logger = logging.getLogger(__name__)

_RESPONSE_MAX_TOKENS = 1000
_SYSTEM_PROMPT = RESPONSE_SYSTEM_PROMPT

# Minimum keyword presence per next_question_target. If the LLM's reply for an
# intake question is missing all of these, we discard it and fall back to the
# deterministic prompt. Prevents the model from riffing into a wrap-up ("we'll
# be in touch") when it should be asking the next question.
_TARGET_KEYWORDS: dict[str, tuple[str, ...]] = {
    # Minimal sanity check — the reply must clearly be asking for the right
    # thing. Keep these very permissive: overly strict rules cause good creative
    # LLM replies to be discarded and replaced with stiff template strings.
    # Rule: at least ONE of these words must appear. If in doubt, add more words.
    "ask_name": ("name", "who am i chatting", "who's planning"),
    "ask_email": ("email",),
    "ask_phone": ("phone", "number", "reach", "digits"),
    "ask_event_type": ("event", "wedding", "birthday", "corporate", "planning", "celebration", "occasion", "kind", "type", "celebrating"),
    "ask_partner_name": ("partner", "spouse", "fiance", "other half", "name"),
    "ask_company_name": ("company", "organization", "business", "name"),
    "ask_honoree_name": ("who", "honoree", "celebrating", "celebration", "for", "name", "guest of honor"),
    "ask_other_event_type": ("event", "kind", "type", "planning", "confirm", "describe"),
    "ask_service_type": ("drop", "onsite", "on-site", "on site", "service", "staff", "setup", "deliver", "come to"),
    "ask_event_date": ("date", "when", "day", "block off", "schedule"),
    "ask_venue": ("venue", "where", "location", "held", "address", "happening", "place"),
    "ask_guest_count": ("guest", "headcount", "expecting", "how many", "people", "attendees", "crowd", "group", "large", "size", "cooking for"),
    # Menu-flow targets
    "ask_service_style": ("cocktail", "reception", "both"),
    "ask_appetizer_style": ("passed", "station", "served"),
    "ask_meal_style": ("plated", "buffet", "served"),
    "ask_dessert_gate": ("dessert", "sweet", "skip"),
    # Wedding cake flow
    "ask_wedding_cake": ("cake", "wedding"),
    "ask_wedding_cake_flavor": ("flavor", "cake"),
    "ask_wedding_cake_filling": ("filling", "cake", "inside"),
    "ask_wedding_cake_buttercream": ("buttercream", "frosting", "outside"),
    # Add-ons
    "ask_drinks_interest": ("drinks", "coffee", "bar", "beverage"),
    "ask_drinks_setup": ("drinks", "coffee", "bar", "setup"),
    "ask_bar_package": ("bar", "beer", "wine", "open", "signature", "cocktail"),
    "ask_tableware_gate": ("tableware", "plates", "china", "disposable", "utensils"),
    "ask_tableware": ("tableware", "china", "plates", "disposable"),
    "ask_utensils": ("utensils", "fork", "plastic", "bamboo", "biodegradable", "cutlery"),
    "ask_rentals_gate": ("rental", "tables", "chairs", "linen", "anything"),
    "ask_labor_services": ("labor", "setup", "cleanup", "staff", "service", "ceremony", "preset", "trash"),
    # Finalization
    "ask_special_requests_gate": ("special", "request", "anything", "flag", "note"),
    "ask_dietary_gate": ("dietary", "allerg", "diet", "food", "restriction"),
    "ask_additional_notes_gate": ("notes", "anything else", "to add"),
    "ask_followup_call": ("call", "follow", "schedule", "lock", "talk"),
}

# Phrases the LLM should NEVER emit unless the intake is actually complete.
_WRAP_UP_PHRASES: tuple[str, ...] = (
    "hear from our office",
    "hear from our team",
    "24-48 hours",
    "24 to 48 hours",
    "we'll be in touch",
    "we will be in touch",
    "reach out shortly",
    "make your event a success",
    "all set!",
)


_BANNED_OPENERS: tuple[str, ...] = (
    "perfect", "great", "awesome", "got it", "sweet", "nice", "wonderful",
    "excellent", "noted", "thank you", "thanks for", "of course",
    "absolutely", "certainly", "sure thing", "sounds good",
    # Corporate / robotic openings
    "welcome to", "welcome,", "welcome!", "welcome ", "hello,", "hello!",
    "hi there", "greetings", "to begin", "to get started",
    # Robotic preambles flagged in the screenshot
    "now that we have",
    "now then",
    "alright, so",
    "since it's a wedding",
    "since it is a wedding",
)


_BANNED_PHRASES: tuple[str, ...] = (
    "may i have",
    "may i get",
    "could i have",
    "could i get",
    "please provide",
    "please share",
    "please tell me",
    "i'd like to know",
    # Commenty / flattery — never editorialize on the user's answer
    "lovely name",
    "great name",
    "nice name",
    "cool name",
    "what a beautiful",
    "sounds amazing",
    "sounds delicious",
    "sounds wonderful",
)


def _reply_fails_guardrail(text: str, ctx: dict[str, Any], status: str) -> bool:
    """Return True if the LLM reply should be discarded in favor of the fallback."""
    if not text:
        return False
    lower = text.lower().lstrip()

    # Reject banned openers — the prompt already bans them but LLMs drift;
    # this enforces it structurally so a retry is forced.
    for opener in _BANNED_OPENERS:
        if lower.startswith(opener):
            return True

    # Reject corporate/stiff phrases anywhere in the reply
    # ("may I have your name?", "please provide your email", etc.)
    for phrase in _BANNED_PHRASES:
        if phrase in lower:
            return True

    # Reject ultra-curt replies for free-text intake questions. "Phone number?"
    # / "Your email?" / "Your name?" feel like a form. Require at least ~4 words
    # so the LLM produces something that sounds like a person speaking.
    target = str(ctx.get("next_question_target") or "")
    _conversational_targets = {
        "ask_name", "ask_email", "ask_phone",
        "ask_event_type", "ask_event_date", "ask_venue", "ask_guest_count",
        "ask_partner_name", "ask_company_name", "ask_honoree_name",
        "ask_other_event_type",
    }
    if target in _conversational_targets:
        word_count = len(text.split())
        if word_count < 4:
            return True

    if status != "pending_staff_review":
        for phrase in _WRAP_UP_PHRASES:
            if phrase in lower:
                return True

    required = _TARGET_KEYWORDS.get(target)
    if required and not any(k in lower for k in required):
        return True

    return False


def _is_duplicate_of_previous(text: str, history: list[BaseMessage]) -> bool:
    """Return True if `text` is the same (or near-same) as the previous AI message."""
    if not text or not history:
        return False
    last_ai_text = ""
    for msg in reversed(history):
        if getattr(msg, "type", "") == "ai":
            last_ai_text = str(getattr(msg, "content", "") or "").strip()
            break
    if not last_ai_text:
        return False
    norm_new = " ".join(text.lower().split())
    norm_prev = " ".join(last_ai_text.lower().split())
    if not norm_new:
        return False
    if norm_new == norm_prev:
        return True
    # Short replies that are entirely contained in the previous one are echoes.
    if len(norm_new) < 80 and norm_new in norm_prev:
        return True
    return False


def _retry_via_fallback(
    ctx: dict[str, Any],
    state: dict[str, Any] | None,
    history: list[BaseMessage],
) -> str:
    """When direct_response duplicates, ask the registry for an alternate variant.

    Re-rolls the seed with the message count so the variant differs from the
    last one, even when ctx is otherwise identical.
    """
    candidate = _fallback(ctx, state)
    if candidate and not _is_duplicate_of_previous(candidate, history):
        return candidate
    return ""


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
        text = tool_result.direct_response
        # Apply duplicate-guard to direct_response too. If a clarify/OOS path
        # produces the EXACT same text as the immediately previous AI message,
        # we'd be looping the user. Trim to a deterministic variant if available.
        if _is_duplicate_of_previous(text, history):
            varied = _retry_via_fallback(ctx, tool_result.state, history)
            if varied:
                logger.info(
                    "render_source=direct_response_dedup tool=%s target=%s",
                    ctx.get("tool", "-"),
                    ctx.get("next_question_target", "-"),
                )
                return varied
        logger.info(
            "render_source=direct_response tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return text

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
        temperature=0.7,
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

    status = get_slot_value(tool_result.state.get("slots", {}), "conversation_status") or "active"
    if _reply_fails_guardrail(text, ctx, status):
        logger.warning(
            "render_source=guardrail_fallback tool=%s target=%s discarded=%r",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
            text[:160],
        )
        return _fallback(ctx, tool_result.state)

    # Duplicate-response guard: if the LLM regenerated the same reply as the
    # immediately-preceding AI message, fall back to the deterministic prompt.
    # This prevents echoes like "Reception it is." appearing twice in a row
    # when the user pastes a long answer that the LLM gets confused on.
    last_ai_text = ""
    for msg in reversed(history):
        if getattr(msg, "type", "") == "ai":
            last_ai_text = str(getattr(msg, "content", "") or "").strip()
            break
    if last_ai_text:
        norm_new = " ".join(text.lower().split())
        norm_prev = " ".join(last_ai_text.lower().split())
        if norm_new and (norm_new == norm_prev or (len(norm_new) < 80 and norm_new in norm_prev)):
            logger.warning(
                "render_source=duplicate_fallback tool=%s target=%s",
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

    tone = detect_tone(history, user_message)
    ctx_for_capture = tool_result.response_context or {}
    filled_this_turn = ctx_for_capture.get("filled_this_turn") or []
    nothing_captured = not filled_this_turn and not ctx_for_capture.get("modification")

    payload = {
        "user_message": user_message,
        "tone_profile": tone,
        "tone_guidance": guidance_for_tone(tone),
        "nothing_was_captured": nothing_captured,
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


_TEMPLATE_ONLY_TARGETS = frozenset({
    # By default we let the LLM generate every question with waiter-style warmth
    # (see WAITER PROMPT GUIDANCE in RESPONSE_SYSTEM_PROMPT). The registry then
    # acts as a fallback when the LLM fails the keyword guardrail.
    #
    # The exceptions below are NOT free-text questions — they are pure transitions
    # or post-gate collection prompts where the LLM would tend to re-ask the gate
    # ("are you sure you want desserts?") instead of moving on. Keep them deterministic.
    "transition_to_menu",
    "transition_to_addons",
    "transition_to_special_requests",
    "collect_special_requests",
    "collect_dietary_concerns",
    "collect_additional_notes",
})


def _should_force_direct_prompt(ctx: dict[str, Any]) -> bool:
    target = str(ctx.get("next_question_target") or "")
    if target in _TEMPLATE_ONLY_TARGETS:
        return True
    # Edge-case handling: if a basic-info validator rejects the user's answer,
    # re-ask deterministically instead of letting the response LLM generate a
    # vague "clarify" message.
    if ctx.get("tool") == "basic_info_tool" and (ctx.get("rejected_past_date") or ctx.get("wrong_field_for_phase")):
        return True
    # If the tool didn't capture anything and the next prompt is a constrained
    # choice question, do not let the response LLM generate vague "clarify"
    # replies.
    filled_this_turn = ctx.get("filled_this_turn") or []
    if not filled_this_turn and target in {
        "ask_service_type",
        "ask_bar_package",
        "ask_drinks_interest",
        "ask_drinks_setup",
        "ask_tableware_gate",
        "ask_tableware",
        "ask_utensils",
        "ask_labor_services",
    }:
        return True
    return False


def _direct_prompt_text(ctx: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    if ctx.get("tool") == "basic_info_tool" and ctx.get("rejected_past_date"):
        return "That date is in the past — what's the event date? Any future date works."
    return _next_prompt(ctx, state)


# Warm one-clause acks for unparseable input — paired with the actual next
# question by _fallback() so the user always knows what to answer next.
# NEVER use "didn't catch", "I don't understand", "rephrase", "try again" —
# those are buzzkills. Keep it playful, brief, friendly waiter energy.
_COULD_NOT_PARSE_REPLIES = [
    "haha okay —",
    "no worries —",
    "alright —",
    "sure —",
    "got it —",
    "right —",
]

_INVALID_VALUE_REPLIES = [
    "hmm, that doesn't look quite right —",
    "let me re-ask —",
    "small snag —",
    "one more try —",
]


def _pick(pool: list[str], seed: str) -> str:
    idx = int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(pool)
    return pool[idx]


def _fallback(ctx: dict[str, Any], state: dict[str, Any] | None = None) -> str:
    tool = str(ctx.get("tool") or "")
    _seed = f"{tool}:{ctx.get('error')}:{ctx.get('next_question_target')}"

    if ctx.get("error") in {"could_not_parse", "could_not_route"}:
        # Warm ack + the actual next question. The ack alone is a buzzkill;
        # always pair it with the question so the user knows what to answer.
        ack = _pick(_COULD_NOT_PARSE_REPLIES, _seed)
        nxt = _next_prompt(ctx, state)
        return f"{ack} {nxt}".strip() if nxt else ack
    if ctx.get("error") == "invalid_new_value":
        ack = _pick(_INVALID_VALUE_REPLIES, _seed)
        nxt = _next_prompt(ctx, state)
        return f"{ack} {nxt}".strip() if nxt else ack
    if ctx.get("error") == "locked_slot":
        return (
            "That's set automatically based on your bar service selection — "
            "to change it, update your bar service choice."
        )

    if ctx.get("awaiting_confirm"):
        return "Here's the summary so far — does everything look correct?"
    if ctx.get("status") == "pending_staff_review":
        return "All set! One of our coordinators will review your request and reach out shortly."

    if tool == "modification_tool":
        return _modification_prompt(ctx, state)

    next_prompt = _next_prompt(ctx, state)
    if next_prompt:
        return next_prompt

    return "What would you like to do next?"


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
    already_selected = [str(v) for v in (mod.get("already_selected") or []) if str(v).strip()]
    unavailable = [str(v) for v in (mod.get("unavailable") or []) if str(v).strip()]
    remaining = [str(v) for v in (mod.get("remaining_items") or []) if str(v).strip()]
    new_value = mod.get("new_value")

    if action == "reopen":
        return f"Let's revisit your {label}. What would you like to pick?"

    follow_up = _next_prompt(ctx, state) or (ctx.get("next_question_prompt") or "")

    if removed or added:
        sentences: list[str] = []
        if action == "replace" and len(removed) == 1 and len(added) == 1:
            sentences.append(f"I swapped {removed[0]} for {added[0]} in your {label}.")
        else:
            parts: list[str] = []
            if removed:
                parts.append(f"removed {', '.join(removed)} from your {label}")
            if added:
                parts.append(f"added {', '.join(added)} to your {label}")
            sentences.append("I " + " and ".join(parts) + ".")
        current_state = _modification_current_state_sentence(
            target=target,
            label=label,
            new_value=new_value,
            remaining_items=remaining,
        )
        if current_state:
            sentences.append(current_state)
        if already_selected:
            preview = ", ".join(already_selected[:6])
            suffix = "…" if len(already_selected) > 6 else ""
            seed = _prompt_variant_seed(ctx, state) + "|already"
            sentences.append(
                _select_variant_text(
                    (
                        f"FYI — already in your selection: {preview}{suffix}.",
                        f"Already in your selection: {preview}{suffix}.",
                        f"You already have: {preview}{suffix}.",
                    ),
                    seed,
                )
            )
        if unavailable:
            missing = ", ".join(unavailable[:6])
            suffix = "…" if len(unavailable) > 6 else ""
            sentences.append(f"'{missing}{suffix}' isn't on the menu.")
        sentences.extend(_additional_modification_sentences(mod.get("additional_changes")))
        if follow_up:
            sentences.append(follow_up)
        return " ".join(sentences).strip()

    if action == "remove" or new_value in (None, ""):
        text = f"I removed your {label}."
    else:
        pretty_value = _modification_value_text(target, new_value)
        if isinstance(new_value, bool) and target in _BOOL_TARGETS:
            seed = _prompt_variant_seed(ctx, state) + "|bool_ack"
            text = _bool_modification_sentence(
                target=target,
                value=bool(new_value),
                action=action,
                seed=seed,
            )
        elif action == "add":
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
        "meal_style": "meal style",
        "appetizer_style": "appetizer style",
        "service_style": "service style",
        "cocktail_hour": "cocktail hour",
        "tableware": "tableware",
        "utensils": "utensils",
        "bar_package": "bar package",
        "bar_service": "bar service",
        "coffee_service": "coffee bar",
        "wedding_cake": "wedding cake",
        "partner_name": "partner's name",
        "company_name": "company name",
        "honoree_name": "honoree's name",
        "event_type": "event type",
    }.get(target, target.replace("_", " "))


def _select_variant_text(options: tuple[str, ...], seed: str) -> str:
    if not options:
        return ""
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(options)
    return options[index]


_BOOL_TARGETS = frozenset({
    "drinks",
    "bar_service",
    "coffee_service",
    "linens",
    "cocktail_hour",
    "followup_call_requested",
})


def _bool_modification_sentence(*, target: str, value: bool, action: str, seed: str) -> str:
    label = _modification_label(target)
    if target == "followup_call_requested":
        if value:
            return _select_variant_text(
                (
                    "Follow-up call added.",
                    "I'll flag that you'd like a follow-up call.",
                    "You're on the list for a follow-up call.",
                ),
                seed,
            )
        return _select_variant_text(
            (
                "No follow-up call — works for me.",
                "Skipping the follow-up call.",
                "Follow-up call removed.",
            ),
            seed,
        )

    if value:
        return _select_variant_text(
            (f"Adding {label}.", f"{label.capitalize()} added.", f"{label.capitalize()} is in."),
            seed,
        )
    if action == "remove":
        return _select_variant_text(
            (f"Removed {label}.", f"Dropped {label}.", f"{label.capitalize()} removed."),
            seed,
        )
    return _select_variant_text(
        (f"Skipping {label}.", f"No {label} — that works.", f"{label.capitalize()} not included."),
        seed,
    )


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
            "no_utensils": "no utensils",
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
    # For scalar slots, avoid duplicating the acknowledgement:
    # "I updated your X to Y. Your X is now Y."
    return ""


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
    last_user_msg = ""
    last_ai_msg = ""
    if state:
        phase = str(state.get("conversation_phase") or "")
        msgs = state.get("messages", []) or []
        turn_count = len(msgs)
        # Include the most recent user/AI message text so different conversations
        # produce different seeds even at the same phase + turn_count. Without this,
        # ask_phone always picked the same variant on a fresh chat at turn 4.
        for m in reversed(msgs):
            mtype = getattr(m, "type", "") or (m.get("type") if isinstance(m, dict) else "")
            content = getattr(m, "content", "") or (m.get("content") if isinstance(m, dict) else "")
            if mtype == "human" and not last_user_msg:
                last_user_msg = str(content)[:80]
            elif mtype == "ai" and not last_ai_msg:
                last_ai_msg = str(content)[:80]
            if last_user_msg and last_ai_msg:
                break

    tool = str(ctx.get("tool") or "")
    target = str(ctx.get("next_question_target") or "")
    filled = ",".join(sorted(str(item) for item in (ctx.get("filled_this_turn") or [])))
    return f"{tool}|{target}|{phase}|{turn_count}|{filled}|{last_user_msg}|{last_ai_msg}"


__all__ = ["render"]

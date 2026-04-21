"""
Orchestrator router — single-dispatch tool selection per turn.

Rules (AGENT_SPEC Section 8):
- Exactly ONE tool call per turn. Multi-tool fan-out is forbidden.
- If `conversation_status != "active"`, short-circuit: no tool runs.
- Confidence < 0.80 → action = 'clarify', no tool call.
- Modification intent ALWAYS wins over phase-based routing when the user is
  correcting a previously-filled slot.
- When no modification, pick the Tool that owns the next unfilled required slot.

The router returns an `OrchestratorDecision`. The outer orchestrator shell
dispatches (or asks a clarifying question) based on that decision.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import BaseMessage

from agent.instructor_client import MODEL_ROUTER, extract
from agent.list_slot_reopen import explicit_reopen_list_slot, menu_section_for_phase
from agent.models import OrchestratorDecision, TurnRoutingSignals
from agent.prompt_registry import (
    ROUTER_SYSTEM_PROMPT,
    build_turn_signal_system_prompt,
)
from agent.trace_context import trace_scope
from agent.state import (
    PHASE_COCKTAIL,
    PHASE_COMPLETE,
    PHASE_CONDITIONAL_FOLLOWUP,
    PHASE_DESSERT,
    PHASE_DIETARY,
    PHASE_DRINKS_BAR,
    PHASE_EVENT_DATE,
    PHASE_EVENT_TYPE,
    PHASE_FOLLOWUP,
    PHASE_GREETING,
    PHASE_GUEST_COUNT,
    PHASE_LABOR,
    PHASE_MAIN_MENU,
    PHASE_RENTALS,
    PHASE_REVIEW,
    PHASE_SERVICE_TYPE,
    PHASE_SPECIAL_REQUESTS,
    PHASE_TABLEWARE,
    PHASE_TRANSITION,
    PHASE_VENUE,
    PHASE_WEDDING_CAKE,
    REQUIRED_SLOTS,
    SLOT_NAMES,
    filled_slot_summary,
    get_slot_value,
    is_filled,
    unfilled_required,
)
from agent.tools.add_ons_tool import (
    _next_target as _addons_next_target,
    _normalize_labor_services,
)
from agent.tools.structured_choice import normalize_structured_choice as _normalize_choice
from agent.tools.finalization_tool import _next_target as _finalization_next_target

logger = logging.getLogger(__name__)


CONFIDENCE_THRESHOLD = 0.80

# Words that almost always mean "I want to change something already filled."
_MOD_KEYWORDS = frozenset({
    "change", "update", "replace", "swap", "remove", "delete", "edit",
    "instead", "switch", "different", "wrong", "correct", "modify",
    "fix", "actually", "no wait", "wait", "i meant", "cancel",
    "take out", "take off", "add back", "bring back", "put back", "undo",
})

_VENUE_TBD_TOKENS = frozenset({
    "tbd",
    "tbd_confirm_call",
    "to be determined",
    "confirm on call",
    "confirm venue on call",
    "venue confirm on call",
    "confirm later",
    "confirm venue later",
    "venue confirm later",
    "i'll confirm later",
    "not decided yet",
    "venue tbd - will confirm later",
    "venue tbd - confirm later",
})

# Phrases that mean "keep going, ask me the next question."
_CONTINUATIONS = frozenset({
    "nice", "ok", "okay", "sure", "continue", "next", "proceed",
    "sounds good", "looks good", "great", "perfect", "done",
    "move on", "go ahead", "that works", "go", "yes please",
    "let's go", "lets go", "got it", "show me", "show",
    "see the menu", "what are my options", "k", "cool",
})

_ADDONS_STRUCTURED_VALUES: dict[str, frozenset[str]] = {
    "ask_drinks_interest": frozenset({
        "yes", "no", "yes, add drinks", "no thanks",
    }),
    "ask_drinks_setup": frozenset({
        "coffee only", "bar only", "coffee and bar", "both", "neither",
        "bar service only", "both coffee & bar", "coffee bar only",
    }),
    "ask_bar_package": frozenset({
        "beer_wine", "beer_wine_signature", "full_open_bar",
        "beer & wine", "beer and wine", "signature", "open bar",
    }),
    "ask_tableware_gate": frozenset({
        "standard_disposable", "upgrade", "no_tableware",
        "standard disposable", "standard disposable (included)",
        "standard disposable (included, no upgrade)",
        "yes i'd like to upgrade", "yes, i'd like to upgrade",
        "silver_disposable", "gold_disposable", "china",
        "silver disposable", "gold disposable", "full china", "real china",
        "silver disposable (+$1/pp)", "gold disposable (+$1/pp)",
        "no tableware", "no tableware needed", "none",
    }),
    "ask_tableware": frozenset({
        "silver_disposable", "gold_disposable", "china",
        "silver disposable", "gold disposable", "full china", "real china",
        "silver disposable (+$1/pp)", "gold disposable (+$1/pp)",
    }),
    "ask_utensils": frozenset({
        "standard_plastic", "eco_biodegradable", "bamboo",
        "standard plastic", "standard plastic (included)",
        "eco / biodegradable", "eco-friendly / biodegradable",
    }),
    "ask_rentals_gate": frozenset({
        "yes", "no", "yes, add rentals", "no rentals needed",
    }),
}

_FINALIZATION_STRUCTURED_VALUES: dict[str, frozenset[str]] = {
    "ask_special_requests_gate": frozenset({
        "yes", "no", "yes, add a special request", "no special requests",
    }),
    "ask_dietary_gate": frozenset({
        "yes", "no", "yes, note food or health needs", "no dietary concerns",
    }),
    "ask_additional_notes_gate": frozenset({
        "yes", "no", "yes, add a final note", "no additional notes",
    }),
    "ask_followup_call": frozenset({
        "yes", "no", "yes, schedule a call", "no call needed",
        "yes, please call me", "no, no call needed",
    }),
    "review": frozenset({
        "confirm", "change", "yes, looks good", "no, make changes",
    }),
}

_WEDDING_CAKE_STRUCTURED_VALUES: dict[str, frozenset[str]] = {
    "ask_wedding_cake": frozenset({
        "yes", "no", "yes please", "no thanks", "skip", "yes, add a wedding cake",
    }),
    "ask_wedding_cake_flavor": frozenset({
        "yellow", "white", "almond", "chocolate", "carrot", "red velvet",
        "bananas foster", "whiskey caramel", "lemon", "spice", "funfetti",
        "pumpkin spice", "cookies and cream", "strawberry", "coconut",
    }),
    "ask_wedding_cake_filling": frozenset({
        "butter cream", "lemon curd", "raspberry jam", "strawberry jam",
        "cream cheese icing", "peanut butter cream", "mocha buttercream",
        "salted caramel buttercream", "cinnamon butter cream",
    }),
    "ask_wedding_cake_buttercream": frozenset({
        "signature", "chocolate", "cream cheese frosting",
    }),
}

_SERVICE_TYPE_STRUCTURED_VALUES = frozenset({
    "onsite",
    "on-site",
    "on site",
    "onsite - staff present at your event",
    "onsite (staff present)",
    "dropoff",
    "drop-off",
    "drop off",
    "drop-off - delivery only, no staff",
    "drop-off (no staff)",
})

_MENU_SERVICE_STYLE_VALUES = frozenset({
    "cocktail hour",
    "cocktail",
    "reception",
    "reception only",
    "full reception",
    "both",
    "cocktail hour + reception",
})

_MENU_APPETIZER_STYLE_VALUES = frozenset({
    "passed around",
    "passed",
    "pass",
    "station",
    "stations",
})

_MENU_MEAL_STYLE_VALUES = frozenset({
    "plated",
    "plated-style",
    "plated style",
    "buffet",
    "buffet-style",
    "buffet style",
    "buffet-styled",
})

_MENU_DESSERT_GATE_VALUES = frozenset({
    "yes",
    "yes please",
    "show desserts",
    "show me desserts",
    "desserts",
    "add desserts",
    "skip dessert",
    "no thanks",
    "skip",
})


def _can_reopen_list_slot(slot: str, state: dict) -> bool:
    slots = state["slots"]
    phase = state.get("conversation_phase") or PHASE_GREETING

    if is_filled(slots, slot):
        return True
    if slot == "desserts" and get_slot_value(slots, "__gate_desserts") is not None:
        return True
    if slot == "rentals" and (
        get_slot_value(slots, "rentals") is not None or get_slot_value(slots, "linens") is not None
    ):
        return True
    if slot == "appetizers" and phase in {
        PHASE_MAIN_MENU,
        PHASE_DESSERT,
        PHASE_DRINKS_BAR,
        PHASE_TABLEWARE,
        PHASE_RENTALS,
        PHASE_LABOR,
        PHASE_SPECIAL_REQUESTS,
        PHASE_DIETARY,
        PHASE_FOLLOWUP,
        PHASE_REVIEW,
    }:
        return True
    if slot == "selected_dishes" and phase in {
        PHASE_DESSERT,
        PHASE_DRINKS_BAR,
        PHASE_TABLEWARE,
        PHASE_RENTALS,
        PHASE_LABOR,
        PHASE_SPECIAL_REQUESTS,
        PHASE_DIETARY,
        PHASE_FOLLOWUP,
        PHASE_REVIEW,
    }:
        return True
    return False


def _looks_like_structured_addons_answer(message: str, state: dict) -> bool:
    phase = state.get("conversation_phase") or PHASE_GREETING
    if phase not in {PHASE_DRINKS_BAR, PHASE_TABLEWARE, PHASE_RENTALS, PHASE_LABOR}:
        return False

    target = _addons_next_target(state["slots"])
    msg = _normalize_choice(message)

    if target == "ask_labor_services":
        return _normalize_labor_services([msg]) is not None

    return msg in _ADDONS_STRUCTURED_VALUES.get(target, frozenset())


def _looks_like_wedding_cake_reopen(message: str, state: dict) -> bool:
    slots = state["slots"]
    if get_slot_value(slots, "event_type") != "Wedding":
        return False

    msg = _normalize_choice(message)
    if "wedding cake" not in msg and "cake" not in msg:
        return False

    revisit_markers = {
        "again",
        "add back",
        "bring back",
        "put back",
        "choose",
        "reselect",
        "redo",
        "want it again",
        "need it again",
    }
    return any(marker in msg for marker in revisit_markers)


def _looks_like_structured_basic_info_answer(message: str, state: dict) -> bool:
    phase = state.get("conversation_phase") or PHASE_GREETING
    if phase != PHASE_SERVICE_TYPE:
        return False
    return _normalize_choice(message) in _SERVICE_TYPE_STRUCTURED_VALUES


def _looks_like_structured_menu_answer(message: str, state: dict) -> bool:
    phase = state.get("conversation_phase") or PHASE_GREETING
    if phase not in {PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT}:
        return False

    slots = state["slots"]
    msg = _normalize_choice(message)

    if phase == PHASE_COCKTAIL:
        if not get_slot_value(slots, "cocktail_hour"):
            return msg in _MENU_SERVICE_STYLE_VALUES
        if is_filled(slots, "appetizers") and not get_slot_value(slots, "appetizer_style"):
            return msg in _MENU_APPETIZER_STYLE_VALUES
        return False

    if phase == PHASE_MAIN_MENU:
        return bool(get_slot_value(slots, "selected_dishes")) and not get_slot_value(slots, "meal_style") and msg in _MENU_MEAL_STYLE_VALUES

    return not get_slot_value(slots, "desserts") and get_slot_value(slots, "__gate_desserts") is not True and msg in _MENU_DESSERT_GATE_VALUES


def _looks_like_structured_finalization_answer(message: str, state: dict) -> bool:
    phase = state.get("conversation_phase") or PHASE_GREETING
    if phase not in {PHASE_SPECIAL_REQUESTS, PHASE_DIETARY, PHASE_FOLLOWUP, PHASE_REVIEW}:
        return False

    target = _finalization_next_target(state["slots"])
    msg = _normalize_choice(message)
    return msg in _FINALIZATION_STRUCTURED_VALUES.get(target, frozenset())


def _looks_like_structured_wedding_cake_answer(message: str, state: dict) -> bool:
    phase = state.get("conversation_phase") or PHASE_GREETING
    if phase != PHASE_WEDDING_CAKE:
        return False

    slots = state["slots"]
    msg = _normalize_choice(message)

    if not get_slot_value(slots, "__wedding_cake_gate"):
        target = "ask_wedding_cake"
    elif not get_slot_value(slots, "__wedding_cake_flavor"):
        target = "ask_wedding_cake_flavor"
    elif not get_slot_value(slots, "__wedding_cake_filling"):
        target = "ask_wedding_cake_filling"
    else:
        target = "ask_wedding_cake_buttercream"

    return msg in _WEDDING_CAKE_STRUCTURED_VALUES.get(target, frozenset())


def _looks_like_modification_intent(message: str) -> bool:
    msg = _normalize_choice(message)
    if not msg:
        return False
    if any(kw in msg for kw in _MOD_KEYWORDS):
        return True
    if re.search(r"\b(?:add|readd|re-add|bring|put)\b.*\bback\b", msg):
        return True
    if re.search(r"\b(?:remove|delete|drop|replace|swap)\b", msg):
        return True
    return False


def _looks_like_tbd_venue_answer(message: str) -> bool:
    msg = _normalize_choice(message)
    if msg in _VENUE_TBD_TOKENS:
        return True
    if (
        msg.startswith("venue tbd")
        or ("tbd" in msg and "venue" in msg)
        or "to be determined" in msg
        or "confirm later" in msg
        or "confirm on call" in msg
        or ("confirm" in msg and "venue" in msg and ("call" in msg or "later" in msg))
        or "not decided yet" in msg
    ):
        return True
    return False


def _quick_route(message: str, state: dict) -> str | None:
    """Bypass the LLM for obvious cases. Returns tool name or None."""
    msg = message.strip().lower()
    phase = state.get("conversation_phase") or PHASE_GREETING
    reopen_slot = explicit_reopen_list_slot(message, phase)

    if get_slot_value(state["slots"], "__pending_modification_choice"):
        return "modification_tool"
    if get_slot_value(state["slots"], "__pending_modification_request"):
        return "modification_tool"
    if get_slot_value(state["slots"], "__pending_menu_choice"):
        return "menu_selection_tool"

    if reopen_slot and _can_reopen_list_slot(reopen_slot, state):
        return "modification_tool"

    if _looks_like_wedding_cake_reopen(message, state):
        return "modification_tool"

    # Reopening a previous menu section from a later phase should route to the
    # modification tool so the picker can be shown again without guessing items.
    if phase in {PHASE_DRINKS_BAR, PHASE_TABLEWARE, PHASE_RENTALS, PHASE_LABOR, PHASE_SPECIAL_REQUESTS, PHASE_DIETARY, PHASE_FOLLOWUP, PHASE_REVIEW}:
        if (
            "dessert" in msg
            or "appetizer" in msg
            or "main menu" in msg
            or "main dish" in msg
            or "mains" in msg
        ) and any(term in msg for term in {"show", "menu", "change", "actually", "add", "have", "want"}):
            return "modification_tool"

    # Plain continuations — just advance the current phase, no LLM needed.
    if msg in _CONTINUATIONS:
        return _fallback_tool(state)

    if phase == PHASE_VENUE and _looks_like_tbd_venue_answer(message):
        return "basic_info_tool"

    if _looks_like_structured_basic_info_answer(message, state):
        return "basic_info_tool"

    if _looks_like_structured_menu_answer(message, state):
        return "menu_selection_tool"

    if _looks_like_structured_addons_answer(message, state):
        return "add_ons_tool"

    if _looks_like_structured_wedding_cake_answer(message, state):
        return "basic_info_tool"

    if _looks_like_structured_finalization_answer(message, state):
        return "finalization_tool"

    # Modification intent: keyword present AND at least one slot already filled.
    if _looks_like_modification_intent(message):
        if filled_slot_summary(state["slots"]):
            return "modification_tool"

    return None


# Phase → owning Tool. Single source of truth for "who handles this phase".
_PHASE_TO_TOOL: dict[str, str] = {
    PHASE_GREETING: "basic_info_tool",
    PHASE_EVENT_TYPE: "basic_info_tool",
    PHASE_CONDITIONAL_FOLLOWUP: "basic_info_tool",
    PHASE_WEDDING_CAKE: "basic_info_tool",
    PHASE_SERVICE_TYPE: "basic_info_tool",
    PHASE_EVENT_DATE: "basic_info_tool",
    PHASE_VENUE: "basic_info_tool",
    PHASE_GUEST_COUNT: "basic_info_tool",
    PHASE_TRANSITION: "menu_selection_tool",
    PHASE_COCKTAIL: "menu_selection_tool",
    PHASE_MAIN_MENU: "menu_selection_tool",
    PHASE_DESSERT: "menu_selection_tool",
    PHASE_DRINKS_BAR: "add_ons_tool",
    PHASE_TABLEWARE: "add_ons_tool",
    PHASE_RENTALS: "add_ons_tool",
    PHASE_LABOR: "add_ons_tool",
    PHASE_SPECIAL_REQUESTS: "finalization_tool",
    PHASE_DIETARY: "finalization_tool",
    PHASE_FOLLOWUP: "finalization_tool",
    PHASE_REVIEW: "finalization_tool",
}


_TURN_SIGNAL_SYSTEM_PROMPT = build_turn_signal_system_prompt(list(SLOT_NAMES))


def _history_for_llm(history: list[BaseMessage]) -> list[dict]:
    out: list[dict] = []
    for m in history[-8:]:
        role = "user" if getattr(m, "type", "") == "human" else "assistant"
        out.append({"role": role, "content": m.content})
    return out


def _context_block(state: dict) -> str:
    slots = state["slots"]
    phase = state.get("conversation_phase") or PHASE_GREETING
    filled = filled_slot_summary(slots)
    missing = unfilled_required(slots)
    active_section = menu_section_for_phase(phase)
    # Keep the context short — one line per fact category.
    lines = [
        f"current_phase: {phase}",
        f"active_menu_section: {active_section or '(none)'}",
        f"conversation_status: {get_slot_value(slots, 'conversation_status') or 'active'}",
        f"filled_slots: {', '.join(f'{k}={v}' for k, v in filled.items()) or '(none)'}",
        f"missing_required: {', '.join(missing) or '(none)'}",
    ]
    return "\n".join(lines)


def _fallback_tool(state: dict) -> str:
    """Deterministic fallback when the LLM router is uncertain or errors."""
    phase = state.get("conversation_phase") or PHASE_GREETING
    if phase == PHASE_COMPLETE:
        return "finalization_tool"
    return _PHASE_TO_TOOL.get(phase, "basic_info_tool")


async def _extract_turn_signals(
    *,
    message: str,
    history: list[BaseMessage],
    state: dict,
) -> TurnRoutingSignals | None:
    user_block = (
        f"User message: {message}\n\n"
        f"Conversation context:\n{_context_block(state)}"
    )
    with trace_scope(route_stage="turn_signals"):
        return await extract(
            schema=TurnRoutingSignals,
            system=_TURN_SIGNAL_SYSTEM_PROMPT,
            user_message=user_block,
            history=_history_for_llm(history),
            model=MODEL_ROUTER,
            max_tokens=180,
        )


async def route(
    *,
    message: str,
    history: list[BaseMessage],
    state: dict,
) -> OrchestratorDecision:
    """Decide which Tool handles this turn (or whether to clarify).

    Never raises. Returns a deterministic phase-based fallback if the LLM
    call errors or the schema fails to validate.
    """
    status = get_slot_value(state["slots"], "conversation_status") or "active"
    if status != "active":
        return OrchestratorDecision(
            action="no_action",
            tool_calls=[],
            confidence=1.0,
        )

    # Fast path — skip LLM for obvious continuations and modification intents.
    quick = _quick_route(message, state)
    if quick:
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name=quick, reason="quick_route")],
            confidence=1.0,
        )

    signals = await _extract_turn_signals(message=message, history=history, state=state)
    if isinstance(signals, TurnRoutingSignals) and signals.confidence >= CONFIDENCE_THRESHOLD:
        if signals.intent == "reopen_previous_section":
            slot = signals.referenced_slot
            if slot is None or _can_reopen_list_slot(slot, state):
                from agent.models import ToolCall as _TC
                return OrchestratorDecision(
                    action="tool_call",
                    tool_calls=[_TC(tool_name="modification_tool", reason=f"turn_signals:{signals.intent}")],
                    confidence=signals.confidence,
                )
        if signals.intent == "modify_existing":
            slot = signals.referenced_slot
            if slot is None or slot in SLOT_NAMES:
                if slot is None or is_filled(state["slots"], slot):
                    from agent.models import ToolCall as _TC
                    return OrchestratorDecision(
                        action="tool_call",
                        tool_calls=[_TC(tool_name="modification_tool", reason=f"turn_signals:{signals.intent}")],
                        confidence=signals.confidence,
                    )
        if signals.intent in {"answer_current_prompt", "continue_current_flow"}:
            tool = _fallback_tool(state)
            from agent.models import ToolCall as _TC
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[_TC(tool_name=tool, reason=f"turn_signals:{signals.intent}")],
                confidence=signals.confidence,
            )
        if signals.intent == "provide_other_information" and signals.proposed_tool:
            from agent.models import ToolCall as _TC
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[_TC(tool_name=signals.proposed_tool, reason=f"turn_signals:{signals.intent}")],
                confidence=signals.confidence,
            )
        if signals.intent == "unclear":
            return OrchestratorDecision(
                action="clarify",
                tool_calls=[],
                confidence=signals.confidence,
            )

    user_block = (
        f"User message: {message}\n\n"
        f"Conversation context:\n{_context_block(state)}"
    )

    with trace_scope(route_stage="decision"):
        decision = await extract(
            schema=OrchestratorDecision,
            system=ROUTER_SYSTEM_PROMPT,
            user_message=user_block,
            history=_history_for_llm(history),
            model=MODEL_ROUTER,
            max_tokens=200,
        )

    if decision is None:
        logger.warning("Router extraction returned None — using phase fallback")
        return _phase_fallback_decision(state)

    # Enforce single-dispatch hard rule, even if the LLM returned multiple.
    if decision.action == "tool_call":
        if not decision.tool_calls:
            return _phase_fallback_decision(state)
        decision.tool_calls = decision.tool_calls[:1]
        if decision.confidence < CONFIDENCE_THRESHOLD:
            return OrchestratorDecision(
                action="clarify",
                tool_calls=[],
                confidence=decision.confidence,
            )

    # Phase lock: for add_ons and finalization phases, if the router picked a
    # different tool and it isn't modification_tool, override with the phase owner.
    # This prevents conversational fillers from jumping past required steps.
    if decision.action == "tool_call" and decision.tool_calls:
        chosen = decision.tool_calls[0].tool_name
        phase = state.get("conversation_phase") or PHASE_GREETING
        expected = _PHASE_TO_TOOL.get(phase)
        _PHASE_LOCKED = {
            # Wedding cake phase
            PHASE_WEDDING_CAKE,
            # Menu phases — must stay with menu_selection_tool
            PHASE_TRANSITION, PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT,
            # Add-ons phases
            PHASE_DRINKS_BAR, PHASE_TABLEWARE, PHASE_RENTALS, PHASE_LABOR,
            # Finalization phases
            PHASE_SPECIAL_REQUESTS, PHASE_DIETARY, PHASE_FOLLOWUP, PHASE_REVIEW,
        }
        if (
            phase in _PHASE_LOCKED
            and expected is not None
            and chosen != expected
            and chosen != "modification_tool"
        ):
            if _looks_like_modification_intent(message) and filled_slot_summary(state["slots"]):
                logger.info(
                    "phase_lock: overriding %s -> modification_tool for phase %s",
                    chosen, phase,
                )
                from agent.models import ToolCall as _TC
                decision.tool_calls = [_TC(tool_name="modification_tool", reason="phase_lock_modification")]
                return decision
            logger.info(
                "phase_lock: overriding %s → %s for phase %s",
                chosen, expected, phase,
            )
            from agent.models import ToolCall as _TC
            decision.tool_calls = [_TC(tool_name=expected, reason="phase_lock")]

    return decision


def _phase_fallback_decision(state: dict) -> OrchestratorDecision:
    tool = _fallback_tool(state)
    from agent.models import ToolCall

    return OrchestratorDecision(
        action="tool_call",
        tool_calls=[ToolCall(tool_name=tool, reason="phase_fallback")],
        confidence=1.0,
    )


__all__ = ["route", "CONFIDENCE_THRESHOLD"]

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

import asyncio
import logging
import re
from typing import Any

from langchain_core.messages import BaseMessage

from agent.instructor_client import MODEL_ROUTER, extract
from agent.tools.base import history_for_llm
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
# Hard markers: alone signal modification intent unambiguously.
_HARD_MOD_KEYWORDS = frozenset({
    "change", "update", "replace", "swap", "remove", "delete", "edit",
    "switch", "different", "wrong", "correct", "modify", "fix",
    "take out", "take off", "add back", "bring back", "put back", "undo",
    "not a", "not an", "it is a", "it's a",
})

# Soft markers: hedging words that only signal modification when paired with a hard marker
# or an explicit removal/replacement verb. Alone they appear in first fills too
# ("actually, chocolate please" as a first wedding-cake flavor answer).
_SOFT_MOD_KEYWORDS = frozenset({
    "actually", "no wait", "wait", "i meant", "cancel",
    "mistake", "my bad", "mb", "sorry", "oops", "scratch that", "nevermind",
    "never mind", "instead",
})

_MOD_KEYWORDS = _HARD_MOD_KEYWORDS | _SOFT_MOD_KEYWORDS

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

    has_hard = False
    has_soft = False

    for kw in _HARD_MOD_KEYWORDS:
        if " " in kw:
            if kw in msg:
                has_hard = True
                break
        elif re.search(rf"\b{re.escape(kw)}\b", msg):
            has_hard = True
            break

    if not has_hard:
        for kw in _SOFT_MOD_KEYWORDS:
            if " " in kw:
                if kw in msg:
                    has_soft = True
                    break
            elif re.search(rf"\b{re.escape(kw)}\b", msg):
                has_soft = True
                break

    if has_hard:
        return True

    # Soft markers alone only count as modification if paired with an
    # explicit change/removal verb so "actually, I'd like salmon" (first fill)
    # doesn't block the free-text autoroute.
    if has_soft:
        return bool(re.search(r"\b(?:remove|delete|drop|replace|swap|change|update|fix|edit)\b", msg))

    if re.search(r"\b(?:add|readd|re-add|bring|put)\b.*\bback\b", msg):
        return True
    if re.search(r"\b(?:remove|delete|drop|replace|swap)\b", msg):
        return True
    # "add X to/in menu" or "add [bar|cake|rentals|drinks|…]" outside a first-fill
    # context. These are mid-flow additions to already-progressed intake, not answers.
    if re.search(
        r"\badd\b.{0,40}\b(?:bar|bar service|cocktail|appetizer|appetizers|dessert|desserts|"
        r"rental|rentals|linen|linens|labor|staff|wedding cake|cake|drink|drinks)\b",
        msg,
    ):
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


_YES_TOKENS = frozenset({
    "yes", "yep", "yeah", "yup", "sure", "ok", "okay", "of course",
    "absolutely", "definitely", "please do", "i do", "yes please",
    "yes ok", "sounds good", "go ahead", "please", "do it",
})
_NO_TOKENS = frozenset({
    "no", "nope", "nah", "n", "no thanks", "no thank you", "skip",
    "none", "not really", "no need", "pass", "nothing", "i dont",
    "i don't", "neither", "no special requests", "no dietary concerns",
    "no additional notes", "no, don't schedule a call", "no call needed",
})


def _quick_route(message: str, state: dict) -> str | None:
    """Bypass the LLM only for explicit internal state markers."""
    slots = state["slots"]

    if get_slot_value(slots, "__pending_modification_choice"):
        return "modification_tool"
    if get_slot_value(slots, "__pending_modification_request"):
        return "modification_tool"
    if get_slot_value(slots, "__pending_menu_choice"):
        return "menu_selection_tool"

    phase = state.get("conversation_phase") or PHASE_GREETING
    msg_lower = _normalize_choice(message)

    # Review recap: "change" always goes to modification_tool so the user can
    # pick what to modify. Never gate on finalization state — if the user says
    # "change" at the recap, they want to edit, full stop.
    if phase == PHASE_REVIEW and msg_lower in {
        "change", "no, make changes", "i need to change something", "make changes",
    }:
        return "modification_tool"

    # Route bare yes/no directly to the tool that owns the pending gate
    # question — no slot filling here. The tool itself handles the fill
    # so that _next_target, cascade, and structured_answer all run in
    # the correct order without a race condition.
    pending = get_slot_value(slots, "__pending_confirmation")
    if pending:
        if msg_lower in _YES_TOKENS or msg_lower in _NO_TOKENS:
            return pending.get("tool", "finalization_tool")

    # Free-text basic-info phases: the phase owner is always basic_info_tool,
    # and the user's message is almost always a direct answer (name, date,
    # venue, guest count, etc). Skipping the router LLM saves ~2s/turn on
    # these phases. We still defer to the LLM when the message looks like a
    # modification, a meta-command, or anything else ambiguous.
    if phase in _FREE_TEXT_AUTOROUTE_PHASES:
        # In free-text phases, soft markers (sorry, actually, wait, i meant…)
        # almost always mean the user is correcting a prior answer, not giving
        # a first fill. Defer to the LLM router which can detect the correction.
        has_soft_marker = any(
            (re.search(rf"\b{re.escape(kw)}\b", msg_lower) if " " not in kw else kw in msg_lower)
            for kw in _SOFT_MOD_KEYWORDS
        )
        if (
            msg_lower
            and not _looks_like_modification_intent(message)
            and not has_soft_marker
            and not _looks_like_meta_command(msg_lower)
            and not _contains_out_of_phase_topic(msg_lower)
        ):
            return "basic_info_tool"

    # Structured option-based answers — skip router LLM for known exact-match
    # inputs. These detection functions existed but were never wired up here.
    if msg_lower and not _looks_like_modification_intent(message) and not _looks_like_meta_command(msg_lower):
        if _looks_like_structured_wedding_cake_answer(message, state):
            return "basic_info_tool"
        if _looks_like_structured_basic_info_answer(message, state):
            return "basic_info_tool"
        if _looks_like_structured_addons_answer(message, state):
            return _PHASE_TO_TOOL.get(phase, "add_ons_tool")
        if _looks_like_structured_menu_answer(message, state):
            return "menu_selection_tool"
        if _looks_like_structured_finalization_answer(message, state):
            return "finalization_tool"

    return None


_FREE_TEXT_AUTOROUTE_PHASES = frozenset({
    PHASE_GREETING,
    PHASE_EVENT_TYPE,
    PHASE_CONDITIONAL_FOLLOWUP,
    PHASE_EVENT_DATE,
    PHASE_VENUE,
    PHASE_GUEST_COUNT,
})


_META_COMMAND_MARKERS = (
    "go back",
    "start over",
    "restart",
    "reset",
    "help",
    "what can you",
    "can you",
    "show me",
    "show the",
    "let me see",
    "?",
)

# Keywords that, when present in a free-text phase message, indicate the user
# is simultaneously addressing an out-of-phase topic (e.g. "May 25, and add
# appetizers"). In that case we defer to the LLM router so it can split intent.
_OUT_OF_PHASE_MARKERS = frozenset({
    "appetizer", "appetizers", "starter", "starters",
    "main dish", "main dishes", "entree", "entrees",
    "dessert", "desserts",
    "bar service", "bar package", "drinks",
    "tableware", "utensils", "linens", "rentals",
    "wedding cake",
    # Event-identity corrections in partner/honoree/company phases
    "event type", "type of event", "event is", "it is a", "it's a",
})


def _looks_like_meta_command(msg_lower: str) -> bool:
    """Conservative check for messages that should still hit the LLM router.

    Question-asking, meta-commands, and anything that isn't clearly answering
    the current question falls back to the LLM for safety.
    """
    if not msg_lower:
        return False
    for marker in _META_COMMAND_MARKERS:
        if marker in msg_lower:
            return True
    return False


def _contains_out_of_phase_topic(msg_lower: str) -> bool:
    """Return True when a free-text answer also mentions a different intake section.

    Prevents the free-text autoroute from silently swallowing multi-topic messages
    like "May 25, and can we add appetizers too?" — those need the LLM router.
    """
    return any(marker in msg_lower for marker in _OUT_OF_PHASE_MARKERS)


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
    return history_for_llm(history, max_messages=8)


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

    user_block = (
        f"User message: {message}\n\n"
        f"Conversation context:\n{_context_block(state)}"
    )

    # Fire both extractions simultaneously. On the confident-signals path we
    # cancel the decision task (saves one full LLM round-trip). On the
    # low-confidence path the decision result is already in-flight.
    with trace_scope(route_stage="turn_signals"):
        signals_task = asyncio.create_task(
            extract(
                schema=TurnRoutingSignals,
                system=_TURN_SIGNAL_SYSTEM_PROMPT,
                user_message=user_block,
                history=_history_for_llm(history),
                model=MODEL_ROUTER,
                max_tokens=180,
            )
        )
    with trace_scope(route_stage="decision"):
        decision_task = asyncio.create_task(
            extract(
                schema=OrchestratorDecision,
                system=ROUTER_SYSTEM_PROMPT,
                user_message=user_block,
                history=_history_for_llm(history),
                model=MODEL_ROUTER,
                max_tokens=200,
            )
        )

    signals = await signals_task

    def _cancel_decision() -> None:
        if not decision_task.done():
            decision_task.cancel()

    if isinstance(signals, TurnRoutingSignals) and signals.confidence >= CONFIDENCE_THRESHOLD:
        if signals.intent == "reopen_previous_section":
            slot = signals.referenced_slot
            if slot is None or _can_reopen_list_slot(slot, state):
                _cancel_decision()
                from agent.models import ToolCall as _TC
                return OrchestratorDecision(
                    action="tool_call",
                    tool_calls=[_TC(tool_name="modification_tool", reason=f"turn_signals:{signals.intent}")],
                    confidence=signals.confidence,
                )
        if signals.intent == "modify_existing":
            slot = signals.referenced_slot
            if slot is None or slot in SLOT_NAMES:
                # Allow through even if the slot isn't filled yet — the user may
                # be adding something they skipped earlier (e.g. "add bar in menu"
                # in finalization phase when bar_package was never set). Intent
                # wins over slot-fill state.
                _cancel_decision()
                from agent.models import ToolCall as _TC
                return OrchestratorDecision(
                    action="tool_call",
                    tool_calls=[_TC(tool_name="modification_tool", reason=f"turn_signals:{signals.intent}")],
                    confidence=signals.confidence,
                )
        if signals.intent in {"answer_current_prompt", "continue_current_flow"}:
            _cancel_decision()
            tool = _fallback_tool(state)
            from agent.models import ToolCall as _TC
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[_TC(tool_name=tool, reason=f"turn_signals:{signals.intent}")],
                confidence=signals.confidence,
            )
        if signals.intent == "provide_other_information" and signals.proposed_tool:
            _cancel_decision()
            from agent.models import ToolCall as _TC
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[_TC(tool_name=signals.proposed_tool, reason=f"turn_signals:{signals.intent}")],
                confidence=signals.confidence,
            )
        if signals.intent == "unclear":
            _cancel_decision()
            return OrchestratorDecision(
                action="clarify",
                tool_calls=[],
                confidence=signals.confidence,
            )

    try:
        decision = await decision_task
    except asyncio.CancelledError:
        decision = None

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
        ):
            # modification_tool is always allowed through — users can modify at
            # any phase (the LLM already passed the 0.80 confidence gate above).
            # Structured first-fill answers ("plated", "upgrade", "ADD DESSERTS")
            # are caught by _quick_route before reaching this code, so
            # high-confidence modification_tool picks here are genuine edits.
            if chosen != "modification_tool":
                logger.info(
                    "phase_lock: overriding %s -> %s for phase %s",
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

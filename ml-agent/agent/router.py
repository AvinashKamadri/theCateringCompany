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
from pydantic import BaseModel as _BaseModel

from agent.instructor_client import MODEL_ROUTER, extract, generate_text
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
    validate_pending_state,
)
from agent.tools.add_ons_tool import (
    _next_target as _addons_next_target,
    _normalize_labor_services,
)
from agent.tools.structured_choice import normalize_structured_choice as _normalize_choice
from agent.tools.finalization_tool import _next_target as _finalization_next_target

logger = logging.getLogger(__name__)


CONFIDENCE_THRESHOLD = 0.80

# FLAG-9: phase-specific clarifying questions for the "unclear" intent path.
# When TurnRoutingSignals can't determine intent, return a targeted re-ask
# rather than an empty clarifying_question that forces the LLM generator to guess.
_PHASE_CLARIFYING_QUESTIONS: dict[str, str] = {
    PHASE_GREETING:            "Sorry — what's your name?",
    PHASE_EVENT_TYPE:          "What kind of event is this — wedding, birthday, corporate, or something else?",
    PHASE_CONDITIONAL_FOLLOWUP: "Could you clarify that a bit? I want to make sure I get the name right.",
    PHASE_EVENT_DATE:          "What date are you thinking for the event?",
    PHASE_VENUE:               "Where's the event happening? Or say TBD if it's not locked in yet.",
    PHASE_GUEST_COUNT:         "How many people are you expecting? Even a rough number works.",
    PHASE_SERVICE_TYPE:        "Did you want drop-off delivery or full onsite service with staff?",
    PHASE_COCKTAIL:            "Not sure I caught that — want to do a cocktail hour, the full reception, or both?",
    PHASE_MAIN_MENU:           "Could you repeat that? I want to make sure I pick the right dishes.",
    PHASE_DESSERT:             "Want to add desserts, or skip them?",
    PHASE_DRINKS_BAR:          "Did you want to add drinks or bar service, or skip for now?",
    PHASE_TABLEWARE:           "Could you clarify what you'd like for tableware?",
    PHASE_RENTALS:             "Did you need any rentals like linens, tables, or chairs?",
    PHASE_LABOR:               "What onsite labor services did you want to include?",
    PHASE_SPECIAL_REQUESTS:    "Did you have a special request in mind, or would you like to skip?",
    PHASE_DIETARY:             "Any dietary needs or food allergies to note, or are we good?",
    PHASE_FOLLOWUP:            "Want a quick follow-up call, or are you good to go from here?",
    PHASE_REVIEW:              "Does the summary look right, or is there something you'd like to change?",
}

# Words that almost always mean "I want to change something already filled."
# Hard markers: alone signal modification intent unambiguously.
_HARD_MOD_KEYWORDS = frozenset({
    "change", "update", "replace", "swap", "remove", "delete", "edit",
    "switch", "different", "wrong", "correct", "modify", "fix",
    "take out", "take off", "add back", "bring back", "put back", "undo",
    "not a", "not an", "it is a", "it's a", "its a", "its an",
    # FLAG-2: common natural-language removal phrases missed before
    "get rid of", "lose the", "ditch", "drop the", "no more",
})

# Soft markers: hedging words that only signal modification when paired with a hard marker
# or an explicit removal/replacement verb. Alone they appear in first fills too
# ("actually, chocolate please" as a first wedding-cake flavor answer).
_SOFT_MOD_KEYWORDS = frozenset({
    "actually", "no wait", "wait", "i meant", "cancel",
    "mistake", "my bad", "mb", "sorry", "oops", "scratch that", "nevermind",
    "never mind", "instead",
    # Common typos for "actually" — users sometimes mistype and we don't want
    # the modification intent to be silently dropped.
    "acutally", "actaully", "acually",
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
        change_verb = bool(re.search(r"\b(?:remove|delete|drop|replace|swap|change|update|fix|edit)\b", msg))
        if change_verb:
            return True
        # FLAG-1: "actually/wait/sorry ... instead" — hedging + alternative phrasing
        # is almost always a correction ("actually salmon instead"). Guard: require
        # the hedging word to be present alongside "instead" so bare "instead" in a
        # first-fill answer (e.g. "I'd like a reception instead") doesn't trigger this.
        if re.search(r"\b(?:actually|no wait|wait|sorry|i meant)\b", msg) and re.search(r"\binstead\b", msg):
            return True
        return False

    if re.search(r"\b(?:add|readd|re-add|bring|put)\b.*\bback\b", msg):
        return True
    if re.search(r"\b(?:remove|delete|drop|replace|swap)\b", msg):
        return True
    # "add X to/in menu" or "add [bar|cake|rentals|drinks|…]" outside a first-fill
    # context. These are mid-flow additions to already-progressed intake, not answers.
    if re.search(
        r"\badd\b.{0,60}\b(?:main\s+menu|main\s+dish|main\s+dishes|entree|entrees|dishes|"
        r"bar|bar service|cocktail|appetizer|appetizers|dessert|desserts|"
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

    # Deterministic gate-skip — single source of truth in agent/intents.py.
    # If the user's reply is a known skip value for the current phase's gate,
    # route directly to the owning tool. Must run BEFORE any modification-intent
    # detection since "skip" is not a modification verb.
    from agent.intents import classify_skip_gate
    if msg_lower:
        skip_intent = classify_skip_gate(message, phase, slots)
        if skip_intent:
            if skip_intent.section in {"desserts"}:
                return "menu_selection_tool"
            if skip_intent.section in {"wedding_cake"}:
                return "basic_info_tool"
            if skip_intent.section in {"rentals", "tableware", "drinks", "labor"}:
                return "add_ons_tool"
            if skip_intent.section in {"special_requests", "dietary_concerns", "followup_call_requested"}:
                return "finalization_tool"

    # Wedding cake → desserts phase-jump: when the user is mid wedding-cake
    # flavor/filling/buttercream and says "actually lets do desserts" / "want
    # desserts" / "add desserts", treat it as an explicit phase-jump back to
    # the dessert section rather than answering the cake question.
    if (
        phase == PHASE_WEDDING_CAKE
        and is_filled(slots, "__wedding_cake_gate")
        and get_slot_value(slots, "__wedding_cake_gate") is True
        and msg_lower
        and re.search(
            r"\b(?:lets?\s+do|let'?s\s+do|actually\s+(?:do\s+)?|want|add|do)\s+desserts?\b"
            r"|^desserts?$"
            r"|\bdessert\s+menu\b"
            r"|\b(?:show|reselect|redo|reopen|revisit|change|update|edit)\s+(?:the\s+|my\s+)?desserts?\b",
            msg_lower,
        )
    ):
        return "modification_tool"

    # Wedding cake gate protection — at PHASE_WEDDING_CAKE with the gate question
    # still pending, don't let the LLM router silently bypass the question. Only
    # explicit modification commands (add/remove/etc.) should leave this phase.
    # Without this guard, an unrelated message like "I need pepsi" was being routed
    # to modification_tool which set wedding_cake=none and advanced to drinks.
    if (
        phase == PHASE_WEDDING_CAKE
        and not is_filled(slots, "__wedding_cake_gate")
        and msg_lower
        and not re.match(
            r"^(?:(?:can|could|would|please|let(?:'s|\s+us))\s+)?"
            r"(?:add|remove|delete|change|update|swap|replace|cancel|skip|include|exclude|edit|fix)\b",
            msg_lower,
        )
    ):
        return "basic_info_tool"

    # Free-text phases (date/venue/guests/service type): if the user starts
    # the message with an edit verb, it's almost certainly a modification (not
    # the answer we asked for). Route to modification_tool so the request
    # doesn't get swallowed by the basic-info autoroute.
    if phase in _FREE_TEXT_AUTOROUTE_PHASES and msg_lower:
        if re.match(r"^(?:add|remove|delete|drop|replace|swap|change|update|edit)\b", msg_lower):
            return "modification_tool"

    # If the user is clearly *updating* a basic-info field while we're in some
    # other phase (menus, add-ons, etc.), route to modification_tool so it can
    # apply the update without phase-lock swallowing it.
    # Excluded: PHASE_SERVICE_TYPE and PHASE_WEDDING_CAKE where "drop-off" / "yes"
    # are structured first-fill answers, not service-type modification commands.
    _BASIC_UPDATE_EXCLUDED = _FREE_TEXT_AUTOROUTE_PHASES | {PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE}
    if phase not in _BASIC_UPDATE_EXCLUDED and msg_lower:
        mentions_basic_update = bool(
            re.search(
                r"\b(?:venue|location|guest count|guests|headcount|attendees|"
                r"event date|date is|service type|drop[- ]?off|on[- ]?site)\b",
                msg_lower,
            )
            # FLAG-7: natural numeric guest count patterns ("party of 100",
            # "we have 80 people", "it's for 50 people") not caught above.
            or re.search(
                r"\b(?:party|group|table|event)\s+of\s+\d+\b"
                r"|\bwe(?:'re|'ll|\s+are|\s+will\s+be)?\s+(?:have\s+)?\d+\s+(?:people|guests|attendees|folks)\b"
                r"|\b(?:it(?:'s|\s+is)\s+for|for\s+about|around)\s+\d+\s+(?:people|guests)\b",
                msg_lower,
            )
        )
        # Avoid routing short confirmations ("ok", "yes") as modifications.
        if mentions_basic_update and len(msg_lower) >= 8:
            return "modification_tool"

    # "dont want X" / "don't want X" / "do not want X" — bypass FAQ for any item
    # removal so modification_tool can handle the negation and offer special-request
    # for unknown items. Catches: "I dont want chair", "dont want bar service", etc.
    if msg_lower and phase not in _FREE_TEXT_AUTOROUTE_PHASES and re.search(
        r"\b(?:dont|don[\s']?t|do\s+not)\s+(?:want|need|include|have)\b",
        msg_lower,
    ):
        return "modification_tool"

    # "I want X" patterns where X might not be on the menu → let modification_tool
    # handle it and offer a special request if the item isn't found.
    # Excluded phases: free-text phases (user is answering a direct question),
    # PHASE_SERVICE_TYPE / PHASE_WEDDING_CAKE (structured binary choices), and
    # menu phases where "I want salmon" is a valid first-fill answer that should
    # reach menu_selection_tool via LLM router, not detour through modification_tool.
    # FLAG-3: added PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT
    _WANT_X_EXCLUDED = _FREE_TEXT_AUTOROUTE_PHASES | {
        PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE,
        PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT,
    }
    if msg_lower and phase not in _WANT_X_EXCLUDED and re.match(
        r"^i\s+(?:want|need|would\s+like|d\s+like|am\s+looking\s+for)\s+\w",
        msg_lower,
    ):
        return "modification_tool"

    # Modification intent always routes to modification_tool regardless of phase.
    # Exception: free-text phases and PHASE_SERVICE_TYPE/PHASE_WEDDING_CAKE use the
    # autoroute guard below (line 632+) or structured-answer detection instead.
    _MOD_INTENT_EXCLUDED = _FREE_TEXT_AUTOROUTE_PHASES | {PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE}
    if msg_lower and phase not in _MOD_INTENT_EXCLUDED and _looks_like_modification_intent(message):
        # Event identity corrections ("actually it's a corporate event",
        # "my bad it is a wedding", "it's a birthday not a wedding") must
        # route to modification_tool. Past bug: routed to basic_info_tool but
        # the basic_info_tool's _PHASE_ALLOWED_FIELDS filter strips event_type
        # at every phase past PHASE_EVENT_TYPE, so the correction silently
        # disappeared. modification_tool has the proper event-type-reset
        # confirmation flow (does the user want to wipe partner_name, menu, etc.).
        if re.search(
            r"\b(?:it(?:'s|\s+is)\s+a|type\s+is|actually\s+a"
            r"|not\s+a\s+wedding|not\s+a\s+birthday|not\s+corporate)\b",
            msg_lower,
        ) and re.search(r"\b(?:corporate|wedding|birthday|other)\b", msg_lower):
            return "modification_tool"
        return "modification_tool"

    # Partner/company/honoree name updates should not be swallowed by basic-info
    # phases like venue/date/guest_count. If the user explicitly says which name
    # they are updating, treat it as a modification.
    if phase != PHASE_CONDITIONAL_FOLLOWUP and msg_lower:
        if re.search(r"\b(?:partner|fianc[eé]|fiancee|company|honoree)\b.{0,20}\bname\b", msg_lower):
            return "modification_tool"

    # Deterministic replace/swap commands should always go to modification_tool.
    # Prevents menu phases (e.g., ask_meal_style) from accidentally eating the
    # request and just repeating the prior question.
    if msg_lower:
        has_replace = bool(re.search(r"\breplace\b", msg_lower)) and " with " in msg_lower
        has_swap = bool(re.search(r"\bswap\b", msg_lower)) and bool(re.search(r"\b(?:with|for)\b", msg_lower))
        if has_replace or has_swap:
            return "modification_tool"

    # If the event type is currently TBD and the user later states the event
    # type in free text (e.g. "wedding", "birthday"), route to modification_tool
    # so it can update event_type mid-flow.
    current_event_type = str(get_slot_value(slots, "event_type") or "").strip().lower()
    if current_event_type.startswith("tbd"):
        if (
            msg_lower
            and "," not in msg_lower
            and not re.search(r"\d", msg_lower)
            and len(msg_lower) <= 40
            and (
                msg_lower in {"wedding", "birthday", "bday", "corporate", "company", "office"}
                or msg_lower.startswith(("event is ", "event type is ", "it's a ", "it is a "))
            )
        ):
            return "modification_tool"

    # Review recap: "change" always goes to modification_tool so the user can
    # pick what to modify. Never gate on finalization state — if the user says
    # "change" at the recap, they want to edit, full stop.
    if phase == PHASE_REVIEW and msg_lower in {
        "change", "no, make changes", "i need to change something", "make changes",
    }:
        return "modification_tool"

    # Review recap: confirmation phrases → finalization_tool deterministically.
    # These fall through to the LLM otherwise, which is non-deterministic and
    # occasionally mis-routes them to modification_tool.
    if phase == PHASE_REVIEW and msg_lower and re.search(
        r"\b(?:looks?\s+(?:good|great|correct|right|fine|perfect|solid|good\s+to\s+go)"
        r"|all\s+(?:good|set|correct|looks?\s+good)"
        r"|send\s+it|submit(?:\s+it)?"
        r"|confirm(?:ed)?|approve[sd]?"
        r"|go\s+ahead|proceed(?:\s+with\s+(?:it|this|that))?"
        r"|that(?:'s|\s+is)\s+(?:correct|right|it|all|fine|good|perfect)"
        r"|yes[,.]?\s+(?:proceed|submit|confirm|send|go|looks?\s+good)"
        r")\b",
        msg_lower,
    ) and not _looks_like_modification_intent(message):
        return "finalization_tool"

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

    # Menu-selection phases: any non-modification, non-meta message is almost
    # certainly a menu selection answer. Route directly to avoid LLM latency
    # and prevent the LLM from misrouting "I want salmon" to modification_tool.
    # Guard: _normalize_choice strips leading soft markers ("actually", "wait"),
    # so check the raw message for soft mod markers before firing the catch-all.
    _has_soft_marker_raw = any(
        (re.search(rf"\b{re.escape(kw)}\b", message.lower()) if " " not in kw else kw in message.lower())
        for kw in _SOFT_MOD_KEYWORDS
    )
    if (
        phase in {PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT}
        and msg_lower
        and not _looks_like_modification_intent(message)
        and not _has_soft_marker_raw
        and not _looks_like_meta_command(msg_lower)
    ):
        return "menu_selection_tool"

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
    "main dish", "main dishes", "entree", "entrees", "main menu",
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


# Keywords that anchor a message to the catering/event domain — presence of
# any of these means the message is in scope even if it sounds generic.
_IN_SCOPE_ANCHORS = re.compile(
    r"\b(?:event|catering|menu|food|dish|dishes|appetizer|dessert|drink|bar|venue|"
    r"guest|budget|price|cost|service|rental|linen|staff|labor|date|wedding|birthday|"
    r"corporate|party|reception|cocktail|cake|buffet|plated|honoree|partner|fiancee|"
    r"company|table|chair|cutlery|coffee|tea|passed|station|brisket|salmon|chicken|"
    r"beef|pork|veg|seafood|halal|kosher|dietary|allergy|quote|proposal)\b",
    re.IGNORECASE,
)

# Patterns that are almost certainly off-topic if no in-scope anchor is present.
_OUT_OF_SCOPE_PATTERNS = re.compile(
    r"\b(?:python|javascript|java|code|program|algorithm|syntax|variable|function|class|"
    r"database|sql|html|css|api|server|cloud|kubernetes|docker|react|angular|"
    r"machine\s*learning|artificial\s*intelligence|blockchain|crypto|bitcoin|"
    r"weather|temperature|news|sports|stock|movie|song|music|game|joke|recipe|"
    r"math|calculus|algebra|physics|chemistry|biology|history|geography|capital\s+of|"
    r"who\s+(?:is|was|are)|what\s+is\s+(?:the\s+)?(?!your|this|a\s+catering|an?\s+event)"
    r")\b",
    re.IGNORECASE,
)

_OUT_OF_SCOPE_REPLIES = [
    "Ha, not quite my territory — but I'd love to help plan your event. Where were we?",
    "Way outside my lane, but events? That's my whole thing. Back to yours.",
    "Catering and parties is what I do — happy to keep that going.",
    "I'll leave that one alone — but the food and event side, I'm all yours. Let's keep building this.",
    "Not my area, but your event is. Back to the fun stuff.",
]

# Signals that a message is personal/expressive and clearly off-topic.
# Checked ONLY when no _IN_SCOPE_ANCHORS are present, so catering context
# (e.g. "dying to try the salmon") won't accidentally trigger this path.
_EXPRESSIVE_OOS_PATTERN = re.compile(
    # Personal address words that rarely appear in catering intake
    r"\b(?:brother|bro(?:tha)?|sis(?:ta)?|sister|bruh|bruv|dawg|homie|dude|fam|man|mate|babes?|babe)\b"
    # Health/physical state with zero catering relevance
    r"|\b(?:ulcer|stomachache|heartburn|migraine|nauseous|vomit(?:ing)?|hangover|"
    r"bleeding|dizzy|faint(?:ing)?|cramp(?:s|ing)?)\b"
    # "where's my [non-catering item]" — personal possession queries
    r"|\bwhere(?:'s|\s+is)\s+(?:my|the)\s+(?!(?:proposal|quote|booking|order|event|contract|invoice))\w+"
    # Internet/informal slang that signals off-topic banter
    r"|\b(?:lmao|lmfao|smh|oof|yikes|bruhhh+|ayyy+|ngl|imo|tbh|lowkey|highkey|slay|periodt?)\b"
    # Social/flirty messages ("hey baby", "wanna hang", "wanna date")
    r"|\b(?:wanna\s+(?:hang|date|chill|meet|talk|hook)|hey\s+(?:baby|girl|boy|sexy|cutie)|"
    r"you\s+(?:cute|pretty|hot|fine|sexy)|how\s+old\s+are\s+you|what(?:'s|\s+is)\s+your\s+(?:name|number|age))\b"
    # Repeated letters = expressive elongation (WOOOOOTAHHH, WOTAHHH, noooo, yesss)
    r"|[a-zA-Z]*([a-zA-Z])\1{2,}[a-zA-Z]*"
    # Foreign / non-English phrases (non-ASCII characters) — clearly off-topic
    r"|[^\x00-\x7F]{3,}"
    # Euphemistic profanity and expressive nonsense ("motherflower", "what the")
    r"|\b(?:motherflower|motherfudge|what\s+the\s+(?:heck|heck|fudge|flip)|"
    r"oh\s+my\s+(?:god|gosh|lord|goodness)|holy\s+(?:moly|cow|smokes?|crap))\b",
    re.IGNORECASE,
)

_PERSONALITY_REDIRECT_PROMPT = """\
You are a warm, playful catering coordinator with a waiter's personality — peaceful, \
joyous, and chatty. The customer just sent a message that doesn't relate to event details.

Rules:
1. Acknowledge their message in ONE short clause — match their energy (light-hearted \
if they're joking, empathetic if they're struggling, calm if they're confused).
2. Pivot naturally back to the catering form in the same breath.
3. ONE OR TWO SHORT SENTENCES MAXIMUM. Total reply under 25 words. Punchy, NOT corporate.
4. NEVER start with: Got it, Perfect, Great, Noted, Of course, Absolutely, Sure thing, \
Thanks, I understand, I see, No worries.
5. Do NOT answer the off-topic content literally or give advice on it.
6. End with the pending question (provided in context) word-for-word or close to it.
7. CRITICAL: do NOT lecture or volunteer extra catering facts. Only mention water/lemonade \
or menu items if the customer's message LITERALLY references them. If they said "I have \
ulcers" or "I'm tired" — just acknowledge the feeling briefly and redirect. Don't bring up \
water, lemonade, drinks, menu items, or anything else.
8. NEVER repeat your previous reply. If you already redirected once, find a different short \
acknowledgement this turn.

ONLY when the customer's literal message contains "water", "wotah", "lemonade", "drink(s)", \
"thirsty", or similar — you may say "water and lemonade are on us" before redirecting. \
NEVER use "drinks are free" — only water and lemonade are.
"""


def _extract_last_question(history: list) -> str:
    """Pull just the most recent question sentence from the last AI message.

    The previous bug split on '?' and grabbed pieces[-1] + '?', which captured
    the entire prior message. We want ONLY the final question — typically the
    last 1-2 sentences ending in '?'.
    """
    if not history:
        return ""
    for msg in reversed(history):
        if getattr(msg, "type", "") != "ai":
            continue
        content = str(getattr(msg, "content", "") or "").strip()
        if "?" not in content:
            return ""
        # Take everything up to the last '?', then walk back to the last sentence
        # boundary (period, newline) to isolate just the question sentence.
        before_q, _, _ = content.rpartition("?")
        # Find the start of the question sentence: last period, newline, or '!'
        boundary = max(
            before_q.rfind("\n"),
            before_q.rfind(". "),
            before_q.rfind("! "),
            before_q.rfind(": "),
        )
        question_start = boundary + 1 if boundary >= 0 else 0
        question = before_q[question_start:].strip(" .!\n") + "?"
        # Sanity cap — never longer than 200 chars
        if len(question) > 200:
            question = question[-200:].lstrip()
        return question
    return ""


async def _personality_oos_response(message: str, state: dict, history: list | None = None) -> str | None:
    """
    Acknowledge + bridge for personal/expressive off-topic messages.

    Fires when a message has no in-scope catering anchors AND contains at least
    one expressive OOS signal (personal address, health term, internet slang, etc.).
    Calls the LLM to generate a personality-matched one-liner that acknowledges the
    user's vibe and redirects to the current pending question.
    """
    stripped = message.strip()
    # Personality OOS fires for two cases:
    #   1. Expressive markers (brother/bruh/health terms/elongation/foreign chars)
    #   2. Personal statements like "I have X", "I'm X", "we feel X" that don't
    #      look like a service question or a structured intake answer.
    _msg_lower_stripped = stripped.lower()
    _is_personal_statement = bool(re.match(
        r"^(?:i\s+(?:have|got|am|feel|need|don'?t|can'?t|'m|'ve)\s+\w|"
        r"i'm\s+\w|im\s+\w|we'?(?:re|ve|ll)\s+\w|"
        r"my\s+\w|me\s+(?:and|too|also)\b)",
        _msg_lower_stripped,
    ))
    # Don't treat "i want X" / "i'd like X" as personality OOS — those are
    # legitimate intake answers ("I want salmon", "I'd like a wedding cake").
    _is_intake_intent = bool(re.match(
        r"^i\s+(?:want|need\s+)|i'd\s+(?:like|love)|i\s+would\s+like",
        _msg_lower_stripped,
    ))
    if not _EXPRESSIVE_OOS_PATTERN.search(stripped) and not (
        _is_personal_statement and not _is_intake_intent
    ):
        return None

    # Pull the actual question the bot just asked. Use _extract_last_question so
    # we get only the question sentence, not the entire previous AI message.
    pending_q = _extract_last_question(history or [])
    if not pending_q:
        phase = state.get("conversation_phase", "")
        pending_q = _PHASE_CLARIFYING_QUESTIONS.get(phase, "")

    # Pass the previous AI reply so the LLM can avoid duplicating wording.
    last_ai = ""
    if history:
        for msg in reversed(history):
            if getattr(msg, "type", "") == "ai":
                last_ai = str(getattr(msg, "content", "") or "").strip()[:300]
                break

    context_lines = []
    if pending_q:
        context_lines.append(f"Current pending question to redirect to: {pending_q}")
    else:
        context_lines.append("Redirect them back to continuing the event planning form.")
    if last_ai:
        context_lines.append(
            f"Your previous reply was: {last_ai}\n"
            "Do NOT repeat that wording. Pick a different short acknowledgement."
        )
    context_block = "\n".join(context_lines)

    try:
        response = await generate_text(
            system=_PERSONALITY_REDIRECT_PROMPT,
            user=f"Customer message: {message}\n{context_block}",
            model=MODEL_ROUTER,
            max_tokens=80,
            temperature=0.95,
        )
        if response:
            return response.strip()
    except Exception:
        logger.debug("Personality OOS response failed", exc_info=True)

    import hashlib
    idx = int(hashlib.md5(message.encode()).hexdigest(), 16) % len(_OUT_OF_SCOPE_REPLIES)
    return _OUT_OF_SCOPE_REPLIES[idx]


def _out_of_scope_response(message: str) -> str | None:
    """Return a varied redirect message if the message is clearly off-topic, else None."""
    if _IN_SCOPE_ANCHORS.search(message):
        return None
    if _OUT_OF_SCOPE_PATTERNS.search(message):
        import hashlib
        idx = int(hashlib.md5(message.encode()).hexdigest(), 16) % len(_OUT_OF_SCOPE_REPLIES)
        return _OUT_OF_SCOPE_REPLIES[idx]
    return None


# ---------------------------------------------------------------------------
# FAQ routing — keyword pre-filter + canned answers + LLM fallback
#
# Architecture:
#   1. Short/direct messages → skip FAQ check entirely (0ms)
#   2. FAQ keyword match → return canned answer (0ms)
#   3. FAQ keyword match but no canned answer → call LLM for answer (~400ms)
#   4. No keyword match → skip FAQ check entirely (0ms)
#
# This replaces the previous always-on LLM FAQ classification call that ran
# for every single message (~400ms wasted on 90%+ of turns that are NOT FAQs).
# ---------------------------------------------------------------------------

# Patterns that signal a genuine service question — not an intake answer.
_FAQ_KEYWORD_PATTERN = re.compile(
    r"\b(?:"
    # Pricing
    r"how\s+much|what\s+(?:does|do|is|are)\s+(?:it|this|the|your|that)\s+(?:cost|price|run|go\s+for)"
    r"|pric(?:e|es|ing)|cost(?:s|ing)?|quot(?:e|es|ing)|rate(?:s)?|budget|package(?:s)?|proposal"
    r"|expensive|cheap|afford"
    # Dietary
    r"|halal|kosher|vegan|vegetarian|gluten[\s-]?free|nut[\s-]?free|dairy[\s-]?free"
    r"|allerg(?:y|ies|ic)|dietary|food\s+restriction"
    # What's included
    r"|what(?:'s|\s+is)\s+included|what\s+comes\s+with|what\s+do\s+you\s+include"
    r"|is\s+(?:water|lemonade|drinks?|tea|coffee)\s+included"
    # Minimums / capacity
    r"|minimum\s+(?:guest|order|booking|headcount)|guest\s+minimum|minimum\s+order"
    r"|how\s+many\s+(?:guests|people)\s+(?:minimum|min|do\s+you|can\s+you)"
    r"|max(?:imum)?\s+(?:guest|capacity|headcount)"
    # Service area / travel
    r"|service\s+area|what\s+areas|where\s+do\s+you\s+(?:serve|operate|go|travel|deliver|work|cover)"
    r"|do\s+you\s+(?:travel|come\s+to|cover|serve|deliver\s+to)\b"
    r"|how\s+far\s+do\s+you\s+(?:travel|go|deliver)"
    # Tastings
    r"|tasting(?:s)?|taste\s+test|try\s+the\s+food|sample\s+the\s+(?:menu|food)"
    # Follow-up / timeline
    r"|when\s+(?:will|do|should|would|can)\s+(?:i|we|you|someone)\s+(?:hear|get|receive|reach|contact|follow)"
    r"|how\s+(?:long|soon|quickly)\s+(?:will|do|does|can)\s+(?:you|we|someone|they)\s+(?:get\s+back|respond|reply|reach|contact)"
    r"|follow[\s-]?up|get\s+back\s+to\s+(?:me|us)|response\s+time|turnaround"
    # Cancellation / changes / refunds
    r"|cancell?ation\s+polic(?:y|ies)|cancell?ation\s+fee|refund(?:s|able)?|cancel(?:led)?\s+(?:my\s+)?(?:order|booking|event)"
    r"|can\s+i\s+(?:change|modify|update|edit|cancel)\s+(?:my|the)\s+(?:order|booking|menu|event|selection)"
    r"|change\s+(?:my\s+)?(?:order|booking|menu)\s+later"
    # How it works / process
    r"|how\s+does\s+this\s+work|what\s+(?:are\s+the\s+)?steps|what\s+happens\s+next\s+after"
    r"|what\s+is\s+the\s+process|walk\s+me\s+through"
    # Recommendations / popular
    r"|what\s+(?:do\s+you\s+)?recommend|what(?:'s|\s+is)\s+(?:most\s+)?popular|best[\s-]seller"
    r"|your\s+(?:best|top|most\s+popular)\s+(?:dish|item|option|choice)"
    # Deposits / payment
    r"|deposit(?:s)?|payment\s+(?:plan|method|option)|invoice|billing|when\s+(?:do\s+i|is)\s+(?:pay|payment|due)"
    r"|how\s+do\s+(?:i|we)\s+pay"
    # Advance booking
    r"|how\s+far\s+in\s+advance|how\s+early|book(?:ing)?\s+(?:deadline|window|period|notice)"
    r"|last[\s-]minute\s+booking"
    # Staff / rentals
    r"|do\s+you\s+(?:provide|have|offer|include|supply)\s+(?:tables?|chairs?|linens?|rentals?|staff|servers?|setup)"
    r"|(?:tables?|chairs?|linens?|rentals?|staff|servers?)\s+(?:included|provided|available|rented)"
    r")\b",
    re.IGNORECASE,
)

# Short messages that are almost certainly intake answers, not FAQs.
# Checked BEFORE the keyword scan to avoid false positives on short messages
# that contain an incidental keyword (e.g. "no bar please" shouldn't hit FAQ).
# Allow underscores so structured option values (beer_wine_signature) skip FAQ.
# Word count kept at 5 to avoid catching real FAQs like "do you offer vegan options".
_FAQ_SKIP_PATTERN = re.compile(
    r"^(?:"
    r"[a-z_]+(?:[\s,]+[a-z_]+){0,4}"  # 1-5 word phrases incl. structured values
    r"|[0-9]{1,4}"                      # pure numbers (guest counts, years)
    r"|[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}"  # email addresses
    r"|\+?[\d\s\-().]{7,15}"           # phone numbers
    r"|\d{4}-\d{2}-\d{2}"             # ISO dates
    r")$",
    re.IGNORECASE,
)

# Structured-value pattern: a single token with underscores (no spaces).
# Examples: beer_wine_signature, labor_ceremony_setup, eco_biodegradable.
# These are sent by option buttons and are NEVER service questions, regardless
# of length. Skip the FAQ check up front.
_STRUCTURED_VALUE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Business facts the LLM uses to answer ANY service question.
# Single source of truth — update this block when policies change.
# ---------------------------------------------------------------------------
_FAQ_BUSINESS_FACTS_PROMPT = """\
You are a friendly catering coordinator helping a customer plan their event — think \
of yourself like a great waiter taking down details: peaceful, playful, and joyous. \
You're chatty mid-form, so questions about the service get a quick warm answer \
before steering back to the planning.

STEP 1 — CLASSIFY:
Is this message a question about the catering service itself (pricing, what's included, \
policies, dietary options, how it works, minimum guests, service area, tastings, follow-up, \
cancellation, deposits, rentals, staffing, recommendations, etc.)?

If NO — the message is an intake answer (name, date, venue, yes/no, food choice, etc.) — \
reply with exactly: NOT_FAQ

A phase hint may be included. If the customer is mid-collection (e.g. phase is \
S17_special_requests, S18_dietary, S5–S8 menu phases) and the message reads as a \
description of what they want or need (rather than a question), reply NOT_FAQ — \
let the intake collect their answer rather than answering it as a FAQ.

If YES — answer it using ONLY the facts below.

BUSINESS FACTS:
- Complimentary (on the house, every package): chilled water and fresh lemonade. \
Basic napkins and utensils are also included.
- Drinks beyond water/lemonade are NOT free — coffee service and bar service \
(beer, wine, signature cocktails, full open bar) are paid add-ons.
- Add-ons (available, not default): bar service / alcohol, coffee station, premium tableware \
(silver/gold disposable, real china), rental items (tables, chairs, linens), \
on-site servers / labor (ceremony setup, table setup, preset, cleanup, trash removal)
- Menu highlights: 40+ appetizers (chicken, pork, beef, seafood, canapés, vegetarian), \
17 main menus including signature combos like Prime Rib & Salmon, BBQ menus, Burger Bar, \
Mediterranean, Mexican Char Grilled, Tex-Mex, Italian, Soup/Salad/Sandwich, plus 8 desserts. \
For weddings, we also offer a 2-tier custom wedding cake with multiple flavor/filling/buttercream combos.
- Service style: onsite (our staff sets up and serves at your venue) or drop-off (we deliver, \
no staff). For weddings the customer also picks cocktail hour, reception, or both.
- Pricing: fully custom — based on guest count, menu selections, and add-ons; \
a detailed proposal is sent after the form is complete; NEVER quote a dollar amount.
- Guest minimums: vary by event type — confirmed on the follow-up call
- Service area: we serve the greater area; travel details and fees confirmed on follow-up call
- Tastings: available for select packages — discussed during the follow-up call
- Follow-up timeline: a coordinator reaches out within 24-48 hours of form completion
- Cancellation / payment / deposits: outlined in the contract, reviewed on the follow-up call
- Booking lead time: recommend at least 2-4 weeks in advance; last-minute handled case by case
- Dietary / allergens: we accommodate vegetarian, vegan, halal, gluten-free, common allergies; \
note it in the form and the team handles it
- If a fact is not listed above: tell them it will be confirmed on the follow-up call

RESPONSE RULES (only when answering a FAQ):
1. Answer in 1-2 short sentences using only the facts above. Sound like a warm waiter \
chatting at the table — playful, peaceful, joyous, NEVER stiff or order-taking.
2. End with a natural redirect back to the form. No question marks anywhere. \
Examples: "anyway, where were we", "let's keep going", "back to your event", "now then —".
3. NEVER start with: Got it, Perfect, Great, Noted, Of course, Absolutely, Sure thing, \
Thanks, I understand, Certainly.
4. Do NOT invent policies, prices, or details not listed above.
5. When the customer asks about water specifically, lead with "water and lemonade are on us" \
(or similar) — never say "drinks are free", because the bar/coffee add-ons cost extra.
6. Reference the menu specifically when relevant (e.g. if they ask about signature dishes, \
mention real ones from the catalog like "Prime Rib & Salmon" or "Mediterranean Bar").
"""


async def _in_scope_faq_response(
    message: str,
    history: list,
    phase: str = "",
    pending_question: str = "",
) -> str | None:
    """
    Detect and answer catering FAQs using a single LLM classify+answer call.

    The LLM decides if the message is a service question — no keyword gate needed.
    Only short/obvious intake answers (names, numbers, yes/no) are skipped up front
    to avoid wasting tokens on clear non-FAQs.

    When `pending_question` is provided, it's appended to the FAQ answer so the
    user is reminded what they were being asked — without this, the chat can lose
    the original intake question after a FAQ answer.
    """
    stripped = message.strip()
    lower = stripped.lower()

    # Structured option values (e.g. "beer_wine_signature", "labor_ceremony_setup")
    # are sent by option buttons. Never a FAQ regardless of length.
    if _STRUCTURED_VALUE_PATTERN.match(stripped):
        return None

    # Comma-separated structured values from multi-select widgets
    # (e.g. "labor_ceremony_setup, labor_table_setup, labor_cleanup").
    if "," in stripped and all(
        _STRUCTURED_VALUE_PATTERN.match(p.strip()) for p in stripped.split(",") if p.strip()
    ):
        return None

    # If the message clearly looks like a question, do NOT skip the FAQ check
    # even when it's short. "where is my water?", "do you have vegan?", etc.
    _looks_like_question = (
        "?" in stripped
        or lower.startswith((
            "what", "where", "when", "why", "how", "who", "which",
            "do you", "does ", "is ", "are ", "can ", "could ", "would ",
            "should ", "will ", "have you", "any ",
        ))
    )

    if not _looks_like_question:
        # Skip short messages that are almost certainly intake answers.
        if len(stripped) <= 40 and _FAQ_SKIP_PATTERN.match(stripped):
            return None

        # Skip very short messages regardless (1-2 words won't be a service question).
        if len(stripped) <= 15:
            return None

    # Phase context helps the LLM disambiguate intake answers from FAQs. E.g.
    # "we have peanut allergies for two guests" is an answer in PHASE_DIETARY,
    # but could look like a FAQ ("do you accommodate allergies?") otherwise.
    phase_hint = f"\nCurrent conversation phase: {phase}" if phase else ""

    def _append_pending(answer_text: str) -> str:
        """Tack the pending intake question onto the FAQ answer."""
        if not pending_question:
            return answer_text
        return f"{answer_text}\n\n{pending_question}"

    try:
        answer = await generate_text(
            system=_FAQ_BUSINESS_FACTS_PROMPT,
            user=f"Customer message: {message}{phase_hint}",
            model=MODEL_ROUTER,
            max_tokens=150,
            temperature=0.5,
        )
        if not answer:
            # Empty LLM response — fall through to deterministic fallback,
            # not None (which would let the conversation give up on this FAQ).
            answer = ""
        clean = answer.strip()
        # LLM signals "not a FAQ" — fall through to normal routing.
        if clean.upper().startswith("NOT_FAQ") or clean == "NOT_FAQ":
            return None
        # Strip a trailing question the model snuck in (we'll append our own).
        # Past bug: if the trimmed answer was ≤20 chars, we returned None and
        # the user got nothing — looked like the bot "gave up". Now we always
        # produce SOMETHING (even short acks get padded by _append_pending).
        if "?" in clean:
            clean = clean.rsplit("?", 1)[0].strip()
            if len(clean) > 20:
                return _append_pending(clean + ".")
            # Too short on its own — defer to the deterministic fallback below.
            clean = ""
        if clean:
            return _append_pending(clean)
        # Empty / too-short LLM answer → fall through to deterministic fallback
    except Exception:
        logger.debug("FAQ LLM answer failed — skipping", exc_info=True)

    import hashlib as _hs
    _faq_fallbacks = [
        "The team can cover that on the follow-up call — anyway, back to it.",
        "That one's better confirmed on the follow-up call. Where were we?",
        "Coordinator will walk through that with you after you submit. Moving on.",
        "We'll get to the specifics on the follow-up. Let's keep going.",
        "Good question — your coordinator will go over that on the call.",
        "We'll cover the specifics during the follow-up. Picking up where we left off:",
    ]
    _fi = int(_hs.md5(message.encode()).hexdigest(), 16) % len(_faq_fallbacks)
    return _append_pending(_faq_fallbacks[_fi])


# Short vague/filler messages that can't advance the flow but aren't off-topic.
# We catch these before the LLM router to avoid noisy extractions on junk input.
_VAGUE_TOKENS = frozenset({
    "hmm", "hm", "hmmm", "hmmmm", "idk", "i don't know", "i dont know",
    "not sure", "unsure", "no idea", "no clue", "whatever", "either",
    "you choose", "you decide", "up to you", "your call", "surprise me",
    "doesn't matter", "doesnt matter", "don't care", "dont care", "i don't care",
    "i dont care", "anything", "anything is fine", "anything works",
    "i have no preference", "no preference", "random", "i don't mind",
    "i dont mind", "lol", "haha", "ok ok", "okay okay", "sure sure",
    "um", "uh", "er", "uhh", "umm", "ugh", "meh", "eh", "blah",
    "i don't understand", "i dont understand", "what", "what?", "huh",
    "pardon", "can you repeat", "say that again",
    "i'm confused", "im confused", "confused", "lost",
    "what do you recommend", "what would you suggest", "what do you suggest",
    "what should i pick", "what should i choose", "help me choose", "help me pick",
    "i have no idea", "beats me", "who knows", "good question",
    "does it matter", "does it really matter", "is it important",
    "can you choose for me", "just pick for me", "pick for me",
    "i'll go with whatever", "ill go with whatever",
    "what are my options", "what are the options",
})

# Also catch patterns like "I don't really know what to pick here" (longer vague)
_VAGUE_PATTERNS = re.compile(
    r"^(?:i\s+)?(?:don[\s']?t|do\s+not)\s+(?:really\s+)?(?:know|care|mind|have\s+a\s+preference)"
    r"|^(?:not\s+(?:really\s+)?sure|unsure\s+(?:about\s+)?(?:this|that)?)"
    r"|^(?:you\s+(?:can\s+)?(?:choose|decide|pick|select))"
    r"|^(?:whatever(?:\s+(?:you|is|works|feels))?)"
    r"|^(?:it\s+(?:doesn[\s']?t|does\s+not)\s+matter)"
    r"|^(?:i\s+(?:have\s+)?no\s+(?:idea|clue|preference))",
    re.IGNORECASE,
)

_VAGUE_REPLIES = [
    "No worries — take your time.",
    "That's fine, no rush.",
    "All good — whenever you're ready.",
    "No rush at all.",
    "Take your time!",
    "Happy to wait.",
]

def _vague_response(message: str, state: dict) -> str | None:
    """Return a gentle nudge if the message is clearly too vague to act on.

    FLAG-5: appends the current pending question so the user knows exactly
    where to pick back up, instead of getting a dead-end 'take your time'.
    """
    phase = state.get("conversation_phase") or ""
    msg_norm = _normalize_choice(message)
    if not msg_norm:
        return None
    # Don't intercept during menu phases — user could be typing item numbers/names.
    if phase in {PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT}:
        return None

    is_vague = msg_norm in _VAGUE_TOKENS or (len(msg_norm) <= 60 and _VAGUE_PATTERNS.search(msg_norm))
    if not is_vague:
        return None

    import hashlib
    idx = int(hashlib.md5(message.encode()).hexdigest(), 16) % len(_VAGUE_REPLIES)
    base = _VAGUE_REPLIES[idx]

    pending_q = _PHASE_CLARIFYING_QUESTIONS.get(phase, "")
    if pending_q:
        return f"{base} To pick up where we left off: {pending_q}"
    return base


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

    # Pending-state TTL — auto-clear stale __pending_* slots so a forgotten
    # "yes/no" offer from 3 turns ago can't replay itself today (the Dragon
    # Chicken bleed). Counted in turns via len(state["messages"]).
    _turn_count = len(state.get("messages") or [])
    _cleared_pending = validate_pending_state(state["slots"], _turn_count)
    if _cleared_pending:
        logger.info(
            "pending_state_ttl cleared=%s turn=%d",
            ",".join(_cleared_pending),
            _turn_count,
        )

    # Pending confirmation/choice/request must take TOP priority — if the bot
    # asked "yes/no" to reset event type and the user replies "yes", that yes
    # must reach the tool that asked the question, NOT get swallowed by a
    # phase bypass below.
    #
    # CRITICAL: __pending_confirmation can be set by ANY tool (modification_tool
    # for event-type-reset, add_ons_tool for rentals/tableware/drinks gates,
    # finalization_tool for confirmation gates). The payload includes a `tool`
    # field saying which tool owns the pending question — route there, NOT
    # always to modification_tool. Past bug: hard-coded routing to modification_tool
    # caused the rentals gate to loop forever because add_ons_tool's pending
    # confirmations were sent to the wrong handler.
    _pending_confirm = get_slot_value(state["slots"], "__pending_confirmation")
    if _pending_confirm:
        owning_tool = "modification_tool"  # safe default for legacy payloads
        if isinstance(_pending_confirm, dict):
            tool_in_payload = _pending_confirm.get("tool")
            if tool_in_payload in {
                "modification_tool", "add_ons_tool",
                "menu_selection_tool", "basic_info_tool", "finalization_tool",
            }:
                owning_tool = tool_in_payload
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name=owning_tool, reason=f"pending:__pending_confirmation:{owning_tool}")],
            confidence=1.0,
        )

    # The other pending slots have a fixed owning tool — no payload routing needed.
    _pending_routes: list[tuple[str, str]] = [
        ("__pending_modification_choice", "modification_tool"),
        ("__pending_modification_request", "modification_tool"),
        ("__pending_menu_choice", "menu_selection_tool"),
        ("__pending_cancel_event_confirm", "modification_tool"),
    ]
    for _slot_name, _route_tool in _pending_routes:
        if get_slot_value(state["slots"], _slot_name):
            from agent.models import ToolCall as _TC
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[_TC(tool_name=_route_tool, reason=f"pending:{_slot_name}")],
                confidence=1.0,
            )

    # Out-of-scope guardrail — catch clearly off-topic messages before any
    # routing logic runs, so they never reach a tool or the LLM router.
    _oos = _out_of_scope_response(message)
    if _oos:
        return OrchestratorDecision(
            action="clarify",
            tool_calls=[],
            confidence=1.0,
            clarifying_question=_oos,
        )

    # Pre-FAQ deterministic bypass — patterns that are NEVER FAQ:
    # "dont/don't/do not want/need X" → always a removal intent → modification_tool
    # "I want X" (outside free-text phases) → add/special-request intent → modification_tool
    # "cancel the event/party/booking" → cancel-event confirmation flow → modification_tool
    # These must be checked before the FAQ LLM call to prevent misclassification.
    _pre_faq_phase = state.get("conversation_phase", "")
    _pre_faq_msg = message.lower()

    # Greeting phase — always basic_info_tool. No FAQ possible at turn 1.
    # Without this, "Hello! I need help planning my event." hits the FAQ LLM
    # which misclassifies "help planning" as a service inquiry.
    if _pre_faq_phase == PHASE_GREETING:
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="basic_info_tool", reason="greeting_phase_bypass")],
            confidence=1.0,
        )

    # Cancel-event intent — always modification_tool regardless of phase so the
    # confirmation flow runs, never FAQ/OOS which would swallow it.
    if _pre_faq_msg and re.search(
        r"\b(?:cancel|end|stop|terminate|quit|abort)\b.{0,30}"
        r"\b(?:event|party|booking|order|reservation|session|everything)\b",
        _pre_faq_msg,
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="modification_tool", reason="cancel_event_bypass")],
            confidence=1.0,
        )

    # Also bypass FAQ when waiting for yes/no on cancel confirmation
    if get_slot_value(state["slots"], "__pending_cancel_event_confirm") is True:
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="modification_tool", reason="cancel_event_confirm_pending")],
            confidence=1.0,
        )

    if _pre_faq_msg and _pre_faq_phase not in _FREE_TEXT_AUTOROUTE_PHASES:
        _is_dont_want = bool(re.search(
            r"\b(?:dont|don[\s']?t|do\s+not)\s+(?:want|need|include|have)\b",
            _pre_faq_msg,
        ))
        _is_i_want = bool(re.match(
            r"^i\s+(?:want|need|would\s+like|d\s+like|am\s+looking\s+for)\s+\w",
            _pre_faq_msg,
        ) and _pre_faq_phase not in {
            PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE,
            # FLAG-3: "I want X" is a valid first-fill answer in menu phases
            PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT,
        })
        if _is_dont_want or _is_i_want:
            from agent.models import ToolCall as _TC
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[_TC(tool_name="modification_tool", reason="pre_faq_intent_bypass")],
                confidence=1.0,
            )

    # Command-style bypass — "add X", "can we add X", "please remove X", etc. are
    # always modification intents, never service questions. Bypass FAQ LLM to
    # prevent "can we add a coffee station" being classified as a coffee-service FAQ.
    #
    # EXCEPTION: gate-skip values like "skip dessert" / "skip cake" must reach
    # the gate handler (via _quick_route → menu_selection_tool / basic_info_tool),
    # NOT modification_tool. The gate handler clears the section cleanly; routing
    # to modification_tool would invoke an LLM extractor that mis-fires
    # action=reopen and shows the menu again.
    from agent.intents import classify_skip_gate as _classify_skip_gate
    _skip_gate_intent = _classify_skip_gate(message, _pre_faq_phase, state["slots"])
    # Strip leading conjunctions ("and add Sushi Bites", "also remove X", "plus add Y")
    # before the command-style match so a stray "and" doesn't drop the modification.
    _pre_faq_msg_stripped = re.sub(
        r"^(?:and|also|plus|&&)\s+", "", _pre_faq_msg
    ).strip()
    if _pre_faq_msg and _skip_gate_intent is None and (
        re.match(
            r"^(?:(?:can|could|would)\s+(?:we|you|i)\s+|please\s+|let(?:'s|\s+us)\s+)?"
            r"(?:add|remove|delete|change|update|swap|replace|cancel|skip|include|exclude)\b",
            _pre_faq_msg,
        )
        or re.match(
            r"^(?:(?:can|could|would)\s+(?:we|you|i)\s+|please\s+|let(?:'s|\s+us)\s+)?"
            r"(?:add|remove|delete|change|update|swap|replace|cancel|skip|include|exclude)\b",
            _pre_faq_msg_stripped,
        )
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="modification_tool", reason="pre_faq_command_bypass")],
            confidence=1.0,
        )

    # Free-text collection bypass — when the user is mid-answering a free-text
    # question (special requests / dietary concerns), their reply is the answer,
    # not a service question. Without this guard "we have a kid with peanut allergy"
    # could be misclassified as a dietary FAQ and never get stored.
    _slots = state.get("slots", {})
    _in_special_req_collect = (
        get_slot_value(_slots, "__gate_special_requests") is True
        and not is_filled(_slots, "special_requests")
    )
    _in_dietary_collect = (
        get_slot_value(_slots, "__gate_dietary") is True
        and not is_filled(_slots, "dietary_concerns")
    )
    if _in_special_req_collect or _in_dietary_collect:
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="finalization_tool", reason="collection_phase_bypass")],
            confidence=1.0,
        )

    # Event-type-correction guard runs BEFORE every phase bypass below.
    # Catches "actually it's a wedding" / "my bad it is a wedding" /
    # "its a wedding not birthday" at any phase past greeting and routes to
    # modification_tool (which has the proper event-type-reset confirmation
    # flow). Otherwise these would get swallowed by menu/conditional/etc.
    # bypasses and the correction would silently disappear.
    _is_event_type_correction_early = bool(re.search(
        r"\b(?:it(?:'s|\s+is)\s+a|its\s+a|actually(?:\s+(?:a|an|its|it's))?|"
        r"my\s+bad|i\s+meant|correction|change\s+(?:to|it))\b.{0,40}"
        r"\b(?:wedding|birthday|corporate)\b",
        _pre_faq_msg,
    ))
    if _is_event_type_correction_early and _pre_faq_phase != PHASE_GREETING:
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="modification_tool", reason="event_type_correction")],
            confidence=1.0,
        )

    # Menu-phase fast path — only fire when the message CLEARLY looks like a
    # menu selection: comma-separated list, numeric index, or a structured value.
    # For everything else (personal chitchat, off-topic, etc.), let the message
    # fall through to OOS/FAQ/LLM router so we don't silently swallow it as a
    # "no items matched" turn that re-asks without acknowledgement.
    _menu_phases = {PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT}
    _has_oos_marker = bool(_EXPRESSIVE_OOS_PATTERN.search(_pre_faq_msg))
    _mentions_off_menu_drink = bool(re.search(
        r"\b(?:water|wotah|woder|warer|wadder|"
        r"lemonade|pepsi|coke|coca|sprite|soda|juice|tea|"
        r"milk|smoothie)\b",
        _pre_faq_msg,
    ))
    # Clear menu-selection signals
    _looks_like_menu_pick = (
        "," in _pre_faq_msg                                   # multi-item list
        or bool(re.match(r"^\d+(?:[\s,]+\d+)*$", _pre_faq_msg))  # numeric indices
        or _pre_faq_msg in {"all", "everything", "all of them"}
    )
    # Personal statements (health/feeling/state) should NEVER be treated as menu picks.
    # Carefully exclude "want"/"need"/"would like" — those are intake intents
    # ("I want salmon", "I need a wedding cake" are valid menu requests).
    _looks_like_personal = bool(re.match(
        r"^(?:i\s+(?:have|got|am|feel|don'?t|can'?t|'m|'ve|hate|love)|"
        r"i'm|im\s+|we're|we'?ve\s+(?:got|been)|"
        r"my\s+\w|me\s+(?:and|too|also))",
        _pre_faq_msg,
    ))
    if (
        _pre_faq_phase in _menu_phases
        and _pre_faq_msg
        and "?" not in _pre_faq_msg
        and not _pre_faq_msg.startswith((
            "what", "where", "when", "why", "how", "who", "which",
            "do you", "does ", "is ", "are ", "can ", "could ", "would ",
            "should ", "will ", "have you", "any ",
        ))
        and not _has_oos_marker
        and not _mentions_off_menu_drink
        and not _looks_like_personal
        and (_looks_like_menu_pick or len(_pre_faq_msg) <= 30)
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="menu_selection_tool", reason="menu_phase_answer_bypass")],
            confidence=1.0,
        )

    # Conditional follow-up bypass — partner_name / honoree_name / company_name
    # collection. The user's reply is a name, not a service question.
    if (
        _pre_faq_phase == PHASE_CONDITIONAL_FOLLOWUP
        and _pre_faq_msg
        and "?" not in _pre_faq_msg
        and not _pre_faq_msg.startswith((
            "what", "where", "when", "why", "how", "who", "which", "do you",
        ))
        and not _has_oos_marker
        and not _looks_like_personal
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="basic_info_tool", reason="conditional_followup_bypass")],
            confidence=1.0,
        )

    # Free-text basic-info phase bypass — date/venue/guest count answers may be long
    # phrases that the FAQ LLM misclassifies. If the user is in a free-text intake
    # phase and the message doesn't start with a question word, treat it as the answer.
    _free_text_intake_phases = {PHASE_EVENT_DATE, PHASE_VENUE, PHASE_GUEST_COUNT, PHASE_EVENT_TYPE}
    if (
        _pre_faq_phase in _free_text_intake_phases
        and _pre_faq_msg
        and "?" not in _pre_faq_msg
        and not _pre_faq_msg.startswith((
            "what", "where", "when", "why", "how", "who", "which",
            "do you", "does ", "is ", "are ", "can ", "could ", "would ",
            "should ", "will ", "have you", "any ",
        ))
        and not re.search(
            r"\b(?:remove|delete|change|update|swap|replace|cancel|skip)\b",
            _pre_faq_msg,
        )
        and not _has_oos_marker
        and not _looks_like_personal
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="basic_info_tool", reason="free_text_intake_bypass")],
            confidence=1.0,
        )

    # Service type / wedding cake gate phases — short structured answers ("drop-off",
    # "yes", "skip", "tbd"). When in these phases and the message isn't a question,
    # treat as answer. We INCLUDE "skip" here (unlike other phases) because the basic
    # info tool's _SERVICE_TYPE_INVALID handling re-asks gracefully rather than
    # letting modification_tool wrongly "remove" an unfilled service_type.
    if (
        _pre_faq_phase in {PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE}
        and _pre_faq_msg
        and "?" not in _pre_faq_msg
        and not _pre_faq_msg.startswith((
            "what", "where", "when", "why", "how", "who", "which", "do you",
        ))
        and not re.search(
            r"\b(?:remove|delete|change|update|swap|replace|cancel)\b",
            _pre_faq_msg,
        )
        and not _has_oos_marker
        and not _looks_like_personal
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="basic_info_tool", reason="binary_gate_bypass")],
            confidence=1.0,
        )

    # Add-ons phases (drinks/bar/tableware/rentals/labor) — short answers like "yes",
    # "no", "coffee and bar". Same protection: non-question messages are answers.
    _addons_phases = {PHASE_DRINKS_BAR, PHASE_TABLEWARE, PHASE_RENTALS, PHASE_LABOR}
    if (
        _pre_faq_phase in _addons_phases
        and _pre_faq_msg
        and "?" not in _pre_faq_msg
        and not _pre_faq_msg.startswith((
            "what", "where", "when", "why", "how", "who", "which",
            "do you", "does ", "is ", "are ", "can ", "could ",
        ))
        and not re.search(
            r"\b(?:remove|delete|change|update|swap|replace|cancel)\b",
            _pre_faq_msg,
        )
        and not _has_oos_marker
        and not _looks_like_personal
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="add_ons_tool", reason="addons_phase_answer_bypass")],
            confidence=1.0,
        )

    # Finalization gates (special_requests/dietary/followup/review) — non-question
    # messages route to finalization_tool so it can apply yes/no, confirm, etc.
    _finalization_phases = {PHASE_SPECIAL_REQUESTS, PHASE_DIETARY, PHASE_FOLLOWUP, PHASE_REVIEW}
    if (
        _pre_faq_phase in _finalization_phases
        and _pre_faq_msg
        and "?" not in _pre_faq_msg
        and not _pre_faq_msg.startswith((
            "what", "where", "when", "why", "how", "who", "which",
            "do you", "does ", "is ", "are ",
        ))
        and not re.search(
            r"\b(?:remove|delete|change|update|swap|replace)\b",
            _pre_faq_msg,
        )
        and not _has_oos_marker
        and not _looks_like_personal
    ):
        from agent.models import ToolCall as _TC
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[_TC(tool_name="finalization_tool", reason="finalization_phase_bypass")],
            confidence=1.0,
        )

    # In-scope FAQ guard — catering-related questions that can't advance the
    # form (pricing, what's included, recommendations, dietary, etc.).
    # Answer briefly and redirect rather than letting the LLM router fumble them.
    # Also pull the pending intake question from history so we can re-ask it
    # after the FAQ answer (state stays put while FAQ runs, but we need to remind
    # the user what they were being asked).
    _pending_question = _extract_last_question(history)
    _faq = await _in_scope_faq_response(
        message, history, phase=_pre_faq_phase, pending_question=_pending_question,
    )
    if _faq:
        return OrchestratorDecision(
            action="clarify",
            tool_calls=[],
            confidence=1.0,
            clarifying_question=_faq,
        )

    # Vague/filler guard — "idk", "whatever", "you choose", etc. — give a gentle
    # nudge to continue without wasting an LLM extraction call.
    _vague = _vague_response(message, state)
    if _vague:
        return OrchestratorDecision(
            action="clarify",
            tool_calls=[],
            confidence=1.0,
            clarifying_question=_vague,
        )

    # Personality OOS catch — personal/expressive messages with no catering context
    # (e.g. "BROTHER WHERE IS MY SALT", "I HAVE ULCER BROTHER"). The _FAQ_SKIP_PATTERN
    # in _in_scope_faq_response correctly skips these as "short intake answers", so they
    # would fall through to the LLM router which answers them too literally. Intercept here
    # with an acknowledge+bridge LLM response that mirrors the user's energy and redirects.
    if not _IN_SCOPE_ANCHORS.search(message):
        _persona_oos = await _personality_oos_response(message, state, history=history)
        if _persona_oos:
            return OrchestratorDecision(
                action="clarify",
                tool_calls=[],
                confidence=1.0,
                clarifying_question=_persona_oos,
            )

    # Fast path — skip LLM for obvious continuations and modification intents.
    # Honor structured answers to the most recent assistant question, even if
    # `conversation_phase` drifted (common after modification resume prompts).
    # Prevents replies like "drop-off" from being mis-routed to modification_tool
    # and accidentally reopening an unrelated section.
    msg_norm = _normalize_choice(message)
    if msg_norm and history:
        last_ai = next((m for m in reversed(history) if getattr(m, "type", "") == "ai"), None)
        last_text = _normalize_choice(str(getattr(last_ai, "content", "") or "")) if last_ai else ""
        if msg_norm in _SERVICE_TYPE_STRUCTURED_VALUES and ("onsite" in last_text and "drop" in last_text):
            from agent.models import ToolCall as _TC
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[_TC(tool_name="basic_info_tool", reason="recent_prompt:service_type")],
                confidence=1.0,
            )

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
                max_tokens=5000,
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
                max_tokens=5000,
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
            # FLAG-9: return a phase-grounded question instead of empty clarification
            # so the orchestrator has a real clarifying_question to show rather than
            # falling back to a generic LLM-generated "I didn't understand".
            _phase_q = _PHASE_CLARIFYING_QUESTIONS.get(
                state.get("conversation_phase") or PHASE_GREETING,
                "Could you say that a different way? I want to make sure I get it right.",
            )
            return OrchestratorDecision(
                action="clarify",
                tool_calls=[],
                confidence=signals.confidence,
                clarifying_question=_phase_q,
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
            #
            # FLAG-12: also allow basic_info_tool through when the message is
            # clearly correcting event identity ("actually it's corporate",
            # "wait it's a birthday") — phase-locking those sends the wrong tool
            # and completely ignores the correction.
            _is_identity_correction = (
                chosen == "basic_info_tool"
                and re.search(
                    r"\b(?:event\s+type|it(?:'s|\s+is)\s+a|type\s+is|actually\s+a"
                    r"|corporate|wedding|birthday|not\s+a\s+wedding|not\s+a\s+birthday"
                    r"|not\s+corporate)\b",
                    message.lower(),
                )
            )
            if chosen != "modification_tool" and not _is_identity_correction:
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

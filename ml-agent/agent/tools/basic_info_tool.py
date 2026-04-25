"""
BasicInfoTool - S1 through S7.

Owns: name, email, phone, event_type, event_date, venue, guest_count,
partner_name, company_name, honoree_name, service_type.

Key rules:
- `service_type` collected BEFORE food (moved from old flow).
- Future dates only - ALL event types including Birthday (FIX).
- Meta-commands ("change date") during venue step never fill venue (FIX-01).
- Multiple slots can be filled from one message - Orchestrator doesn't care
  about order, this Tool takes whatever the extractor finds.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import BaseMessage

from agent.cascade import apply_cascade
from agent.event_identity import filter_identity_fields
from agent.instructor_client import extract, filter_extraction_fields
from agent.models import EventDetailsExtraction
from agent.state import (
    PHASE_CONDITIONAL_FOLLOWUP,
    PHASE_DRINKS_BAR,
    PHASE_EVENT_DATE,
    PHASE_EVENT_TYPE,
    PHASE_GREETING,
    PHASE_GUEST_COUNT,
    PHASE_REVIEW,
    PHASE_SERVICE_TYPE,
    PHASE_TRANSITION,
    PHASE_VENUE,
    PHASE_WEDDING_CAKE,
    clear_slot,
    fill_slot,
    get_slot_value,
    is_filled,
)
from agent.tools.base import ToolResult, history_for_llm
from agent.modification_picker import make_modification_picker_result
from agent.tools.structured_choice import normalize_structured_choice


_PHASE_ALLOWED_FIELDS = {
    PHASE_GREETING: ["name", "email", "phone"],
    PHASE_EVENT_TYPE: ["event_type"],
    PHASE_CONDITIONAL_FOLLOWUP: ["partner_name", "company_name", "honoree_name"],
    PHASE_WEDDING_CAKE: ["wedding_cake"],
    PHASE_SERVICE_TYPE: ["service_type"],
    PHASE_EVENT_DATE: ["event_date"],
    PHASE_VENUE: ["venue"],
    PHASE_GUEST_COUNT: ["guest_count"],
}


_SYSTEM_PROMPT = (
    "# Role\n"
    "You extract event planning details from a customer message.\n\n"
    "# Rules\n"
    "- Extract ONLY what is explicitly stated in the message.\n"
    "- Return None for anything not mentioned.\n"
    "- Never invent data.\n"
    "- name: first+last if both given, else whatever is given.\n"
    "- event_type: ONLY extract if the user clearly names an event type. "
    "Map 'wedding'->Wedding, 'birthday/bday'->Birthday, "
    "'corporate/company/office'->Corporate. "
    "CRITICAL: if the user says 'no', 'yes', 'ok', 'sure', 'maybe', or anything that "
    "does not name an event type, return None for event_type. Do NOT invent 'Other'.\n"
    "- event_type_other: only extract if explicitly requested.\n"
    "- event_date: accept any format ('may 5', '05/19/27'), parse to YYYY-MM-DD. "
    "MUST be a future date. Reject past dates by returning None for this field.\n"
    "- guest_count: extract number only ('around 100' -> 100). Must be > 0.\n"
    "- service_type: 'onsite/on site/staff'->Onsite, 'dropoff/drop off/delivery'->Dropoff.\n"
    "- venue: physical location only. If the user says 'change date' or any "
    "meta-command during a venue question, return None for venue.\n"
    "- partner_name / company_name / honoree_name: only extract if event_type "
    "matches (Wedding / Corporate / Birthday).\n\n"
    "# Examples\n"
    "1. User: 'Syed Ali'\n"
    "   Extract: name='Syed Ali'\n"
    "2. User: 'corporate'\n"
    "   Extract: event_type='Corporate'\n"
    "3. User: 'drop off'\n"
    "   Extract: service_type='Dropoff'\n"
    "4. User: 'around 100'\n"
    "   Extract: guest_count=100\n"
    "5. User: '2026-04-25'\n"
    "   Extract: event_date='2026-04-25'\n"
    "6. User: 'change the date'\n"
    "   Extract: (all fields None)\n"
)

_BASIC_FOLLOWUP_FILLER = {
    "nice", "ok", "okay", "cool", "sounds good", "great", "perfect",
    "got it", "works", "that works", "awesome", "sweet",
}


_WEDDING_CAKE_FLAVORS = {
    "yellow", "white", "almond", "chocolate", "carrot", "red velvet",
    "bananas foster", "whiskey caramel", "lemon", "spice", "funfetti",
    "pumpkin spice", "cookies and cream", "strawberry", "coconut",
}
_WEDDING_CAKE_FILLINGS = {
    "butter cream", "lemon curd", "raspberry jam", "strawberry jam",
    "cream cheese icing", "peanut butter cream", "mocha buttercream",
    "salted caramel buttercream", "cinnamon butter cream",
}
_WEDDING_CAKE_BUTTERCREAMS = {
    "signature", "chocolate", "cream cheese frosting",
}


def _normalize_wedding_cake_choice(raw: str, allowed: set[str]) -> str | None:
    msg = (raw or "").strip().lower().strip(" .,!?")
    if not msg:
        return None
    if msg in allowed:
        return msg
    # Robust partial matching so "cream cheese" or "cream-cheese frosting" works.
    simplified = re.sub(r"[^a-z0-9\s]+", " ", msg).strip()
    simplified = re.sub(r"\s+", " ", simplified)
    for option in allowed:
        if option in simplified:
            return option
    # Extra friendly aliases
    if "cream cheese" in simplified and any("cream cheese" in o for o in allowed):
        for option in allowed:
            if "cream cheese" in option:
                return option
    if "buttercream" in simplified and "butter cream" in allowed:
        return "butter cream"
    return None


def _display_structured_choice(raw_message: str, normalized: str) -> str:
    raw = (raw_message or "").strip()
    if raw and raw.lower().strip(" .,!?") == normalized:
        return raw
    return normalized.title()


def _wedding_cake_stage(slots: dict) -> str | None:
    if not is_filled(slots, "__wedding_cake_gate"):
        return "ask_wedding_cake"
    if get_slot_value(slots, "__wedding_cake_gate") is False:
        return None
    if not is_filled(slots, "__wedding_cake_flavor"):
        return "ask_wedding_cake_flavor"
    if not is_filled(slots, "__wedding_cake_filling"):
        return "ask_wedding_cake_filling"
    if not is_filled(slots, "__wedding_cake_buttercream"):
        return "ask_wedding_cake_buttercream"
    return None


def _normalize_tbd_venue(message_lower: str) -> str | None:
    msg = message_lower.strip()
    if not msg:
        return None

    exact_matches = {
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
        "skip",
        "skip for now",
        "venue tbd - will confirm later",
        "venue tbd - confirm later",
        # Short "I don't know yet" replies that are never a real venue name
        "no", "nope", "nah", "not sure", "unsure", "idk", "i don't know",
        "i dont know", "not confirmed", "not confirmed yet", "call",
        "confirm", "later", "tbd confirm", "dont know", "unknown", "n/a",
        "no venue", "no venue yet", "none", "none yet",
    }
    if msg in exact_matches:
        return "TBD - Confirm on call"

    if (
        msg.startswith("venue tbd")
        or ("tbd" in msg and "venue" in msg)
        or "to be determined" in msg
        or "confirm later" in msg
        or "confirm on call" in msg
        or ("confirm" in msg and "venue" in msg and ("call" in msg or "later" in msg))
        or "not decided yet" in msg
    ):
        return "TBD - Confirm on call"

    return None


def _history_for_llm(history: list[BaseMessage]) -> list[dict]:
    return history_for_llm(history)


def _menu_is_complete(slots: dict) -> bool:
    """Return True when all core menu selections have been collected."""
    if not is_filled(slots, "cocktail_hour"):
        return False
    if not is_filled(slots, "appetizers"):
        return False
    if not is_filled(slots, "appetizer_style"):
        return False
    if not is_filled(slots, "selected_dishes") and not get_slot_value(slots, "custom_menu"):
        return False
    if not is_filled(slots, "meal_style"):
        return False
    if not is_filled(slots, "desserts"):
        return False
    return True


def _next_phase(slots: dict) -> str:
    """Return the phase that represents the first missing basic-info slot.

    Flow order:
      1. name → email → phone → event_type   (always first)
      2. conditional (partner/company/honoree name)
      3. appetizers → mains → desserts           (menu)
      4. wedding_cake                            (weddings only)
      5. service_type                            (after desserts)
      6. event_date → venue → guest_count
      7. PHASE_DRINKS_BAR                        (all basic info done)
    """
    # 1. Core identity — collected before anything else
    if not is_filled(slots, "name"):
        return PHASE_GREETING
    if not is_filled(slots, "email"):
        return PHASE_GREETING
    if not is_filled(slots, "phone"):
        return PHASE_GREETING
    if not is_filled(slots, "event_type"):
        return PHASE_EVENT_TYPE

    # 2. Conditional followup immediately after event type
    event_type = get_slot_value(slots, "event_type")
    if event_type == "Wedding" and not is_filled(slots, "partner_name"):
        return PHASE_CONDITIONAL_FOLLOWUP
    if event_type == "Corporate" and not is_filled(slots, "company_name"):
        return PHASE_CONDITIONAL_FOLLOWUP
    if event_type == "Birthday" and not is_filled(slots, "honoree_name"):
        return PHASE_CONDITIONAL_FOLLOWUP
    # Custom event types are stored directly in event_type; no extra follow-up.

    # 3. Jump to menu
    if not _menu_is_complete(slots):
        return PHASE_TRANSITION

    # 4. Post-menu basic info
    if event_type == "Wedding" and _wedding_cake_stage(slots) is not None:
        return PHASE_WEDDING_CAKE
    if not is_filled(slots, "service_type"):
        return PHASE_SERVICE_TYPE
    if not is_filled(slots, "event_date"):
        return PHASE_EVENT_DATE
    if not is_filled(slots, "venue"):
        return PHASE_VENUE
    if not is_filled(slots, "guest_count"):
        return PHASE_GUEST_COUNT

    # 7. All basic info done — hand off to add-ons
    return PHASE_DRINKS_BAR


def _next_phase_from_current(current_phase: str | None, slots: dict) -> str:
    """Compute next phase without regressing earlier intake steps.

    In normal flows, phases advance sequentially. But when resuming from a
    persisted state (or when a tool is called directly in tests), we should not
    jump backwards to re-ask name/email/phone if the caller is already working
    on a later phase like venue or wedding cake.
    """
    phase = current_phase or PHASE_GREETING
    if phase == PHASE_GREETING:
        return _next_phase(slots)

    event_type = get_slot_value(slots, "event_type")

    if phase in {PHASE_EVENT_TYPE, PHASE_CONDITIONAL_FOLLOWUP}:
        if not is_filled(slots, "event_type"):
            return PHASE_EVENT_TYPE
        if event_type == "Wedding" and not is_filled(slots, "partner_name"):
            return PHASE_CONDITIONAL_FOLLOWUP
        if event_type == "Corporate" and not is_filled(slots, "company_name"):
            return PHASE_CONDITIONAL_FOLLOWUP
        if event_type == "Birthday" and not is_filled(slots, "honoree_name"):
            return PHASE_CONDITIONAL_FOLLOWUP
        # Custom event types are stored directly in event_type; no extra follow-up.
        if not _menu_is_complete(slots):
            return PHASE_TRANSITION

    if phase == PHASE_WEDDING_CAKE:
        if event_type == "Wedding" and _wedding_cake_stage(slots) is not None:
            return PHASE_WEDDING_CAKE
        # If cake is complete/declined, continue forward to post-menu basics.

    if phase == PHASE_TRANSITION:
        if not _menu_is_complete(slots):
            return PHASE_TRANSITION
        # Menu complete — fall through to post-menu ordering below.

    if phase in {PHASE_EVENT_DATE, PHASE_VENUE, PHASE_GUEST_COUNT, PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE}:
        if phase == PHASE_WEDDING_CAKE and event_type == "Wedding" and _wedding_cake_stage(slots) is not None:
            return PHASE_WEDDING_CAKE
        if event_type == "Wedding" and _wedding_cake_stage(slots) is not None:
            return PHASE_WEDDING_CAKE
        if not is_filled(slots, "service_type"):
            return PHASE_SERVICE_TYPE
        if not is_filled(slots, "event_date"):
            return PHASE_EVENT_DATE
        if not is_filled(slots, "venue"):
            return PHASE_VENUE
        if not is_filled(slots, "guest_count"):
            return PHASE_GUEST_COUNT
        return PHASE_DRINKS_BAR

    return _next_phase(slots)


class BasicInfoTool:
    name = "basic_info_tool"

    async def run(
        self,
        *,
        message: str,
        history: list[BaseMessage],
        state: dict,
    ) -> ToolResult:
        slots = state["slots"]

        filled_this_turn: list[tuple[str, Any]] = []
        cascade_effects: list[tuple[str, str]] = []
        rejected_date = False

        _msg_lower = normalize_structured_choice(message)
        _skip_extraction = False

        _SERVICE_TYPE_MAP: dict[str, str] = {
            "dropoff": "Dropoff",
            "drop-off": "Dropoff",
            "drop off": "Dropoff",
            "drop-off - delivery only, no staff": "Dropoff",
            "drop-off (no staff)": "Dropoff",
            "onsite": "Onsite",
            "on-site": "Onsite",
            "on site": "Onsite",
            "onsite - staff present at your event": "Onsite",
            "onsite (staff present)": "Onsite",
        }
        _SERVICE_TYPE_INVALID = {
            "no", "nope", "nah", "skip", "tbd", "confirm later", "both", "neither",
            "none", "not sure", "i'll confirm later", "not sure yet", "fix it", "fix",
        }
        if not is_filled(slots, "service_type") and state.get("conversation_phase") == PHASE_SERVICE_TYPE:
            if _msg_lower in _SERVICE_TYPE_INVALID:
                # Service type is required — must be onsite or dropoff, no TBD allowed.
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "filled_this_turn": [],
                        "cascade_effects": [],
                        "next_phase": PHASE_SERVICE_TYPE,
                        "next_question_target": "ask_service_type",
                    },
                    input_hint={
                        "type": "options",
                        "options": [
                            {"value": "Onsite", "label": "Onsite (staff present)"},
                            {"value": "Dropoff", "label": "Drop-off (delivery only)"},
                        ],
                    },
                    direct_response=(
                        "Service type is required — please choose one:\n"
                        "• **Onsite** — our staff will be present at your event\n"
                        "• **Drop-off** — we deliver the food, no staff onsite"
                    ),
                )
            elif _msg_lower in _SERVICE_TYPE_MAP:
                _svc = _SERVICE_TYPE_MAP[_msg_lower]
                fill_slot(slots, "service_type", _svc)
                filled_this_turn.append(("service_type", _svc))
                cascade_effects.extend(apply_cascade("service_type", None, _svc, slots))
                _skip_extraction = True
        elif not is_filled(slots, "service_type") and _msg_lower in _SERVICE_TYPE_MAP:
            _svc = _SERVICE_TYPE_MAP[_msg_lower]
            fill_slot(slots, "service_type", _svc)
            filled_this_turn.append(("service_type", _svc))
            cascade_effects.extend(apply_cascade("service_type", None, _svc, slots))
            _skip_extraction = True

        if state.get("conversation_phase") == PHASE_EVENT_DATE and not is_filled(slots, "event_date"):
            if _msg_lower in {
                "skip", "confirm later", "tbd", "i'll confirm later", "not sure yet",
                "skip for now", "decide later",
            }:
                fill_slot(slots, "event_date", "TBD")
                filled_this_turn.append(("event_date", "TBD"))
                _skip_extraction = True

        if state.get("conversation_phase") == PHASE_VENUE and not is_filled(slots, "venue"):
            normalized_tbd_venue = _normalize_tbd_venue(_msg_lower)
            if normalized_tbd_venue:
                fill_slot(slots, "venue", normalized_tbd_venue)
                filled_this_turn.append(("venue", normalized_tbd_venue))
                _skip_extraction = True

        if state.get("conversation_phase") == PHASE_GUEST_COUNT and not is_filled(slots, "guest_count"):
            if _msg_lower in {
                "tbd",
                "tbd_guest",
                "confirm on call",
                "i'll confirm later",
                "confirm later",
                "not confirmed yet",
                "skip",
            }:
                fill_slot(slots, "guest_count", "TBD")
                filled_this_turn.append(("guest_count", "TBD"))
                _skip_extraction = True

        if state.get("conversation_phase") == PHASE_CONDITIONAL_FOLLOWUP:
            # Self-reference guard: user says "me/my/mine/myself/i/our" for a
            # slot that requires a *different* person's name.
            _SELF_REF_TOKENS = {"me", "my", "mine", "myself", "i", "our", "my only"}
            _event_type_val = str(get_slot_value(slots, "event_type") or "").lower()
            if _msg_lower.strip() in _SELF_REF_TOKENS:
                if "birthday" in _event_type_val:
                    _user_name = str(get_slot_value(slots, "name") or "").strip()
                    if _user_name:
                        fill_slot(slots, "honoree_name", _user_name)
                        filled_this_turn.append(("honoree_name", _user_name))
                        _skip_extraction = True
                elif "wedding" in _event_type_val:
                    return ToolResult(
                        state=state,
                        response_context={
                            "tool": self.name,
                            "filled_this_turn": [],
                            "next_phase": state.get("conversation_phase"),
                            "next_question_target": "ask_partner_name",
                        },
                        direct_response="Ha, that's you! Who's your partner? What's their name?",
                    )
                elif "corporate" in _event_type_val:
                    return ToolResult(
                        state=state,
                        response_context={
                            "tool": self.name,
                            "filled_this_turn": [],
                            "next_phase": state.get("conversation_phase"),
                            "next_question_target": "ask_company_name",
                        },
                        direct_response="What's the name of the company hosting the event?",
                    )
            if _msg_lower in _BASIC_FOLLOWUP_FILLER:
                _skip_extraction = True
            # LLM extraction runs normally — _PHASE_ALLOWED_FIELDS filters the
            # result to only partner_name / company_name / honoree_name, so
            # any `name` over-extraction is discarded automatically.

        if state.get("conversation_phase") == PHASE_WEDDING_CAKE:
            cake_stage = _wedding_cake_stage(slots)
            if cake_stage == "ask_wedding_cake":
                if _msg_lower in {"yes", "yes please", "yes, add a wedding cake"}:
                    fill_slot(slots, "__wedding_cake_gate", True)
                    filled_this_turn.append(("__wedding_cake_gate", True))
                    _skip_extraction = True
                elif _msg_lower in {"no", "no thanks", "skip"}:
                    fill_slot(slots, "__wedding_cake_gate", False)
                    fill_slot(slots, "wedding_cake", "none")
                    filled_this_turn.append(("__wedding_cake_gate", False))
                    filled_this_turn.append(("wedding_cake", "none"))
                    _skip_extraction = True
            elif cake_stage == "ask_wedding_cake_flavor":
                normalized = _normalize_wedding_cake_choice(_msg_lower, _WEDDING_CAKE_FLAVORS)
                if not normalized:
                    _skip_extraction = False
                else:
                    flavor = _display_structured_choice(message, normalized)
                    fill_slot(slots, "__wedding_cake_flavor", flavor)
                    filled_this_turn.append(("__wedding_cake_flavor", flavor))
                    _skip_extraction = True
            elif cake_stage == "ask_wedding_cake_filling":
                normalized = _normalize_wedding_cake_choice(_msg_lower, _WEDDING_CAKE_FILLINGS)
                if not normalized:
                    _skip_extraction = False
                else:
                    filling = _display_structured_choice(message, normalized)
                    fill_slot(slots, "__wedding_cake_filling", filling)
                    filled_this_turn.append(("__wedding_cake_filling", filling))
                    _skip_extraction = True
            elif cake_stage == "ask_wedding_cake_buttercream":
                normalized = _normalize_wedding_cake_choice(_msg_lower, _WEDDING_CAKE_BUTTERCREAMS)
                if not normalized:
                    _skip_extraction = False
                else:
                    flavor = str(get_slot_value(slots, "__wedding_cake_flavor") or "").strip()
                    filling = str(get_slot_value(slots, "__wedding_cake_filling") or "").strip()
                    buttercream = _display_structured_choice(message, normalized)
                    fill_slot(slots, "__wedding_cake_buttercream", buttercream)
                    fill_slot(
                        slots,
                        "wedding_cake",
                        f'2 Tier 6" & 8" - {flavor}, {filling}, {buttercream}',
                    )
                    filled_this_turn.append(("__wedding_cake_buttercream", buttercream))
                    filled_this_turn.append(("wedding_cake", get_slot_value(slots, "wedding_cake")))
                    _skip_extraction = True

        extracted = None
        if (
            state.get("conversation_phase") == PHASE_EVENT_TYPE
            and not is_filled(slots, "event_type")
            and get_slot_value(slots, "__awaiting_custom_event_type") is not True
        ):
            _EVENT_TYPE_MAP = {
                "wedding": "Wedding",
                "birthday": "Birthday",
                "bday": "Birthday",
                "corporate": "Corporate",
                "company": "Corporate",
                "office": "Corporate",
            }
            _CONFIRM_EVENT_TYPE_VALUES = {
                "confirm on call",
                "confirm later",
                "tbd",
                "skip",
                "tbd - confirm on call",
            }

            if _msg_lower in _CONFIRM_EVENT_TYPE_VALUES:
                fill_slot(slots, "event_type", "TBD - Confirm on call")
                filled_this_turn.append(("event_type", "TBD - Confirm on call"))
                cascade_effects.extend(apply_cascade("event_type", None, "TBD - Confirm on call", slots))
                _skip_extraction = True
            elif _msg_lower in {"other", "others"}:
                # Two-step "Other": set an internal marker so the next prompt
                # asks what the event actually is (or confirm on call).
                fill_slot(slots, "__awaiting_custom_event_type", True)
                filled_this_turn.append(("__awaiting_custom_event_type", True))
                _skip_extraction = True
            elif _msg_lower in _EVENT_TYPE_MAP:
                val = _EVENT_TYPE_MAP[_msg_lower]
                fill_slot(slots, "event_type", val)
                filled_this_turn.append(("event_type", val))
                cascade_effects.extend(apply_cascade("event_type", None, val, slots))
                _skip_extraction = True
            else:
                # Free-text event type: store verbatim instead of forcing "Other".
                # Explicitly reject ambiguous non-answers so they are never stored.
                _EVENT_TYPE_JUNK = {
                    "no", "nope", "nah", "n", "yes", "yeah", "yep", "yup",
                    "ok", "okay", "sure", "maybe", "idk", "i don't know",
                    "i dont know", "not sure", "hmm", "hm", "uh", "um",
                    "none", "nothing", "skip", "fix", "fix it",
                }
                val = (message or "").strip()
                if val and _msg_lower not in _BASIC_FOLLOWUP_FILLER and _msg_lower not in _EVENT_TYPE_JUNK:
                    fill_slot(slots, "event_type", val)
                    filled_this_turn.append(("event_type", val))
                    cascade_effects.extend(apply_cascade("event_type", None, val, slots))
                    _skip_extraction = True

        # "Other" follow-up: user is now specifying the custom event label.
        if (
            state.get("conversation_phase") == PHASE_EVENT_TYPE
            and not is_filled(slots, "event_type")
            and get_slot_value(slots, "__awaiting_custom_event_type") is True
            and not _skip_extraction
        ):
            # Accept confirm-on-call tokens
            _CONFIRM_EVENT_TYPE_VALUES = {
                "confirm on call",
                "confirm later",
                "tbd",
                "skip",
                "tbd - confirm on call",
            }
            if _msg_lower in _CONFIRM_EVENT_TYPE_VALUES:
                fill_slot(slots, "event_type", "TBD - Confirm on call")
                filled_this_turn.append(("event_type", "TBD - Confirm on call"))
                cascade_effects.extend(apply_cascade("event_type", None, "TBD - Confirm on call", slots))
                clear_slot(slots, "__awaiting_custom_event_type")
                filled_this_turn.append(("__awaiting_custom_event_type", None))
                _skip_extraction = True
            else:
                # Ignore unhelpful/ambiguous replies — re-ask rather than save garbage.
                # "No", "yes", "ok", "sure", etc. are NOT valid event type names.
                _INVALID_EVENT_TYPE_REPLIES = {
                    "no", "nope", "nah", "n", "yes", "yeah", "yep", "yup",
                    "ok", "okay", "sure", "maybe", "idk", "i don't know",
                    "i dont know", "not sure", "hmm", "hm", "uh", "um",
                }
                if _msg_lower in {"other", "others"} or not (message or "").strip() or _msg_lower in _INVALID_EVENT_TYPE_REPLIES:
                    # Explain the two valid options instead of silently re-asking.
                    return ToolResult(
                        state=state,
                        response_context={
                            "tool": self.name,
                            "filled_this_turn": [],
                            "cascade_effects": [],
                            "next_phase": PHASE_EVENT_TYPE,
                            "next_question_target": "ask_other_event_type",
                        },
                        input_hint={
                            "type": "options",
                            "options": [
                                {"value": "confirm on call", "label": "Confirm on call"},
                            ],
                        },
                        direct_response=(
                            "No worries! You can either tell me what kind of event it is "
                            "(e.g., graduation, anniversary, quinceañera) so I can note it down, "
                            "or reply \"confirm on call\" and we'll sort out the details before the event."
                        ),
                    )
                else:
                    val = (message or "").strip()
                    fill_slot(slots, "event_type", val)
                    filled_this_turn.append(("event_type", val))
                    cascade_effects.extend(apply_cascade("event_type", None, val, slots))
                    clear_slot(slots, "__awaiting_custom_event_type")
                    filled_this_turn.append(("__awaiting_custom_event_type", None))
                    _skip_extraction = True

        if not _skip_extraction:
            extracted = await extract(
                schema=EventDetailsExtraction,
                system=_SYSTEM_PROMPT,
                user_message=message,
                history=_history_for_llm(history),
            )

        wrong_field_for_phase = False
        if extracted is not None:
            extracted_values = extracted.model_dump(exclude_none=True)
            effective_event_type = extracted_values.get("event_type") or get_slot_value(slots, "event_type")
            extracted_values = filter_identity_fields(
                extracted_values,
                event_type=effective_event_type,
            )
            # event_type_other is deprecated; avoid accidentally populating it.
            extracted_values.pop("event_type_other", None)
            allowed = _PHASE_ALLOWED_FIELDS.get(state.get("conversation_phase"), [])
            pre_filter_had_values = bool(extracted_values)
            extracted_values = filter_extraction_fields(extracted_values, allowed)
            # The LLM extracted something, but none of it was allowed for the
            # current phase — user is answering the wrong question. Signal the
            # response generator to re-ask instead of fabricating a confirmation.
            if pre_filter_had_values and not extracted_values:
                wrong_field_for_phase = True

            for field_name, value in extracted_values.items():
                old_value = get_slot_value(slots, field_name)
                if field_name == "event_date":
                    value = value.isoformat() if hasattr(value, "isoformat") else str(value)
                # Name must contain at least one letter — reject purely numeric/symbol strings
                if field_name == "name":
                    name_str = str(value or "").strip()
                    if not any(c.isalpha() for c in name_str):
                        return ToolResult(
                            state=state,
                            response_context={
                                "tool": self.name,
                                "filled_this_turn": [],
                                "cascade_effects": [],
                                "next_phase": state.get("conversation_phase"),
                                "next_question_target": "ask_name",
                            },
                            direct_response="That doesn't look like a name. Could you please share your first and last name?",
                        )
                fill_slot(slots, field_name, value)
                filled_this_turn.append((field_name, value))
                cascade_effects.extend(apply_cascade(field_name, old_value, value, slots))
        else:
            if state.get("conversation_phase") == PHASE_EVENT_DATE:
                rejected_date = True

        next_phase = _next_phase_from_current(state.get("conversation_phase"), slots)
        state["conversation_phase"] = next_phase

        # If the user initiated this slot change from the final review recap,
        # they usually want to quickly edit multiple fields. Return them to the
        # modification picker instead of continuing the normal flow.
        marker = get_slot_value(slots, "__return_to_review_after_edit")
        if isinstance(marker, dict):
            slot = str(marker.get("slot") or "").strip()
            return_to = str(marker.get("return_to") or "review").strip().lower()
            filled_slots = {k for k, _ in filled_this_turn}
            if slot and return_to == "picker" and slot in filled_slots:
                clear_slot(slots, "__return_to_review_after_edit")
                return make_modification_picker_result(
                    slots=slots,
                    state=state,
                    prompt="Anything else you want to change?",
                    include_done=True,
                    origin_phase=PHASE_REVIEW,
                )

        response_context = {
            "tool": self.name,
            "filled_this_turn": filled_this_turn,
            "cascade_effects": cascade_effects,
            "next_phase": next_phase,
            "rejected_past_date": rejected_date,
            "wrong_field_for_phase": wrong_field_for_phase,
            "filled_summary": {k: v for k, v in filled_this_turn},
            "current_event_type": get_slot_value(slots, "event_type"),
            "current_name": get_slot_value(slots, "name"),
            "next_question_target": _phase_to_question(next_phase, slots),
        }

        input_hint = _input_hint_for_phase(next_phase, slots)

        return ToolResult(
            state=state,
            response_context=response_context,
            input_hint=input_hint,
        )


def _phase_to_question(phase: str, slots: dict) -> str:
    """Short label describing what question the response generator should ask."""
    event_type = get_slot_value(slots, "event_type")
    if phase == PHASE_GREETING:
        if not is_filled(slots, "name"):
            return "ask_name"
        if not is_filled(slots, "email"):
            return "ask_email"
        if not is_filled(slots, "phone"):
            return "ask_phone"
    if phase == PHASE_EVENT_TYPE:
        # "Other" is a 2-step capture: user clicks "Other", then we ask what
        # kind of event it actually is (or "confirm on call"). We keep the
        # eventual label in `event_type` directly.
        if get_slot_value(slots, "__awaiting_custom_event_type") is True and not is_filled(slots, "event_type"):
            return "ask_other_event_type"
        return "ask_event_type"
    if phase == PHASE_CONDITIONAL_FOLLOWUP:
        if event_type == "Wedding":
            return "ask_partner_name"
        if event_type == "Corporate":
            return "ask_company_name"
        if event_type == "Birthday":
            return "ask_honoree_name"
    if phase == PHASE_WEDDING_CAKE:
        return _wedding_cake_stage(slots) or "continue"
    if phase == PHASE_SERVICE_TYPE:
        return "ask_service_type"
    if phase == PHASE_EVENT_DATE:
        return "ask_event_date"
    if phase == PHASE_VENUE:
        return "ask_venue"
    if phase == PHASE_GUEST_COUNT:
        return "ask_guest_count"
    if phase == PHASE_TRANSITION:
        if event_type == "Wedding":
            return "ask_service_style"
        return "transition_to_menu"
    if phase == PHASE_DRINKS_BAR:
        return "transition_to_addons"
    return "continue"


def _input_hint_for_phase(phase: str, slots: dict | None = None) -> dict | None:
    event_type = get_slot_value(slots or {}, "event_type")
    if phase == PHASE_GREETING:
        _slots = slots or {}
        if not is_filled(_slots, "name"):
            return {"type": "name"}
        if not is_filled(_slots, "email"):
            return {"type": "email"}
        if not is_filled(_slots, "phone"):
            return {"type": "phone"}
    if phase == PHASE_EVENT_TYPE:
        # If the user chose "Other", switch to a free-text follow-up with an
        # optional "confirm on call" chip.
        if get_slot_value(slots or {}, "__awaiting_custom_event_type") is True and not is_filled(slots or {}, "event_type"):
            return {
                "type": "options",
                "options": [
                    {"value": "confirm on call", "label": "Confirm on call"},
                ],
            }
        return {
            "type": "options",
            "options": [
                {"value": "Wedding", "label": "Wedding"},
                {"value": "Birthday", "label": "Birthday"},
                {"value": "Corporate", "label": "Corporate"},
                {"value": "Other", "label": "Other"},
                {"value": "confirm on call", "label": "Confirm on call"},
            ],
        }
    if phase == PHASE_SERVICE_TYPE:
        return {
            "type": "options",
            "options": [
                {"value": "Onsite", "label": "Onsite - staff present at event"},
                {"value": "Dropoff", "label": "Drop-off - delivery only, no staff"},
                {"value": "skip", "label": "Confirm later"},
            ],
        }
    if phase == PHASE_WEDDING_CAKE:
        target = _wedding_cake_stage(slots or {})
        if target == "ask_wedding_cake":
            return {
                "type": "options",
                "options": [
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No thanks"},
                ],
            }
        if target == "ask_wedding_cake_flavor":
            return {
                "type": "options",
                "options": [{"value": v, "label": v.title()} for v in [
                    "yellow", "white", "almond", "chocolate", "carrot", "red velvet",
                    "bananas foster", "whiskey caramel", "lemon", "spice", "funfetti",
                    "pumpkin spice", "cookies and cream", "strawberry", "coconut",
                ]],
            }
        if target == "ask_wedding_cake_filling":
            return {
                "type": "options",
                "options": [{"value": v, "label": v.title()} for v in [
                    "butter cream", "lemon curd", "raspberry jam", "strawberry jam",
                    "cream cheese icing", "peanut butter cream", "mocha buttercream",
                    "salted caramel buttercream", "cinnamon butter cream",
                ]],
            }
        if target == "ask_wedding_cake_buttercream":
            return {
                "type": "options",
                "options": [{"value": v, "label": v.title()} for v in [
                    "signature", "chocolate", "cream cheese frosting",
                ]],
            }
    if phase == PHASE_EVENT_DATE:
        return {
            "type": "date",
            "allow_skip": True,
            "skip_label": "Confirm later",
        }
    if phase == PHASE_VENUE:
        return {
            "type": "options",
            "subtype": "venue",
            "options": [
                {"value": "tbd_confirm_call", "label": "Confirm venue on call"},
            ],
            "allow_text": True,
        }
    if phase == PHASE_GUEST_COUNT:
        return {
            "type": "options",
            "subtype": "guest_count",
            "options": [
                {"value": "tbd", "label": "TBD / Confirm later"},
            ],
            "allow_text": True,
        }
    if phase == PHASE_TRANSITION and event_type == "Wedding":
        return {
            "type": "options",
            "options": [
                {"value": "cocktail hour", "label": "Cocktail hour"},
                {"value": "reception", "label": "Reception"},
                {"value": "both", "label": "Both"},
            ],
        }
    if phase == PHASE_DRINKS_BAR:
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes, add drinks or bar"},
                {"value": "no", "label": "No thanks"},
            ],
        }
    return None


__all__ = ["BasicInfoTool"]

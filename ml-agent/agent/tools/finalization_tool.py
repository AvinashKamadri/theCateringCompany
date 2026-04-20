"""
FinalizationTool — S16 through S19.

Owns: special_requests, dietary_concerns, additional_notes,
followup_call_requested, and the terminal review / confirm step.

On final confirmation it:
- Invokes `calculate_event_pricing()` from tools/pricing.py (authoritative
  financial breakdown that the /ml/contracts/generate endpoint consumes).
- Produces the short client-facing summary (item titles only, no prices —
  per AGENT_SPEC S19).
- Sets `conversation_status = pending_staff_review` so the frontend/email
  hooks can pick up the handoff.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import BaseMessage

from pydantic import BaseModel, Field

from agent.instructor_client import extract
from agent.menu_resolver import parse_slot_items
from agent.models import FinalizationExtraction
from agent.state import (
    PHASE_COMPLETE,
    PHASE_DIETARY,
    PHASE_FOLLOWUP,
    PHASE_REVIEW,
    PHASE_SPECIAL_REQUESTS,
    fill_slot,
    get_slot_value,
    is_filled,
)
from agent.tools.base import ToolResult
from tools.pricing import calculate_event_pricing


_SYSTEM_PROMPT = (
    "You parse the customer's wrap-up responses for a catering order.\n"
    "- special_requests: any free-form requests (decor, timing, allergies wording). "
    "IMPORTANT: if the user says 'no', 'none', 'nope', 'skip', 'nothing', 'no special requests', "
    "or any clear decline, set special_requests to the string 'none' (not null/None).\n"
    "- dietary_concerns: allergies / restrictions stated ('vegan', 'nut allergy'). "
    "If user says no dietary concerns / no restrictions, set to the string 'none'.\n"
    "- additional_notes: anything else the customer wants the staff to see.\n"
    "- followup_call_requested: True if they want a human call; False if they decline.\n"
    "- confirm_final: True ONLY if user explicitly confirms the summary is correct "
    "('yes looks good', 'confirm', 'send it'). Never guess."
)


def _history_for_llm(history: list[BaseMessage]) -> list[dict]:
    out: list[dict] = []
    for m in history[-6:]:
        role = "user" if getattr(m, "type", "") == "human" else "assistant"
        out.append({"role": role, "content": m.content})
    return out


def _next_target(slots: dict) -> str:
    if not is_filled(slots, "special_requests"):
        if not is_filled(slots, "__gate_special_requests"):
            return "ask_special_requests_gate"
        return "collect_special_requests"
    if not is_filled(slots, "dietary_concerns"):
        if not is_filled(slots, "__gate_dietary"):
            return "ask_dietary_gate"
        return "collect_dietary_concerns"
    if not is_filled(slots, "additional_notes"):
        if not is_filled(slots, "__gate_additional_notes"):
            return "ask_additional_notes_gate"
        return "collect_additional_notes"
    if not is_filled(slots, "followup_call_requested"):
        return "ask_followup_call"
    return "review"


def _phase_of(slots: dict) -> str:
    target = _next_target(slots)
    if target in {"ask_special_requests_gate", "collect_special_requests"}:
        return PHASE_SPECIAL_REQUESTS
    if target in {"ask_dietary_gate", "collect_dietary_concerns", "ask_additional_notes_gate", "collect_additional_notes"}:
        return PHASE_DIETARY
    if target == "ask_followup_call":
        return PHASE_FOLLOWUP
    return PHASE_REVIEW


def _allowed_fields_for_target(target: str) -> set[str]:
    if target == "collect_special_requests":
        return {"special_requests"}
    if target == "collect_dietary_concerns":
        return {"dietary_concerns"}
    if target == "collect_additional_notes":
        return {"additional_notes"}
    if target == "review":
        return {"confirm_final"}
    return set()


def _apply_structured_answer(
    *,
    target: str,
    message_lower: str,
    slots: dict,
    fills: list[tuple[str, Any]],
) -> bool:
    yes_values = {
        "yes",
        "yes, i have a special request",
        "yes, i have dietary concerns",
        "yes, add a note",
        "yes, schedule a call",
        "yes, please call me",
    }
    no_values = {
        "no",
        "no special requests",
        "no dietary concerns",
        "no additional notes",
        "no, don't schedule a call",
        "no, no call needed",
    }

    if target == "ask_special_requests_gate":
        if message_lower in yes_values:
            fill_slot(slots, "__gate_special_requests", True)
            fills.append(("__gate_special_requests", True))
            return True
        if message_lower in no_values:
            fill_slot(slots, "special_requests", "none")
            fills.append(("special_requests", "none"))
            return True

    if target == "ask_dietary_gate":
        if message_lower in yes_values:
            fill_slot(slots, "__gate_dietary", True)
            fills.append(("__gate_dietary", True))
            return True
        if message_lower in no_values:
            fill_slot(slots, "dietary_concerns", "none")
            fills.append(("dietary_concerns", "none"))
            return True

    if target == "ask_additional_notes_gate":
        if message_lower in yes_values:
            fill_slot(slots, "__gate_additional_notes", True)
            fills.append(("__gate_additional_notes", True))
            return True
        if message_lower in no_values:
            fill_slot(slots, "additional_notes", "none")
            fills.append(("additional_notes", "none"))
            return True

    if target == "ask_followup_call":
        if message_lower in yes_values:
            fill_slot(slots, "followup_call_requested", True)
            fills.append(("followup_call_requested", True))
            return True
        if message_lower in no_values:
            fill_slot(slots, "followup_call_requested", False)
            fills.append(("followup_call_requested", False))
            return True

    return False


def _input_hint_for_target(target: str) -> dict | None:
    if target == "ask_special_requests_gate":
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes, add a special request"},
                {"value": "no", "label": "No special requests"},
            ],
        }
    if target == "ask_dietary_gate":
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes, note food or health needs"},
                {"value": "no", "label": "No dietary concerns"},
            ],
        }
    if target == "ask_additional_notes_gate":
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes, add a final note"},
                {"value": "no", "label": "No additional notes"},
            ],
        }
    if target == "ask_followup_call":
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes, schedule a call"},
                {"value": "no", "label": "No call needed"},
            ],
        }
    if target == "review":
        return {
            "type": "options",
            "options": [
                {"value": "confirm", "label": "Looks good — send it"},
                {"value": "change", "label": "I need to change something"},
            ],
        }
    return None


def _direct_response_for_target(target: str) -> str | None:
    prompts = {
        "ask_special_requests_gate": (
            "Do you want anything extra at the event, like flowers, decor, timing help, "
            "or something special?"
        ),
        "collect_special_requests": (
            "Tell me the special thing you want us to note. For example: flowers, decor, "
            "timing, setup, or something extra."
        ),
        "ask_dietary_gate": (
            "Does anyone have food needs or health needs we should know about, like allergies, "
            "diabetes, vegan, or gluten-free?"
        ),
        "collect_dietary_concerns": "Tell me the food or health needs we should note.",
        "ask_additional_notes_gate": "Is there anything else you want us to remember before we finish?",
        "collect_additional_notes": "Tell me any last note you want us to remember.",
        "ask_followup_call": "Would you like us to schedule a quick call to go over everything?",
    }
    return prompts.get(target)


class FinalizationTool:
    name = "finalization_tool"

    async def run(
        self,
        *,
        message: str,
        history: list[BaseMessage],
        state: dict,
    ) -> ToolResult:
        slots = state["slots"]

        fills: list[tuple[str, Any]] = []
        confirm_final = False
        current_target = _next_target(slots)
        _msg_lower = message.strip().lower().rstrip(".,!?")

        structured_handled = _apply_structured_answer(
            target=current_target,
            message_lower=_msg_lower,
            slots=slots,
            fills=fills,
        )

        extracted = None
        if not structured_handled and current_target in {
            "collect_special_requests",
            "collect_dietary_concerns",
            "collect_additional_notes",
            "review",
        }:
            extracted = await extract(
                schema=FinalizationExtraction,
                system=_SYSTEM_PROMPT,
                user_message=message,
                history=_history_for_llm(history),
            )

        if extracted is not None:
            rescued = _apply_cross_target_capture(
                target=current_target,
                extracted=extracted,
                message=message,
                message_lower=_msg_lower,
                slots=slots,
                fills=fills,
            )
            if rescued:
                extracted = None

        if extracted is not None:
            dump = extracted.model_dump(exclude_none=True)
            for field_name, value in dump.items():
                if field_name == "confirm_final":
                    confirm_final = bool(value)
                    continue
                if field_name not in _allowed_fields_for_target(current_target):
                    continue
                fill_slot(slots, field_name, value)
                fills.append((field_name, value))

        _DECLINE_RE = {"no", "nope", "none", "skip", "nothing", "nah", "no thanks", "not really",
                       "no special requests", "no dietary concerns", "no additional notes",
                       "no notes", "all good", "im good", "i'm good"}
        if current_target == "collect_special_requests" and not is_filled(slots, "special_requests") and _msg_lower in _DECLINE_RE:
            fill_slot(slots, "special_requests", "none")
            fills.append(("special_requests", "none"))
        if current_target == "collect_dietary_concerns" and not is_filled(slots, "dietary_concerns") and _msg_lower in _DECLINE_RE:
            fill_slot(slots, "dietary_concerns", "none")
            fills.append(("dietary_concerns", "none"))
        if current_target == "collect_additional_notes" and not is_filled(slots, "additional_notes") and _msg_lower in _DECLINE_RE:
            fill_slot(slots, "additional_notes", "none")
            fills.append(("additional_notes", "none"))

        # Fallback: detect confirmation at review phase when extractor missed it.
        # The LLM is strict about "confirm_final" so casual phrases like
        # "we are done", "ok", "great", "looks good" slip through — resulting
        # in the review loop that wedges the conversation. Use a dedicated
        # yes/no classifier rather than a regex to avoid past over-match bugs.
        if not confirm_final and _phase_of(slots) == PHASE_REVIEW:
            if await _classify_review_confirmation(message):
                confirm_final = True

        # If user just confirmed, run pricing + freeze state
        if confirm_final and _phase_of(slots) == PHASE_REVIEW:
            pricing = await self._safe_pricing(slots)
            client_summary = _client_facing_summary(slots)
            fill_slot(slots, "conversation_status", "pending_staff_review")
            state["conversation_phase"] = PHASE_COMPLETE

            recap = _render_review_recap(client_summary)
            closing = (
                "\n\nPerfect — your request is locked in and sent to our team. "
                "A coordinator will review everything and reach out shortly to confirm. "
                "Thanks so much!"
            )
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "filled_this_turn": fills,
                    "confirm_final": True,
                    "client_summary": client_summary,
                    "pricing": pricing,
                    "next_phase": PHASE_COMPLETE,
                    "status": "pending_staff_review",
                },
                direct_response=recap + closing,
            )

        next_target = _next_target(slots)
        next_phase = _phase_of(slots)
        state["conversation_phase"] = next_phase

        response_context: dict[str, Any] = {
            "tool": self.name,
            "filled_this_turn": fills,
            "next_phase": next_phase,
            "next_question_target": next_target,
        }

        # On S19 review, hand the response generator a preview summary
        direct_response: str | None = None
        if next_phase == PHASE_REVIEW:
            summary = _client_facing_summary(slots)
            response_context["client_summary"] = summary
            response_context["awaiting_confirm"] = True
            # Deterministic recap — avoids the LLM echoing tableware/service
            # option words that would re-trigger those card widgets in the UI.
            direct_response = _render_review_recap(summary)
        elif next_target in {
            "collect_special_requests",
            "collect_dietary_concerns",
            "collect_additional_notes",
        }:
            # Keep free-text follow-ups deterministic so the agent does not
            # drift back into a repeated yes/no gate after the user already said yes.
            direct_response = _direct_response_for_target(next_target)
        input_hint = _input_hint_for_target(next_target)

        return ToolResult(
            state=state,
            response_context=response_context,
            input_hint=input_hint,
            direct_response=direct_response,
        )

    async def _safe_pricing(self, slots: dict) -> dict | None:
        guest_count = get_slot_value(slots, "guest_count")
        event_type = get_slot_value(slots, "event_type") or "Other"
        service_type = get_slot_value(slots, "service_type") or "Onsite"
        if not guest_count:
            return None
        try:
            gc = int(guest_count)
        except (TypeError, ValueError):
            return None
        return await calculate_event_pricing(
            guest_count=gc,
            event_type=event_type,
            service_type=service_type,
            selected_dishes=get_slot_value(slots, "selected_dishes"),
            appetizers=get_slot_value(slots, "appetizers"),
            desserts=get_slot_value(slots, "desserts"),
            utensils=get_slot_value(slots, "utensils"),
            rentals=get_slot_value(slots, "rentals"),
        )


def _client_facing_summary(slots: dict) -> dict:
    """Short-form summary — item titles only, no prices (spec S19)."""

    def _titles(slot: str) -> list[str]:
        raw = get_slot_value(slots, slot)
        if not raw or str(raw).lower() in ("none", "no", "n/a"):
            return []
        return parse_slot_items(str(raw))

    return {
        # Basic info
        "name": get_slot_value(slots, "name"),
        "email": get_slot_value(slots, "email"),
        "phone": get_slot_value(slots, "phone"),
        "event_type": get_slot_value(slots, "event_type"),
        "event_date": get_slot_value(slots, "event_date"),
        "venue": get_slot_value(slots, "venue"),
        "guest_count": get_slot_value(slots, "guest_count"),
        "service_type": get_slot_value(slots, "service_type"),
        # Conditional basic info
        "partner_name": get_slot_value(slots, "partner_name"),
        "company_name": get_slot_value(slots, "company_name"),
        "honoree_name": get_slot_value(slots, "honoree_name"),
        # Menu
        "cocktail_hour": get_slot_value(slots, "cocktail_hour"),
        "service_style": get_slot_value(slots, "service_style"),
        "meal_style": get_slot_value(slots, "meal_style"),
        "appetizer_style": get_slot_value(slots, "appetizer_style"),
        "appetizers": _titles("appetizers"),
        "selected_dishes": _titles("selected_dishes"),
        "desserts": _titles("desserts"),
        "wedding_cake": get_slot_value(slots, "wedding_cake"),
        "menu_notes": get_slot_value(slots, "menu_notes"),
        # Drinks & bar
        "drinks": get_slot_value(slots, "drinks"),
        "bar_service": get_slot_value(slots, "bar_service"),
        "bar_package": get_slot_value(slots, "bar_package"),
        "bartender": get_slot_value(slots, "bartender"),
        "coffee_service": get_slot_value(slots, "coffee_service"),
        # Tableware
        "tableware": get_slot_value(slots, "tableware"),
        "utensils": get_slot_value(slots, "utensils"),
        # Rentals & labor
        "linens": get_slot_value(slots, "linens"),
        "rentals": get_slot_value(slots, "rentals"),
        "labor_ceremony_setup": get_slot_value(slots, "labor_ceremony_setup"),
        "labor_table_setup": get_slot_value(slots, "labor_table_setup"),
        "labor_table_preset": get_slot_value(slots, "labor_table_preset"),
        "labor_cleanup": get_slot_value(slots, "labor_cleanup"),
        "labor_trash": get_slot_value(slots, "labor_trash"),
        "travel_fee": get_slot_value(slots, "travel_fee"),
        # Finalization
        "special_requests": get_slot_value(slots, "special_requests"),
        "dietary_concerns": get_slot_value(slots, "dietary_concerns"),
        "additional_notes": get_slot_value(slots, "additional_notes"),
        "followup_call_requested": get_slot_value(slots, "followup_call_requested"),
    }


_TABLEWARE_PRETTY = {
    "standard_disposable": "standard flatware",
    "silver_disposable": "silver flatware",
    "gold_disposable": "gold flatware",
    "china": "real china",
    "no_tableware": "no tableware",
}

_UTENSILS_PRETTY = {
    "standard_plastic": "standard utensils",
    "eco_biodegradable": "eco-friendly utensils",
    "bamboo": "bamboo utensils",
}


class _ReviewConfirmClassification(BaseModel):
    """Is the user confirming the final review summary, or asking to change something?"""

    is_confirming: bool = Field(
        ...,
        description=(
            "True ONLY if the user is giving a clear affirmative to submit the "
            "order as shown ('yes', 'looks good', 'send it', 'we're done', "
            "'perfect', 'ship it', 'confirm'). False if they want changes, ask "
            "a question, or are ambiguous. When unsure, return False."
        ),
    )


_CLASSIFIER_SYSTEM = (
    "You decide whether the customer is confirming their final catering order "
    "as displayed, or pushing back / asking for changes.\n"
    "The assistant has just shown a full recap and asked 'are we good to submit this?'.\n"
    "Return is_confirming=True for ANY clear affirmative — this includes:\n"
    "  'yes', 'ok', 'okay', 'sure', 'yep', 'yeah', 'looks good', 'we good',\n"
    "  'yes we good', 'send it', 'confirm', 'go ahead', 'perfect', 'great',\n"
    "  'all good', 'lets go', \"that's fine\", 'sounds good', 'do it'.\n"
    "Return is_confirming=False ONLY if the customer explicitly wants to change\n"
    "something, asks a question, or expresses doubt ('actually...', 'wait',\n"
    "'can you change', 'I want to add', 'remove the', 'what about').\n"
    "When in doubt, lean True — the customer has already reviewed the full recap."
)


_FAST_CONFIRMS = {
    "yes", "ok", "okay", "yep", "yeah", "sure", "confirm", "send it",
    "go ahead", "looks good", "we good", "yes we good", "all good",
    "lets go", "let's go", "do it", "great", "perfect", "sounds good",
    "that works", "approved", "submit", "ship it", "yes looks good",
    "yes, looks good", "yes, send it",
}


async def _classify_review_confirmation(message: str) -> bool:
    if not message or not message.strip():
        return False
    # Fast path — skip the LLM call for unambiguous single-phrase confirms
    _normalized = message.strip().lower().rstrip(".,!?")
    if _normalized in _FAST_CONFIRMS:
        return True
    try:
        result = await extract(
            schema=_ReviewConfirmClassification,
            system=_CLASSIFIER_SYSTEM,
            user_message=message,
        )
    except Exception:
        return False
    return bool(result and result.is_confirming)


_DIETARY_HINT_RE = re.compile(
    r"\b(allerg(?:y|ies)|diabet|vegan|vegetarian|gluten|celiac|halal|kosher|"
    r"nut|dairy|lactose|shellfish|egg|soy|pork[- ]?free|food need|health need)\b",
    re.IGNORECASE,
)


def _apply_cross_target_capture(
    *,
    target: str,
    extracted: FinalizationExtraction,
    message: str,
    message_lower: str,
    slots: dict,
    fills: list[tuple[str, Any]],
) -> bool:
    if target != "collect_special_requests":
        return False

    dietary_value = extracted.dietary_concerns
    if not dietary_value and _DIETARY_HINT_RE.search(message_lower):
        dietary_value = message.strip()
    if not dietary_value:
        return False

    if not is_filled(slots, "special_requests"):
        fill_slot(slots, "special_requests", "none")
        fills.append(("special_requests", "none"))
    fill_slot(slots, "dietary_concerns", dietary_value)
    fills.append(("dietary_concerns", dietary_value))
    return True



def _render_review_recap(s: dict) -> str:
    """Human-readable recap that avoids frontend card-trigger keywords.

    The frontend scans agent text for words like 'disposable', 'china',
    'drop-off', 'plated', 'passed around' and re-injects option cards. At the
    review step those cards are stale — so we sanitize the wording.
    """
    name = s.get("name") or "there"
    lines: list[str] = [f"Here's the recap{', ' + name if name != 'there' else ''}:"]

    parts = []
    if s.get("event_type"):
        parts.append(str(s["event_type"]))
    if s.get("event_date"):
        parts.append(f"on {s['event_date']}")
    if s.get("venue"):
        parts.append(f"at {s['venue']}")
    if s.get("guest_count"):
        parts.append(f"for {s['guest_count']} guests")
    if parts:
        lines.append("• " + " ".join(parts))

    if s.get("email"):
        lines.append(f"• Email: {s['email']}")
    if s.get("phone"):
        lines.append(f"• Phone: {s['phone']}")

    event_type = str(s.get("event_type") or "").lower()
    if "wedding" in event_type and s.get("partner_name"):
        lines.append(f"• Partner: {s['partner_name']}")
    if "corporate" in event_type and s.get("company_name"):
        lines.append(f"• Company: {s['company_name']}")
    if "birthday" in event_type and s.get("honoree_name"):
        lines.append(f"• Honoree: {s['honoree_name']}")

    service = (s.get("service_type") or "").lower()
    if service == "dropoff":
        lines.append("• Service: delivery only")
    elif service == "onsite":
        lines.append("• Service: full onsite staffing")

    meal = (s.get("meal_style") or "").lower()
    if meal == "plated":
        lines.append("• Meal served individually to each guest")
    elif meal == "buffet":
        lines.append("• Meal served buffet-style")

    if "wedding" in event_type:
        service_style = str(s.get("service_style") or "").lower()
        if service_style == "cocktail_hour":
            lines.append("• Service style: cocktail hour")
        elif service_style == "reception":
            lines.append("• Service style: reception")
        elif service_style == "both":
            lines.append("• Service style: both")
        elif s.get("cocktail_hour") is True:
            lines.append("• Cocktail hour: yes")
        elif s.get("cocktail_hour") is False:
            lines.append("• Cocktail hour: no")

    if s.get("appetizers"):
        lines.append(f"• Appetizers: {', '.join(s['appetizers'])}")
    if s.get("selected_dishes"):
        lines.append(f"• Mains: {', '.join(s['selected_dishes'])}")
    if s.get("desserts"):
        lines.append(f"• Desserts: {', '.join(s['desserts'])}")
    else:
        lines.append("• Desserts: none")
    if s.get("wedding_cake"):
        lines.append(f"• Wedding cake: {s['wedding_cake']}")

    tw_label = _TABLEWARE_PRETTY.get(str(s.get("tableware") or "").lower())
    if tw_label:
        lines.append(f"• Flatware: {tw_label}")
    ut_label = _UTENSILS_PRETTY.get(str(s.get("utensils") or "").lower())
    if ut_label:
        lines.append(f"• Cutlery: {ut_label}")
    if s.get("linens"):
        lines.append("• Linens included")

    if s.get("drinks") is True:
        lines.append("• Drinks: included")
    elif s.get("drinks") is False:
        lines.append("• Drinks: not included")

    if s.get("bar_service"):
        lines.append("• Bar service included")
        if s.get("bar_package"):
            _bp_pretty = {
                "beer_wine": "beer & wine",
                "beer_wine_signature": "beer, wine + 2 signature drinks",
                "full_open_bar": "full open bar",
            }
            lines.append(f"  — {_bp_pretty.get(str(s['bar_package']), s['bar_package'])}")
    if s.get("coffee_service"):
        lines.append("• Coffee bar included")

    rentals = s.get("rentals")
    if rentals and str(rentals).lower() not in {"none", "no"}:
        if isinstance(rentals, str):
            lines.append(f"• Rentals: {rentals}")
        else:
            lines.append(f"• Rentals: {', '.join(rentals)}")

    # Labor (onsite only — skip for dropoff)
    if service == "onsite":
        _labor_map = {
            "labor_ceremony_setup": "Ceremony setup",
            "labor_table_setup": "Table setup",
            "labor_table_preset": "Tables preset before guests",
            "labor_cleanup": "Cleanup after event",
            "labor_trash": "Trash removal",
        }
        labor_yes = [label for slot, label in _labor_map.items() if s.get(slot) is True]
        if labor_yes:
            lines.append(f"• Staffing: {', '.join(labor_yes)}")

    if s.get("special_requests") and str(s["special_requests"]).lower() != "none":
        lines.append(f"• Special requests: {s['special_requests']}")
    if s.get("dietary_concerns") and str(s["dietary_concerns"]).lower() != "none":
        lines.append(f"• Dietary: {s['dietary_concerns']}")
    if s.get("additional_notes") and str(s["additional_notes"]).lower() != "none":
        lines.append(f"• Additional notes: {s['additional_notes']}")
    if s.get("followup_call_requested") is True:
        lines.append("• Follow-up call: requested")
    elif s.get("followup_call_requested") is False:
        lines.append("• Follow-up call: not requested")

    lines.append("")
    lines.append("Everything's locked in — are we good to submit this?")
    return "\n".join(lines)


__all__ = ["FinalizationTool"]

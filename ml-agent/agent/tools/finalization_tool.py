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
    clear_slot,
    fill_slot,
    get_slot_value,
    is_filled,
)
from agent.tools.base import ToolResult, history_for_llm
from agent.tools.structured_choice import normalize_structured_choice
from tools.pricing import calculate_event_pricing


_SYSTEM_PROMPT = (
    "# Role\n"
    "You parse the customer's wrap-up responses for a catering order.\n\n"
    "# Rules\n"
    "- The user may answer the current question, decline it, or volunteer other wrap-up details early.\n"
    "- Capture facts explicitly stated without inventing anything.\n"
    "- special_requests: free-form requests. If user clearly declines, set to the string 'none' (not null).\n"
    "- dietary_concerns: allergies/restrictions. If user clearly declines, set to the string 'none'.\n"
    "- additional_notes: anything else the customer wants staff to see.\n"
    "- followup_call_requested: True if they want a human call; False if they decline.\n"
    "- confirm_final: True ONLY if user explicitly confirms the summary is correct ('confirm', 'send it', 'looks good'). Never guess.\n\n"
    "# Examples\n"
    "1. User: 'no special requests'\n"
    "   Extract: special_requests='none'\n"
    "2. User: 'nut allergy'\n"
    "   Extract: dietary_concerns='nut allergy'\n"
    "3. User: 'no dietary restrictions'\n"
    "   Extract: dietary_concerns='none'\n"
    "4. User: 'looks good, send it'\n"
    "   Extract: confirm_final=True\n"
)


def _history_for_llm(history: list[BaseMessage]) -> list[dict]:
    return history_for_llm(history)


def _next_target(slots: dict) -> str:
    if not is_filled(slots, "special_requests"):
        if not is_filled(slots, "__gate_special_requests"):
            return "ask_special_requests_gate"
        return "collect_special_requests"
    if not is_filled(slots, "dietary_concerns"):
        if not is_filled(slots, "__gate_dietary"):
            return "ask_dietary_gate"
        return "collect_dietary_concerns"
    # Skip "additional notes" entirely (too many closing questions).
    if not is_filled(slots, "additional_notes"):
        fill_slot(slots, "additional_notes", "none")
    if not is_filled(slots, "followup_call_requested"):
        return "ask_followup_call"
    return "review"


def _phase_of(slots: dict) -> str:
    target = _next_target(slots)
    if target in {"ask_special_requests_gate", "collect_special_requests"}:
        return PHASE_SPECIAL_REQUESTS
    if target in {"ask_dietary_gate", "collect_dietary_concerns"}:
        return PHASE_DIETARY
    if target == "ask_followup_call":
        return PHASE_FOLLOWUP
    return PHASE_REVIEW


def _allowed_fields_for_target(target: str) -> set[str]:
    if target in {"ask_special_requests_gate", "collect_special_requests"}:
        return {"special_requests"}
    if target in {"ask_dietary_gate", "collect_dietary_concerns"}:
        return {"dietary_concerns"}
    if target == "ask_followup_call":
        return {"followup_call_requested"}
    if target == "review":
        return {"confirm_final"}
    return set()


# Exact-match only — no prefix matching. Messages like "yes i have diabetes"
# intentionally fall through to LLM extraction, which fills the content slot
# directly (e.g. dietary_concerns="diabetes") without losing the content.
_GATE_YES_EXACT = frozenset({
    "yes", "yep", "yeah", "yup", "sure", "ok", "okay", "of course",
    "absolutely", "definitely", "please do", "i do", "yes please",
    "yes ok", "sounds good", "go ahead", "please", "do it",
})
_GATE_NO_EXACT = frozenset({
    "no", "nope", "nah", "n", "no thanks", "no thank you", "skip",
    "none", "not really", "no need", "pass", "nothing", "i dont",
    "i don't", "neither", "no special requests", "no dietary concerns",
    "no additional notes", "no, don't schedule a call", "no call needed",
})


def _is_gate_yes(msg: str) -> bool:
    return msg in _GATE_YES_EXACT


def _is_gate_no(msg: str) -> bool:
    return msg in _GATE_NO_EXACT


def _apply_structured_answer(
    *,
    target: str,
    message_lower: str,
    slots: dict,
    fills: list[tuple[str, Any]],
) -> bool:
    if target == "ask_special_requests_gate":
        if _is_gate_yes(message_lower):
            fill_slot(slots, "__gate_special_requests", True)
            fills.append(("__gate_special_requests", True))
            return True
        if _is_gate_no(message_lower):
            fill_slot(slots, "special_requests", "none")
            fills.append(("special_requests", "none"))
            return True

    if target == "ask_dietary_gate":
        if _is_gate_yes(message_lower):
            fill_slot(slots, "__gate_dietary", True)
            fills.append(("__gate_dietary", True))
            return True
        if _is_gate_no(message_lower):
            fill_slot(slots, "dietary_concerns", "none")
            fills.append(("dietary_concerns", "none"))
            return True

    if target == "ask_followup_call":
        # Follow-up call is a pure yes/no gate (no free-text capture), so we
        # can safely accept prefix variants like "yes, schedule a call".
        if _is_gate_yes(message_lower) or message_lower.startswith("yes"):
            fill_slot(slots, "followup_call_requested", True)
            fills.append(("followup_call_requested", True))
            return True
        if _is_gate_no(message_lower) or message_lower.startswith("no"):
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
        _msg_lower = normalize_structured_choice(message)

        structured_handled = _apply_structured_answer(
            target=current_target,
            message_lower=_msg_lower,
            slots=slots,
            fills=fills,
        )

        extracted = None
        if not structured_handled:
            extracted = await extract(
                schema=FinalizationExtraction,
                system=_SYSTEM_PROMPT,
                user_message=message,
                history=_history_for_llm(history),
            )

        if extracted is not None:
            confirm_final = _apply_extracted_fields(
                target=current_target,
                extracted=extracted,
                slots=slots,
                fills=fills,
            )

        _DECLINE_RE = {"no", "nope", "none", "skip", "nothing", "nah", "no thanks", "not really",
                       "no special requests", "no dietary concerns", "no additional notes",
                       "no notes", "all good", "im good", "i'm good"}
        if current_target == "collect_special_requests" and not is_filled(slots, "special_requests") and _msg_lower in _DECLINE_RE:
            fill_slot(slots, "special_requests", "none")
            fills.append(("special_requests", "none"))
        if current_target == "collect_dietary_concerns" and not is_filled(slots, "dietary_concerns") and _msg_lower in _DECLINE_RE:
            fill_slot(slots, "dietary_concerns", "none")
            fills.append(("dietary_concerns", "none"))

        # Fallback: detect confirmation at review phase when extractor missed it.
        # The LLM is strict about "confirm_final" so casual phrases like
        # "we are done", "ok", "great", "looks good" slip through — resulting
        # in the review loop that wedges the conversation. Use a dedicated
        # yes/no classifier rather than a regex to avoid past over-match bugs.
        if not confirm_final and current_target == "review":
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
                "\n\nYour request is locked in and sent to our team. "
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

        # Store which yes/no question is pending so the router can resolve
        # bare "yes"/"no" replies without an LLM call.
        _GATE_TARGETS = {
            "ask_special_requests_gate": ("__gate_special_requests", "special_requests"),
            "ask_dietary_gate": ("__gate_dietary", "dietary_concerns"),
            "ask_followup_call": (None, "followup_call_requested"),
        }
        if next_target in _GATE_TARGETS:
            gate_slot, content_slot = _GATE_TARGETS[next_target]
            fill_slot(slots, "__pending_confirmation", {
                "question_id": next_target,
                "tool": "finalization_tool",
                "yes_action": "open_gate" if gate_slot else "set_true",
                "no_action": "skip",
                "gate_slot": gate_slot,
                "content_slot": content_slot,
            })
        else:
            # Clear pending confirmation when no longer on a gate question
            if is_filled(slots, "__pending_confirmation"):
                clear_slot(slots, "__pending_confirmation")

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
        "event_type_other": get_slot_value(slots, "event_type_other"),
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
    "no_utensils": "no utensils",
}

_SERVICE_STYLE_PRETTY = {
    "cocktail_hour": "cocktail hour",
    "reception": "reception",
    "both": "cocktail hour + reception",
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
    "# Role\n"
    "You decide whether the customer is confirming their final catering order as displayed, or pushing back / asking for changes.\n\n"
    "# Rules\n"
    "- The assistant has just shown a full recap and asked 'are we good to submit this?'.\n"
    "- Return is_confirming=True only for a clear affirmative.\n"
    "- Return is_confirming=False if the customer asks a question, requests changes, expresses doubt, or is ambiguous.\n"
    "- When in doubt, lean False (avoid premature submission).\n\n"
    "# Examples\n"
    "1. User: 'yes'\n"
    "   Output: is_confirming=True\n"
    "2. User: 'looks good, send it'\n"
    "   Output: is_confirming=True\n"
    "3. User: 'actually can you change the venue'\n"
    "   Output: is_confirming=False\n"
    "4. User: 'wait what is included?'\n"
    "   Output: is_confirming=False\n"
    "5. User: 'not sure'\n"
    "   Output: is_confirming=False\n"
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


def _append_text_value(
    *,
    slot_name: str,
    value: str,
    slots: dict,
    fills: list[tuple[str, Any]],
) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False

    old_value = get_slot_value(slots, slot_name)
    old_text = str(old_value or "").strip()
    cleaned_lower = cleaned.lower()
    old_lower = old_text.lower()

    if cleaned_lower == "none":
        if old_lower in {"", "none"}:
            if old_lower == "none":
                return False
            fill_slot(slots, slot_name, "none")
            fills.append((slot_name, "none"))
            return True
        return False

    if old_lower in {"", "none"}:
        fill_slot(slots, slot_name, cleaned)
        fills.append((slot_name, cleaned))
        return True

    if cleaned_lower in old_lower:
        return False

    merged = f"{old_text}; {cleaned}"
    fill_slot(slots, slot_name, merged)
    fills.append((slot_name, merged))
    return True


def _apply_extracted_fields(
    *,
    target: str,
    extracted: FinalizationExtraction,
    slots: dict,
    fills: list[tuple[str, Any]],
) -> bool:
    allowed = _allowed_fields_for_target(target)
    confirm_final = bool(extracted.confirm_final) if "confirm_final" in allowed and extracted.confirm_final else False

    # When asking for the actual content ("tell me your dietary concern"),
    # a bare affirmative like "yes" is not a concern — it's the user still
    # agreeing to the gate. Reject these so the tool re-asks for real content.
    _BARE_AFFIRMATIVES = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "y", "yes please"}

    for slot_name in ("special_requests", "dietary_concerns", "additional_notes"):
        if slot_name not in allowed:
            continue
        value = getattr(extracted, slot_name, None)
        if value is None:
            continue
        if target.startswith("collect_") and str(value).strip().lower() in _BARE_AFFIRMATIVES:
            continue
        _append_text_value(
            slot_name=slot_name,
            value=str(value),
            slots=slots,
            fills=fills,
        )

    if "followup_call_requested" in allowed and extracted.followup_call_requested is not None:
        current_value = get_slot_value(slots, "followup_call_requested")
        new_value = bool(extracted.followup_call_requested)
        if current_value is None or bool(current_value) != new_value:
            fill_slot(slots, "followup_call_requested", new_value)
            fills.append(("followup_call_requested", new_value))

    return confirm_final



def _render_review_recap(s: dict) -> str:
    """Human-readable recap that avoids frontend card-trigger keywords.

    The frontend scans agent text for words like 'disposable', 'china',
    'drop-off', 'plated', 'passed around' and re-injects option cards. At the
    review step those cards are stale — so we sanitize the wording.
    """
    name = s.get("name") or "there"
    lines: list[str] = [f"Here's the recap{', ' + name if name != 'there' else ''}:"]

    def _canonical_event_type(et_raw: str) -> tuple[str, str]:
        """Return (key, display) where key is wedding/birthday/corporate/other/free-text."""
        et_raw = (et_raw or "").strip()
        if not et_raw:
            return "", ""
        low = et_raw.lower().strip()
        if low in {"wedding", "weddimg", "weding", "weddding"} or low.startswith("wedd"):
            return "wedding", "Wedding"
        if low in {"birthday", "bday"} or "birthday" in low or low.startswith("birth"):
            return "birthday", "Birthday"
        if low in {"corporate", "corp"} or "corporate" in low or "company" in low:
            return "corporate", "Corporate"
        if low in {"other", "others"}:
            return "other", "Other"
        return low, et_raw

    parts = []
    event_type_key = ""
    if s.get("event_type"):
        et = str(s["event_type"])
        event_type_key, et_display = _canonical_event_type(et)
        if (et_display == "Other" or et == "Other") and s.get("event_type_other"):
            parts.append(f"Other ({s['event_type_other']})")
        else:
            parts.append(et_display or et)
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

    if not event_type_key:
        event_type_key, _ = _canonical_event_type(str(s.get("event_type") or ""))
    event_type = str(s.get("event_type") or "").lower()
    if event_type_key == "wedding" and s.get("partner_name"):
        lines.append(f"• Partner: {s['partner_name']}")
    if event_type_key == "corporate" and s.get("company_name"):
        lines.append(f"• Company: {s['company_name']}")
    if event_type_key == "birthday" and s.get("honoree_name"):
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

    if event_type_key == "wedding":
        service_style = str(s.get("service_style") or "").lower()
        if service_style in _SERVICE_STYLE_PRETTY:
            lines.append(f"• Service style: {_SERVICE_STYLE_PRETTY[service_style]}")
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
    elif s.get("linens"):
        lines.append("• Rentals: Linens")

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

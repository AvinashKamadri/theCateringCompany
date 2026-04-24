"""Shared helper for rendering the "what would you like to change?" picker.

Multiple tools may need to return the user to a modification picker after a
review-stage edit (instead of continuing the original flow).
"""

from __future__ import annotations

from agent.state import LOCKED_SLOTS, PHASE_REVIEW, fill_slot, is_filled
from agent.tools.base import ToolResult


SLOT_LABELS: dict[str, str] = {
    "name": "name",
    "email": "email",
    "phone": "phone number",
    "event_type": "event type",
    "event_type_other": "event (other)",
    "event_date": "date",
    "venue": "venue",
    "guest_count": "guest count",
    "partner_name": "partner name",
    "company_name": "company name",
    "honoree_name": "honoree",
    "appetizers": "appetizers",
    "selected_dishes": "main dishes",
    "meal_style": "meal style",
    "desserts": "desserts",
    "menu_notes": "menu notes",
    "wedding_cake": "wedding cake",
    "service_type": "service",
    "drinks": "drinks",
    "bar_service": "bar service",
    "bar_package": "bar package",
    "coffee_service": "coffee service",
    "tableware": "tableware",
    "utensils": "utensils",
    "linens": "rentals (linens)",
    "rentals": "rentals",
    "special_requests": "special requests",
    "dietary_concerns": "dietary concerns",
    "additional_notes": "notes",
    "followup_call_requested": "follow-up call",
}


PREFERRED_ORDER: list[str] = [
    "event_type",
    "event_date",
    "venue",
    "guest_count",
    "service_type",
    "appetizers",
    "selected_dishes",
    "meal_style",
    "desserts",
    "wedding_cake",
    "drinks",
    "bar_service",
    "bar_package",
    "coffee_service",
    "tableware",
    "utensils",
    "rentals",
    "special_requests",
    "dietary_concerns",
    "additional_notes",
    "followup_call_requested",
]


def build_modification_picker_options(*, slots: dict, include_done: bool, max_slots: int = 12) -> list[dict]:
    options: list[dict] = []
    if include_done:
        options.append({"value": "done", "label": "Done — back to recap"})

    for slot in PREFERRED_ORDER:
        if slot in LOCKED_SLOTS or slot.startswith("__"):
            continue
        if not is_filled(slots, slot):
            continue
        label = SLOT_LABELS.get(slot, slot.replace("_", " "))
        options.append({"value": slot, "label": label.title()})
        if len(options) >= max_slots + (1 if include_done else 0):
            break
    return options


def make_modification_picker_result(
    *,
    slots: dict,
    state: dict,
    prompt: str,
    include_done: bool,
    origin_phase: str | None = None,
) -> ToolResult:
    fill_slot(
        slots,
        "__pending_modification_request",
        {
            "stage": "target",
            "origin_phase": origin_phase or state.get("conversation_phase"),
        },
    )
    # Only force the UI phase to review when we're actually in the review loop.
    # Mid-flow edits should keep the current phase marker so the frontend
    # progress doesn't "jump" unexpectedly.
    if include_done or (origin_phase == PHASE_REVIEW) or (state.get("conversation_phase") == PHASE_REVIEW):
        state["conversation_phase"] = PHASE_REVIEW
    options = build_modification_picker_options(slots=slots, include_done=include_done)
    return ToolResult(
        state=state,
        response_context={
            "tool": "modification_tool",
            "next_phase": PHASE_REVIEW,
            "next_question_target": "ask_modification_target",
        },
        direct_response=prompt,
        input_hint={"type": "options", "options": options} if options else None,
    )

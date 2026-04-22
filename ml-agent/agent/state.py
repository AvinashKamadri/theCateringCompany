"""
Conversation state schema (post-rebuild).

The 42-node state machine is GONE. `current_node` is replaced by two fields:
  - `conversation_phase`  — coarse progress marker (S1..S19), drives frontend UI
  - `conversation_status` — lifecycle: active | pending_staff_review | contract_sent

Every tool MUST write state through `fill_slot()`. Direct dict assignment
breaks the Next.js frontend — it relies on the `{value, filled, modified_at,
modification_history}` shape to render progress cards.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Annotated, Any, Literal, Sequence, TypedDict

from langchain_core.messages import BaseMessage


logger = logging.getLogger(__name__)


# ============================================================================
# Slot record shape — frontend depends on this exact structure
# ============================================================================

class SlotModification(TypedDict):
    old_value: Any
    new_value: Any
    timestamp: str


class SlotData(TypedDict):
    value: Any | None
    filled: bool
    modified_at: str | None
    modification_history: list[SlotModification]


ConversationStatus = Literal["active", "pending_staff_review", "contract_sent"]


class ConversationState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "Conversation history"]
    conversation_id: str
    project_id: str
    thread_id: str
    # Phase marker — frontend uses this for progress display. Replaces current_node.
    conversation_phase: str
    # Lifecycle — controls whether the orchestrator will route at all.
    conversation_status: ConversationStatus
    slots: dict[str, SlotData]
    contract_data: dict | None
    is_complete: bool
    error: str | None


# ============================================================================
# Slot registry — MUST match Section 6 of AGENT_SPEC.md exactly
# ============================================================================
# Order here is informational only. Fill order is determined by the orchestrator,
# not by list index. Typos here break the frontend silently — triple-check.

SLOT_NAMES: list[str] = [
    # --- Basic info (BasicInfoTool) ---
    "name",
    "email",
    "phone",
    "event_type",
    "event_date",
    "venue",
    "guest_count",
    "partner_name",
    "company_name",
    "honoree_name",
    "service_type",

    # --- Menu (MenuSelectionTool) ---
    "cocktail_hour",
    "service_style",
    "appetizers",
    "appetizer_style",
    "meal_style",
    "selected_dishes",
    "custom_menu",
    "desserts",
    "wedding_cake",
    "menu_notes",

    # --- Add-ons (AddOnsTool) ---
    "drinks",
    "bar_service",
    "bar_package",
    "bartender",
    "coffee_service",
    "tableware",
    "utensils",
    "linens",
    "rentals",
    "labor_ceremony_setup",
    "labor_table_setup",
    "labor_table_preset",
    "labor_cleanup",
    "labor_trash",
    "travel_fee",

    # --- Finalization (FinalizationTool) ---
    "special_requests",
    "dietary_concerns",
    "additional_notes",
    "followup_call_requested",

    # --- Internal flow state (never shown to user) ---
    # Stores the pending yes/no question so "yes"/"no" can be resolved
    # deterministically without an LLM call.
    # Shape: {question_id: str, yes_action: str, no_action: str}
    "__pending_confirmation",
]


# Required-for-contract slot set. Drives the "can we move to review?" gate.
REQUIRED_SLOTS: set[str] = {
    "name",
    "email",
    "phone",
    "event_type",
    "event_date",
    "guest_count",
    "service_type",
    "meal_style",
    "selected_dishes",
    "tableware",
}

# Slots that the frontend must NOT treat as user-modifiable.
LOCKED_SLOTS: set[str] = {"bartender", "conversation_status"}


# ============================================================================
# Phases (coarse progress markers) — S1..S19 from AGENT_SPEC.md Section 3
# ============================================================================

PHASE_GREETING = "S1_greeting"
PHASE_EVENT_TYPE = "S2_event_type"
PHASE_CONDITIONAL_FOLLOWUP = "S3_conditional"
PHASE_WEDDING_CAKE = "S3b_wedding_cake"
PHASE_SERVICE_TYPE = "S4_service_type"
PHASE_EVENT_DATE = "S5_event_date"
PHASE_VENUE = "S6_venue"
PHASE_GUEST_COUNT = "S7_guest_count"
PHASE_TRANSITION = "S8_transition"
PHASE_COCKTAIL = "S9_cocktail_hour"
PHASE_MAIN_MENU = "S10_main_menu"
PHASE_DESSERT = "S11_dessert"
PHASE_DRINKS_BAR = "S12_drinks_bar"
PHASE_TABLEWARE = "S13_tableware"
PHASE_RENTALS = "S14_rentals"
PHASE_LABOR = "S15_labor"
PHASE_SPECIAL_REQUESTS = "S16_special_requests"
PHASE_DIETARY = "S17_dietary"
PHASE_FOLLOWUP = "S18_followup"
PHASE_REVIEW = "S19_review"
PHASE_COMPLETE = "complete"


# ============================================================================
# Slot helpers
# ============================================================================

def initialize_empty_slots() -> dict[str, SlotData]:
    """Create the empty slot dictionary for a brand-new conversation."""
    empty: dict[str, SlotData] = {}
    for name in SLOT_NAMES:
        empty[name] = {
            "value": None,
            "filled": False,
            "modified_at": None,
            "modification_history": [],
        }
    return empty


def fill_slot(slots: dict, name: str, value: Any) -> dict:
    """Write a slot. ALWAYS use this — never write to `slots[name]` directly.

    Preserves modification_history and timestamps so the frontend can render
    edit-over-time views without extra plumbing.
    """
    if name not in slots:
        # Unknown slot — create the empty shell first. Keeps tools resilient
        # against forgotten registry entries, but the registry check in
        # ModificationTool will still reject typos before they reach here.
        slots[name] = {
            "value": None,
            "filled": False,
            "modified_at": None,
            "modification_history": [],
        }

    existing = slots[name]
    now = datetime.now().isoformat()
    old_value = existing.get("value") if existing.get("filled") else None
    history = list(existing.get("modification_history", []))

    if existing.get("filled") and old_value != value:
        history.append({
            "old_value": old_value,
            "new_value": value,
            "timestamp": now,
        })

    slots[name] = {
        "value": value,
        "filled": True,
        "modified_at": now,
        "modification_history": history,
    }
    logger.info(
        "slot_update slot=%s action=fill old=%r new=%r internal=%s",
        name,
        old_value,
        value,
        name.startswith("__"),
    )
    return slots


def clear_slot(slots: dict, name: str) -> dict:
    """Reset a slot to empty — used by the cascade map (Section 7)."""
    if name not in slots:
        return slots
    now = datetime.now().isoformat()
    existing = slots[name]
    old_value = existing.get("value") if existing.get("filled") else None
    history = list(existing.get("modification_history", []))
    if old_value is not None:
        history.append({
            "old_value": old_value,
            "new_value": None,
            "timestamp": now,
        })
    slots[name] = {
        "value": None,
        "filled": False,
        "modified_at": now,
        "modification_history": history,
    }
    logger.info(
        "slot_update slot=%s action=clear old=%r new=%r internal=%s",
        name,
        old_value,
        None,
        name.startswith("__"),
    )
    return slots


def get_slot_value(slots: dict, name: str) -> Any:
    slot = slots.get(name, {})
    return slot.get("value") if slot.get("filled") else None


def is_filled(slots: dict, name: str) -> bool:
    return bool(slots.get(name, {}).get("filled"))


def filled_slot_summary(slots: dict) -> dict[str, Any]:
    """Compact {name: value} view of filled slots for the orchestrator prompt."""
    return {
        name: slot["value"]
        for name, slot in slots.items()
        if slot.get("filled") and not name.startswith("__")
    }


def unfilled_required(slots: dict) -> list[str]:
    """Which REQUIRED_SLOTS are still empty — drives routing prompt context."""
    return [name for name in REQUIRED_SLOTS if not is_filled(slots, name)]


__all__ = [
    "ConversationState",
    "ConversationStatus",
    "SlotData",
    "SlotModification",
    "SLOT_NAMES",
    "REQUIRED_SLOTS",
    "LOCKED_SLOTS",
    "initialize_empty_slots",
    "fill_slot",
    "clear_slot",
    "get_slot_value",
    "is_filled",
    "filled_slot_summary",
    "unfilled_required",
    # phases
    "PHASE_GREETING",
    "PHASE_EVENT_TYPE",
    "PHASE_CONDITIONAL_FOLLOWUP",
    "PHASE_WEDDING_CAKE",
    "PHASE_SERVICE_TYPE",
    "PHASE_EVENT_DATE",
    "PHASE_VENUE",
    "PHASE_GUEST_COUNT",
    "PHASE_TRANSITION",
    "PHASE_COCKTAIL",
    "PHASE_MAIN_MENU",
    "PHASE_DESSERT",
    "PHASE_DRINKS_BAR",
    "PHASE_TABLEWARE",
    "PHASE_RENTALS",
    "PHASE_LABOR",
    "PHASE_SPECIAL_REQUESTS",
    "PHASE_DIETARY",
    "PHASE_FOLLOWUP",
    "PHASE_REVIEW",
    "PHASE_COMPLETE",
]

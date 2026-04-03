"""
LangGraph state schema for the catering intake conversation flow.

Each slot stores its value, fill status, timestamp, and full modification_history
so that @AI changes are tracked inline (matching ai_conversation_states schema).
"""

from typing import TypedDict, Annotated, Sequence, Any
from datetime import datetime
from langchain_core.messages import BaseMessage


class SlotModification(TypedDict):
    old_value: Any
    new_value: Any
    timestamp: str


class SlotData(TypedDict):
    value: Any | None
    filled: bool
    modified_at: str | None
    modification_history: list[SlotModification]


class ConversationState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], "Conversation history"]
    conversation_id: str
    project_id: str
    thread_id: str
    current_node: str
    slots: dict[str, SlotData]
    next_action: str
    error: str | None
    summary_data: dict | None
    is_complete: bool
    dietary_conflict_attempts: int  # tracks conflict re-asks to cap the loop at 2


# All slots in the full catering flow
SLOT_NAMES = [
    # Basic info
    "name",              # First and last name
    "event_type",        # Wedding, Corporate, Birthday, Social, Custom
    "fiance_name",       # Fiancé name (wedding only)
    "company_name",      # Company name (corporate only)
    "birthday_person",   # Birthday person name (birthday only)
    "event_date",        # Event date
    "venue",             # Venue details
    "guest_count",       # Approximate guest count
    "service_type",      # Drop-off or Onsite
    # Menu building
    "service_style",     # cocktail hour: passed / station / both
    "appetizers",        # List of appetizers or None
    "buffet_or_plated",  # Buffet or Plated
    "selected_dishes",   # List of main dishes
    "menu_notes",        # Special menu design notes
    # Add-ons
    "desserts",          # Dessert selections or "no"
    "drinks",            # Coffee / drink selections or "no"
    "bar_service",       # Bar package selections or "no"
    "tableware",         # Standard disposable / premium / china
    "rentals",           # linen/table/chair selections or "no"
    # Final details
    "special_requests",  # Special requests or "none"
    "labor_services",    # Setup/cleanup/travel selections or "no"
    "dietary_concerns",  # Health and dietary concerns
]


def initialize_empty_slots() -> dict[str, SlotData]:
    """Create empty slot structure for a new conversation."""
    return {
        name: {
            "value": None,
            "filled": False,
            "modified_at": None,
            "modification_history": [],
        }
        for name in SLOT_NAMES
    }


def fill_slot(slots: dict, name: str, value: Any) -> dict:
    """
    Fill a slot with a value and timestamp.
    If the slot already had a value, record it in modification_history.

    Guards: silently rejects None, empty string, and LLM null-string variants
    (e.g. "null", "N/A", "undefined") so a bad extraction can never mark a
    slot as filled with a garbage value.
    """
    # Inline null guard — mirrors is_null_extraction() without creating a
    # circular import between state.py and helpers.py.
    _NULL_STRINGS = {
        "none", "null", "nil", "n/a", "na", "undefined",
        "not found", "not available", "unknown", "not specified",
        "not provided", "not mentioned", "not given", "not stated",
        "-", "--", "—",
    }
    if value is None:
        return slots
    if isinstance(value, str) and (not value.strip() or value.strip().lower() in _NULL_STRINGS):
        return slots

    now = datetime.now().isoformat()
    existing = slots.get(name, {})
    old_value = existing.get("value") if existing.get("filled") else None
    history = list(existing.get("modification_history", []))

    # If overwriting an existing value, log the change
    if old_value is not None and old_value != value:
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
    return slots


def get_slot_value(slots: dict, name: str) -> Any:
    """Get the value of a slot, or None if not filled."""
    slot = slots.get(name, {})
    return slot.get("value") if slot.get("filled") else None


# Node flow sequence - defines the order of conversation nodes
NODE_SEQUENCE = [
    "start",
    "collect_name",
    "select_event_type",
    "collect_event_type_followup",  # conditional: wedding→fiancé, corporate→company, birthday→person
    "collect_event_date",
    "collect_venue",
    "collect_guest_count",
    "select_service_type",          # Drop-off or Onsite only
    # Menu building
    "ask_cocktail_hour",
    "select_appetizers",
    "ask_buffet_or_plated",
    "present_menu",
    "select_dishes",
    "ask_menu_changes",
    "collect_menu_changes",         # conditional: only if yes
    # Add-ons
    "ask_desserts",
    "select_desserts",              # conditional: only if yes
    "ask_drinks",
    "ask_bar_service",              # conditional: only if wants bar
    "ask_tableware",
    "ask_rentals",
    # Final
    "ask_special_requests",
    "collect_special_requests",     # conditional: only if yes
    "ask_labor_services",
    "collect_dietary",
    "generate_summary",
    "offer_followup_call",
]

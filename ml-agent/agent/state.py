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
    contract_data: dict | None
    is_complete: bool


# All slots in the full catering flow
SLOT_NAMES = [
    # Basic info
    "name",              # First and last name
    "event_date",        # Event date
    "service_type",      # drop-off or on-site
    "event_type",        # Wedding, Corporate, Birthday, Social, Custom
    "partner_name",      # Fiancé/partner name (weddings only)
    "company_name",      # Company name (corporate only)
    "honoree_name",      # Whose birthday/celebration (birthday only)
    "venue",             # Venue details
    "guest_count",       # Approximate guest count
    "service_style",     # cocktail hour, reception, both
    # Menu building
    "selected_dishes",   # List of 3-5 main dishes
    "appetizers",        # List of appetizers or None
    "menu_notes",        # Special menu design notes
    # Add-ons
    "utensils",          # Utensil selections or "no"
    "desserts",          # Dessert selections or "no"
    "rentals",           # linen/table/chair selections or "no"
    "florals",           # Floral arrangement selections or "no" (wedding only)
    # Final details
    "special_requests",  # Special requests or "none"
    "dietary_concerns",  # Health and dietary concerns
    "additional_notes",  # Anything else
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
    """
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
    "collect_event_date",
    "select_service_type",
    "select_event_type",
    "wedding_message",       # conditional: only for weddings
    "collect_venue",
    "collect_guest_count",
    "select_service_style",
    # Menu building
    "select_dishes",
    "ask_appetizers",
    "select_appetizers",     # conditional: only if yes
    "menu_design",
    "ask_menu_changes",
    "collect_menu_changes",  # conditional: only if yes
    # Add-ons
    "ask_utensils",
    "select_utensils",       # conditional: only if yes
    "ask_desserts",
    "select_desserts",       # conditional: only if yes
    "ask_more_desserts",     # conditional: only if yes
    "ask_rentals",
    "ask_florals",           # conditional: only for weddings
    # Final
    "ask_special_requests",
    "collect_special_requests",  # conditional: only if yes
    "collect_dietary",
    "ask_anything_else",
    "collect_anything_else",     # conditional: only if yes
    "generate_contract",
]

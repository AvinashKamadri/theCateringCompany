import sys

from agent.router import _quick_route  # noqa: E402
from agent.state import (  # noqa: E402
    PHASE_MAIN_MENU,
    fill_slot,
    initialize_empty_slots,
)

def test_quick_route_tbd_event_type_wedding_routes_to_modification() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "TBD - Confirm on call")
    state = {"conversation_phase": PHASE_MAIN_MENU, "slots": slots}
    assert _quick_route("Wedding", state) == "modification_tool"


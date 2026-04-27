import sys

from agent.router import _quick_route  # noqa: E402
from agent.state import (  # noqa: E402
    PHASE_MAIN_MENU,
    fill_slot,
    initialize_empty_slots,
)

def test_quick_route_replace_with_routes_to_modification_tool() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Chicken & Ham ($27.99/per_person)")

    state = {"conversation_phase": PHASE_MAIN_MENU, "slots": slots}
    assert _quick_route("replace chicken & ham with chicken & ham", state) == "modification_tool"


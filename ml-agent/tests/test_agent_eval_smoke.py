import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")

from agent.router import _quick_route
from agent.state import (
    PHASE_MAIN_MENU,
    PHASE_SERVICE_TYPE,
    PHASE_SPECIAL_REQUESTS,
    PHASE_TABLEWARE,
    PHASE_VENUE,
    fill_slot,
    initialize_empty_slots,
)


@pytest.mark.parametrize(
    ("phase", "message", "slot_fills", "expected_tool"),
    [
        (
            PHASE_SERVICE_TYPE,
            "actually onsite",
            {"name": "Syed Ali", "event_type": "Wedding"},
            "basic_info_tool",
        ),
        (PHASE_VENUE, "tbd_confirm_call", {}, "basic_info_tool"),
        (
            PHASE_MAIN_MENU,
            "let's do buffet",
            {
                "name": "Syed Ali",
                "event_type": "Wedding",
                "service_type": "Onsite",
                "selected_dishes": "Chicken Piccata ($29.49/per_person)",
            },
            "menu_selection_tool",
        ),
        (
            PHASE_TABLEWARE,
            "china",
            {
                "drinks": True,
                "coffee_service": True,
                "bar_service": True,
                "bar_package": "beer_wine_signature",
            },
            "add_ons_tool",
        ),
        (PHASE_SPECIAL_REQUESTS, "actually yes", {}, "finalization_tool"),
    ],
)
def test_agent_eval_smoke_quick_route_cases(phase, message, slot_fills, expected_tool):
    slots = initialize_empty_slots()
    for key, value in slot_fills.items():
        if value is not None:
            fill_slot(slots, key, value)

    state = {
        "conversation_phase": phase,
        "slots": slots,
    }

    assert _quick_route(message, state) == expected_tool

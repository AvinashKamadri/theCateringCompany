import sys


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.router import _quick_route  # noqa: E402
from agent.state import (  # noqa: E402
    PHASE_DRINKS_BAR,
    PHASE_TABLEWARE,
    PHASE_VENUE,
    fill_slot,
    initialize_empty_slots,
)


def test_quick_route_basic_info_update_in_addons_phase_routes_to_modification_tool() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    state = {"conversation_phase": PHASE_DRINKS_BAR, "slots": slots}
    msg = "the venue is Pearluxe Tower and number of guests is 66"
    assert _quick_route(msg, state) == "modification_tool"


def test_quick_route_remove_intent_in_addons_phase_routes_to_modification_tool() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    state = {"conversation_phase": PHASE_TABLEWARE, "slots": slots}
    assert _quick_route("remove brownies from desserts", state) == "modification_tool"


def test_quick_route_add_main_menu_intent_in_venue_phase_routes_to_modification_tool() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    state = {"conversation_phase": PHASE_VENUE, "slots": slots}
    assert _quick_route("add dragon chicken in main menu", state) == "modification_tool"


def test_quick_route_add_verb_in_venue_phase_routes_to_modification_tool() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    state = {"conversation_phase": PHASE_VENUE, "slots": slots}
    assert _quick_route("add dragon chicken", state) == "modification_tool"


def test_quick_route_venue_name_starting_with_add_is_not_forced_to_modification() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    state = {"conversation_phase": PHASE_VENUE, "slots": slots}
    assert _quick_route("Addison Park", state) == "basic_info_tool"

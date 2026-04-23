import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.models import EventDetailsExtraction  # noqa: E402
from agent.state import (  # noqa: E402
    PHASE_DRINKS_BAR,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)
from agent.tools.modification_tool import (  # noqa: E402
    ModificationExtraction,
    ModificationTool,
)


@pytest.mark.asyncio
async def test_modification_updates_venue_and_guest_count_from_one_message(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module

    async def fake_extract(**_kwargs):
        return EventDetailsExtraction(venue="Pearluxe Tower", guest_count=66)

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")

    tool = ModificationTool()
    state = {"conversation_phase": PHASE_DRINKS_BAR, "slots": slots}
    result = await tool._apply_scalar_modification(
        ModificationExtraction(target_slot="venue", action="replace", new_value="Pearluxe Tower"),
        "the venue is Pearluxe Tower and number of guests is 66",
        slots,
        state,
        history=[],
    )

    assert get_slot_value(result.state["slots"], "venue") == "Pearluxe Tower"
    assert get_slot_value(result.state["slots"], "guest_count") == 66


@pytest.mark.asyncio
async def test_custom_event_type_after_tbd_does_not_force_reset(monkeypatch) -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "TBD - Confirm on call")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")

    tool = ModificationTool()
    state = {"conversation_phase": PHASE_DRINKS_BAR, "slots": slots}
    result = await tool._apply_scalar_modification(
        ModificationExtraction(target_slot="event_type", action="replace", new_value="Baby shower"),
        "Baby shower",
        slots,
        state,
        history=[],
    )

    assert get_slot_value(result.state["slots"], "event_type") == "Baby shower"
    assert not get_slot_value(result.state["slots"], "__pending_confirmation")


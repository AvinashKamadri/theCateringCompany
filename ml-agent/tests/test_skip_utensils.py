import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import PHASE_TABLEWARE, fill_slot, get_slot_value, initialize_empty_slots  # noqa: E402
from agent.tools.add_ons_tool import AddOnsTool  # noqa: E402


@pytest.mark.asyncio
async def test_skip_utensils_sets_no_utensils(monkeypatch) -> None:
    import agent.tools.add_ons_tool as add_ons_module

    async def fake_extract(**_kwargs):
        return None

    monkeypatch.setattr(add_ons_module, "extract", fake_extract)

    tool = AddOnsTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "service_type", "Onsite")
    fill_slot(slots, "drinks", False)
    fill_slot(slots, "bar_service", False)
    fill_slot(slots, "bartender", False)
    fill_slot(slots, "coffee_service", False)
    fill_slot(slots, "tableware", "standard_disposable")

    state = {"slots": slots, "conversation_phase": PHASE_TABLEWARE}
    result = await tool.run(message="skip", history=[], state=state)
    assert get_slot_value(result.state["slots"], "utensils") == "no_utensils"


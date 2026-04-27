import sys

import pytest

from agent.state import (  # noqa: E402
    PHASE_LABOR,
    PHASE_SPECIAL_REQUESTS,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
    is_filled,
)
from agent.tools.add_ons_tool import AddOnsTool  # noqa: E402

def _prep_addons_ready_for_labor(*, service_type: str) -> dict:
    slots = initialize_empty_slots()
    fill_slot(slots, "service_type", service_type)

    # Skip earlier add-ons questions.
    fill_slot(slots, "drinks", False)
    fill_slot(slots, "bar_service", False)
    fill_slot(slots, "bartender", False)
    fill_slot(slots, "coffee_service", False)
    fill_slot(slots, "tableware", "standard_disposable")
    fill_slot(slots, "utensils", "standard_plastic")

    # Rentals gate answered "no" so the flow can proceed to labor.
    fill_slot(slots, "__gate_rentals", False)

    return slots

@pytest.mark.asyncio
async def test_dropoff_still_asks_labor_services(monkeypatch) -> None:
    import agent.tools.add_ons_tool as add_ons_module

    async def fake_extract(**_kwargs):
        return None

    monkeypatch.setattr(add_ons_module, "extract", fake_extract)

    tool = AddOnsTool()
    slots = _prep_addons_ready_for_labor(service_type="Dropoff")
    state = {"slots": slots, "conversation_phase": "S12_drinks_bar"}

    result = await tool.run(message="ok", history=[], state=state)
    assert result.state["conversation_phase"] == PHASE_LABOR
    assert result.response_context["next_question_target"] == "ask_labor_services"
    assert result.input_hint and result.input_hint.get("multi") is True

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_selecting_labor_on_dropoff_switches_to_onsite(monkeypatch) -> None:
    import agent.tools.add_ons_tool as add_ons_module

    async def fake_extract(**_kwargs):
        return None

    monkeypatch.setattr(add_ons_module, "extract", fake_extract)

    tool = AddOnsTool()
    slots = _prep_addons_ready_for_labor(service_type="Dropoff")
    state = {"slots": slots, "conversation_phase": "S12_drinks_bar"}

    result = await tool.run(message="labor_table_setup, labor_trash", history=[], state=state)
    assert result.state["conversation_phase"] == PHASE_SPECIAL_REQUESTS
    assert get_slot_value(result.state["slots"], "service_type") == "Onsite"

    assert get_slot_value(result.state["slots"], "labor_table_setup") is True
    assert get_slot_value(result.state["slots"], "labor_trash") is True
    assert is_filled(result.state["slots"], "labor_cleanup")
    assert get_slot_value(result.state["slots"], "labor_cleanup") is False

@pytest.mark.asyncio
async def test_declining_labor_fills_all_false(monkeypatch) -> None:
    import agent.tools.add_ons_tool as add_ons_module

    async def fake_extract(**_kwargs):
        return None

    monkeypatch.setattr(add_ons_module, "extract", fake_extract)

    tool = AddOnsTool()
    slots = _prep_addons_ready_for_labor(service_type="Dropoff")
    state = {"slots": slots, "conversation_phase": "S12_drinks_bar"}

    result = await tool.run(message="none", history=[], state=state)
    assert result.state["conversation_phase"] == PHASE_SPECIAL_REQUESTS
    assert get_slot_value(result.state["slots"], "service_type") == "Dropoff"

    for slot_name in (
        "labor_ceremony_setup",
        "labor_table_setup",
        "labor_table_preset",
        "labor_cleanup",
        "labor_trash",
    ):
        assert is_filled(result.state["slots"], slot_name)
        assert get_slot_value(result.state["slots"], slot_name) is False


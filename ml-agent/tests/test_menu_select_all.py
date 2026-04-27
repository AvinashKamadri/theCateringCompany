import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_MAIN_MENU,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)


@pytest.mark.asyncio
async def test_menu_select_all_does_not_require_llm(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called for select-all")

    async def fake_load_main_dish_menu(**_kwargs):
        return {
            "Signature Combinations": [
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(menu_tool_module, "extract", fail_extract)
    monkeypatch.setattr(menu_tool_module, "load_main_dish_menu", fake_load_main_dish_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")  # non-wedding; no service-style question
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "station")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="all",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    assert get_slot_value(result.state["slots"], "selected_dishes")
    assert "Chicken Piccata" in str(get_slot_value(result.state["slots"], "selected_dishes"))


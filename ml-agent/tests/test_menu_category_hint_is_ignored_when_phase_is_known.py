import sys

import pytest

from agent.models import MenuSelectionExtraction  # noqa: E402
from agent.state import (  # noqa: E402
    PHASE_MAIN_MENU,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)

@pytest.mark.asyncio
async def test_main_menu_phase_ignores_wrong_category_hint(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fake_extract(**_kwargs):
        # Simulate the extractor mis-labeling a mains list as appetizers.
        return MenuSelectionExtraction(
            raw_items=["Chicken Piccata", "Prime Rib & Salmon"],
            category_hint="appetizers",
        )

    async def fake_load_appetizer_menu():
        raise AssertionError("Should not resolve mains against appetizer menu")

    async def fake_load_main_dish_menu():
        return {
            "Signature Combinations": [
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)
    monkeypatch.setattr(menu_tool_module, "load_main_dish_menu", fake_load_main_dish_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "station")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="Chicken Piccata, Prime Rib & Salmon",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    selected = str(get_slot_value(result.state["slots"], "selected_dishes") or "")
    assert "Chicken Piccata" in selected
    assert "Prime Rib & Salmon" in selected
    assert result.response_context["next_question_target"] == "ask_meal_style"


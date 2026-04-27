import sys

import pytest

from agent.models import MenuSelectionExtraction  # noqa: E402
from agent.state import (  # noqa: E402
    PHASE_COCKTAIL,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)

@pytest.mark.asyncio
async def test_appetizer_style_not_filled_from_acknowledgement(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fake_extract(**_kwargs):
        # Simulate an extractor hallucinating appetizer_style on a short "ok".
        return MenuSelectionExtraction(appetizer_style="passed")

    async def fake_load_appetizer_menu():
        return {
            "Appetizers": [
                {"name": "Brie Bites", "unit_price": 3.00, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")  # non-wedding auto-sets cocktail_hour=True

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="ok",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert not get_slot_value(result.state["slots"], "appetizer_style")


import sys

import pytest

from agent.models import ModificationExtraction  # noqa: E402
from agent.state import PHASE_COCKTAIL, PHASE_REVIEW, fill_slot, get_slot_value, initialize_empty_slots  # noqa: E402
from agent.tools.menu_selection_tool import MenuSelectionTool  # noqa: E402
from agent.tools.modification_tool import ModificationTool  # noqa: E402

@pytest.mark.asyncio
async def test_mod_remove_seafood_removes_only_seafood(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot != "appetizers":
            return {}
        return {
            "Chicken": [{"name": "Chicken Satay", "unit_price": 3.50, "price_type": "per_person"}],
            "Seafood": [{"name": "Crab Cakes", "unit_price": 4.75, "price_type": "per_person"}],
            "Canapes": [{"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person"}],
            "Vegetarian": [{"name": "Brie Bites", "unit_price": 3.00, "price_type": "per_person"}],
        }

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Chicken Satay ($3.50/pp), Crab Cakes ($4.75/pp), Deviled Egg ($3.00/pp), Brie Bites ($3.00/pp)",
    )

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="appetizers",
            action="remove",
            items_to_remove=["seafood"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="remove seafood",
    )

    assert result.direct_response
    remaining = str(get_slot_value(slots, "appetizers") or "")
    assert "Crab Cakes" not in remaining
    assert "Chicken Satay" in remaining
    assert "Deviled Egg" in remaining
    assert "Brie Bites" in remaining

@pytest.mark.asyncio
async def test_mod_add_all_non_veg_except_pork_and_chicken_adds_only_allowed(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot != "appetizers":
            return {}
        return {
            "Chicken": [{"name": "Chicken Satay", "unit_price": 3.50, "price_type": "per_person"}],
            "Pork": [{"name": "Bacon Bourbon Meatballs", "unit_price": 3.50, "price_type": "per_person"}],
            "Seafood": [{"name": "Crab Cakes", "unit_price": 4.75, "price_type": "per_person"}],
            "Canapes": [
                {"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person"},
                {"name": "Charred Tomato and Pesto", "unit_price": 2.75, "price_type": "per_person"},
            ],
            "Vegetarian": [{"name": "Brie Bites", "unit_price": 3.00, "price_type": "per_person"}],
        }

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/pp)")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="appetizers",
            action="add",
            items_to_add=["all non veg except pork and chicken"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="add all non veg except pork and chicken",
    )

    assert result.direct_response
    remaining = str(get_slot_value(slots, "appetizers") or "")
    assert "Brie Bites" in remaining
    assert "Crab Cakes" in remaining
    assert "Deviled Egg" in remaining
    assert "Chicken Satay" not in remaining
    assert "Bacon Bourbon Meatballs" not in remaining
    assert "Charred Tomato and Pesto" not in remaining

@pytest.mark.asyncio
async def test_menu_select_all_non_veg_except_pork_and_chicken(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called for tag-select")

    async def fake_load_appetizer_menu():
        return {
            "Chicken": [{"name": "Chicken Satay", "unit_price": 3.50, "price_type": "per_person"}],
            "Pork": [{"name": "Bacon Bourbon Meatballs", "unit_price": 3.50, "price_type": "per_person"}],
            "Seafood": [{"name": "Crab Cakes", "unit_price": 4.75, "price_type": "per_person"}],
            "Canapes": [
                {"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person"},
                {"name": "Charred Tomato and Pesto", "unit_price": 2.75, "price_type": "per_person"},
            ],
            "Vegetarian": [{"name": "Brie Bites", "unit_price": 3.00, "price_type": "per_person"}],
        }

    monkeypatch.setattr(menu_tool_module, "extract", fail_extract)
    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "cocktail_hour", True)

    tool = MenuSelectionTool()
    result = await tool.run(
        message="all non veg except pork and chicken",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    apps = str(get_slot_value(result.state["slots"], "appetizers") or "")
    assert "Crab Cakes" in apps
    assert "Deviled Egg" in apps
    assert "Brie Bites" not in apps
    assert "Charred Tomato and Pesto" not in apps
    assert "Chicken Satay" not in apps
    assert "Bacon Bourbon Meatballs" not in apps

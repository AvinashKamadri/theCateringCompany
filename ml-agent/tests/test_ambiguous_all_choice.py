import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_COCKTAIL,
    PHASE_DESSERT,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)


@pytest.mark.asyncio
async def test_pending_menu_choice_all_selects_all_options(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fake_load_appetizer_menu(**_kwargs):
        return {
            "Seafood": [
                {"name": "Firecracker Shrimp", "unit_price": 4.75, "price_type": "per_person"},
                {"name": "Grilled Shrimp Cocktail", "unit_price": 4.75, "price_type": "per_person"},
                {"name": "Shrimp and Mango Bites", "unit_price": 3.50, "price_type": "per_person"},
            ]
        }

    async def fake_load_main_dish_menu(**_kwargs):
        return {
            "Signature Combinations": [
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)
    monkeypatch.setattr(menu_tool_module, "load_main_dish_menu", fake_load_main_dish_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")  # avoid wedding-only sub-questions
    fill_slot(
        slots,
        "__pending_menu_choice",
        {
            "category": "appetizers",
            "query": "shrimp",
            "matches": ["Firecracker Shrimp", "Grilled Shrimp Cocktail", "Shrimp and Mango Bites"],
            "raw_items": ["shrimp"],
        },
    )

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="I want all",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert not get_slot_value(result.state["slots"], "__pending_menu_choice")
    appetizers = str(get_slot_value(result.state["slots"], "appetizers") or "")
    assert "Firecracker Shrimp" in appetizers
    assert "Grilled Shrimp Cocktail" in appetizers
    assert "Shrimp and Mango Bites" in appetizers


@pytest.mark.asyncio
async def test_modification_add_unknown_item_shows_ack_before_resuming(monkeypatch) -> None:
    from agent.models import ModificationExtraction
    from agent.tools.modification_tool import ModificationTool

    async def fake_menu_for_slot(self, slot, slots):
        if slot == "selected_dishes":
            return {"Global Inspirations": [{"name": "Souvlaki Bar", "unit_price": 21.49, "price_type": "per_person"}]}
        return {}

    async def fake_find_correct_slot_for_items(self, *, add_texts, exclude_slot, slots):
        return None

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)
    monkeypatch.setattr(ModificationTool, "_find_correct_slot_for_items", fake_find_correct_slot_for_items)

    slots = initialize_empty_slots()
    fill_slot(slots, "__gate_desserts", "asked")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="add",
            items_to_add=["Sushi"],
        ),
        slots,
        {"conversation_phase": PHASE_DESSERT, "slots": slots},
        message="add sushi in main menu",
    )

    assert result.direct_response
    assert "isn't on the menu" in result.direct_response.lower()
    assert "desserts" in result.direct_response.lower()

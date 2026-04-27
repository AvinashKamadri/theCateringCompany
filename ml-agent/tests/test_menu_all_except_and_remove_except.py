import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_DESSERT,
    PHASE_MAIN_MENU,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)


@pytest.mark.asyncio
async def test_menu_all_except_numeric_does_not_call_llm(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called for all-except")

    async def fake_load_main_dish_menu(**_kwargs):
        return {
            "Signature Combinations": [
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
                {"name": "Veggie Pasta", "unit_price": 24.00, "price_type": "per_person"},
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
        message="all except 2",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    selected = str(get_slot_value(result.state["slots"], "selected_dishes") or "")
    assert "Chicken Piccata" in selected
    assert "Veggie Pasta" in selected
    assert "Prime Rib & Salmon" not in selected


@pytest.mark.asyncio
async def test_menu_remove_all_except_replaces_existing_list(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called for remove-all-except")

    async def fake_load_main_dish_menu(**_kwargs):
        return {
            "Signature Combinations": [
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
                {"name": "Veggie Pasta", "unit_price": 24.00, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(menu_tool_module, "extract", fail_extract)
    monkeypatch.setattr(menu_tool_module, "load_main_dish_menu", fake_load_main_dish_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "station")
    fill_slot(
        slots,
        "selected_dishes",
        "Chicken Piccata ($29.49/pp), Prime Rib & Salmon ($39.99/pp), Veggie Pasta ($24.00/pp)",
    )
    fill_slot(slots, "meal_style", "buffet")  # ensures target is show_main_menu again

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="remove all except 2",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    selected = str(get_slot_value(result.state["slots"], "selected_dishes") or "")
    assert "Prime Rib & Salmon" in selected
    assert "Chicken Piccata" not in selected
    assert "Veggie Pasta" not in selected


@pytest.mark.asyncio
async def test_dessert_overflow_message_is_appetite_line(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called for select-all")

    async def fake_load_dessert_menu_expanded(*, is_wedding: bool = False, **_kwargs):
        return [
            {"name": "Chocolate Cake", "unit_price": 3.00, "price_type": "per_person"},
            {"name": "Cheesecake", "unit_price": 3.00, "price_type": "per_person"},
            {"name": "Brownies", "unit_price": 3.00, "price_type": "per_person"},
            {"name": "Cookies", "unit_price": 3.00, "price_type": "per_person"},
            {"name": "Fruit Tart", "unit_price": 3.00, "price_type": "per_person"},
        ]

    monkeypatch.setattr(menu_tool_module, "extract", fail_extract)
    monkeypatch.setattr(menu_tool_module, "load_dessert_menu_expanded", fake_load_dessert_menu_expanded)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "station")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/pp)")
    fill_slot(slots, "meal_style", "buffet")
    fill_slot(slots, "__gate_desserts", True)

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="all",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DESSERT},
    )

    assert result.direct_response
    assert "I appreciate your appetite" in result.direct_response
    assert "only choose 4 desserts" in result.direct_response


@pytest.mark.asyncio
async def test_remove_all_except_with_category_override_targets_appetizers(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called for remove-all-except")

    async def fake_load_appetizer_menu(**_kwargs):
        return {
            "Appetizers": [
                {"name": "Brie Bites", "unit_price": 3.00, "price_type": "per_person"},
                {"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person"},
            ]
        }

    async def fake_load_main_dish_menu(**_kwargs):
        # Still needed because the user is mid-flow in PHASE_MAIN_MENU.
        return {
            "Signature Combinations": [
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(menu_tool_module, "extract", fail_extract)
    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)
    monkeypatch.setattr(menu_tool_module, "load_main_dish_menu", fake_load_main_dish_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(
        slots,
        "appetizers",
        "Brie Bites ($3.00/per_person), Deviled Egg ($3.00/per_person)",
    )
    fill_slot(slots, "appetizer_style", "station")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="remove all in appetizers except Brie Bites",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    apps = str(get_slot_value(result.state["slots"], "appetizers") or "")
    assert "Brie Bites" in apps
    assert "Deviled Egg" not in apps

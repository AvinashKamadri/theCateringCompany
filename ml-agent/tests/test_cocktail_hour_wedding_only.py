import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_COCKTAIL,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)


@pytest.mark.asyncio
async def test_non_wedding_auto_sets_cocktail_hour_without_messaging(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fake_extract(**_kwargs):
        return None

    async def fake_load_appetizer_menu():
        return {"Appetizers": [{"name": "Brie Bites", "unit_price": 3.0, "price_type": "per_person"}]}

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="ok",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert get_slot_value(result.state["slots"], "cocktail_hour") is True
    filled = result.response_context.get("filled_this_turn") or []
    assert not any(slot == "cocktail_hour" for slot, _ in filled)
    text = (result.direct_response or "").lower()
    assert "cocktail hour" not in text


@pytest.mark.asyncio
async def test_non_wedding_ignores_cocktail_hour_keyword_as_service_style(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fake_extract(**_kwargs):
        # Even if the extractor emits cocktail_hour, the tool should ignore it for non-weddings.
        return menu_tool_module.MenuSelectionExtraction(cocktail_hour=True)

    async def fake_load_appetizer_menu():
        return {"Appetizers": [{"name": "Brie Bites", "unit_price": 3.0, "price_type": "per_person"}]}

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="cocktail hour",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert not get_slot_value(result.state["slots"], "service_style")


@pytest.mark.asyncio
async def test_wedding_accepts_cocktail_hour_service_style(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module

    async def fake_extract(**_kwargs):
        return menu_tool_module.MenuSelectionExtraction(cocktail_hour=True)

    async def fake_load_appetizer_menu():
        return {"Appetizers": [{"name": "Brie Bites", "unit_price": 3.0, "price_type": "per_person"}]}

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module, "load_appetizer_menu", fake_load_appetizer_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="cocktail hour",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert get_slot_value(result.state["slots"], "cocktail_hour") is True
    assert get_slot_value(result.state["slots"], "service_style") in {"cocktail_hour", "both"}


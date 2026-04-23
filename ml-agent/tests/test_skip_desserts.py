import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


@pytest.mark.asyncio
async def test_skip_desserts_does_not_call_llm(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module
    from agent.state import PHASE_DESSERT, fill_slot, get_slot_value, initialize_empty_slots

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called when skipping desserts")

    monkeypatch.setattr(menu_tool_module, "extract", fail_extract)

    slots = initialize_empty_slots()
    # Make it to dessert phase legitimately
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "station")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")
    fill_slot(slots, "meal_style", "buffet")
    # Gate already asked/shown
    fill_slot(slots, "__gate_desserts", "asked")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="skip",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DESSERT},
    )

    assert get_slot_value(result.state["slots"], "desserts") == "none"
    assert result.state["conversation_phase"] != PHASE_DESSERT


@pytest.mark.asyncio
async def test_skip_desserts_prompts_for_wedding_cake_gate(monkeypatch) -> None:
    import agent.tools.menu_selection_tool as menu_tool_module
    from agent.state import PHASE_DESSERT, fill_slot, get_slot_value, initialize_empty_slots

    async def fail_extract(**_kwargs):
        raise AssertionError("LLM extraction should not be called when skipping desserts")

    monkeypatch.setattr(menu_tool_module, "extract", fail_extract)

    slots = initialize_empty_slots()
    # Make it to dessert phase legitimately
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Sydney")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "station")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")
    fill_slot(slots, "meal_style", "buffet")
    # Gate already asked/shown
    fill_slot(slots, "__gate_desserts", "asked")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="skip dessert",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DESSERT},
    )

    assert get_slot_value(result.state["slots"], "desserts") == "none"
    assert result.response_context.get("next_question_target") == "ask_wedding_cake"
    menu_progress = str(result.response_context.get("menu_progress") or "")
    assert "wedding cake" in menu_progress.lower()
    assert "?" in menu_progress

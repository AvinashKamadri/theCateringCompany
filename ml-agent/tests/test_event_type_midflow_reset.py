import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


@pytest.mark.asyncio
async def test_midflow_event_type_change_requires_confirmation_and_resets_on_yes(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module
    from agent.models import EventDetailsExtraction, ModificationExtraction
    from agent.state import (
        PHASE_CONDITIONAL_FOLLOWUP,
        PHASE_MAIN_MENU,
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
    )

    async def fake_extract(**kwargs):
        schema = kwargs.get("schema")
        if schema is ModificationExtraction:
            return ModificationExtraction(target_slot="event_type", action="replace", new_value="Birthday")
        if schema is EventDetailsExtraction:
            return EventDetailsExtraction(event_type="Birthday")
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)

    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Ayaan")
    fill_slot(slots, "email", "ayaan@example.com")
    fill_slot(slots, "phone", "+1 1234567890")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Sydney")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "passed")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")
    fill_slot(slots, "__pending_modification_request", {"stage": "value", "target_slot": "event_type"})

    tool = mod_tool_module.ModificationTool()
    result = await tool.run(
        message="Birthday",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    assert result.direct_response is not None
    assert "reset" in result.direct_response.lower()
    pending = get_slot_value(result.state["slots"], "__pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("question_id") == "confirm_event_type_reset"
    assert pending.get("new_event_type") == "Birthday"

    result2 = await tool.run(
        message="yes",
        history=[],
        state=result.state,
    )

    assert result2.state["conversation_phase"] == PHASE_CONDITIONAL_FOLLOWUP
    assert get_slot_value(result2.state["slots"], "event_type") == "Birthday"
    assert get_slot_value(result2.state["slots"], "honoree_name") is None
    # Contact info preserved
    assert get_slot_value(result2.state["slots"], "name") == "Ayaan"
    assert get_slot_value(result2.state["slots"], "email") == "ayaan@example.com"
    assert get_slot_value(result2.state["slots"], "phone") == "+1 1234567890"
    # Menu cleared
    assert get_slot_value(result2.state["slots"], "appetizers") is None
    assert get_slot_value(result2.state["slots"], "selected_dishes") is None
    assert get_slot_value(result2.state["slots"], "desserts") is None
    assert result2.response_context.get("next_question_target") == "ask_honoree_name"


@pytest.mark.asyncio
async def test_event_type_mod_normalizes_to_wedding_from_to_prefix(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module
    from agent.models import EventDetailsExtraction, ModificationExtraction
    from agent.state import (
        PHASE_MAIN_MENU,
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
    )

    async def fake_extract(**kwargs):
        schema = kwargs.get("schema")
        if schema is ModificationExtraction:
            return ModificationExtraction(target_slot="event_type", action="replace", new_value="to wedding")
        if schema is EventDetailsExtraction:
            return EventDetailsExtraction(event_type="Wedding")
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)

    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Sam")
    fill_slot(slots, "email", "sam@example.com")
    fill_slot(slots, "phone", "+1 1234567890")
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "honoree_name", "Ava")
    fill_slot(slots, "selected_dishes", "Burger Bar ($23.99/per_person)")

    tool = mod_tool_module.ModificationTool()
    result = await tool.run(
        message="to wedding",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    pending = get_slot_value(result.state["slots"], "__pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("question_id") == "confirm_event_type_reset"
    assert pending.get("new_event_type") == "Wedding"


@pytest.mark.asyncio
async def test_event_type_mod_extracts_value_from_full_sentence(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module
    from agent.models import EventDetailsExtraction, ModificationExtraction
    from agent.state import (
        PHASE_MAIN_MENU,
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
    )

    async def fake_extract(**kwargs):
        schema = kwargs.get("schema")
        if schema is ModificationExtraction:
            # Simulate an extractor that only identifies the target slot but
            # leaves `new_value` empty.
            return ModificationExtraction(target_slot="event_type", action="replace", new_value=None)
        if schema is EventDetailsExtraction:
            return EventDetailsExtraction(event_type="Wedding")
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)

    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Sam")
    fill_slot(slots, "email", "sam@example.com")
    fill_slot(slots, "phone", "+1 1234567890")
    fill_slot(slots, "event_type", "Corporate")
    fill_slot(slots, "company_name", "Acme")
    fill_slot(slots, "selected_dishes", "Burger Bar ($23.99/per_person)")

    tool = mod_tool_module.ModificationTool()
    result = await tool.run(
        message="change my event type to wedding",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    pending = get_slot_value(result.state["slots"], "__pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("question_id") == "confirm_event_type_reset"
    assert pending.get("new_event_type") == "Wedding"


@pytest.mark.asyncio
async def test_event_type_mod_with_no_value_asks_for_new_value(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module
    from agent.models import EventDetailsExtraction, ModificationExtraction
    from agent.state import (
        PHASE_REVIEW,
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
    )

    async def fake_extract(**kwargs):
        schema = kwargs.get("schema")
        if schema is ModificationExtraction:
            return ModificationExtraction(target_slot="event_type", action="replace", new_value=None)
        if schema is EventDetailsExtraction:
            return EventDetailsExtraction(event_type=None)
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)

    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Sam")
    fill_slot(slots, "email", "sam@example.com")
    fill_slot(slots, "phone", "+1 1234567890")
    fill_slot(slots, "event_type", "Birthday")

    tool = mod_tool_module.ModificationTool()
    result = await tool.run(
        message="change my event type",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_REVIEW},
    )

    pending = get_slot_value(result.state["slots"], "__pending_modification_request")
    assert isinstance(pending, dict)
    assert pending.get("stage") == "value"
    assert pending.get("target_slot") == "event_type"
    assert result.direct_response is not None and "event type" in result.direct_response.lower()


@pytest.mark.asyncio
async def test_event_type_change_from_review_surfaces_reset_confirmation(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module
    from agent.models import EventDetailsExtraction, ModificationExtraction
    from agent.state import (
        PHASE_REVIEW,
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
    )

    async def fake_extract(**kwargs):
        schema = kwargs.get("schema")
        if schema is ModificationExtraction:
            return ModificationExtraction(target_slot="event_type", action="replace", new_value="Birthday")
        if schema is EventDetailsExtraction:
            return EventDetailsExtraction(event_type="Birthday")
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)

    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Sam")
    fill_slot(slots, "email", "sam@example.com")
    fill_slot(slots, "phone", "+1 1234567890")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Ava")
    # Downstream filled -> should require reset confirmation
    fill_slot(slots, "selected_dishes", "Burger Bar ($23.99/per_person)")
    fill_slot(slots, "meal_style", "buffet")

    # Simulate the "change -> event_type -> birthday" picker flow
    fill_slot(slots, "__pending_modification_request", {"stage": "value", "target_slot": "event_type", "origin_phase": PHASE_REVIEW})

    tool = mod_tool_module.ModificationTool()
    result = await tool.run(
        message="Birthday",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_REVIEW},
    )

    pending = get_slot_value(result.state["slots"], "__pending_confirmation")
    assert isinstance(pending, dict)
    assert pending.get("question_id") == "confirm_event_type_reset"
    assert result.response_context.get("next_question_target") == "confirm_event_type_reset"
    assert result.direct_response is not None and "reset" in result.direct_response.lower()

import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


@pytest.mark.asyncio
async def test_other_event_type_flows_into_custom_label_prompt() -> None:
    from agent.state import (
        PHASE_EVENT_TYPE,
        PHASE_TRANSITION,
        get_slot_value,
        initialize_empty_slots,
        is_filled,
    )
    from agent.tools.basic_info_tool import BasicInfoTool

    slots = initialize_empty_slots()
    for key, value in {
        "name": "Syed Ali",
        "email": "syed@example.com",
        "phone": "+1 1234567890",
    }.items():
        from agent.state import fill_slot

        fill_slot(slots, key, value)

    tool = BasicInfoTool()

    # Step 1: user clicks "Other"
    result1 = await tool.run(
        message="Other",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_EVENT_TYPE},
    )
    assert result1.state["conversation_phase"] == PHASE_EVENT_TYPE
    assert get_slot_value(slots, "__awaiting_custom_event_type") is True
    assert not is_filled(slots, "event_type")
    assert result1.response_context.get("next_question_target") == "ask_other_event_type"

    # Step 2: user repeats "Other" (still unhelpful) -> should keep asking
    result2 = await tool.run(
        message="Other",
        history=[],
        state=result1.state,
    )
    assert result2.state["conversation_phase"] == PHASE_EVENT_TYPE
    assert get_slot_value(slots, "__awaiting_custom_event_type") is True
    assert not is_filled(slots, "event_type")
    assert result2.response_context.get("next_question_target") == "ask_other_event_type"

    # Step 3: user provides custom label -> stored in event_type and flow advances
    result3 = await tool.run(
        message="Engagement party",
        history=[],
        state=result2.state,
    )
    assert is_filled(slots, "event_type")
    assert get_slot_value(slots, "event_type") == "Engagement party"
    assert get_slot_value(slots, "__awaiting_custom_event_type") is None
    assert result3.state["conversation_phase"] == PHASE_TRANSITION


@pytest.mark.asyncio
async def test_other_event_type_accepts_confirm_on_call() -> None:
    from agent.state import (
        PHASE_EVENT_TYPE,
        get_slot_value,
        initialize_empty_slots,
        is_filled,
    )
    from agent.tools.basic_info_tool import BasicInfoTool
    from agent.state import fill_slot

    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "email", "syed@example.com")
    fill_slot(slots, "phone", "+1 1234567890")

    tool = BasicInfoTool()
    await tool.run(
        message="Other",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_EVENT_TYPE},
    )

    result2 = await tool.run(
        message="confirm on call",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_EVENT_TYPE},
    )
    assert is_filled(slots, "event_type")
    assert get_slot_value(slots, "event_type") == "TBD - Confirm on call"
    assert get_slot_value(slots, "__awaiting_custom_event_type") is None
    assert result2.response_context.get("current_event_type") == "TBD - Confirm on call"


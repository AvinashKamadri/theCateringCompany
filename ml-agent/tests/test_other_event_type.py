import sys

import pytest


# Keep imports consistent with the rest of the suite (run from repo root).
sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_EVENT_TYPE,
    PHASE_TRANSITION,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)
from agent.tools.basic_info_tool import BasicInfoTool  # noqa: E402


@pytest.mark.asyncio
async def test_custom_event_type_is_stored_verbatim_or_confirm_on_call() -> None:
    tool = BasicInfoTool()
    state = {
        "slots": initialize_empty_slots(),
        "conversation_phase": PHASE_EVENT_TYPE,
    }
    fill_slot(state["slots"], "name", "Test User")
    fill_slot(state["slots"], "email", "test@example.com")
    fill_slot(state["slots"], "phone", "+1 1111111111")

    # "Other" is not a usable event type; it should not set event_type.
    result = await tool.run(message="Other", history=[], state=state)
    assert not get_slot_value(result.state["slots"], "event_type")
    assert result.state["conversation_phase"] == PHASE_EVENT_TYPE
    assert result.response_context["next_question_target"] == "ask_other_event_type"
    assert result.input_hint
    # After clicking "Other", the follow-up surface offers free-text plus a
    # "confirm on call" chip — repeating "Other" would be UX noise.
    assert any(
        str(o.get("value")).lower() == "confirm on call"
        for o in (result.input_hint.get("options") or [])
    )

    # Free-text custom event type is stored as-is.
    result = await tool.run(message="Baby shower", history=[], state=result.state)
    assert get_slot_value(result.state["slots"], "event_type") == "Baby shower"
    assert result.state["conversation_phase"] == PHASE_TRANSITION

    # Confirm-on-call sets a clear value (not "Other").
    state2 = {
        "slots": initialize_empty_slots(),
        "conversation_phase": PHASE_EVENT_TYPE,
    }
    fill_slot(state2["slots"], "name", "Test User")
    fill_slot(state2["slots"], "email", "test@example.com")
    fill_slot(state2["slots"], "phone", "+1 1111111111")
    result2 = await tool.run(message="confirm on call", history=[], state=state2)
    assert get_slot_value(result2.state["slots"], "event_type") == "TBD - Confirm on call"
    assert result2.state["conversation_phase"] == PHASE_TRANSITION

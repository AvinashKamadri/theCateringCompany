import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_GREETING,
    PHASE_SERVICE_TYPE,
    fill_slot,
    initialize_empty_slots,
)
from agent.tools.basic_info_tool import BasicInfoTool  # noqa: E402


@pytest.mark.asyncio
async def test_service_type_is_collected_after_menu(monkeypatch) -> None:
    import agent.tools.basic_info_tool as basic_tool_module

    async def fake_extract(**_kwargs):
        return None

    monkeypatch.setattr(basic_tool_module, "extract", fake_extract)

    tool = BasicInfoTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Test User")
    fill_slot(slots, "email", "test@example.com")
    fill_slot(slots, "phone", "+1 1111111111")
    fill_slot(slots, "event_type", "Baby shower")  # no conditional followup
    state = {"slots": slots, "conversation_phase": PHASE_GREETING}

    result = await tool.run(message="ok", history=[], state=state)
    assert result.state["conversation_phase"] != PHASE_SERVICE_TYPE

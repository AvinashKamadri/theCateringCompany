import sys

import pytest

from agent.models import EventDetailsExtraction  # noqa: E402
from agent.state import (  # noqa: E402
    PHASE_GUEST_COUNT,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)
from agent.tools.modification_tool import (  # noqa: E402
    ModificationExtraction,
    ModificationTool,
)

@pytest.mark.asyncio
async def test_partner_phone_email_updated_together(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module

    async def fake_extract(**_kwargs):
        return EventDetailsExtraction(
            partner_name="Saniya Afzali",
            phone="+917995928521",
            email="syedali040205@gmail.com",
        )

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Old Name")
    fill_slot(slots, "phone", "+1 0000000000")
    fill_slot(slots, "email", "old@example.com")

    tool = ModificationTool()
    state = {"conversation_phase": PHASE_GUEST_COUNT, "slots": slots}
    result = await tool._apply_scalar_modification(
        ModificationExtraction(target_slot="partner_name", action="replace", new_value="Saniya Afzali"),
        "change my partner name to Saniya Afzali, my phone number to +917995928521 and email to syedali040205@gmail.com",
        slots,
        state,
        history=[],
    )

    assert get_slot_value(result.state["slots"], "partner_name") == "Saniya Afzali"
    assert get_slot_value(result.state["slots"], "phone") == "+917995928521"
    assert get_slot_value(result.state["slots"], "email") == "syedali040205@gmail.com"


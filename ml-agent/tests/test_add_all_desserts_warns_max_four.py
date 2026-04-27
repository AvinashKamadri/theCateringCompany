import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_SERVICE_TYPE,
    fill_slot,
    initialize_empty_slots,
)
from agent.tools.modification_tool import ModificationTool  # noqa: E402
from agent.tools.modification_tool import ModificationExtraction  # noqa: E402


@pytest.mark.asyncio
async def test_add_all_desserts_reopen_warns_about_max_four(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module

    async def fake_extract(**_kwargs):
        return ModificationExtraction(target_slot="desserts", action="reopen")

    async def fake_load_dessert_menu_expanded(*, is_wedding: bool = False, **_kwargs):
        return [
            {"name": "7-Layer Bars", "unit_price": 5.25, "price_type": "per_person"},
            {"name": "Blondies", "unit_price": 5.25, "price_type": "per_person"},
        ]

    monkeypatch.setattr(mod_tool_module, "extract", fake_extract)
    monkeypatch.setattr(mod_tool_module, "load_dessert_menu_expanded", fake_load_dessert_menu_expanded)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "event_date", "2026-04-30")

    tool = ModificationTool()
    result = await tool.run(
        message="add all desserts",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SERVICE_TYPE},
    )

    assert result.direct_response
    lowered = result.direct_response.lower()
    assert "only choose up to 4 desserts" in lowered
    assert "dessert options" in lowered

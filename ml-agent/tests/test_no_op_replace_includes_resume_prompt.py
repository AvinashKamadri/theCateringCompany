import sys

import pytest

from agent.models import ModificationExtraction  # noqa: E402
from agent.state import PHASE_REVIEW, fill_slot, initialize_empty_slots  # noqa: E402
from agent.tools.modification_tool import ModificationTool  # noqa: E402

@pytest.mark.asyncio
async def test_no_op_replace_appends_resume_prompt(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        return {}

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    # Force a deterministic resume prompt without depending on other tools.
    async def fake_resume_after_modification(*, slots, state, modified_slot=None):
        return "S19_review", "review", None, "Does everything look correct?"

    import agent.tools.modification_tool as mod_module

    monkeypatch.setattr(mod_module, "_resume_after_modification", fake_resume_after_modification)

    slots = initialize_empty_slots()
    fill_slot(slots, "desserts", "Brownies ($5.25/pp)")
    state = {"conversation_phase": PHASE_REVIEW, "slots": slots}

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="desserts",
            action="replace",
            items_to_remove=["Brownies"],
            items_to_add=["Brownies"],
        ),
        slots,
        state,
        message="replace brownies with brownies",
    )

    assert result.direct_response
    assert "already selected" in result.direct_response.lower()
    assert "does everything look correct" in result.direct_response.lower()


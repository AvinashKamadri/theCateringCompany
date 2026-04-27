import sys

import pytest

from agent.models import ModificationExtraction  # noqa: E402
from agent.state import PHASE_WEDDING_CAKE, fill_slot, initialize_empty_slots  # noqa: E402
from agent.tools.modification_tool import ModificationTool  # noqa: E402

@pytest.mark.asyncio
async def test_remove_all_desserts_in_wedding_cake_phase_repeats_cake_question(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        return {}

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Test User")
    fill_slot(slots, "email", "test@example.com")
    fill_slot(slots, "phone", "+1 1111111111")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Partner")
    fill_slot(slots, "desserts", "Brownies ($5.25/pp)")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/pp)")
    fill_slot(slots, "appetizer_style", "passed")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/pp)")
    fill_slot(slots, "meal_style", "buffet")

    tool = ModificationTool()
    state = {"conversation_phase": PHASE_WEDDING_CAKE, "slots": slots}
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="desserts",
            action="remove",
            items_to_remove=["all desserts"],
        ),
        slots,
        state,
        message="remove all desserts",
    )

    assert result.direct_response
    assert "wedding cake" in result.direct_response.lower()
    assert (result.response_context.get("next_question_target") or "") == "ask_wedding_cake"

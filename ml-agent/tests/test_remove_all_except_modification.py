import sys

import pytest

from agent.models import ModificationExtraction  # noqa: E402
from agent.state import PHASE_REVIEW, fill_slot, get_slot_value, initialize_empty_slots  # noqa: E402
from agent.tools.modification_tool import ModificationTool  # noqa: E402

@pytest.mark.asyncio
async def test_remove_all_from_main_menu_except_single_item(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot != "selected_dishes":
            return {}
        return {
            "Signature Combinations": [
                {"name": "Chicken & Ham", "unit_price": 27.99, "price_type": "per_person"},
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "selected_dishes",
        "Chicken & Ham ($27.99/pp), Chicken Piccata ($29.49/pp), Prime Rib & Salmon ($39.99/pp)",
    )

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="remove",
            items_to_remove=["all from main menu except chicken piccata"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="remove all from main menu except chicken piccata",
    )

    assert result.direct_response
    remaining = str(get_slot_value(slots, "selected_dishes") or "")
    assert "Chicken Piccata" in remaining
    assert "Chicken & Ham" not in remaining
    assert "Prime Rib & Salmon" not in remaining


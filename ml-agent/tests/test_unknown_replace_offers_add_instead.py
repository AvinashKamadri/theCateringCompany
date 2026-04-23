import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.state import (  # noqa: E402
    PHASE_TABLEWARE,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)
from agent.tools.modification_tool import (  # noqa: E402
    ModificationExtraction,
    ModificationTool,
)


@pytest.mark.asyncio
async def test_replace_unknown_menu_item_offers_add_instead(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module

    async def fake_load_main_dish_menu():
        return {
            "Global Inspirations": [
                {"name": "Ravioli Menu", "unit_price": 31.99, "price_type": "per_person"},
                {"name": "Mediterranean Bar", "unit_price": 23.49, "price_type": "per_person"},
            ]
        }

    monkeypatch.setattr(mod_tool_module, "load_main_dish_menu", fake_load_main_dish_menu)

    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")

    tool = ModificationTool()
    state = {"conversation_phase": PHASE_TABLEWARE, "slots": slots}
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="replace",
            items_to_remove=["Dragon Sushi"],
            items_to_add=["ravioli bar"],
        ),
        slots,
        state,
        message="replace dragon sushi with ravioli bar in main menu",
    )

    assert result.response_context["next_question_target"] == "confirm_add_instead"
    lowered = (result.direct_response or "").lower()
    assert "dragon sushi" in lowered
    assert "isn't on our menu" in lowered
    assert "ravioli menu" in lowered
    pending = get_slot_value(result.state["slots"], "__pending_modification_request") or {}
    assert str(pending.get("stage") or "") == "confirm_add_instead"


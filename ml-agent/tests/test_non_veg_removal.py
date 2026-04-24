import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")


from agent.models import ModificationExtraction  # noqa: E402
from agent.state import PHASE_REVIEW, fill_slot, get_slot_value, initialize_empty_slots  # noqa: E402
from agent.tools.modification_tool import ModificationTool  # noqa: E402


@pytest.mark.asyncio
async def test_remove_non_veg_appetizers_keeps_vegetarian(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot != "appetizers":
            return {}
        return {
            "Chicken": [{"name": "Chicken Satay", "unit_price": 3.50, "price_type": "per_person"}],
            "Seafood": [{"name": "Crab Cakes", "unit_price": 4.75, "price_type": "per_person"}],
            "Vegetarian": [{"name": "Brie Bites", "unit_price": 3.00, "price_type": "per_person"}],
        }

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Chicken Satay ($3.50/per_person), Crab Cakes ($4.75/per_person), Brie Bites ($3.00/per_person)",
    )

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="appetizers",
            action="remove",
            items_to_remove=["non-veg items"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="remove non-veg items from appetizers",
    )

    assert result.direct_response
    remaining = str(get_slot_value(slots, "appetizers") or "")
    assert "Brie Bites" in remaining
    assert "Chicken Satay" not in remaining
    assert "Crab Cakes" not in remaining


@pytest.mark.asyncio
async def test_ambiguous_remove_all_does_not_loop_into_ambiguity(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot != "appetizers":
            return {}
        return {
            "Seafood": [
                {"name": "Firecracker Shrimp", "unit_price": 4.75, "price_type": "per_person"},
                {"name": "Grilled Shrimp Cocktail", "unit_price": 4.75, "price_type": "per_person"},
                {"name": "Shrimp and Mango Bites", "unit_price": 3.50, "price_type": "per_person"},
            ]
        }

    async def fail_ground(*_args, **_kwargs):
        raise AssertionError("Grounding should not be called when user selects 'all'")

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)
    monkeypatch.setattr(ModificationTool, "_ground_selected_removals", fail_ground)

    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Firecracker Shrimp ($4.75/per_person), Grilled Shrimp Cocktail ($4.75/per_person), Shrimp and Mango Bites ($3.50/per_person)",
    )
    fill_slot(
        slots,
        "__pending_modification_choice",
        {
            "target_slot": "appetizers",
            "action": "remove",
            "choice_kind": "remove",
            "query": "shrimp",
            "matches": ["Firecracker Shrimp", "Grilled Shrimp Cocktail", "Shrimp and Mango Bites"],
            "items_to_remove": ["shrimp"],
            "items_to_add": [],
        },
    )

    tool = ModificationTool()
    result = await tool.run(
        message="all",
        history=[],
        state={"conversation_phase": PHASE_REVIEW, "slots": slots},
    )

    assert not get_slot_value(slots, "__pending_modification_choice")
    mod_ack = (
        (result.response_context or {}).get("modification", {}) or {}
    ).get("mod_ack_text") or ""
    assert "removed" in str(mod_ack).lower()
    assert str(get_slot_value(slots, "appetizers") or "").lower() in {"", "none"}


@pytest.mark.asyncio
async def test_ambiguous_remove_multi_indices_removes_subset(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot != "appetizers":
            return {}
        return {
            "Seafood": [
                {"name": "Firecracker Shrimp", "unit_price": 4.75, "price_type": "per_person"},
                {"name": "Grilled Shrimp Cocktail", "unit_price": 4.75, "price_type": "per_person"},
                {"name": "Shrimp and Mango Bites", "unit_price": 3.50, "price_type": "per_person"},
            ]
        }

    async def fail_ground(*_args, **_kwargs):
        raise AssertionError("Grounding should not be called when user selects indices")

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)
    monkeypatch.setattr(ModificationTool, "_ground_selected_removals", fail_ground)

    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Firecracker Shrimp ($4.75/per_person), Grilled Shrimp Cocktail ($4.75/per_person), Shrimp and Mango Bites ($3.50/per_person)",
    )
    fill_slot(
        slots,
        "__pending_modification_choice",
        {
            "target_slot": "appetizers",
            "action": "remove",
            "choice_kind": "remove",
            "query": "shrimp",
            "matches": ["Firecracker Shrimp", "Grilled Shrimp Cocktail", "Shrimp and Mango Bites"],
            "items_to_remove": ["shrimp"],
            "items_to_add": [],
        },
    )

    tool = ModificationTool()
    await tool.run(
        message="1,2",
        history=[],
        state={"conversation_phase": PHASE_REVIEW, "slots": slots},
    )

    remaining = str(get_slot_value(slots, "appetizers") or "")
    assert "Shrimp and Mango Bites" in remaining
    assert "Firecracker Shrimp" not in remaining
    assert "Grilled Shrimp Cocktail" not in remaining

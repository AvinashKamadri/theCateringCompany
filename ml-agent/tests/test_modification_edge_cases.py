import sys

import pytest

from agent.state import (  # noqa: E402
    PHASE_REVIEW,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)
from agent.tools.modification_tool import ModificationTool  # noqa: E402
from agent.models import ModificationExtraction  # noqa: E402

@pytest.mark.asyncio
async def test_remove_all_desserts_clears_list() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "desserts", "Brownies ($5.25/per_person), Lemon Bars ($5.25/per_person)")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="desserts",
            action="remove",
            items_to_remove=["all desserts"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="remove all desserts",
    )

    assert get_slot_value(slots, "desserts") == "none"
    assert result.direct_response and "removed all" in result.direct_response.lower()

@pytest.mark.asyncio
async def test_remove_all_desserts_when_empty_acknowledges() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "desserts", "none")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="desserts",
            action="remove",
            items_to_remove=["all desserts"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="remove all desserts",
    )

    assert get_slot_value(slots, "desserts") == "none"
    assert result.direct_response and "don't have any" in result.direct_response.lower()

@pytest.mark.asyncio
async def test_replace_with_same_item_is_no_op() -> None:
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Ravioli Menu ($31.99/per_person)")

    tool = ModificationTool()
    async def fake_menu_for_slot(self, slot, slots):
        return {}
    tool._menu_for_slot = fake_menu_for_slot.__get__(tool, ModificationTool)  # type: ignore[attr-defined]
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="replace",
            items_to_remove=["Ravioli Menu"],
            items_to_add=["Ravioli Menu"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="replace Ravioli Menu with Ravioli Menu",
    )

    assert get_slot_value(slots, "selected_dishes")
    assert result.direct_response and "already selected" in result.direct_response.lower()

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_replace_same_item_alias_is_no_op(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot == "appetizers":
            return {
                "Vegetarian": [
                    {"name": "White Bean Tapenade w/ Crostini", "unit_price": 1.75, "price_type": "per_person"},
                ]
            }
        return {}

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(slots, "appetizers", "White Bean Tapenade w/ Crostini ($1.75/per_person)")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="appetizers",
            action="replace",
            items_to_remove=["White bean tapenade"],
            items_to_add=["white bean tapenade"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="replace White bean tapenade with white bean tapenade",
    )

    assert result.direct_response and "already selected" in result.direct_response.lower()
    assert "White Bean Tapenade w/ Crostini" in str(get_slot_value(slots, "appetizers") or "")

@pytest.mark.asyncio
async def test_add_already_selected_item_acknowledges(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot == "selected_dishes":
            return {
                "Signature Combinations": [
                    {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                ]
            }
        return {}

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)
    async def fake_find_correct_slot_for_items(self, *, add_texts, exclude_slot, slots):
        return None
    monkeypatch.setattr(ModificationTool, "_find_correct_slot_for_items", fake_find_correct_slot_for_items)

    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="add",
            items_to_add=["Chicken Piccata"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="add chicken piccata",
    )

    # Should not claim it's "not on the menu" when it is just already selected.
    assert result.direct_response and "already" in result.direct_response.lower()
    assert "not on the menu" not in result.direct_response.lower()

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_replace_non_existing_offers_add_instead(monkeypatch) -> None:
    async def fake_menu_for_slot(self, slot, slots):
        if slot == "selected_dishes":
            return {
                "Global Inspirations": [
                    {"name": "Ravioli Menu", "unit_price": 31.99, "price_type": "per_person"},
                    {"name": "Southern Comfort", "unit_price": 24.99, "price_type": "per_person"},
                ]
            }
        return {}

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Southern Comfort ($24.99/per_person)")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="replace",
            items_to_remove=["Sushi Bar"],
            items_to_add=["Ravioli Menu"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="replace Sushi Bar with Ravioli Menu",
    )

    pending = get_slot_value(slots, "__pending_modification_request") or {}
    assert pending.get("stage") == "confirm_add_instead"
    assert result.direct_response and "want to add" in result.direct_response.lower()

@pytest.mark.asyncio
async def test_replace_dessert_with_appetizer_requires_confirmation(monkeypatch) -> None:
    import agent.tools.modification_tool as mod_tool_module

    class _FakeDessertResolution:
        ambiguous_choices = []
        matched_items = []

    async def fake_resolve_dessert_choices(*_args, **_kwargs):
        return _FakeDessertResolution()

    async def fake_menu_for_slot(self, slot, slots):
        if slot == "desserts":
            return {}
        if slot == "appetizers":
            return {
                "Chicken": [
                    {"name": "Chicken Satay", "unit_price": 3.50, "price_type": "per_person"},
                ]
            }
        return {}

    monkeypatch.setattr(mod_tool_module, "resolve_dessert_choices", fake_resolve_dessert_choices)
    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    slots = initialize_empty_slots()
    fill_slot(slots, "desserts", "Brownies ($5.25/per_person)")

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="desserts",
            action="replace",
            items_to_remove=["Brownies"],
            items_to_add=["Chicken Satay"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
        message="replace Brownies with Chicken Satay",
    )

    pending = get_slot_value(slots, "__pending_modification_request") or {}
    assert pending.get("stage") == "confirm_cross_category_replace"
    assert result.direct_response and "do you want me to remove" in result.direct_response.lower()

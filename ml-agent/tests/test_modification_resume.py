import sys

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")

from agent.models import ModificationExtraction, OrchestratorDecision, ToolCall
from agent.response_generator import _fallback
from agent.router import _quick_route, route
from agent.state import (
    PHASE_COCKTAIL,
    PHASE_CONDITIONAL_FOLLOWUP,
    PHASE_DESSERT,
    PHASE_DIETARY,
    PHASE_DRINKS_BAR,
    PHASE_FOLLOWUP,
    PHASE_GUEST_COUNT,
    PHASE_RENTALS,
    PHASE_REVIEW,
    PHASE_SERVICE_TYPE,
    PHASE_SPECIAL_REQUESTS,
    PHASE_TABLEWARE,
    PHASE_VENUE,
    PHASE_WEDDING_CAKE,
    fill_slot,
    get_slot_value,
    initialize_empty_slots,
)
from agent.tools import add_ons_tool as add_ons_tool_module
from agent.tools.basic_info_tool import BasicInfoTool, _normalize_tbd_venue
from agent.tools import finalization_tool as finalization_tool_module
from agent.tools import menu_selection_tool as menu_tool_module
from agent.tools.modification_tool import ModificationTool, _resume_after_modification
from agent.tools.add_ons_tool import _apply_structured_answer, _next_target


@pytest.mark.asyncio
async def test_resume_after_mid_flow_date_change_returns_to_rentals():
    slots = initialize_empty_slots()
    for key, value in {
        "drinks": True,
        "coffee_service": True,
        "bar_service": True,
        "bar_package": "full_open_bar",
        "tableware": "standard_disposable",
        "utensils": "bamboo",
    }.items():
        fill_slot(slots, key, value)

    phase, target, hint, prompt = await _resume_after_modification(
        slots=slots,
        state={"conversation_phase": PHASE_RENTALS},
    )

    assert phase == PHASE_RENTALS
    assert target == "ask_rentals_gate"
    assert hint == {
        "type": "options",
        "options": [
            {"value": "yes", "label": "Yes, show rental options"},
            {"value": "no", "label": "No rentals needed"},
        ],
    }
    assert prompt == "Do you need any rentals like linens, tables, or chairs?"


@pytest.mark.asyncio
async def test_resume_after_review_edit_renders_review_again():
    slots = initialize_empty_slots()
    for key, value in {
        "name": "Syed Ali",
        "email": "syed@example.com",
        "phone": "+11234567890",
        "event_type": "Birthday",
        "event_date": "2026-04-30",
        "venue": "Pearluxe Tower",
        "guest_count": 55,
        "service_type": "Dropoff",
        "meal_style": "buffet",
        "selected_dishes": "Burger Bar ($23.99/per_person)",
        "tableware": "standard_disposable",
        "special_requests": "none",
        "dietary_concerns": "none",
        "additional_notes": "none",
        "followup_call_requested": False,
    }.items():
        fill_slot(slots, key, value)

    phase, target, hint, prompt = await _resume_after_modification(
        slots=slots,
        state={"conversation_phase": PHASE_REVIEW},
    )

    assert phase == PHASE_REVIEW
    assert target == "review"
    assert hint == {
        "type": "options",
        "options": [
            {"value": "confirm", "label": "Looks good — send it"},
            {"value": "change", "label": "I need to change something"},
        ],
    }
    assert prompt is not None
    assert prompt.startswith("Here's the recap")


def test_quick_route_keeps_canonical_tableware_and_utensil_answers_in_add_ons():
    slots = initialize_empty_slots()
    fill_slot(slots, "drinks", True)
    fill_slot(slots, "coffee_service", True)
    fill_slot(slots, "bar_service", True)
    fill_slot(slots, "bar_package", "beer_wine_signature")

    state = {
        "conversation_phase": PHASE_TABLEWARE,
        "slots": slots,
    }

    assert _quick_route("china", state) == "add_ons_tool"
    assert _quick_route("no_tableware", state) == "add_ons_tool"

    fill_slot(slots, "__gate_tableware", True)
    fill_slot(slots, "tableware", "china")
    assert _quick_route("bamboo", state) == "add_ons_tool"


def test_tableware_gate_accepts_no_tableware_and_advances_to_utensils():
    slots = initialize_empty_slots()
    fill_slot(slots, "drinks", True)
    fill_slot(slots, "coffee_service", True)
    fill_slot(slots, "bar_service", False)

    fills: list[tuple[str, object]] = []
    effects: list[tuple[str, str]] = []

    handled = _apply_structured_answer(
        target="ask_tableware_gate",
        message_lower="no_tableware",
        slots=slots,
        fills=fills,
        effects=effects,
    )

    assert handled is True
    assert get_slot_value(slots, "tableware") == "no_tableware"
    assert _next_target(slots) == "ask_utensils"


def test_quick_route_keeps_finalization_gate_answers_deterministic():
    slots = initialize_empty_slots()

    state = {
        "conversation_phase": PHASE_SPECIAL_REQUESTS,
        "slots": slots,
    }
    assert _quick_route("yes", state) == "finalization_tool"
    assert _quick_route("no", state) == "finalization_tool"

    fill_slot(slots, "special_requests", "none")
    state["conversation_phase"] = PHASE_DIETARY
    assert _quick_route("no dietary concerns", state) == "finalization_tool"

    fill_slot(slots, "dietary_concerns", "none")
    state["conversation_phase"] = PHASE_FOLLOWUP
    fill_slot(slots, "additional_notes", "none")
    assert _quick_route("yes, schedule a call", state) == "finalization_tool"

    fill_slot(slots, "followup_call_requested", False)
    state["conversation_phase"] = PHASE_REVIEW
    assert _quick_route("confirm", state) == "finalization_tool"


def test_quick_route_keeps_wedding_cake_answers_in_basic_info():
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Sydney Sweeney")

    state = {
        "conversation_phase": PHASE_WEDDING_CAKE,
        "slots": slots,
    }

    assert _quick_route("yes", state) == "basic_info_tool"
    assert _quick_route("strawberry", state) is None

    fill_slot(slots, "__wedding_cake_gate", True)
    assert _quick_route("strawberry", state) == "basic_info_tool"

    fill_slot(slots, "__wedding_cake_flavor", "Strawberry")
    assert _quick_route("cinnamon butter cream", state) == "basic_info_tool"

    fill_slot(slots, "__wedding_cake_filling", "Cinnamon Butter Cream")
    assert _quick_route("cream cheese frosting", state) == "basic_info_tool"


@pytest.mark.asyncio
async def test_router_phase_lock_keeps_wedding_cake_phase_from_jumping_to_finalization(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Sydney Sweeney")

    async def fake_extract(**kwargs):
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[ToolCall(tool_name="finalization_tool", reason="bad_guess")],
            confidence=0.95,
        )

    monkeypatch.setattr("agent.router.extract", fake_extract)

    decision = await route(
        message="maybe",
        history=[],
        state={"conversation_phase": PHASE_WEDDING_CAKE, "slots": slots},
    )

    assert decision.tool_calls[0].tool_name == "basic_info_tool"


def test_normalize_tbd_venue_variants():
    assert _normalize_tbd_venue("tbd") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("to be determined") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("venue tbd - will confirm later") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("not decided yet") == "TBD - Confirm on call"


@pytest.mark.asyncio
async def test_basic_info_tool_accepts_tbd_venue_without_llm_extraction():
    slots = initialize_empty_slots()
    for key, value in {
        "name": "Sam Client",
        "event_type": "Birthday",
        "honoree_name": "Ava",
        "service_type": "Onsite",
        "event_date": "2026-05-10",
    }.items():
        fill_slot(slots, key, value)

    tool = BasicInfoTool()
    result = await tool.run(
        message="to be determined",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_VENUE},
    )

    assert get_slot_value(slots, "venue") == "TBD - Confirm on call"
    assert result.state["conversation_phase"] == PHASE_GUEST_COUNT


@pytest.mark.asyncio
async def test_basic_info_tool_does_not_store_filler_as_partner_name():
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "event_type", "Wedding")

    tool = BasicInfoTool()
    result = await tool.run(
        message="nice",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_CONDITIONAL_FOLLOWUP},
    )

    assert get_slot_value(slots, "partner_name") is None
    assert result.response_context["next_question_target"] == "ask_partner_name"


@pytest.mark.asyncio
async def test_basic_info_tool_wedding_after_partner_advances_to_cake_gate():
    slots = initialize_empty_slots()
    for key, value in {
        "name": "Syed Ali",
        "event_type": "Wedding",
        "partner_name": "Amina",
    }.items():
        fill_slot(slots, key, value)

    tool = BasicInfoTool()
    result = await tool.run(
        message="yes",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )

    assert get_slot_value(slots, "__wedding_cake_gate") is True
    assert result.state["conversation_phase"] == PHASE_WEDDING_CAKE
    assert result.response_context["next_question_target"] == "ask_wedding_cake_flavor"
    assert result.input_hint is not None
    assert len(result.input_hint["options"]) == 15


@pytest.mark.asyncio
async def test_basic_info_tool_wedding_cake_decline_moves_to_service_type():
    slots = initialize_empty_slots()
    for key, value in {
        "name": "Syed Ali",
        "event_type": "Wedding",
        "partner_name": "Amina",
    }.items():
        fill_slot(slots, key, value)

    tool = BasicInfoTool()
    result = await tool.run(
        message="no thanks",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )

    assert get_slot_value(slots, "__wedding_cake_gate") is False
    assert get_slot_value(slots, "wedding_cake") == "none"
    assert result.state["conversation_phase"] == PHASE_SERVICE_TYPE
    assert result.response_context["next_question_target"] == "ask_service_type"


@pytest.mark.asyncio
async def test_basic_info_tool_wedding_cake_full_sequence_stores_summary():
    slots = initialize_empty_slots()
    for key, value in {
        "name": "Syed Ali",
        "event_type": "Wedding",
        "partner_name": "Amina",
    }.items():
        fill_slot(slots, key, value)

    tool = BasicInfoTool()

    result = await tool.run(
        message="yes",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )
    assert result.response_context["next_question_target"] == "ask_wedding_cake_flavor"

    result = await tool.run(
        message="Strawberry",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )
    assert get_slot_value(slots, "__wedding_cake_flavor") == "Strawberry"
    assert result.response_context["next_question_target"] == "ask_wedding_cake_filling"

    result = await tool.run(
        message="Cinnamon Butter Cream",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )
    assert get_slot_value(slots, "__wedding_cake_filling") == "Cinnamon Butter Cream"
    assert result.response_context["next_question_target"] == "ask_wedding_cake_buttercream"

    result = await tool.run(
        message="Cream Cheese Frosting",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )

    assert get_slot_value(slots, "wedding_cake") == '2 Tier 6" & 8" - Strawberry, Cinnamon Butter Cream, Cream Cheese Frosting'
    assert result.state["conversation_phase"] == PHASE_SERVICE_TYPE
    assert result.response_context["next_question_target"] == "ask_service_type"


def test_response_fallback_uses_specific_venue_prompt():
    text = _fallback({
        "tool": "basic_info_tool",
        "next_question_target": "ask_venue",
    })
    assert "venue" in text.lower()
    assert "confirm venue on call" in text.lower()


def test_response_fallback_uses_specific_special_requests_prompt():
    text = _fallback({
        "tool": "finalization_tool",
        "next_question_target": "ask_special_requests_gate",
    })
    assert "anything extra" in text.lower()
    assert "special" in text.lower()


def test_response_fallback_uses_specific_menu_prompt():
    text = _fallback({
        "tool": "menu_selection_tool",
        "next_question_target": "ask_meal_style",
    })
    assert "plated" in text.lower()
    assert "buffet" in text.lower()


def test_response_fallback_uses_specific_add_ons_prompt():
    text = _fallback({
        "tool": "add_ons_tool",
        "next_question_target": "ask_tableware_gate",
    })
    assert "tableware" in text.lower()
    assert "upgrade" in text.lower()


@pytest.mark.asyncio
async def test_scalar_modification_with_missing_new_value_does_not_clear_slot():
    slots = initialize_empty_slots()
    fill_slot(slots, "drinks", True)
    fill_slot(slots, "coffee_service", True)
    fill_slot(slots, "bar_service", True)
    fill_slot(slots, "bar_package", "beer_wine_signature")
    fill_slot(slots, "tableware", "china")

    tool = ModificationTool()
    result = await tool._apply_scalar_modification(
        ModificationExtraction(
            target_slot="tableware",
            action="replace",
            new_value=None,
        ),
        "bamboo",
        slots,
        {"conversation_phase": PHASE_TABLEWARE, "slots": slots},
        [],
    )

    assert get_slot_value(slots, "tableware") == "china"
    assert result.response_context["error"] == "invalid_new_value"
    assert result.response_context["next_question_target"] == "ask_utensils"
    assert result.direct_response == "What utensils would you like to add?"


@pytest.mark.asyncio
async def test_menu_selection_tool_defers_style_question_wording_to_response_layer(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "cocktail_hour", True)

    async def fake_extract(**kwargs):
        return menu_tool_module.MenuSelectionExtraction(
            raw_items=["Parmesan Artichoke Dip"],
            category_hint="appetizers",
        )

    async def fake_resolve_raw_items(self, raw_items, category, slots):
        return [("appetizers", "Parmesan Artichoke Dip ($3.00/per_person)", 1)]

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module.MenuSelectionTool, "_resolve_raw_items", fake_resolve_raw_items)

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="Parmesan Artichoke Dip",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert result.response_context["next_question_target"] == "ask_appetizer_style"
    assert result.input_hint == {
        "type": "options",
        "options": [
            {"value": "passed", "label": "Passed around"},
            {"value": "station", "label": "At a station"},
        ],
    }
    assert result.direct_response is not None
    assert "Added Parmesan Artichoke Dip" in result.direct_response
    assert "Your appetizers are now" in result.direct_response


@pytest.mark.asyncio
async def test_menu_selection_tool_dessert_gate_requires_explicit_yes(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "passed")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")
    fill_slot(slots, "meal_style", "plated")

    async def fake_extract(**kwargs):
        return menu_tool_module.MenuSelectionExtraction()

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="sure",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DESSERT},
    )

    assert get_slot_value(slots, "__gate_desserts") == "asked"
    assert result.direct_response == "Would you like to add desserts, or skip them?"


@pytest.mark.asyncio
async def test_resume_after_modification_reasks_dessert_gate_until_affirmed():
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "passed")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")
    fill_slot(slots, "meal_style", "plated")
    fill_slot(slots, "__gate_desserts", "asked")

    phase, target, hint, prompt = await _resume_after_modification(
        slots=slots,
        state={"conversation_phase": PHASE_DESSERT},
    )

    assert phase == PHASE_DESSERT
    assert target == "ask_dessert_gate"
    assert prompt == "Would you like to add desserts, or skip them?"
    assert hint == {
        "type": "options",
        "options": [
            {"value": "yes", "label": "Yes, add desserts"},
            {"value": "skip dessert", "label": "No thanks, skip"},
        ],
    }


@pytest.mark.asyncio
async def test_modification_tool_reopens_dessert_menu_instead_of_adding_everything(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "desserts", "none")
    fill_slot(slots, "__gate_desserts", True)

    async def fake_extract(**kwargs):
        return ModificationExtraction(
            target_slot="desserts",
            action="add",
            items_to_add=["them"],
            new_value="them back",
        )

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)
    async def fake_render_slot_menu(self, target_slot, slots):
        return ("Here are the dessert options:\n1. Brownies", {"type": "menu_picker", "category": "desserts", "items": []})

    monkeypatch.setattr(ModificationTool, "_render_slot_menu", fake_render_slot_menu)

    tool = ModificationTool()
    result = await tool.run(
        message="show me the dessert menu and add them back",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DRINKS_BAR},
    )

    assert get_slot_value(slots, "desserts") is None
    assert get_slot_value(slots, "__gate_desserts") is None
    assert result.response_context["next_phase"] == PHASE_DESSERT
    assert result.direct_response is not None
    assert "Here are the dessert options" in result.direct_response


@pytest.mark.asyncio
async def test_modification_tool_reopens_desserts_even_when_extractor_would_pick_wrong_slot(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "desserts", "none")
    fill_slot(slots, "__gate_desserts", True)

    async def fake_extract(**kwargs):
        raise AssertionError("extract should not run for explicit dessert reopen requests")

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)

    async def fake_render_slot_menu(self, target_slot, slots):
        assert target_slot == "desserts"
        return ("Here are the dessert options:\n1. Brownies", {"type": "menu_picker", "category": "desserts", "items": []})

    monkeypatch.setattr(ModificationTool, "_render_slot_menu", fake_render_slot_menu)

    tool = ModificationTool()
    result = await tool.run(
        message="can you show me the dessert menu and add desserts back",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_FOLLOWUP},
    )

    assert get_slot_value(slots, "desserts") is None
    assert get_slot_value(slots, "__gate_desserts") is None
    assert result.response_context["next_phase"] == PHASE_DESSERT
    assert "Here are the dessert options" in (result.direct_response or "")


def test_quick_route_reopens_menu_sections_from_followup_phase():
    slots = initialize_empty_slots()
    fill_slot(slots, "followup_call_requested", False)

    state = {
        "conversation_phase": PHASE_FOLLOWUP,
        "slots": slots,
    }

    assert _quick_route("show me the dessert menu", state) == "modification_tool"
    assert _quick_route("actually add desserts back", state) == "modification_tool"


@pytest.mark.asyncio
async def test_add_ons_tool_defers_normal_question_wording_to_response_layer():
    slots = initialize_empty_slots()
    fill_slot(slots, "meal_style", "buffet")

    tool = add_ons_tool_module.AddOnsTool()
    result = await tool.run(
        message="yes",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DRINKS_BAR},
    )

    assert result.response_context["next_question_target"] == "ask_drinks_setup"
    assert result.input_hint == {
        "type": "options",
        "options": [
            {"value": "coffee only", "label": "Coffee bar only"},
            {"value": "bar only", "label": "Bar service only"},
            {"value": "coffee and bar", "label": "Both coffee & bar"},
            {"value": "neither", "label": "Neither"},
        ],
    }
    assert result.direct_response is None


@pytest.mark.asyncio
async def test_finalization_tool_defers_free_text_prompt_wording_to_response_layer():
    slots = initialize_empty_slots()

    tool = finalization_tool_module.FinalizationTool()
    result = await tool.run(
        message="yes",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    assert result.response_context["next_question_target"] == "collect_special_requests"
    assert result.input_hint is None
    assert result.direct_response == "Tell me the special thing you want us to note. For example: flowers, decor, timing, setup, or something extra."


@pytest.mark.asyncio
async def test_modification_tool_adds_to_dietary_concerns_instead_of_replacing(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "dietary_concerns", "diabetes and kosher")

    async def fake_extract(**kwargs):
        return ModificationExtraction(
            target_slot="dietary_concerns",
            action="add",
            new_value="peanut allergies",
        )

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)

    tool = ModificationTool()
    result = await tool.run(
        message="okay wait add peanut allergies in dietary concern",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DIETARY},
    )

    assert get_slot_value(slots, "dietary_concerns") == "diabetes and kosher; peanut allergies"
    assert result.direct_response is not None
    assert "Added to your dietary concerns" in result.direct_response

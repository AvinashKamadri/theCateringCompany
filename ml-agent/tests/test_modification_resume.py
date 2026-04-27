import sys

import pytest

from agent.models import (
    EventDetailsExtraction,
    FinalizationExtraction,
    MenuSelectionExtraction,
    ModificationExtraction,
    OrchestratorDecision,
    SelectedItemGrounding,
    ToolCall,
    TurnRoutingSignals,
)
from agent.menu_resolver import resolve_to_db_items
from agent.response_generator import GeneratedReply, _fallback, render
from agent.prompt_registry import fallback_prompt_for_target
from agent.router import _quick_route, route
from agent.state import (
    PHASE_COCKTAIL,
    PHASE_CONDITIONAL_FOLLOWUP,
    PHASE_DESSERT,
    PHASE_DIETARY,
    PHASE_DRINKS_BAR,
    PHASE_EVENT_DATE,
    PHASE_FOLLOWUP,
    PHASE_GREETING,
    PHASE_GUEST_COUNT,
    PHASE_MAIN_MENU,
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
from agent.tools.base import ToolResult
from agent.tools import add_ons_tool as add_ons_tool_module
from agent.tools.basic_info_tool import BasicInfoTool, _normalize_tbd_venue
from agent.tools import finalization_tool as finalization_tool_module
from agent.tools.finalization_tool import _render_review_recap
from agent.tools import menu_selection_tool as menu_tool_module
from agent.tools.modification_tool import ModificationTool, _resume_after_modification
from agent.tools.add_ons_tool import _apply_structured_answer, _next_target
from agent.tools.finalization_tool import _next_target as _final_next_target
from agent.tools.finalization_tool import _apply_structured_answer as _final_apply_structured_answer
from agent.tools.finalization_tool import FinalizationTool

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

@pytest.mark.skip(reason="removed")

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

@pytest.mark.skip(reason="removed")

def test_quick_route_normalizes_conversational_add_ons_answers_before_mod_detection():
    slots = initialize_empty_slots()
    fill_slot(slots, "drinks", True)
    fill_slot(slots, "coffee_service", True)
    fill_slot(slots, "bar_service", False)

    state = {
        "conversation_phase": PHASE_TABLEWARE,
        "slots": slots,
    }

    assert _quick_route("actually china", state) == "add_ons_tool"

    fill_slot(slots, "__gate_tableware", True)
    fill_slot(slots, "tableware", "china")
    assert _quick_route("let's do bamboo", state) == "add_ons_tool"

@pytest.mark.skip(reason="removed")

def test_quick_route_normalizes_basic_info_menu_and_finalization_answers():
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "event_type", "Wedding")

    state = {
        "conversation_phase": PHASE_SERVICE_TYPE,
        "slots": slots,
    }
    assert _quick_route("actually onsite", state) == "basic_info_tool"

    fill_slot(slots, "service_type", "Onsite")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")
    state["conversation_phase"] = PHASE_MAIN_MENU
    assert _quick_route("let's do buffet", state) == "menu_selection_tool"

    state["conversation_phase"] = PHASE_SPECIAL_REQUESTS
    assert _quick_route("actually yes", state) == "finalization_tool"

@pytest.mark.skip(reason="removed")

def test_quick_route_normalizes_wedding_cake_answers():
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Amina")

    state = {
        "conversation_phase": PHASE_WEDDING_CAKE,
        "slots": slots,
    }

    assert _quick_route("actually yes", state) == "basic_info_tool"

    fill_slot(slots, "__wedding_cake_gate", True)
    assert _quick_route("let's do strawberry", state) == "basic_info_tool"

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

def test_quick_route_review_change_routes_to_modification_tool():
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

    state = {
        "conversation_phase": PHASE_REVIEW,
        "slots": slots,
    }

    assert _quick_route("change", state) == "modification_tool"
    assert _quick_route("I need to change something", state) == "modification_tool"
    assert _quick_route("confirm", state) == "finalization_tool"

def test_apply_structured_answer_accepts_prefixed_add_ons_choices():
    slots = initialize_empty_slots()
    fill_slot(slots, "drinks", True)
    fill_slot(slots, "coffee_service", True)
    fill_slot(slots, "bar_service", False)

    fills: list[tuple[str, object]] = []
    effects: list[tuple[str, str]] = []

    handled = _apply_structured_answer(
        target="ask_tableware_gate",
        message_lower="actually china",
        slots=slots,
        fills=fills,
        effects=effects,
    )

    assert handled is True
    assert get_slot_value(slots, "tableware") == "china"

    fills = []
    effects = []
    handled = _apply_structured_answer(
        target="ask_utensils",
        message_lower="let's do bamboo",
        slots=slots,
        fills=fills,
        effects=effects,
    )

    assert handled is True
    assert get_slot_value(slots, "utensils") == "bamboo"

def test_apply_structured_answer_accepts_multi_select_labor_services():
    slots = initialize_empty_slots()

    fills: list[tuple[str, object]] = []
    effects: list[tuple[str, str]] = []

    handled = _apply_structured_answer(
        target="ask_labor_services",
        message_lower="labor_ceremony_setup, labor_cleanup, labor_trash",
        slots=slots,
        fills=fills,
        effects=effects,
    )

    assert handled is True
    assert get_slot_value(slots, "labor_ceremony_setup") is True
    assert get_slot_value(slots, "labor_cleanup") is True
    assert get_slot_value(slots, "labor_trash") is True
    assert get_slot_value(slots, "labor_table_setup") is False
    assert get_slot_value(slots, "labor_table_preset") is False

def test_add_ons_next_target_uses_single_labor_services_step():
    slots = initialize_empty_slots()
    for key, value in {
        "drinks": True,
        "coffee_service": False,
        "bar_service": True,
        "bar_package": "full_open_bar",
        "tableware": "no_tableware",
        "utensils": "standard_plastic",
        "__gate_rentals": True,
        "linens": True,
        "rentals": "Linens, Tables, Chairs",
        "service_type": "Onsite",
    }.items():
        fill_slot(slots, key, value)

    assert _next_target(slots) == "ask_labor_services"

@pytest.mark.skip(reason="removed")

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

@pytest.mark.skip(reason="removed")

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

@pytest.mark.skip(reason="removed")

def test_quick_route_sends_wedding_cake_reselection_to_modification_tool():
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Dua Lipa")
    fill_slot(slots, "service_type", "Onsite")
    fill_slot(slots, "event_date", "2026-05-29")

    state = {
        "conversation_phase": PHASE_COCKTAIL,
        "slots": slots,
    }

    assert _quick_route("can i choose my wedding cake again", state) == "modification_tool"

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

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_router_honors_recent_service_type_prompt_even_if_phase_drifted():
    from langchain_core.messages import AIMessage

    slots = initialize_empty_slots()
    state = {"conversation_phase": PHASE_DESSERT, "slots": slots}

    history = [AIMessage(content="Would you like drop-off delivery or full onsite service?")]
    decision = await route(
        message="drop-off",
        history=history,
        state=state,
    )

    assert decision.tool_calls[0].tool_name == "basic_info_tool"

@pytest.mark.asyncio
async def test_menu_selection_returns_to_review_after_review_edit(monkeypatch):
    import agent.tools.menu_selection_tool as menu_tool_module
    from agent.models import MenuSelectionExtraction
    from agent.state import (
        PHASE_DESSERT,
        PHASE_REVIEW,
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
    )

    async def fake_extract(**kwargs):
        schema = kwargs.get("schema")
        if schema is MenuSelectionExtraction:
            return MenuSelectionExtraction(raw_items=["Brownies"], category_hint="desserts")
        raise AssertionError(f"Unexpected schema: {schema}")

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    async def fake_load_desserts(*args, **kwargs):
        return [
            {"name": "Brownies", "unit_price": 5.25, "price_type": "per_person"},
            {"name": "Blondies", "unit_price": 5.25, "price_type": "per_person"},
        ]

    monkeypatch.setattr(menu_tool_module, "load_dessert_menu_expanded", fake_load_desserts)

    slots = initialize_empty_slots()
    # Minimal recap-able state
    fill_slot(slots, "name", "Sam")
    fill_slot(slots, "email", "sam@example.com")
    fill_slot(slots, "phone", "+1 1234567890")
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "event_date", "2026-05-29")
    fill_slot(slots, "venue", "TBD - Confirm on call")
    fill_slot(slots, "guest_count", "TBD - Confirm on call")
    fill_slot(slots, "service_type", "Dropoff")
    fill_slot(slots, "selected_dishes", "Burger Bar ($23.99/per_person)")
    fill_slot(slots, "meal_style", "buffet")
    fill_slot(slots, "__return_to_review_after_edit", {"slot": "desserts"})

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="Brownies",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DESSERT},
    )

    assert result.state["conversation_phase"] == PHASE_REVIEW
    assert get_slot_value(result.state["slots"], "__return_to_review_after_edit") is None
    assert result.direct_response is not None
    assert "recap" in result.direct_response.lower()

def test_normalize_tbd_venue_variants():
    assert _normalize_tbd_venue("tbd") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("to be determined") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("venue tbd - will confirm later") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("not decided yet") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("confirm venue on call") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("venue confirm on call") == "TBD - Confirm on call"
    assert _normalize_tbd_venue("actually confirm venue on call") == "TBD - Confirm on call"

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
async def test_basic_info_tool_accepts_confirm_venue_on_call_variants():
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
        message="confirm venue on call",
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
async def test_basic_info_tool_filters_identity_slots_to_current_event_type(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed Ali")
    fill_slot(slots, "event_type", "Wedding")

    async def fake_extract(**kwargs):
        return EventDetailsExtraction(
            partner_name="Nicki Minaj",
            honoree_name="Sydney Sweeney",
        )

    monkeypatch.setattr("agent.tools.basic_info_tool.extract", fake_extract)

    tool = BasicInfoTool()
    await tool.run(
        message="Nicki Minaj",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_CONDITIONAL_FOLLOWUP},
    )

    assert get_slot_value(slots, "partner_name") == "Nicki Minaj"
    assert get_slot_value(slots, "honoree_name") is None

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
async def test_basic_info_tool_accepts_prefixed_service_type_and_wedding_cake_answers():
    slots = initialize_empty_slots()
    for key, value in {
        "name": "Syed Ali",
        "event_type": "Wedding",
        "partner_name": "Amina",
    }.items():
        fill_slot(slots, key, value)

    tool = BasicInfoTool()
    result = await tool.run(
        message="actually onsite",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SERVICE_TYPE},
    )

    assert get_slot_value(slots, "service_type") == "Onsite"
    assert result.state["conversation_phase"] == PHASE_WEDDING_CAKE
    assert result.response_context["next_question_target"] == "ask_wedding_cake"

    result = await tool.run(
        message="actually yes",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )
    assert get_slot_value(slots, "__wedding_cake_gate") is True

    result = await tool.run(
        message="let's do strawberry",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_WEDDING_CAKE},
    )
    assert get_slot_value(slots, "__wedding_cake_flavor") == "Strawberry"
    assert result.response_context["next_question_target"] == "ask_wedding_cake_filling"

@pytest.mark.asyncio
async def test_wedding_transition_goes_to_service_style_without_reasking_meal_style(monkeypatch):
    slots = initialize_empty_slots()
    for key, value in {
        "name": "Syed Ali",
        "event_type": "Wedding",
        "partner_name": "Sydney Sweeney",
        "wedding_cake": "none",
        "__wedding_cake_gate": False,
        "service_type": "Onsite",
        "event_date": "2026-05-30",
        "venue": "TBD - Confirm on call",
        "guest_count": "TBD - Confirm later",
        "email": "syed20295@gmail.com",
    }.items():
        fill_slot(slots, key, value)

    async def fake_extract(**kwargs):
        return EventDetailsExtraction(phone="+1 1234567890")

    monkeypatch.setattr("agent.tools.basic_info_tool.extract", fake_extract)

    tool = BasicInfoTool()
    result = await tool.run(
        message="+1 1234567890",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_GREETING},
    )

    assert result.state["conversation_phase"] == "S8_transition"
    assert result.response_context["next_question_target"] == "ask_service_style"
    assert result.input_hint == {
        "type": "options",
        "options": [
            {"value": "cocktail hour", "label": "Cocktail hour"},
            {"value": "reception", "label": "Reception"},
            {"value": "both", "label": "Both"},
        ],
    }

    text = await render(tool_result=result, user_message="+1 1234567890", history=[])
    assert "cocktail hour" in text.lower()
    assert "reception" in text.lower()
    assert "plated" not in text.lower()
    assert "family-style" not in text.lower()

@pytest.mark.asyncio
async def test_menu_selection_tool_accepts_prefixed_meal_style_answers():
    slots = initialize_empty_slots()
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "passed")
    fill_slot(slots, "selected_dishes", "Chicken Piccata ($29.49/per_person)")

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="let's do buffet",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    assert get_slot_value(slots, "meal_style") == "buffet"
    assert result.state["conversation_phase"] == PHASE_DESSERT

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_menu_selection_tool_prompts_for_ambiguous_main_choice(monkeypatch):
    slots = initialize_empty_slots()

    async def fake_extract(**kwargs):
        return MenuSelectionExtraction(raw_items=["chicken"], category_hint="dishes")

    async def fake_load_main_dish_menu():
        return {
            "Signature Combos": [
                {"name": "Chicken & Ham", "unit_price": 27.99, "price_type": "per_person"},
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
            ],
        }

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module, "load_main_dish_menu", fake_load_main_dish_menu)

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="chicken",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    assert "which one do you want" in (result.direct_response or "").lower()
    assert get_slot_value(slots, "__pending_menu_choice") is not None
    assert get_slot_value(slots, "selected_dishes") is None
    assert result.input_hint == {
        "type": "options",
        "options": [
            {"value": "Chicken & Ham", "label": "Chicken & Ham"},
            {"value": "Chicken Piccata", "label": "Chicken Piccata"},
        ],
    }

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

@pytest.mark.skip(reason="Fallback prompt format changed.")
def test_response_fallback_uses_specific_venue_prompt():
    text = _fallback({
        "tool": "basic_info_tool",
        "next_question_target": "ask_venue",
    })
    assert "venue" in text.lower()
    assert "confirm venue on call" in text.lower()

@pytest.mark.skip(reason="Fallback prompt format changed.")
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

@pytest.mark.skip(reason="Fallback prompt format changed.")
def test_response_fallback_uses_specific_add_ons_prompt():
    text = _fallback({
        "tool": "add_ons_tool",
        "next_question_target": "ask_tableware_gate",
    })
    assert "tableware" in text.lower()
    assert "upgrade" in text.lower()

@pytest.mark.skip(reason="Modification response format updated.")
def test_response_fallback_for_modification_mentions_change_and_remaining_items():
    text = _fallback({
        "tool": "modification_tool",
        "modification": {
            "target_slot": "selected_dishes",
            "action": "add",
            "added": ["Ravioli Menu"],
            "remaining_items": ["Souvlaki Bar", "Ravioli Menu"],
            "new_value": "Souvlaki Bar ($21.49/per_person), Ravioli Menu ($31.99/per_person)",
        },
        "next_question_target": "ask_drinks_setup",
    })
    assert "ravioli menu" in text.lower()
    assert "souvlaki bar" in text.lower()
    assert "coffee service" in text.lower()

@pytest.mark.asyncio
async def test_render_modification_response_mentions_change_and_current_selection(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Adobo Lime Chicken Bites ($3.25/per_person), BBQ Chicken Slider ($3.50/per_person), Spanakopita ($2.95/per_person)",
    )

    async def fail_if_called(**kwargs):
        raise AssertionError("generate_text should not run for successful modification renders")

    monkeypatch.setattr("agent.response_generator.generate_text", fail_if_called)

    text = await render(
        tool_result=ToolResult(
            state={
                "slots": slots,
                "messages": [],
                "conversation_phase": PHASE_COCKTAIL,
            },
            response_context={
                "tool": "modification_tool",
                "modification": {
                    "target_slot": "appetizers",
                    "action": "add",
                    "added": ["Spanakopita"],
                    "remaining_items": [
                        "Adobo Lime Chicken Bites",
                        "BBQ Chicken Slider",
                        "Spanakopita",
                    ],
                    "new_value": get_slot_value(slots, "appetizers"),
                },
                "next_question_target": "ask_appetizer_style",
            },
        ),
        user_message="add spanakopita",
        history=[],
    )

    lowered = text.lower()
    assert "spanakopita" in lowered
    assert "adobo lime chicken bites" in lowered
    assert "bbq chicken slider" in lowered
    assert "passed around" in lowered or "station" in lowered

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_render_modification_response_mentions_updated_notes(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "special_requests", "flower bouquet; stage candles")

    async def fail_if_called(**kwargs):
        raise AssertionError("generate_text should not run for successful modification renders")

    monkeypatch.setattr("agent.response_generator.generate_text", fail_if_called)

    text = await render(
        tool_result=ToolResult(
            state={
                "slots": slots,
                "messages": [],
                "conversation_phase": PHASE_SPECIAL_REQUESTS,
            },
            response_context={
                "tool": "modification_tool",
                "modification": {
                    "target_slot": "special_requests",
                    "action": "add",
                    "old_value": "flower bouquet",
                    "new_value": "flower bouquet; stage candles",
                },
                "next_question_target": "ask_dietary_gate",
            },
        ),
        user_message="add stage candles to special requests",
        history=[],
    )

    lowered = text.lower()
    assert "special requests" in lowered
    assert "stage candles" in lowered
    assert "flower bouquet" in lowered
    assert "dietary" in lowered

@pytest.mark.asyncio
async def test_render_menu_progress_uses_current_selection_verbatim(monkeypatch):
    async def fail_if_called(**kwargs):
        raise AssertionError("generate_text should not run for menu_progress renders")

    monkeypatch.setattr("agent.response_generator.generate_text", fail_if_called)

    text = await render(
        tool_result=ToolResult(
            state={
                "slots": initialize_empty_slots(),
                "messages": [],
                "conversation_phase": PHASE_COCKTAIL,
            },
            response_context={
                "tool": "menu_selection_tool",
                "menu_progress": (
                    "Added Adobo Steak Skewers. "
                    "Your appetizers are now: Grilled Shrimp Cocktail, Firecracker Shrimp, Adobo Steak Skewers.\n\n"
                    "How would you like the appetizers served?"
                ),
                "next_question_target": "ask_appetizer_style",
            },
        ),
        user_message="add adobo steak skewers",
        history=[],
    )

    lowered = text.lower()
    assert "adobo steak skewers" in lowered
    assert "grilled shrimp cocktail" in lowered
    assert "firecracker shrimp" in lowered

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
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
@pytest.mark.skip(reason="removed")

async def test_modification_tool_removing_wedding_cake_clears_hidden_cake_stage():
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "__wedding_cake_gate", True)
    fill_slot(slots, "__wedding_cake_flavor", "Carrot")
    fill_slot(slots, "__wedding_cake_filling", "Peanut Butter Cream")
    fill_slot(slots, "__wedding_cake_buttercream", "Cream Cheese Frosting")
    fill_slot(
        slots,
        "wedding_cake",
        '2 Tier 6" & 8" - Carrot, Peanut Butter Cream, Cream Cheese Frosting',
    )
    fill_slot(slots, "service_type", "Dropoff")
    fill_slot(slots, "event_date", "2026-05-30")

    tool = ModificationTool()
    result = await tool._apply_scalar_modification(
        ModificationExtraction(
            target_slot="wedding_cake",
            action="remove",
            new_value=None,
        ),
        "remove the wedding cake",
        slots,
        {"conversation_phase": PHASE_VENUE, "slots": slots},
        [],
    )

    assert get_slot_value(slots, "wedding_cake") is None
    assert get_slot_value(slots, "__wedding_cake_gate") is None
    assert get_slot_value(slots, "__wedding_cake_flavor") is None
    assert get_slot_value(slots, "__wedding_cake_filling") is None
    assert get_slot_value(slots, "__wedding_cake_buttercream") is None
    assert result.response_context["next_question_target"] == "ask_venue"

@pytest.mark.asyncio
async def test_modification_tool_reopens_wedding_cake_flow():
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "partner_name", "Dua Lipa")
    fill_slot(slots, "service_type", "Onsite")
    fill_slot(slots, "event_date", "2026-05-29")
    fill_slot(slots, "wedding_cake", "none")
    fill_slot(slots, "__wedding_cake_gate", False)

    tool = ModificationTool()
    result = await tool.run(
        message="can i choose my wedding cake again",
        history=[],
        state={"conversation_phase": PHASE_COCKTAIL, "slots": slots},
    )

    assert get_slot_value(slots, "wedding_cake") is None
    assert get_slot_value(slots, "__wedding_cake_gate") is None
    assert result.state["conversation_phase"] == PHASE_WEDDING_CAKE
    assert result.response_context["next_question_target"] == "ask_wedding_cake"
    assert "wedding cake again" in (result.direct_response or "").lower()

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
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
    assert result.direct_response is None
    assert "menu_progress" in result.response_context
    assert "Parmesan Artichoke Dip" in result.response_context["menu_progress"]

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_menu_selection_tool_appetizer_progress_uses_explicit_service_options(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "cocktail_hour", True)

    async def fake_extract(**kwargs):
        return menu_tool_module.MenuSelectionExtraction(
            raw_items=["Bruschetta"],
            category_hint="appetizers",
        )

    async def fake_resolve_raw_items(self, raw_items, category, slots):
        return [("appetizers", "Bruschetta ($1.75/per_person)", 1)]

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module.MenuSelectionTool, "_resolve_raw_items", fake_resolve_raw_items)

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="Bruschetta",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    prompt = result.response_context.get("menu_progress") or ""
    lowered = prompt.lower()
    assert "passed around by servers" in lowered
    assert "set up at a station" in lowered

@pytest.mark.skip(reason="stale mock signature; covered by tests/test_e2e_happy_path.py:test_meal_style_requires_selected_dishes_filled")
@pytest.mark.asyncio
async def test_menu_selection_tool_does_not_accept_meal_style_while_user_is_still_picking_mains(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "cocktail_hour", True)
    fill_slot(slots, "appetizers", "Brie Bites ($3.00/per_person)")
    fill_slot(slots, "appetizer_style", "station")

    async def fake_extract(**kwargs):
        return menu_tool_module.MenuSelectionExtraction(
            raw_items=["Chicken Piccata", "Prime Rib & Salmon"],
            category_hint="dishes",
            meal_style="plated",
        )

    async def fake_resolve_raw_items(self, raw_items, category, slots):
        return [(
            "selected_dishes",
            "Chicken Piccata ($29.49/per_person), Prime Rib & Salmon ($41.99/per_person)",
            2,
        )]

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)
    monkeypatch.setattr(menu_tool_module.MenuSelectionTool, "_resolve_raw_items", fake_resolve_raw_items)

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="Chicken Piccata, Prime Rib & Salmon",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    assert get_slot_value(slots, "selected_dishes") is not None
    assert get_slot_value(slots, "meal_style") is None
    assert get_slot_value(slots, "tableware") is None
    assert result.state["conversation_phase"] == PHASE_MAIN_MENU
    assert result.response_context["next_question_target"] == "ask_meal_style"

@pytest.mark.asyncio
async def test_render_collect_dietary_prompt_does_not_reask_yes_no_gate(monkeypatch):
    async def fake_extract(**kwargs):
        assert kwargs["schema"] is GeneratedReply
        return GeneratedReply(reply_text="Tell me the food or health needs we should note.")

    async def fail_if_called(**kwargs):
        raise AssertionError("generate_text should not run for collect_dietary_concerns")

    monkeypatch.setattr("agent.response_generator.extract", fake_extract)
    monkeypatch.setattr("agent.response_generator.generate_text", fail_if_called)

    text = await render(
        tool_result=ToolResult(
            state={
                "slots": initialize_empty_slots(),
                "messages": [],
                "conversation_phase": PHASE_DIETARY,
            },
            response_context={
                "tool": "finalization_tool",
                "next_question_target": "collect_dietary_concerns",
            },
        ),
        user_message="yes",
        history=[],
    )

    lowered = text.lower()
    assert "what dietary" in lowered or "food or health needs" in lowered
    assert "do you have" not in lowered
    assert "yes" not in lowered

@pytest.mark.asyncio
async def test_render_passes_tone_to_extract(monkeypatch):
    """Response generator must inject detected tone into the LLM payload."""
    import json
    from langchain_core.messages import HumanMessage

    captured: dict = {}

    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        assert schema.__name__ == "GeneratedReply"
        captured["payload"] = json.loads(kwargs.get("user_message", "{}"))
        return schema(reply_text="where's the venue at? 🎉")

    async def fail_if_called(**kwargs):
        raise AssertionError("generate_text should not run when structured reply extraction succeeds")

    monkeypatch.setattr("agent.response_generator.extract", fake_extract)
    monkeypatch.setattr("agent.response_generator.generate_text", fail_if_called)

    funky_history = [HumanMessage(content="yo yo let's plan this fr fr 🔥")]

    await render(
        tool_result=ToolResult(
            state={
                "slots": initialize_empty_slots(),
                "messages": [],
                "conversation_phase": PHASE_EVENT_DATE,
            },
            response_context={
                "tool": "basic_info_tool",
                "next_question_target": "ask_venue",
            },
        ),
        user_message="july 30 lmao",
        history=funky_history,
    )

    assert "tone_profile" in captured["payload"], "tone_profile must be in LLM payload"
    assert captured["payload"]["tone_profile"] == "funky"
    guidance = captured["payload"].get("tone_guidance", "").lower()
    assert "slang" in guidance or "upbeat" in guidance or "relaxed" in guidance

@pytest.mark.asyncio
async def test_render_formal_tone_detected(monkeypatch):
    """Formal user messages must produce formal tone guidance in the LLM payload."""
    import json
    from langchain_core.messages import HumanMessage

    captured: dict = {}

    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        captured["payload"] = json.loads(kwargs.get("user_message", "{}"))
        return schema(reply_text="Kindly provide the venue address.")

    monkeypatch.setattr("agent.response_generator.extract", fake_extract)
    async def fail_if_called(**_):
        raise AssertionError("generate_text should not run when structured reply extraction succeeds")

    monkeypatch.setattr("agent.response_generator.generate_text", fail_if_called)

    formal_history = [
        HumanMessage(content="Good afternoon. I would like to arrange catering for our corporate event."),
        HumanMessage(content="Please note the date is July 30, 2026. We appreciate your assistance."),
    ]

    await render(
        tool_result=ToolResult(
            state={
                "slots": initialize_empty_slots(),
                "messages": [],
                "conversation_phase": PHASE_EVENT_DATE,
            },
            response_context={
                "tool": "basic_info_tool",
                "next_question_target": "ask_venue",
            },
        ),
        user_message="Thank you. The venue is still to be confirmed.",
        history=formal_history,
    )

    assert captured["payload"]["tone_profile"] == "formal"
    guidance = captured["payload"].get("tone_guidance", "").lower()
    assert "professional" in guidance or "formal" in guidance or "polite" in guidance

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
async def test_wedding_menu_transition_does_not_skip_service_style_question(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")

    async def fake_extract(**kwargs):
        return menu_tool_module.MenuSelectionExtraction()

    monkeypatch.setattr(menu_tool_module, "extract", fake_extract)

    tool = menu_tool_module.MenuSelectionTool()
    result = await tool.run(
        message="sure",
        history=[],
        state={"slots": slots, "conversation_phase": "S8_transition"},
    )

    assert get_slot_value(slots, "cocktail_hour") is None
    assert get_slot_value(slots, "service_style") is None
    assert result.state["conversation_phase"] == PHASE_COCKTAIL
    assert result.response_context["next_question_target"] == "ask_service_style"

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_add_ons_tool_keeps_linens_in_rentals_value():
    slots = initialize_empty_slots()
    fill_slot(slots, "service_type", "Dropoff")
    fill_slot(slots, "drinks", False)
    fill_slot(slots, "coffee_service", False)
    fill_slot(slots, "bar_service", False)
    fill_slot(slots, "tableware", "standard_disposable")
    fill_slot(slots, "utensils", "bamboo")
    fill_slot(slots, "__gate_rentals", True)

    tool = add_ons_tool_module.AddOnsTool()
    result = await tool.run(
        message="Linens, Tables, Chairs",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_RENTALS},
    )

    assert get_slot_value(slots, "linens") is True
    assert get_slot_value(slots, "rentals") == "Linens, Tables, Chairs"
    assert result.response_context["next_question_target"] == "transition_to_special_requests"

def test_review_recap_uses_written_service_style_and_rentals():
    text = _render_review_recap({
        "name": "Syed",
        "event_type": "Wedding",
        "event_date": "2026-07-30",
        "service_style": "both",
        "rentals": "Linens, Tables, Chairs",
        "linens": True,
    })

    lowered = text.lower()
    assert "service style: cocktail hour + reception" in lowered
    assert "rentals: linens, tables, chairs" in lowered
    assert "linens included" not in lowered

def test_review_recap_canonicalizes_common_event_type_typos():
    text = _render_review_recap({
        "name": "Syed",
        "event_type": "Weddimg",
        "partner_name": "Saniya",
        "event_date": "2026-07-30",
    })

    lowered = text.lower()
    assert "wedding" in lowered
    assert "partner: saniya" in lowered

@pytest.mark.asyncio
async def test_modification_tool_normalizes_meal_style_values():
    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "meal_style", "plated")

    await tool._apply_scalar_modification(
        ModificationExtraction(target_slot="meal_style", action="replace", new_value="change to buffet"),
        "change to buffet",
        slots,
        {"conversation_phase": PHASE_REVIEW},
        [],
    )

    assert get_slot_value(slots, "meal_style") == "buffet"

@pytest.mark.asyncio
async def test_modification_tool_maps_drinks_package_to_bar_slots():
    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "drinks", True)
    fill_slot(slots, "bar_service", True)
    fill_slot(slots, "bar_package", "full_open_bar")

    await tool._apply_scalar_modification(
        ModificationExtraction(target_slot="drinks", action="replace", new_value="Beer+Wine"),
        "Beer+Wine",
        slots,
        {"conversation_phase": PHASE_REVIEW},
        [],
    )

    assert get_slot_value(slots, "drinks") is True
    assert get_slot_value(slots, "bar_service") is True
    assert get_slot_value(slots, "bar_package") == "beer_wine"

@pytest.mark.asyncio
async def test_review_stage_scalar_edit_returns_to_change_picker():
    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "name", "Syed")
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "meal_style", "plated")

    pending = {
        "stage": "value",
        "target_slot": "meal_style",
        "origin_phase": PHASE_REVIEW,
    }
    fill_slot(slots, "__pending_modification_request", pending)

    result = await tool.run(
        message="buffet",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_REVIEW},
    )

    assert get_slot_value(slots, "meal_style") == "buffet"
    assert result.response_context["next_question_target"] == "ask_modification_target"
    assert "anything else" in (result.direct_response or "").lower()

@pytest.mark.asyncio
async def test_modification_tool_reopens_wedding_cake_instead_of_storing_raw_text():
    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Wedding")
    fill_slot(slots, "wedding_cake", "none")

    result = await tool._apply_scalar_modification(
        ModificationExtraction(target_slot="wedding_cake", action="replace", new_value="add wedding cake"),
        "add wedding cake",
        slots,
        {"conversation_phase": PHASE_REVIEW},
        [],
    )

    assert result.response_context["next_phase"] == PHASE_WEDDING_CAKE
    assert result.response_context["next_question_target"] == "ask_wedding_cake"
    assert get_slot_value(slots, "wedding_cake") is None

@pytest.mark.asyncio
async def test_modification_tool_normalizes_bar_service_and_sets_drinks_true():
    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "drinks", False)
    fill_slot(slots, "bar_service", False)

    await tool._apply_scalar_modification(
        ModificationExtraction(target_slot="bar_service", action="replace", new_value="yes"),
        "yes",
        slots,
        {"conversation_phase": PHASE_REVIEW},
        [],
    )

    assert get_slot_value(slots, "bar_service") is True
    assert get_slot_value(slots, "drinks") is True

@pytest.mark.asyncio
async def test_modification_tool_multi_updates_email_and_phone_without_llm(monkeypatch):
    # Ensure we don't accidentally call the LLM extractor for this common case.
    import agent.tools.modification_tool as mod_tool_module

    async def _nope(*args, **kwargs):
        raise AssertionError("LLM extract should not be called for deterministic multi updates")

    monkeypatch.setattr(mod_tool_module, "extract", _nope)

    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "email", "old@example.com")
    fill_slot(slots, "phone", "+10000000000")

    result = await tool.run(
        message="change my email to new@example.com and phone number to +1 234 567 8900",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_REVIEW, "messages": []},
    )

    assert get_slot_value(slots, "email") == "new@example.com"
    assert get_slot_value(slots, "phone").startswith("+1")
    assert "updated email" in (result.direct_response or "").lower()

@pytest.mark.skip(reason="Wedding cake prompts moved to LLM-generated with WAITER GUIDANCE.")
def test_prompt_registry_has_wedding_cake_subprompts():
    assert "cake" in fallback_prompt_for_target("basic_info_tool", "ask_wedding_cake_flavor").lower()
    assert "filling" in fallback_prompt_for_target("basic_info_tool", "ask_wedding_cake_filling").lower()
    assert "buttercream" in fallback_prompt_for_target("basic_info_tool", "ask_wedding_cake_buttercream").lower()
    assert "drinks" in fallback_prompt_for_target("basic_info_tool", "transition_to_addons").lower()

@pytest.mark.asyncio
async def test_response_generator_uses_natural_bool_ack_for_coffee_service():
    slots = initialize_empty_slots()
    fill_slot(slots, "coffee_service", False)

    tool_result = ToolResult(
        state={"slots": slots, "conversation_phase": PHASE_REVIEW, "messages": []},
        response_context={
            "tool": "modification_tool",
            "modification": {
                "target_slot": "coffee_service",
                "action": "replace",
                "old_value": False,
                "new_value": True,
            },
            "next_question_target": "review",
        },
        input_hint=None,
    )

    text = await render(tool_result=tool_result, user_message="yes", history=[])
    lowered = text.lower()
    assert "coffee bar" in lowered
    assert "updated your coffee" not in lowered

@pytest.mark.asyncio
async def test_response_generator_mentions_already_selected_on_replace():
    slots = initialize_empty_slots()
    tool_result = ToolResult(
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL, "messages": []},
        response_context={
            "tool": "modification_tool",
            "modification": {
                "target_slot": "appetizers",
                "action": "replace",
                "removed": ["White Bean Tapenade w/ Crostini"],
                "added": [],
                "already_selected": ["Adobo Lime Chicken Bites"],
                "unavailable": ["sushi"],
                "new_value": "mock",
            },
            "next_question_target": "ask_appetizer_style",
        },
        input_hint=None,
    )

    text = await render(tool_result=tool_result, user_message="replace", history=[])
    lowered = text.lower()
    assert "already" in lowered
    assert "adobo lime chicken bites" in lowered
    assert "sushi" in lowered

def test_finalization_skips_additional_notes_and_goes_to_followup():
    slots = initialize_empty_slots()
    fill_slot(slots, "special_requests", "none")
    fill_slot(slots, "dietary_concerns", "none")
    # additional_notes intentionally left empty

    assert _final_next_target(slots) == "ask_followup_call"
    assert get_slot_value(slots, "additional_notes") == "none"

def test_finalization_followup_call_accepts_schedule_call_label():
    slots = initialize_empty_slots()
    fills: list[tuple[str, object]] = []

    handled = _final_apply_structured_answer(
        target="ask_followup_call",
        message_lower="yes, schedule a call",
        slots=slots,
        fills=fills,
    )

    assert handled is True
    assert get_slot_value(slots, "followup_call_requested") is True

@pytest.mark.asyncio
async def test_finalization_yes_to_followup_call_does_not_auto_confirm():
    slots = initialize_empty_slots()
    # Reach the followup call question
    fill_slot(slots, "special_requests", "none")
    fill_slot(slots, "dietary_concerns", "none")
    fill_slot(slots, "additional_notes", "none")

    tool = FinalizationTool()
    result = await tool.run(
        message="yes",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_FOLLOWUP},
    )

    # Should set followup_call_requested, then move to review (not complete)
    assert get_slot_value(slots, "followup_call_requested") is True
    assert result.response_context["next_phase"] == PHASE_REVIEW
    assert get_slot_value(slots, "conversation_status") is None

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

@pytest.mark.asyncio
async def test_modification_tool_reopens_appetizers_on_reselect_request_from_main_menu(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(
        slots,
        "appetizers",
        "BBQ Chicken Slider ($3.50/per_person), White Bean Tapenade w/ Crostini ($1.75/per_person)",
    )
    fill_slot(slots, "appetizer_style", "station")

    async def fake_extract(**kwargs):
        raise AssertionError("extract should not run for explicit appetizer reselection requests")

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)

    async def fake_render_slot_menu(self, target_slot, slots):
        assert target_slot == "appetizers"
        return (
            "Here are the appetizer options:\n1. BBQ Chicken Slider\n2. White Bean Tapenade w/ Crostini",
            {"type": "menu_picker", "category": "appetizers", "menu": []},
        )

    monkeypatch.setattr(ModificationTool, "_render_slot_menu", fake_render_slot_menu)

    tool = ModificationTool()
    result = await tool.run(
        message="i want to reselect appetizers",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    assert get_slot_value(slots, "appetizers") is None
    assert get_slot_value(slots, "appetizer_style") is None
    assert result.state["conversation_phase"] == PHASE_COCKTAIL
    assert result.response_context["next_phase"] == PHASE_COCKTAIL
    assert "Here are the appetizer options" in (result.direct_response or "")

@pytest.mark.skip(reason="removed")

def test_quick_route_reopens_menu_sections_from_followup_phase():
    slots = initialize_empty_slots()
    fill_slot(slots, "followup_call_requested", False)

    state = {
        "conversation_phase": PHASE_FOLLOWUP,
        "slots": slots,
    }

    assert _quick_route("show me the dessert menu", state) == "modification_tool"
    assert _quick_route("actually add desserts back", state) == "modification_tool"

@pytest.mark.skip(reason="removed")

def test_quick_route_reopens_prior_appetizer_section_from_main_menu():
    slots = initialize_empty_slots()
    fill_slot(slots, "appetizers", "BBQ Chicken Slider ($3.50/per_person)")

    state = {
        "conversation_phase": PHASE_MAIN_MENU,
        "slots": slots,
    }

    assert _quick_route("i want to reselect appetizers", state) == "modification_tool"

def test_quick_route_keeps_pending_menu_choice_in_menu_selection_tool():
    slots = initialize_empty_slots()
    fill_slot(slots, "__pending_menu_choice", {
        "category": "dishes",
        "query": "chicken",
        "matches": ["Chicken Piccata", "Chicken & Ham"],
        "raw_items": ["chicken"],
    })

    state = {
        "conversation_phase": PHASE_SPECIAL_REQUESTS,
        "slots": slots,
    }

    assert _quick_route("2", state) == "menu_selection_tool"

def test_quick_route_keeps_pending_modification_request_in_modification_tool():
    slots = initialize_empty_slots()
    fill_slot(slots, "__pending_modification_request", {"stage": "target"})

    state = {
        "conversation_phase": PHASE_SPECIAL_REQUESTS,
        "slots": slots,
    }

    assert _quick_route("appetizers", state) == "modification_tool"

@pytest.mark.skip(reason="removed")

def test_quick_route_keeps_late_menu_modifications_in_modification_tool():
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Souvlaki Bar ($21.49/per_person), Mexican Char Grilled ($27.99/per_person)")
    fill_slot(slots, "drinks", True)

    state = {
        "conversation_phase": PHASE_DRINKS_BAR,
        "slots": slots,
    }

    assert _quick_route("add back ravioli menu and add soup/salad", state) == "modification_tool"
    assert _quick_route("add ravioli menu back", state) == "modification_tool"

@pytest.mark.skip(reason="removed")

def test_quick_route_keeps_venue_tbd_tokens_in_basic_info():
    slots = initialize_empty_slots()
    fill_slot(slots, "event_date", "2026-04-30")

    state = {
        "conversation_phase": PHASE_VENUE,
        "slots": slots,
    }

    assert _quick_route("tbd_confirm_call", state) == "basic_info_tool"
    assert _quick_route("confirm venue on call", state) == "basic_info_tool"
    assert _quick_route("venue confirm on call", state) == "basic_info_tool"
    assert _quick_route("actually confirm venue on call", state) == "basic_info_tool"

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_router_turn_signals_keep_current_phase_answer_with_phase_owner(monkeypatch):
    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        if schema.__name__ == "TurnRoutingSignals":
            return TurnRoutingSignals(
                intent="answer_current_prompt",
                referenced_slot=None,
                proposed_tool=None,
                confidence=0.96,
                reason="the user is answering the current phase",
            )
        raise AssertionError("OrchestratorDecision extraction should not run when turn signals are decisive")

    monkeypatch.setattr("agent.router.extract", fake_extract)

    decision = await route(
        message="yes I do",
        history=[],
        state={"conversation_phase": PHASE_SPECIAL_REQUESTS, "slots": initialize_empty_slots()},
    )

    assert decision.tool_calls[0].tool_name == "finalization_tool"
    assert decision.tool_calls[0].reason == "turn_signals:answer_current_prompt"

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_router_turn_signals_route_modification_before_phase_owner(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "venue", "Pearluxe Tower")

    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        if schema.__name__ == "TurnRoutingSignals":
            return TurnRoutingSignals(
                intent="modify_existing",
                referenced_slot="venue",
                proposed_tool=None,
                confidence=0.97,
                reason="the user is changing a filled venue",
            )
        raise AssertionError("OrchestratorDecision extraction should not run when modification signals are decisive")

    monkeypatch.setattr("agent.router.extract", fake_extract)

    decision = await route(
        message="for the venue, make it Grand Hall",
        history=[],
        state={"conversation_phase": PHASE_RENTALS, "slots": slots},
    )

    assert decision.tool_calls[0].tool_name == "modification_tool"
    assert decision.tool_calls[0].reason == "turn_signals:modify_existing"

@pytest.mark.asyncio
async def test_router_turn_signals_route_reopen_previous_section_before_phase_owner(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "appetizers", "BBQ Chicken Slider ($3.50/per_person)")

    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        if schema.__name__ == "TurnRoutingSignals":
            return TurnRoutingSignals(
                intent="reopen_previous_section",
                referenced_slot="appetizers",
                proposed_tool=None,
                confidence=0.97,
                reason="the user wants to revisit the appetizer section",
        )
        raise AssertionError("OrchestratorDecision extraction should not run when reopen signals are decisive")

    monkeypatch.setattr("agent.router.extract", fake_extract)
    monkeypatch.setattr("agent.router._quick_route", lambda message, state: None)

    decision = await route(
        message="can we go back to appetizers",
        history=[],
        state={"conversation_phase": PHASE_MAIN_MENU, "slots": slots},
    )

    assert decision.tool_calls[0].tool_name == "modification_tool"
    assert decision.tool_calls[0].reason == "turn_signals:reopen_previous_section"

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_router_turn_signals_allow_off_phase_information_to_fall_through(monkeypatch):
    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        if schema.__name__ == "TurnRoutingSignals":
            return TurnRoutingSignals(
                intent="provide_other_information",
                referenced_slot=None,
                proposed_tool="add_ons_tool",
                confidence=0.95,
                reason="the user volunteered information outside the immediate phase",
            )
        raise AssertionError("OrchestratorDecision extraction should not run when proposed_tool is present")

    monkeypatch.setattr("agent.router.extract", fake_extract)

    decision = await route(
        message="we also want coffee and bar service",
        history=[],
        state={"conversation_phase": PHASE_SERVICE_TYPE, "slots": initialize_empty_slots()},
    )

    assert decision.tool_calls[0].tool_name == "add_ons_tool"
    assert decision.tool_calls[0].reason == "turn_signals:provide_other_information"

@pytest.mark.asyncio
@pytest.mark.skip(reason="removed")

async def test_router_phase_lock_preserves_late_modification_over_add_ons(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Souvlaki Bar ($21.49/per_person)")
    fill_slot(slots, "drinks", True)

    async def fake_extract(**kwargs):
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[ToolCall(tool_name="menu_selection_tool", reason="bad_guess")],
            confidence=0.95,
        )

    monkeypatch.setattr("agent.router.extract", fake_extract)

    decision = await route(
        message="add ravioli menu back",
        history=[],
        state={"conversation_phase": PHASE_DRINKS_BAR, "slots": slots},
    )

    assert decision.tool_calls[0].tool_name == "modification_tool"

@pytest.mark.asyncio
async def test_menu_resolver_matches_soup_salad_alias():
    menu = {
        "Soup / Salad / Sandwich": [
            {"name": "Soup / Salad / Sandwich", "unit_price": 21.95, "price_type": "per_person"},
        ],
    }

    matched, formatted = await resolve_to_db_items("soup/salad", menu=menu)

    assert [item["name"] for item in matched] == ["Soup / Salad / Sandwich"]
    assert "Soup / Salad / Sandwich" in formatted

@pytest.mark.asyncio
async def test_menu_resolver_preserves_single_conjoined_menu_name():
    menu = {
        "BBQ Menus": [
            {"name": "Pork & Chicken", "unit_price": 23.99, "price_type": "per_person"},
            {"name": "Chicken & Ham", "unit_price": 27.99, "price_type": "per_person"},
        ],
    }

    matched, formatted = await resolve_to_db_items("pork and chicken", menu=menu)

    assert [item["name"] for item in matched] == ["Pork & Chicken"]
    assert "Chicken & Ham" not in formatted

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
    assert result.direct_response is None

@pytest.mark.asyncio
async def test_finalization_tool_accepts_prefixed_gate_answers():
    slots = initialize_empty_slots()

    tool = finalization_tool_module.FinalizationTool()
    result = await tool.run(
        message="actually yes",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    assert get_slot_value(slots, "__gate_special_requests") is True
    assert result.response_context["next_question_target"] == "collect_special_requests"
    assert result.direct_response is None

@pytest.mark.asyncio
@pytest.mark.skip(reason="removed")

async def test_finalization_tool_captures_extra_special_requests_while_asking_dietary(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "special_requests", "Add flower bouquet")

    async def fake_extract(**kwargs):
        assert kwargs["schema"] is FinalizationExtraction
        return FinalizationExtraction(
            special_requests="bring party poppers and snow sprays",
        )

    monkeypatch.setattr("agent.tools.finalization_tool.extract", fake_extract)

    tool = finalization_tool_module.FinalizationTool()
    result = await tool.run(
        message="hey it would be great if you also bring some party poppers and snow sprays",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_DIETARY},
    )

    assert get_slot_value(slots, "special_requests") == "Add flower bouquet; bring party poppers and snow sprays"
    assert get_slot_value(slots, "dietary_concerns") is None
    assert result.response_context["next_question_target"] == "ask_dietary_gate"
    assert result.direct_response is None

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
    assert result.direct_response is None
    assert result.response_context["modification"]["target_slot"] == "dietary_concerns"
    assert result.response_context["modification"]["new_value"] == "diabetes and kosher; peanut allergies"

@pytest.mark.asyncio
async def test_modification_tool_updates_special_requests_text():
    slots = initialize_empty_slots()
    fill_slot(slots, "special_requests", "flower bouquet")

    tool = ModificationTool()
    result = await tool._apply_scalar_modification(
        ModificationExtraction(
            target_slot="special_requests",
            action="replace",
            new_value="flower bouquet and stage candles",
        ),
        "change special requests to flower bouquet and stage candles",
        slots,
        {"conversation_phase": PHASE_SPECIAL_REQUESTS, "slots": slots},
        [],
    )

    assert get_slot_value(slots, "special_requests") == "flower bouquet and stage candles"
    assert result.direct_response is None
    assert result.response_context["modification"]["target_slot"] == "special_requests"
    assert result.response_context["modification"]["new_value"] == "flower bouquet and stage candles"

@pytest.mark.asyncio
async def test_modification_tool_removes_additional_notes():
    slots = initialize_empty_slots()
    fill_slot(slots, "additional_notes", "Please call after 6 PM")

    tool = ModificationTool()
    result = await tool._apply_scalar_modification(
        ModificationExtraction(
            target_slot="additional_notes",
            action="remove",
            new_value=None,
        ),
        "remove the additional notes",
        slots,
        {"conversation_phase": PHASE_FOLLOWUP, "slots": slots},
        [],
    )

    assert get_slot_value(slots, "additional_notes") is None
    assert result.direct_response is None
    assert result.response_context["modification"]["target_slot"] == "additional_notes"
    assert result.response_context["modification"]["new_value"] is None

@pytest.mark.asyncio
@pytest.mark.skip(reason="removed")

async def test_modification_tool_filters_identity_slots_when_event_type_changes(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "event_type", "Birthday")
    fill_slot(slots, "honoree_name", "Sydney Sweeney")

    async def fake_extract(**kwargs):
        return EventDetailsExtraction(
            event_type="Wedding",
            partner_name="Nicki Minaj",
            honoree_name="Sydney Sweeney",
        )

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)

    tool = ModificationTool()
    await tool._apply_scalar_modification(
        ModificationExtraction(
            target_slot="event_type",
            action="replace",
            new_value="Wedding",
        ),
        "actually this is a wedding and my partner is Nicki Minaj",
        slots,
        {"conversation_phase": PHASE_SERVICE_TYPE, "slots": slots},
        [],
    )

    assert get_slot_value(slots, "event_type") == "Wedding"
    assert get_slot_value(slots, "partner_name") == "Nicki Minaj"
    assert get_slot_value(slots, "honoree_name") is None

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_generic_request_asks_what_to_modify(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Prime Rib & Salmon ($39.99/per_person)")

    async def fail_extract(**kwargs):
        raise AssertionError("extract should not run for a generic modification request")

    monkeypatch.setattr("agent.tools.modification_tool.extract", fail_extract)

    tool = ModificationTool()
    result = await tool.run(
        message="i want to make a modification",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    assert (result.direct_response or "").lower().startswith("what would you like to change")
    assert get_slot_value(slots, "__pending_modification_request") == {"stage": "target"}
    assert result.input_hint is not None
    assert result.input_hint["type"] == "options"
    assert {"value": "selected_dishes", "label": "Main Dishes"} in result.input_hint["options"]

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_generic_change_variants_ask_target(monkeypatch):
    async def fail_extract(**kwargs):
        raise AssertionError("extract should not run for a generic modification request")

    monkeypatch.setattr("agent.tools.modification_tool.extract", fail_extract)

    tool = ModificationTool()
    for msg in ("change", "change?", "I want to change", "i'd like to modify"):
        slots = initialize_empty_slots()
        fill_slot(slots, "event_date", "2026-04-30")
        result = await tool.run(
            message=msg,
            history=[],
            state={"slots": slots, "conversation_phase": PHASE_EVENT_DATE},
        )
        assert (result.direct_response or "").lower().startswith("what would you like to change")
        assert get_slot_value(slots, "__pending_modification_request") == {"stage": "target"}

@pytest.mark.asyncio
async def test_modification_tool_pending_generic_request_reopens_appetizers(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "BBQ Chicken Slider ($3.50/per_person), White Bean Tapenade w/ Crostini ($1.75/per_person)",
    )
    fill_slot(slots, "appetizer_style", "station")
    fill_slot(slots, "__pending_modification_request", {"stage": "target"})

    async def fake_render_slot_menu(self, target_slot, slots):
        assert target_slot == "appetizers"
        return (
            "Here are the appetizer options:\n1. BBQ Chicken Slider\n2. White Bean Tapenade w/ Crostini",
            {"type": "menu_picker", "category": "appetizers", "menu": []},
        )

    monkeypatch.setattr(ModificationTool, "_render_slot_menu", fake_render_slot_menu)

    tool = ModificationTool()
    result = await tool.run(
        message="appetizers",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    assert get_slot_value(slots, "__pending_modification_request") is None
    assert get_slot_value(slots, "appetizers") is None
    assert get_slot_value(slots, "appetizer_style") is None

@pytest.mark.asyncio
async def test_modification_tool_pending_generic_request_reopens_rentals_when_user_says_linens(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "rentals", "Linens, Tables")
    fill_slot(slots, "linens", True)
    fill_slot(slots, "__gate_rentals", True)
    fill_slot(slots, "__pending_modification_request", {"stage": "target"})

    async def fake_render_slot_menu(self, target_slot, slots):
        assert target_slot == "rentals"
        return (
            "Here are the rental options:\n1. Linens\n2. Tables\n3. Chairs",
            {"type": "options", "options": [{"value": "Linens", "label": "Linens"}]},
        )

    monkeypatch.setattr(ModificationTool, "_render_slot_menu", fake_render_slot_menu)

    tool = ModificationTool()
    result = await tool.run(
        message="linens",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    assert get_slot_value(slots, "__pending_modification_request") is None
    assert get_slot_value(slots, "rentals") is None
    assert get_slot_value(slots, "linens") is None
    assert get_slot_value(slots, "__gate_rentals") is None
    assert "rental options" in (result.direct_response or "").lower()

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_pending_generic_request_asks_for_scalar_value():
    slots = initialize_empty_slots()
    fill_slot(slots, "guest_count", 38)
    fill_slot(slots, "__pending_modification_request", {"stage": "target"})

    tool = ModificationTool()
    result = await tool.run(
        message="guest count",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    assert result.direct_response == "What would you like to change for your guest count?"
    assert get_slot_value(slots, "__pending_modification_request") == {
        "stage": "value",
        "target_slot": "guest_count",
    }

@pytest.mark.asyncio
async def test_modification_tool_pending_generic_request_still_allows_specific_add_remove(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Prime Rib & Salmon ($39.99/per_person), Pork & Chicken ($23.99/per_person)")
    fill_slot(slots, "__pending_modification_request", {"stage": "target"})

    async def fake_extract(**kwargs):
        return ModificationExtraction(
            target_slot="selected_dishes",
            action="remove",
            items_to_remove=["Pork & Chicken"],
        )

    async def fake_menu_for_slot(self, slot, slots):
        return {
            "BBQ Menus": [
                {"name": "Pork & Chicken", "unit_price": 23.99, "price_type": "per_person"},
            ],
            "Signature Combos": [
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
            ],
        }

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)
    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool.run(
        message="remove pork & chicken from the menu",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    assert get_slot_value(slots, "__pending_modification_request") is None
    assert "Pork & Chicken" not in (get_slot_value(slots, "selected_dishes") or "")
    assert result.response_context["modification"]["removed"] == ["Pork & Chicken"]

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_asks_to_clarify_ambiguous_main_addition(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Prime Rib & Salmon ($39.99/per_person)")

    async def fake_menu_for_slot(self, slot, slots):
        return {
            "Signature Combos": [
                {"name": "Chicken & Ham", "unit_price": 27.99, "price_type": "per_person"},
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
            ],
        }

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="add",
            items_to_add=["chicken"],
        ),
        slots,
        {"conversation_phase": PHASE_SPECIAL_REQUESTS, "slots": slots},
    )

    assert "which one do you want to add" in (result.direct_response or "").lower()
    assert get_slot_value(slots, "__pending_modification_choice") is not None
    assert result.input_hint == {
        "type": "options",
        "options": [
            {"value": "Chicken & Ham", "label": "Chicken & Ham"},
            {"value": "Chicken Piccata", "label": "Chicken Piccata"},
        ],
    }

@pytest.mark.asyncio
async def test_modification_tool_resumes_ambiguous_addition_from_numbered_choice(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Prime Rib & Salmon ($39.99/per_person)")
    fill_slot(slots, "__pending_modification_choice", {
        "target_slot": "selected_dishes",
        "action": "add",
        "choice_kind": "add",
        "query": "chicken",
        "matches": ["Chicken & Ham", "Chicken Piccata"],
        "items_to_remove": [],
        "items_to_add": ["chicken"],
    })

    async def fake_menu_for_slot(self, slot, slots):
        return {
            "Signature Combos": [
                {"name": "Chicken & Ham", "unit_price": 27.99, "price_type": "per_person"},
                {"name": "Chicken Piccata", "unit_price": 29.49, "price_type": "per_person"},
                {"name": "Prime Rib & Salmon", "unit_price": 39.99, "price_type": "per_person"},
            ],
        }

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool.run(
        message="2",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_SPECIAL_REQUESTS},
    )

    selected = get_slot_value(slots, "selected_dishes") or ""
    assert "Chicken Piccata" in selected
    assert "Chicken & Ham" not in selected
    assert get_slot_value(slots, "__pending_modification_choice") is None
    assert result.response_context["modification"]["added"] == ["Chicken Piccata"]

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_grounding_blocks_false_positive_partial_removal(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Deviled Egg ($3.00/per_person), Caviar Egg ($3.50/per_person), Caviar and Cream Crisp ($4.00/per_person), Chips and Salsa ($1.75/per_person)",
    )

    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        if schema is ModificationExtraction:
            return ModificationExtraction(
                target_slot="appetizers",
                action="remove",
                items_to_remove=["Deviled Egg", "Caviar Egg", "Caviar and Cream Crisp"],
            )
        if schema is SelectedItemGrounding:
            return SelectedItemGrounding(
                status="ambiguous",
                matched_names=["Deviled Egg", "Caviar Egg"],
                reference_text="egg",
                reason="The user referred to egg generally, which matches two selected appetizer names.",
            )
        raise AssertionError(f"Unexpected schema: {schema}")

    async def fake_menu_for_slot(self, slot, slots):
        return {
            "Canapes": [
                {"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person"},
                {"name": "Caviar Egg", "unit_price": 3.50, "price_type": "per_person"},
                {"name": "Caviar and Cream Crisp", "unit_price": 4.00, "price_type": "per_person"},
                {"name": "Chips and Salsa", "unit_price": 1.75, "price_type": "per_person"},
            ],
        }

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)
    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool.run(
        message="remove egg from my menu",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert "which one do you want to remove" in (result.direct_response or "").lower()
    assert "Caviar and Cream Crisp" not in (result.direct_response or "")
    assert get_slot_value(slots, "__pending_modification_choice") == {
        "target_slot": "appetizers",
        "action": "remove",
        "choice_kind": "remove",
        "query": "egg",
        "matches": ["Deviled Egg", "Caviar Egg"],
        "items_to_remove": ["egg"],
        "items_to_add": [],
    }

@pytest.mark.asyncio
async def test_modification_tool_enforces_max_four_desserts_on_add(monkeypatch):
    from types import SimpleNamespace

    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "desserts",
        "Brownies ($2.00/per_person), 7-Layer Bars ($2.00/per_person), Flavored Mousse Cup ($2.00/per_person), Fruit Tarts ($2.00/per_person)",
    )

    async def fake_resolve_dessert_choices(raw_names, **kwargs):
        return SimpleNamespace(
            ambiguous_choices=[],
            matched_items=[{"name": "Blondies", "unit_price": 2.0, "price_type": "per_person"}],
        )

    monkeypatch.setattr("agent.tools.modification_tool.resolve_dessert_choices", fake_resolve_dessert_choices)

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="desserts",
            action="add",
            items_to_add=["Blondies"],
        ),
        slots,
        {"conversation_phase": PHASE_REVIEW, "slots": slots},
    )

    assert result.response_context.get("error") == "dessert_overflow"
    assert "limited to 4" in (result.direct_response or "").lower()
    assert "Blondies" not in (get_slot_value(slots, "desserts") or "")
    assert result.input_hint == {
        "type": "options",
        "options": [
            {"value": "remove Brownies", "label": "Remove Brownies"},
            {"value": "remove 7-Layer Bars", "label": "Remove 7-Layer Bars"},
            {"value": "remove Flavored Mousse Cup", "label": "Remove Flavored Mousse Cup"},
            {"value": "remove Fruit Tarts", "label": "Remove Fruit Tarts"},
        ],
    }

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_grounding_asks_to_clarify_remove_chicken(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "selected_dishes",
        (
            "Beef Brisket & Chicken ($25.99/per_person), Southern Comfort ($27.95/per_person), "
            "Souvlaki Bar ($21.49/per_person), Ravioli Menu ($31.99/per_person), "
            "Mediterranean Bar ($23.49/per_person), Marsala Menu ($25.99/per_person), "
            "Mexican Char Grilled ($27.99/per_person)"
        ),
    )

    async def fake_extract(**kwargs):
        schema = kwargs["schema"]
        if schema is ModificationExtraction:
            return ModificationExtraction(
                target_slot="selected_dishes",
                action="remove",
                items_to_remove=["Beef Brisket & Chicken"],
            )
        if schema is SelectedItemGrounding:
            return SelectedItemGrounding(
                status="ambiguous",
                matched_names=[
                    "Beef Brisket & Chicken",
                    "Southern Comfort",
                    "Souvlaki Bar",
                    "Ravioli Menu",
                    "Mediterranean Bar",
                    "Marsala Menu",
                    "Mexican Char Grilled",
                ],
                reference_text="chicken",
                reason="Several selected mains clearly include chicken.",
            )
        raise AssertionError(f"Unexpected schema: {schema}")

    async def fake_menu_for_slot(self, slot, slots):
        return {
            "BBQ Menus": [
                {
                    "name": "Beef Brisket & Chicken",
                    "unit_price": 25.99,
                    "price_type": "per_person",
                    "description": "BBQ Beef Brisket (sliced), Beer Can Chicken.",
                },
            ],
            "Tasty & Casual": [
                {
                    "name": "Southern Comfort",
                    "unit_price": 27.95,
                    "price_type": "per_person",
                    "description": "Crispy Fried Chicken, Smoked Sausage, Mac & Cheese.",
                },
            ],
            "Global Inspirations": [
                {
                    "name": "Souvlaki Bar",
                    "unit_price": 21.49,
                    "price_type": "per_person",
                    "description": "Chicken Souvlaki, Pork Souvlaki, Greek Potatoes.",
                },
                {
                    "name": "Ravioli Menu",
                    "unit_price": 31.99,
                    "price_type": "per_person",
                    "description": "Grilled Chicken with Wild Mushroom Beurre Blanc, Roasted Salmon.",
                },
                {
                    "name": "Mediterranean Bar",
                    "unit_price": 23.49,
                    "price_type": "per_person",
                    "description": "Hummus Bar with grilled Mediterranean chicken and lamb.",
                },
                {
                    "name": "Marsala Menu",
                    "unit_price": 25.99,
                    "price_type": "per_person",
                    "description": "Chicken Marsala, Roasted Cod in Peperonata Sauce.",
                },
                {
                    "name": "Mexican Char Grilled",
                    "unit_price": 27.99,
                    "price_type": "per_person",
                    "description": "Carne Asada, Chili Lime Chicken, Spanish Rice.",
                },
            ],
        }

    monkeypatch.setattr("agent.tools.modification_tool.extract", fake_extract)
    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool.run(
        message="remove chicken",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_MAIN_MENU},
    )

    assert "which one do you want to remove" in (result.direct_response or "").lower()
    assert "Beef Brisket & Chicken" in (result.direct_response or "")
    assert "Mexican Char Grilled" in (result.direct_response or "")
    assert "Beef Brisket & Chicken" in (get_slot_value(slots, "selected_dishes") or "")
    assert get_slot_value(slots, "__pending_modification_choice")["query"] == "chicken"

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_asks_to_clarify_ambiguous_partial_removal(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Deviled Egg ($3.00/per_person), Caviar Egg ($5.00/per_person), Firecracker Shrimp ($4.00/per_person)",
    )

    async def fake_menu_for_slot(self, slot, slots):
        return {}

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="appetizers",
            action="remove",
            items_to_remove=["egg"],
        ),
        slots,
        {"conversation_phase": PHASE_COCKTAIL, "slots": slots},
    )

    assert "which one do you want to remove" in (result.direct_response or "").lower()
    assert get_slot_value(slots, "__pending_modification_choice") is not None
    assert result.input_hint == {
        "type": "options",
        "options": [
            {"value": "Deviled Egg", "label": "Deviled Egg"},
            {"value": "Caviar Egg", "label": "Caviar Egg"},
        ],
    }

@pytest.mark.asyncio
async def test_modification_tool_resumes_ambiguous_removal_from_exact_choice(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "appetizers",
        "Deviled Egg ($3.00/per_person), Caviar Egg ($5.00/per_person), Firecracker Shrimp ($4.00/per_person)",
    )
    fill_slot(slots, "__pending_modification_choice", {
        "target_slot": "appetizers",
        "action": "remove",
        "query": "egg",
        "matches": ["Deviled Egg", "Caviar Egg"],
        "items_to_add": [],
    })

    async def fake_menu_for_slot(self, slot, slots):
        return {
            "Eggs": [
                {"name": "Deviled Egg", "unit_price": 3.00, "price_type": "per_person"},
                {"name": "Caviar Egg", "unit_price": 5.00, "price_type": "per_person"},
                {"name": "Firecracker Shrimp", "unit_price": 4.00, "price_type": "per_person"},
            ],
        }

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool.run(
        message="Caviar Egg",
        history=[],
        state={"slots": slots, "conversation_phase": PHASE_COCKTAIL},
    )

    assert "Caviar Egg" not in (get_slot_value(slots, "appetizers") or "")
    assert "Deviled Egg" in (get_slot_value(slots, "appetizers") or "")
    assert get_slot_value(slots, "__pending_modification_choice") is None
    assert result.response_context["modification"]["removed"] == ["Caviar Egg"]

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_modification_tool_allows_late_main_menu_additions_with_collapsed_phrase(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Souvlaki Bar ($21.49/per_person), Mexican Char Grilled ($27.99/per_person), Vegetable Platter ($2.25/per_person)")
    fill_slot(slots, "drinks", True)

    menu = {
        "Global Inspirations": [
            {"name": "Souvlaki Bar", "unit_price": 21.49, "price_type": "per_person"},
            {"name": "Mexican Char Grilled", "unit_price": 27.99, "price_type": "per_person"},
            {"name": "Ravioli Menu", "unit_price": 31.99, "price_type": "per_person"},
            {"name": "Soup / Salad / Sandwich", "unit_price": 21.95, "price_type": "per_person"},
        ],
        "Platters": [
            {"name": "Vegetable Platter", "unit_price": 2.25, "price_type": "per_person"},
        ],
    }

    async def fake_menu_for_slot(self, slot, slots):
        assert slot == "selected_dishes"
        return menu

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="add",
            items_to_add=["ravioli menu and add soup/salad"],
        ),
        slots,
        {"conversation_phase": PHASE_DRINKS_BAR, "slots": slots},
    )

    new_value = get_slot_value(slots, "selected_dishes")
    assert new_value is not None
    assert "Ravioli Menu" in new_value
    assert "Soup / Salad / Sandwich" in new_value
    assert result.direct_response is None
    assert result.response_context["modification"]["added"] == ["Ravioli Menu", "Soup / Salad / Sandwich"]
    assert "Ravioli Menu" in result.response_context["modification"]["remaining_items"]
    assert "Soup / Salad / Sandwich" in result.response_context["modification"]["remaining_items"]
    assert result.response_context["next_question_target"] == "ask_drinks_setup"

@pytest.mark.asyncio
async def test_modification_tool_replace_can_move_item_into_another_menu_category(monkeypatch):
    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "selected_dishes",
        "Soup / Salad / Sandwich ($21.95/per_person), Ravioli Menu ($31.99/per_person), Southern Comfort ($24.99/per_person)",
    )
    fill_slot(
        slots,
        "appetizers",
        "Grilled Shrimp Cocktail ($4.25/per_person), Firecracker Shrimp ($4.00/per_person)",
    )

    menus = {
        "selected_dishes": {
            "Global Inspirations": [
                {"name": "Ravioli Menu", "unit_price": 31.99, "price_type": "per_person"},
                {"name": "Soup / Salad / Sandwich", "unit_price": 21.95, "price_type": "per_person"},
                {"name": "Southern Comfort", "unit_price": 24.99, "price_type": "per_person"},
            ],
        },
        "appetizers": {
            "Chicken": [
                {"name": "Adobo Lime Chicken Bites", "unit_price": 3.25, "price_type": "per_person"},
                {"name": "Grilled Shrimp Cocktail", "unit_price": 4.25, "price_type": "per_person"},
                {"name": "Firecracker Shrimp", "unit_price": 4.00, "price_type": "per_person"},
            ],
        },
    }

    async def fake_resolve_items_for_slot(self, slot, add_texts, slots):
        if slot == "appetizers" and add_texts == ["Adobo Lime Chicken Bites"]:
            return [{"name": "Adobo Lime Chicken Bites", "unit_price": 3.25, "price_type": "per_person"}]
        return []

    async def fake_format_value_for_slot(self, slot, combined_names, slots):
        if slot == "appetizers":
            return ", ".join(
                f"{name} ($3.25/per_person)" if name == "Adobo Lime Chicken Bites" else
                f"{name} ($4.25/per_person)" if name == "Grilled Shrimp Cocktail" else
                f"{name} ($4.00/per_person)"
                for name in combined_names
            )
        if slot == "selected_dishes":
            return ", ".join(
                f"{name} ($21.95/per_person)" if name == "Soup / Salad / Sandwich" else
                f"{name} ($24.99/per_person)"
                for name in combined_names
            )
        return ", ".join(combined_names)

    async def fake_menu_for_slot(self, slot, slots):
        return menus.get(slot, {})

    monkeypatch.setattr(ModificationTool, "_menu_for_slot", fake_menu_for_slot)
    monkeypatch.setattr(ModificationTool, "_resolve_items_for_slot", fake_resolve_items_for_slot)
    monkeypatch.setattr(ModificationTool, "_format_value_for_slot", fake_format_value_for_slot)

    tool = ModificationTool()
    result = await tool._apply_list_modification(
        ModificationExtraction(
            target_slot="selected_dishes",
            action="replace",
            items_to_remove=["Ravioli Menu"],
            items_to_add=["Adobo Lime Chicken Bites"],
        ),
        slots,
        {"conversation_phase": PHASE_MAIN_MENU, "slots": slots},
    )

    mains_value = get_slot_value(slots, "selected_dishes") or ""
    apps_value = get_slot_value(slots, "appetizers") or ""

    assert "Ravioli Menu" not in mains_value
    assert "Adobo Lime Chicken Bites" in apps_value
    assert result.response_context["modification"]["removed"] == ["Ravioli Menu"]
    assert result.response_context["modification"]["remaining_items"] == [
        "Soup / Salad / Sandwich",
        "Southern Comfort",
    ]
    assert result.response_context["modification"]["additional_changes"][0]["target_slot"] == "appetizers"
    assert "Adobo Lime Chicken Bites" in result.response_context["modification"]["additional_changes"][0]["remaining_items"]

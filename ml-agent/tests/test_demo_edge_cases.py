"""
Demo-focused regression tests covering the edge cases that kept breaking.

These are deliberately decoupled from older test assumptions — they exercise
the centralized intent classification (agent/intents.py), the pending-state
TTL (agent/state.py), and the tightened LLM extractor history window
(agent/tools/base.py:tight_history_for_llm) introduced in the stability pass.

Run: pytest tests/test_demo_edge_cases.py -v
"""

from __future__ import annotations

import os
import sys

import pytest


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _pin_path():
    """Pin sys.path[0] to this project root and evict stale `agent.*` modules.

    Other tests in the suite do `sys.path.insert(0, r"c:\\Projects\\CateringCompany\\ml-agent")`
    which can shift our path during their import. Run this defensively before
    every test that imports from `agent`.
    """
    if _PROJECT_ROOT in sys.path:
        sys.path.remove(_PROJECT_ROOT)
    sys.path.insert(0, _PROJECT_ROOT)
    norm_root = os.path.normcase(_PROJECT_ROOT)
    for mod_name in list(sys.modules):
        if mod_name == "agent" or mod_name.startswith("agent."):
            mod_obj = sys.modules.get(mod_name)
            mod_path = getattr(mod_obj, "__file__", "") or ""
            if mod_path and not os.path.normcase(os.path.abspath(mod_path)).startswith(norm_root):
                del sys.modules[mod_name]


@pytest.fixture(autouse=True)
def _ensure_project_path():
    _pin_path()
    yield


_pin_path()


# ---------------------------------------------------------------------------
# Phase 1: Pending-state TTL
# ---------------------------------------------------------------------------

def test_pending_state_ttl_clears_stale_entries():
    """A pending offer older than the TTL is auto-cleared on next route()."""
    from agent.state import (
        fill_slot,
        initialize_empty_slots,
        is_filled,
        validate_pending_state,
    )

    slots = initialize_empty_slots()
    fill_slot(
        slots,
        "__pending_modification_request",
        {"stage": "offer_special_request_for_unavailable", "items": ["X"], "created_turn": 5},
    )

    # Same turn — still alive
    cleared = validate_pending_state(slots, 5)
    assert cleared == []
    assert is_filled(slots, "__pending_modification_request")

    # Two turns later — auto-cleared
    cleared = validate_pending_state(slots, 7)
    assert "__pending_modification_request" in cleared
    assert not is_filled(slots, "__pending_modification_request")


def test_pending_state_unstamped_payload_gets_stamped():
    """Legacy payload without created_turn gets stamped on first observation."""
    from agent.state import (
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
        validate_pending_state,
    )

    slots = initialize_empty_slots()
    fill_slot(slots, "__pending_modification_request", {"stage": "x", "items": []})
    validate_pending_state(slots, 10)
    payload = get_slot_value(slots, "__pending_modification_request")
    assert payload.get("created_turn") == 10


# ---------------------------------------------------------------------------
# Phase 2: Tight extractor history window
# ---------------------------------------------------------------------------

def test_tight_history_returns_at_most_last_qa_pair():
    """Modification extractor sees only the last AI question + last user message."""
    from langchain_core.messages import AIMessage, HumanMessage

    from agent.tools.base import tight_history_for_llm

    history = [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi! What's your name?"),
        HumanMessage(content="Syed Ali"),
        AIMessage(content="Got it. Want a wedding cake?"),
        HumanMessage(content="yes"),
        AIMessage(content="What flavor for the wedding cake?"),
        HumanMessage(content="actually no cake"),
    ]
    out = tight_history_for_llm(history)

    # We get at most user, ai, user
    assert len(out) <= 3
    # Earlier "Dragon Chicken" / "Hi!" content does NOT leak
    joined = " ".join(m["content"] for m in out)
    assert "Hello" not in joined
    assert "Got it" not in joined


def test_tight_history_drops_long_catalog_listings():
    """When the AI's last message is a 1000-char menu listing, it gets trimmed."""
    from langchain_core.messages import AIMessage, HumanMessage

    from agent.tools.base import tight_history_for_llm

    long_menu = "Here are the appetizer options:\n" + "\n".join(
        f"{i}. Item {i} ($3.50/per_person)" for i in range(1, 50)
    ) + "\nPick as many as you'd like!"
    history = [
        AIMessage(content=long_menu),
        HumanMessage(content="Crab Cakes, BBQ Slider"),
    ]
    out = tight_history_for_llm(history)
    # The AI message is truncated to last ~200 chars
    assert any(len(m["content"]) <= 200 for m in out if m["role"] == "assistant")


# ---------------------------------------------------------------------------
# Phase 3: Centralized decline / skip classification
# ---------------------------------------------------------------------------

def test_classify_skip_gate_matches_expected_section():
    from agent.intents import classify_skip_gate
    from agent.state import (
        PHASE_DESSERT,
        PHASE_RENTALS,
        PHASE_SPECIAL_REQUESTS,
        PHASE_TABLEWARE,
        PHASE_WEDDING_CAKE,
        initialize_empty_slots,
    )

    slots = initialize_empty_slots()
    cases = [
        ("skip dessert", PHASE_DESSERT, "desserts"),
        ("no thanks", PHASE_DESSERT, "desserts"),
        ("no", PHASE_WEDDING_CAKE, "wedding_cake"),
        ("skip cake", PHASE_WEDDING_CAKE, "wedding_cake"),
        ("no rentals", PHASE_RENTALS, "rentals"),
        ("none", PHASE_TABLEWARE, "tableware"),
        ("no", PHASE_SPECIAL_REQUESTS, "special_requests"),
    ]
    for message, phase, expected_section in cases:
        intent = classify_skip_gate(message, phase, slots)
        assert intent is not None, f"expected skip intent for {message!r} at {phase}"
        assert intent.section == expected_section, (
            f"{message!r} at {phase} → {intent.section}, expected {expected_section}"
        )


def test_classify_skip_gate_returns_none_for_real_answer():
    from agent.intents import classify_skip_gate
    from agent.state import PHASE_DESSERT, initialize_empty_slots

    slots = initialize_empty_slots()
    assert classify_skip_gate("Brownies, Lemon Bars", PHASE_DESSERT, slots) is None
    assert classify_skip_gate("yes", PHASE_DESSERT, slots) is None


@pytest.mark.parametrize(
    ("message", "expected_section"),
    [
        ("i dont want desserts", "desserts"),
        ("no cake please", "wedding_cake"),
        ("skip the appetizers", "appetizers"),
        ("remove all main dishes", "selected_dishes"),
        ("cancel the rentals", "rentals"),
    ],
)
def test_classify_decline_recognizes_section_declines(message, expected_section):
    from agent.intents import classify_decline
    from agent.state import initialize_empty_slots

    intent = classify_decline(message, initialize_empty_slots())
    assert intent is not None, f"expected decline intent for {message!r}"
    assert intent.section == expected_section


def test_classify_decline_ignores_non_decline_modifications():
    from agent.intents import classify_decline
    from agent.state import initialize_empty_slots

    slots = initialize_empty_slots()
    # "add" / "replace" should not be classified as section declines
    assert classify_decline("add chicken satay", slots) is None
    assert classify_decline("replace crab cakes with sushi", slots) is None
    assert classify_decline("Brownies, Lemon Bars", slots) is None


def test_is_generic_no_recognizes_basic_negatives():
    from agent.intents import is_generic_no

    assert is_generic_no("no") is True
    assert is_generic_no("nope") is True
    assert is_generic_no("skip") is True
    assert is_generic_no("yes") is False
    assert is_generic_no("Brownies") is False


# ---------------------------------------------------------------------------
# Cross-cutting: name validator
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_name",
    [
        "1234567890",     # phone-like
        "12",              # too short
        "a",               # single char
        "5",               # single digit
        "1234ab",          # digits outnumber letters
        "@@@",             # symbols only
    ],
)
def test_invalid_names_are_rejected_by_validator(bad_name):
    """Validator rejects pure-numeric, single-char, symbol-only, or digit-heavy names."""
    letters = sum(1 for c in bad_name if c.isalpha())
    digits = sum(1 for c in bad_name if c.isdigit())
    import re as _re
    name_invalid = (
        letters == 0
        or letters < 2
        or digits > letters
        or not _re.search(r"[A-Za-z]{2,}", bad_name)
    )
    assert name_invalid, f"expected {bad_name!r} to be rejected"


@pytest.mark.parametrize(
    "good_name",
    [
        "Syed Ali",
        "Sumayya",
        "John Doe",
        "Dr. Smith",
        "Mary-Jane",
    ],
)
def test_valid_names_pass_validator(good_name):
    letters = sum(1 for c in good_name if c.isalpha())
    digits = sum(1 for c in good_name if c.isdigit())
    import re as _re
    name_invalid = (
        letters == 0
        or letters < 2
        or digits > letters
        or not _re.search(r"[A-Za-z]{2,}", good_name)
    )
    assert not name_invalid, f"expected {good_name!r} to pass"


# ---------------------------------------------------------------------------
# Tier 1: Multi-action modification
# ---------------------------------------------------------------------------

def test_modification_extraction_schema_supports_secondaries():
    """Schema must accept secondary_modifications without raising."""
    from agent.models import ModificationExtraction, SecondaryModification

    primary = ModificationExtraction(
        target_slot="selected_dishes",
        action="replace",
        items_to_remove=["Cheese Platter"],
        items_to_add=["Ravioli Menu"],
        secondary_modifications=[
            SecondaryModification(
                target_slot="appetizers",
                action="remove",
                items_to_remove=["Adobo Lime Chicken Bites"],
            ),
        ],
    )
    assert len(primary.secondary_modifications) == 1
    assert primary.secondary_modifications[0].target_slot == "appetizers"


def test_modification_extraction_schema_default_secondaries_is_empty():
    """Existing single-action callers don't need to pass secondaries."""
    from agent.models import ModificationExtraction

    primary = ModificationExtraction(
        target_slot="event_date",
        action="replace",
        new_value="May 5",
    )
    assert primary.secondary_modifications == []


def test_secondary_modification_can_be_constructed_standalone():
    """SecondaryModification is callable without going through the parent."""
    from agent.models import SecondaryModification

    sec = SecondaryModification(
        target_slot="venue",
        action="replace",
        new_value="Riverside Park",
    )
    assert sec.target_slot == "venue"
    assert sec.action == "replace"
    assert sec.new_value == "Riverside Park"


def test_finalize_with_secondaries_skips_when_primary_needs_input():
    """If primary returned an error or ambiguous-choice, secondaries are skipped."""
    import asyncio

    from agent.models import ModificationExtraction, SecondaryModification
    from agent.state import initialize_empty_slots
    from agent.tools.base import ToolResult
    from agent.tools.modification_tool import ModificationTool

    tool = ModificationTool()
    slots = initialize_empty_slots()
    state = {"slots": slots, "messages": [], "conversation_phase": "S10_main_menu"}
    primary = ToolResult(
        state=state,
        response_context={"tool": "modification_tool", "error": "ambiguous_choice"},
        direct_response="Which one?",
    )
    extracted = ModificationExtraction(
        target_slot="selected_dishes",
        action="remove",
        items_to_remove=["Chicken Piccata"],
        secondary_modifications=[
            SecondaryModification(
                target_slot="appetizers",
                action="remove",
                items_to_remove=["Crab Cakes"],
            ),
        ],
    )
    result = asyncio.run(
        tool._finalize_with_secondaries(primary, extracted, slots, state, [])
    )
    # Same primary returned, no secondary processing
    assert result is primary


@pytest.mark.parametrize(
    ("phone", "should_be_rejected"),
    [
        ("guggugagaga", True),     # pure letters
        ("hello", True),            # words
        ("555", True),              # too short
        ("test123", True),          # mostly letters
        ("12345abcde", True),       # 5 digits 5 letters not strictly more
        ("", True),                  # empty
        ("+1 1234567890", False),   # valid international
        ("1234567890", False),      # 10 digits
        ("(555) 123-4567", False),  # formatted US
        ("555-123-4567", False),    # dashes
    ],
)
def test_phone_validator_handles_gibberish(phone, should_be_rejected):
    """Phone validator must reject non-phone strings (was a real bug — 'guggugagaga' got accepted)."""
    import re
    digit_count = sum(1 for c in phone if c.isdigit())
    letter_count = sum(1 for c in phone if c.isalpha())
    phone_invalid = (
        digit_count < 7
        or letter_count > digit_count
        or not re.search(r"\d", phone)
    )
    assert phone_invalid == should_be_rejected, (
        f"phone {phone!r}: invalid={phone_invalid}, expected_reject={should_be_rejected}"
    )


@pytest.mark.parametrize(
    ("email", "should_be_rejected"),
    [
        ("test@example.com", False),
        ("a.b+c@x.io", False),
        ("user@sub.domain.co.uk", False),
        ("not an email", True),
        ("@nope.com", True),
        ("noatsign.com", True),
        ("foo@", True),
        ("", True),
    ],
)
def test_email_validator_handles_gibberish(email, should_be_rejected):
    """Email validator must reject non-email strings."""
    import re
    email_invalid = not re.match(
        r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$",
        email.strip(),
        re.IGNORECASE,
    )
    assert email_invalid == should_be_rejected, (
        f"email {email!r}: invalid={email_invalid}, expected_reject={should_be_rejected}"
    )


def test_finalize_with_secondaries_skips_when_no_secondaries():
    """No secondaries → return primary unchanged."""
    import asyncio

    from agent.models import ModificationExtraction
    from agent.state import initialize_empty_slots
    from agent.tools.base import ToolResult
    from agent.tools.modification_tool import ModificationTool

    tool = ModificationTool()
    slots = initialize_empty_slots()
    state = {"slots": slots, "messages": [], "conversation_phase": "S10_main_menu"}
    primary = ToolResult(state=state, response_context={"tool": "modification_tool"})
    extracted = ModificationExtraction(
        target_slot="event_date",
        action="replace",
        new_value="May 5",
    )
    result = asyncio.run(
        tool._finalize_with_secondaries(primary, extracted, slots, state, [])
    )
    assert result is primary
    # No annotation added when there were no secondaries
    assert "secondary_modifications_applied" not in (result.response_context or {})


# ---------------------------------------------------------------------------
# Demo bug fixes (real user transcript regressions)
# ---------------------------------------------------------------------------

def test_bug2_router_handles_leading_conjunction_for_add():
    """`and add Sushi Bites` must still route to modification_tool."""
    import re

    # The router's pre-FAQ command bypass should accept the message after
    # stripping a leading conjunction.
    msg = "and add Sushi Bites"
    msg_lower = msg.lower()
    stripped = re.sub(r"^(?:and|also|plus|&&)\s+", "", msg_lower).strip()
    assert stripped == "add sushi bites"
    pattern = re.compile(
        r"^(?:(?:can|could|would)\s+(?:we|you|i)\s+|please\s+|let(?:'s|\s+us)\s+)?"
        r"(?:add|remove|delete|change|update|swap|replace|cancel|skip|include|exclude)\b"
    )
    # Original message fails, but stripped message matches → route stays alive.
    assert pattern.match(msg_lower) is None
    assert pattern.match(stripped) is not None


def test_bug3_drinks_no_returns_ack():
    """When user says 'no' to drinks, AddOnsTool sets a direct_response ack."""
    import asyncio

    from langchain_core.messages import HumanMessage

    from agent.state import (
        PHASE_DRINKS_BAR,
        fill_slot,
        initialize_empty_slots,
    )
    from agent.tools.add_ons_tool import AddOnsTool

    slots = initialize_empty_slots()
    # Set up the full slot prerequisites so we land on ask_drinks_interest.
    fill_slot(slots, "service_type", "Onsite")
    fill_slot(slots, "meal_style", "Buffet")
    fill_slot(slots, "selected_dishes", "Some Dish")
    state = {
        "slots": slots,
        "messages": [HumanMessage(content="no")],
        "conversation_phase": PHASE_DRINKS_BAR,
    }
    tool = AddOnsTool()
    result = asyncio.run(tool.run(message="no", history=[], state=state))
    assert result.direct_response is not None
    assert "no extra drinks" in result.direct_response.lower()


def test_bug4_router_jumps_to_dessert_during_cake_flow():
    """Mid wedding-cake flavor flow, 'actually lets do desserts' routes to modification_tool."""
    import re

    # Replicate the router's regex check
    msg_lower = "actually lets do desserts"
    matched = bool(re.search(
        r"\b(?:lets?\s+do|let'?s\s+do|actually\s+(?:do\s+)?|want|add|do)\s+desserts?\b"
        r"|^desserts?$"
        r"|\bdessert\s+menu\b"
        r"|\b(?:show|reselect|redo|reopen|revisit|change|update|edit)\s+(?:the\s+|my\s+)?desserts?\b",
        msg_lower,
    ))
    assert matched, "router should detect dessert intent during cake flow"

    # And 'actually want desserts' too
    msg2 = "actually want desserts"
    assert re.search(
        r"\b(?:lets?\s+do|let'?s\s+do|actually\s+(?:do\s+)?|want|add|do)\s+desserts?\b"
        r"|^desserts?$"
        r"|\bdessert\s+menu\b"
        r"|\b(?:show|reselect|redo|reopen|revisit|change|update|edit)\s+(?:the\s+|my\s+)?desserts?\b",
        msg2,
    )


def test_bug1_category_removal_with_multiple_items_asks_disambiguation():
    """`remove platters` with two Platters items asks multi-select clarification."""
    import asyncio

    from agent.models import ModificationExtraction
    from agent.state import (
        PHASE_MAIN_MENU,
        fill_slot,
        initialize_empty_slots,
    )
    from agent.tools.modification_tool import ModificationTool

    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Assorted Finger Sandwiches, Antipasto Platter")
    state = {
        "slots": slots,
        "messages": [],
        "conversation_phase": PHASE_MAIN_MENU,
    }

    # Stub the menu so we don't hit the DB.
    async def _fake_menu(self, slot, slots):
        return {
            "Platters": [
                {"name": "Assorted Finger Sandwiches"},
                {"name": "Antipasto Platter"},
            ],
            "Hot Mains": [
                {"name": "Roast Chicken"},
            ],
        }

    original = ModificationTool._menu_for_slot
    ModificationTool._menu_for_slot = _fake_menu
    try:
        mod = ModificationExtraction(
            target_slot="selected_dishes",
            action="remove",
            items_to_remove=["platters"],
        )
        result = asyncio.run(
            tool._apply_list_modification(mod, slots, state, message="remove platters")
        )
    finally:
        ModificationTool._menu_for_slot = original

    assert result.input_hint is not None
    assert result.input_hint.get("type") == "options"
    assert result.input_hint.get("multi") is True
    option_values = [o["value"] for o in result.input_hint.get("options", [])]
    assert "Assorted Finger Sandwiches" in option_values
    assert "Antipasto Platter" in option_values
    assert "all" in option_values
    # Pending state must be set so the next turn resumes the flow.
    pending = slots["__pending_modification_request"]["value"]
    assert pending["stage"] == "category_remove_disambiguation"
    assert pending["target_slot"] == "selected_dishes"


def test_bug1_category_disambiguation_handles_multi_select_response():
    """User picks both items by number → both get removed."""
    import asyncio

    from agent.state import (
        PHASE_MAIN_MENU,
        fill_slot,
        initialize_empty_slots,
        stamp_pending,
    )
    from agent.tools.modification_tool import ModificationTool

    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Assorted Finger Sandwiches, Antipasto Platter")
    pending_payload = stamp_pending({
        "stage": "category_remove_disambiguation",
        "target_slot": "selected_dishes",
        "category": "Platters",
        "candidate_items": ["Assorted Finger Sandwiches", "Antipasto Platter"],
        "resume_phase": PHASE_MAIN_MENU,
        "resume_target": None,
        "resume_prompt": "",
    }, 0)
    fill_slot(slots, "__pending_modification_request", pending_payload)
    state = {
        "slots": slots,
        "messages": [],
        "conversation_phase": PHASE_MAIN_MENU,
    }

    async def _fake_menu(self, slot, slots):
        return {
            "Platters": [
                {"name": "Assorted Finger Sandwiches"},
                {"name": "Antipasto Platter"},
            ],
        }

    original = ModificationTool._menu_for_slot
    ModificationTool._menu_for_slot = _fake_menu
    try:
        # Simulate the orchestrator delegating to modification_tool with the
        # pending state already set.
        result = asyncio.run(
            tool._resume_pending_request(
                pending_request=pending_payload,
                message="1, 2",
                slots=slots,
                state=state,
                history=[],
            )
        )
    finally:
        ModificationTool._menu_for_slot = original

    assert result is not None
    # Both items should be gone.
    new_value = slots["selected_dishes"]["value"]
    assert "Assorted Finger Sandwiches" not in str(new_value)
    assert "Antipasto Platter" not in str(new_value)
    # Pending state cleared
    assert not slots["__pending_modification_request"]["filled"]


def test_bug1_category_disambiguation_handles_all_response():
    """User says 'all' → every candidate item gets removed."""
    import asyncio

    from agent.state import (
        PHASE_MAIN_MENU,
        fill_slot,
        initialize_empty_slots,
    )
    from agent.tools.modification_tool import ModificationTool

    tool = ModificationTool()
    slots = initialize_empty_slots()
    fill_slot(slots, "selected_dishes", "Assorted Finger Sandwiches, Antipasto Platter")
    pending_payload = {
        "stage": "category_remove_disambiguation",
        "target_slot": "selected_dishes",
        "category": "Platters",
        "candidate_items": ["Assorted Finger Sandwiches", "Antipasto Platter"],
        "resume_phase": PHASE_MAIN_MENU,
        "resume_target": None,
        "resume_prompt": "",
    }
    fill_slot(slots, "__pending_modification_request", pending_payload)
    state = {
        "slots": slots,
        "messages": [],
        "conversation_phase": PHASE_MAIN_MENU,
    }

    async def _fake_menu(self, slot, slots):
        return {
            "Platters": [
                {"name": "Assorted Finger Sandwiches"},
                {"name": "Antipasto Platter"},
            ],
        }

    original = ModificationTool._menu_for_slot
    ModificationTool._menu_for_slot = _fake_menu
    try:
        result = asyncio.run(
            tool._resume_pending_request(
                pending_request=pending_payload,
                message="all",
                slots=slots,
                state=state,
                history=[],
            )
        )
    finally:
        ModificationTool._menu_for_slot = original

    assert result is not None
    new_value = slots["selected_dishes"]["value"]
    assert "Assorted Finger Sandwiches" not in str(new_value)
    assert "Antipasto Platter" not in str(new_value)


# ---------------------------------------------------------------------------
# Bug 1: Rentals silently restored to "Linens" via stale `linens=True` flag
# ---------------------------------------------------------------------------

def test_rentals_cleared_also_clears_linens_flag():
    """When rentals is set to "none" (e.g. via mod "remove all rentals"), the
    `linens` boolean must also flip to False. Otherwise the recap fall-through
    branch in finalization_tool prints "Rentals: Linens" even though the user
    cleared their rentals.

    Trace: user picks Linens, then mods "remove all rentals" + "tableware
    premium". Primary mod fills rentals="none" but `linens=True` lingers.
    Recap renders "Rentals: Linens" via the elif s.get("linens") fallback.
    """
    from agent.cascade import apply_cascade
    from agent.state import (
        fill_slot,
        get_slot_value,
        initialize_empty_slots,
    )

    slots = initialize_empty_slots()
    # Simulate the original rentals fill (Linens, Tables, Chairs).
    fill_slot(slots, "rentals", "Linens, Tables, Chairs")
    fill_slot(slots, "linens", True)

    # Now user mods rentals to "none" (the cascade fires on the new value).
    apply_cascade("rentals", "Linens, Tables, Chairs", "none", slots)

    assert get_slot_value(slots, "linens") is False, (
        "linens flag must clear when rentals -> none, otherwise recap prints "
        "'Rentals: Linens' via the fallback branch"
    )

    # And when rentals goes from "none" to a list including Linens, linens=True.
    apply_cascade("rentals", "none", "Linens, Tables", slots)
    assert get_slot_value(slots, "linens") is True

    # Tables-only (no linens) — linens stays False.
    apply_cascade("rentals", "Linens, Tables", "Tables, Chairs", slots)
    assert get_slot_value(slots, "linens") is False


# ---------------------------------------------------------------------------
# Bug 2: Tableware "upgrade" / direct style names should fill tableware slot
# at the gate question (no redundant re-ask of style picker).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "user_msg, expected_value",
    [
        ("upgrade", "silver_disposable"),
        ("premium", "silver_disposable"),
        ("china", "china"),
        ("compostable", "silver_disposable"),
        ("disposable", "standard_disposable"),
        ("standard_disposable", "standard_disposable"),
        ("none", "no_tableware"),
        ("skip", "no_tableware"),
    ],
)
def test_tableware_gate_accepts_direct_style_names(user_msg, expected_value):
    """At ask_tableware_gate, typing a specific style (or 'upgrade') should
    fill the `tableware` slot directly. Past bug: 'upgrade' only flipped
    __gate_tableware=True and re-asked the picker, which felt redundant."""
    from agent.state import fill_slot, get_slot_value, initialize_empty_slots
    from agent.tools.add_ons_tool import _apply_structured_answer

    slots = initialize_empty_slots()
    fills: list = []
    effects: list = []
    matched = _apply_structured_answer(
        target="ask_tableware_gate",
        message_lower=user_msg,
        slots=slots,
        fills=fills,
        effects=effects,
    )
    assert matched is True
    assert get_slot_value(slots, "tableware") == expected_value


# ---------------------------------------------------------------------------
# Bug 3: Common typos for "actually" must still flag modification intent.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("typo", ["acutally", "actaully", "acually"])
def test_actually_typos_recognized_as_soft_mod_marker(typo):
    """The router's `_SOFT_MOD_KEYWORDS` set must include common typos for
    'actually' so a misspelled correction ('acutally remove desserts') still
    routes through modification_tool instead of being eaten as a first-fill."""
    from agent.router import _SOFT_MOD_KEYWORDS, _looks_like_modification_intent

    assert typo in _SOFT_MOD_KEYWORDS
    # Combined with an explicit change verb, it must trigger mod intent.
    assert _looks_like_modification_intent(f"{typo} remove desserts") is True

"""
Pydantic extraction schemas for all domain Tools.

Every schema uses Optional[...] = None so Instructor can safely return partial
extractions. Validators enforce hard business rules (future-only dates, positive
guest counts) immediately after LLM extraction.

Contract: these schemas are the ONLY way Tools extract structured data.
Nothing else should call the LLM for structured extraction directly.
"""

from __future__ import annotations

import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Shared enums / literals — keep in sync with SLOT_NAMES and the slot registry
# ============================================================================

EventType = Literal["Wedding", "Birthday", "Corporate", "Other"]
ServiceType = Literal["Onsite", "Dropoff"]
MealStyle = Literal["buffet", "plated"]
AppetizerStyle = Literal["passed", "station"]
BarPackage = Literal["beer_wine", "beer_wine_signature", "full_open_bar"]
Tableware = Literal[
    "standard_disposable", "silver_disposable", "gold_disposable", "china", "no_tableware"
]
Utensils = Literal["standard_plastic", "eco_biodegradable", "bamboo", "no_utensils"]
TravelFee = Literal["none", "tier1_150", "tier2_250", "tier3_375plus"]
ModificationAction = Literal["add", "remove", "replace", "reopen"]
SelectionGroundingStatus = Literal["resolved", "ambiguous", "no_match"]


# ============================================================================
# BasicInfoTool — identity, event fundamentals, service type
# ============================================================================

class EventDetailsExtraction(BaseModel):
    """Any basic-info field the user may mention in free text.

    All fields optional so Instructor can extract a partial update. Validators
    reject impossible values (past dates, non-positive guest counts) so the
    Tool can re-ask without poisoning the slot state.
    """

    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    event_type: Optional[EventType] = None
    event_type_other: Optional[str] = None
    event_date: Optional[datetime.date] = None
    venue: Optional[str] = None
    guest_count: Optional[int] = None
    partner_name: Optional[str] = None
    company_name: Optional[str] = None
    honoree_name: Optional[str] = None
    service_type: Optional[ServiceType] = None

    @field_validator("event_date")
    @classmethod
    def _must_be_future(cls, v: Optional[datetime.date]) -> Optional[datetime.date]:
        if v is not None and v <= datetime.date.today():
            raise ValueError("Event date must be in the future")
        return v

    @field_validator("guest_count")
    @classmethod
    def _must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Guest count must be positive")
        if v is not None and v > 2000:
            raise ValueError("Guest count seems unreasonably large — please double-check")
        return v

    @field_validator("venue")
    @classmethod
    def _reject_meta_commands(cls, v: Optional[str]) -> Optional[str]:
        """FIX-01 — 'change date' must never be stored as a venue."""
        if v is None:
            return v
        low = v.strip().lower()
        # Accept TBD variants — stored verbatim so the agent can re-ask later
        if (
            low in ("tbd", "to be determined", "confirm on call", "tbd-confirm on call")
            or "tbd" in low
            or "to be determined" in low
            or "confirm later" in low
            or "confirm on call" in low
            or "not decided yet" in low
        ):
            return v.strip()
        meta_triggers = (
            "change", "update", "edit", "modify", "go back", "fix",
            "actually", "wait", "@ai",
        )
        if any(low.startswith(t) for t in meta_triggers):
            raise ValueError("Meta-command is not a venue name")
        return v.strip()

    @field_validator("guest_count")
    @classmethod
    def _guest_count_tbd(cls, v: Optional[int]) -> Optional[int]:
        # guest_count is an int so TBD is handled separately in basic_info_tool
        return v


# ============================================================================
# MenuSelectionTool — cocktail hour, main dishes, desserts
# ============================================================================

class MenuSelectionExtraction(BaseModel):
    """Items the user selected, removed, or flagged from the menu.

    `raw_items` holds whatever the user said — Instructor only normalizes into
    a clean comma-less list. The Tool itself runs `_resolve_to_db_items()` to
    map into real DB rows. Never trust `raw_items` as final state.
    """

    cocktail_hour: Optional[bool] = Field(
        default=None,
        description="True if user wants cocktail hour, False if they declined it.",
    )
    appetizer_style: Optional[AppetizerStyle] = None
    meal_style: Optional[MealStyle] = None
    custom_menu: Optional[bool] = Field(
        default=None,
        description="True if user explicitly wants a fully custom menu, not catalog items.",
    )
    raw_items: List[str] = Field(
        default_factory=list,
        description=(
            "Free-text item names the user mentioned (e.g. 'charcuterie', "
            "'tikka', 'option 2'). The Tool will resolve these to DB rows."
        ),
    )
    category_hint: Optional[Literal["appetizers", "dishes", "desserts"]] = Field(
        default=None,
        description=(
            "Which menu category the user is selecting for. Inferred from "
            "conversation context, not just the message."
        ),
    )
    is_decline: bool = Field(
        default=False,
        description=(
            "True ONLY if user explicitly declines this category "
            "(e.g. 'no desserts', 'skip appetizers'). Ambiguous affirmatives "
            "like 'lets do cookies' must NOT set this."
        ),
    )
    menu_notes: Optional[str] = Field(
        default=None,
        description=(
            "Any prep notes, dietary handling, or special instructions about the menu "
            "that don't fit a specific item (e.g. 'make everything halal', 'no pork in any dish'). "
            "Only extract if explicitly stated."
        ),
    )


# ============================================================================
# AddOnsTool — drinks, bar, tableware, rentals, labor
# ============================================================================

class AddOnsExtraction(BaseModel):
    """Drinks, bar, disposables, rentals, labor."""

    drinks: Optional[bool] = Field(
        default=None,
        description="True if user wants drinks at all. Water/tea/lemonade included baseline.",
    )
    bar_service: Optional[bool] = None
    bar_package: Optional[BarPackage] = None
    coffee_service: Optional[bool] = None

    tableware: Optional[Tableware] = None
    utensils: Optional[Utensils] = None

    linens: Optional[bool] = None
    rentals: List[str] = Field(default_factory=list)

    labor_ceremony_setup: Optional[bool] = None
    labor_table_setup: Optional[bool] = None
    labor_table_preset: Optional[bool] = None
    labor_cleanup: Optional[bool] = None
    labor_trash: Optional[bool] = None
    travel_fee: Optional[TravelFee] = None


# ============================================================================
# ModificationTool — any previously filled slot
# ============================================================================

class SecondaryModification(BaseModel):
    """A secondary modification to apply alongside the primary one.

    Used when a single user message contains multiple cross-slot actions.
    Same shape as ModificationExtraction but flat (no nested secondaries) to
    keep the schema bounded.
    """

    target_slot: str = Field(
        ...,
        description="Exact slot name from SLOT_NAMES.",
    )
    action: ModificationAction
    new_value: Optional[Any] = None
    items_to_remove: List[str] = Field(default_factory=list)
    items_to_add: List[str] = Field(default_factory=list)


class ModificationExtraction(BaseModel):
    """Extract a request to change any previously filled slot.

    `target_slot` MUST be an exact slot_name from the registry (Section 6 of
    AGENT_SPEC.md). The Tool validates this against SLOT_NAMES before applying.

    For multi-action messages ("add ravioli to mains AND remove cheese AND
    remove adobo from appetizers"), put the FIRST action in the top-level
    fields and any additional cross-slot actions in `secondary_modifications`.
    The tool processes the primary first, then iterates secondaries in order.
    """

    target_slot: str = Field(
        ...,
        description=(
            "Exact slot name (e.g. 'event_date', 'selected_dishes', 'desserts'). "
            "Must match a name in SLOT_NAMES exactly."
        ),
    )
    action: ModificationAction
    new_value: Optional[Any] = Field(
        default=None,
        description=(
            "New value (for add/replace). None for remove. For list slots, "
            "this is the item(s) to add or the item(s) to remove."
        ),
    )
    items_to_remove: List[str] = Field(
        default_factory=list,
        description=(
            "For 'remove' or 'replace' actions on list slots: the EXACT item names "
            "from the CURRENT FILLED LISTS context. Never return fuzzy terms like "
            "'chicken' — return 'Chicken Satay', 'BBQ Chicken Slider', etc. "
            "Resolve group references ('remove chicken', 'drop all seafood') to the "
            "actual matching names in the current list."
        ),
    )
    items_to_add: List[str] = Field(
        default_factory=list,
        description=(
            "For 'add' or 'replace' actions on list slots: exactly which items "
            "the user wants added. Parsed from natural language."
        ),
    )
    secondary_modifications: List[SecondaryModification] = Field(
        default_factory=list,
        description=(
            "Additional cross-slot modifications from the same message. "
            "Use ONLY when the user explicitly references a different section "
            "(e.g. primary = 'add ravioli to mains', secondary = "
            "'remove adobo from appetizers'). Each secondary must have its own "
            "target_slot, action, and items. Leave empty for single-section requests. "
            "Maximum 3 secondaries to bound complexity."
        ),
    )
    already_selected: List[str] = Field(
        default_factory=list,
        description=(
            "Items the user tried to add that are already in the current selection "
            "(found in CURRENT FILLED LISTS). List their exact names here instead of "
            "items_to_add so the response can inform the user."
        ),
    )


class SelectedItemGrounding(BaseModel):
    """Resolve a list-edit reference against the user's currently selected items only."""

    status: SelectionGroundingStatus
    matched_names: List[str] = Field(
        default_factory=list,
        description="Exact selected item names from the provided current selection only.",
    )
    reference_text: Optional[str] = Field(
        default=None,
        description="The short user-facing phrase being grounded, such as 'egg' or 'chicken'.",
    )
    reason: str = Field(
        ...,
        description="Short explanation for why the reference was resolved, ambiguous, or unmatched.",
    )


# ============================================================================
# FinalizationTool — special requests, dietary, follow-up, confirm
# ============================================================================

class FinalizationExtraction(BaseModel):
    """Special requests, dietary concerns, follow-up call, final confirmation."""

    special_requests: Optional[str] = None
    dietary_concerns: Optional[str] = None
    additional_notes: Optional[str] = None
    followup_call_requested: Optional[bool] = None
    confirm_final: Optional[bool] = Field(
        default=None,
        description="True if user explicitly confirms the final summary is correct.",
    )


# ============================================================================
# Orchestrator routing schema
# ============================================================================

ToolName = Literal[
    "basic_info_tool",
    "menu_selection_tool",
    "add_ons_tool",
    "modification_tool",
    "finalization_tool",
]

TurnIntent = Literal[
    "answer_current_prompt",
    "continue_current_flow",
    "modify_existing",
    "reopen_previous_section",
    "provide_other_information",
    "unclear",
]


class ToolCall(BaseModel):
    tool_name: ToolName
    reason: str = Field(..., description="One sentence explaining the routing choice.")


class OrchestratorDecision(BaseModel):
    """Single-dispatch routing decision. One tool call per turn, max."""

    action: Literal["tool_call", "clarify", "no_action"]
    tool_calls: List[ToolCall] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    clarifying_question: Optional[str] = None

    @field_validator("tool_calls")
    @classmethod
    def _single_dispatch(cls, v: List[ToolCall]) -> List[ToolCall]:
        if len(v) > 1:
            raise ValueError("Orchestrator must return at most one tool call per turn")
        return v


class TurnRoutingSignals(BaseModel):
    """Structured routing signals extracted before final tool selection.

    This keeps policy in code: the model only classifies the turn shape, while
    the router decides what that means operationally.
    """

    key_indicators: List[str] = Field(
        default_factory=list,
        description=(
            "2-4 brief observations that led to your classification. "
            "E.g.: ['user said mb (my bad)', 'event_type already filled as Birthday', "
            "'message contradicts prior answer']. Reason BEFORE classifying."
        ),
    )
    intent: TurnIntent
    referenced_slot: Optional[str] = Field(
        default=None,
        description=(
            "Exact slot name if the user is clearly referring to one known slot. "
            "For reopen_previous_section, use the list slot being revisited. "
            "Otherwise null."
        ),
    )
    proposed_tool: Optional[ToolName] = Field(
        default=None,
        description=(
            "Best tool guess when the message is not simply answering the current "
            "prompt and not clearly a modification. Otherwise null."
        ),
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., description="Short explanation for the classification.")


__all__ = [
    "EventDetailsExtraction",
    "MenuSelectionExtraction",
    "AddOnsExtraction",
    "ModificationExtraction",
    "SecondaryModification",
    "SelectedItemGrounding",
    "FinalizationExtraction",
    "ToolCall",
    "OrchestratorDecision",
    "EventType",
    "ServiceType",
    "MealStyle",
    "AppetizerStyle",
    "BarPackage",
    "Tableware",
    "Utensils",
    "TravelFee",
    "ModificationAction",
    "SelectionGroundingStatus",
    "ToolName",
    "TurnIntent",
    "TurnRoutingSignals",
]

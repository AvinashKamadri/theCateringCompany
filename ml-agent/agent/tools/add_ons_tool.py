"""
AddOnsTool — S12 (drinks/bar), S13 (tableware), S14 (rentals), S15 (labor).

Owns drinks, bar_service, bar_package, bartender (auto), coffee_service,
tableware, utensils, linens, rentals, and all labor_* slots + travel_fee.

Enforced rules:
- `service_type == Dropoff` → ALL labor_* slots skipped entirely.
- `bar_service == True` → `bartender` auto-True, non-optional, cannot be unset.
- `meal_style == plated` → auto-note china in tableware (cascade).
- `drinks == False` → skip bar sub-questions.
"""

from __future__ import annotations
from typing import Any

from langchain_core.messages import BaseMessage

from agent.cascade import apply_cascade
from agent.instructor_client import extract
from agent.models import AddOnsExtraction
from agent.state import (
    PHASE_DRINKS_BAR,
    PHASE_LABOR,
    PHASE_RENTALS,
    PHASE_SPECIAL_REQUESTS,
    PHASE_TABLEWARE,
    clear_slot,
    fill_slot,
    get_slot_value,
    is_filled,
)
from agent.tools.base import ToolResult, history_for_llm
from agent.tools.structured_choice import normalize_structured_choice


_SYSTEM_PROMPT = (
    "# Role\n"
    "You parse drink/bar/rental/labor selections from a catering customer's message.\n\n"
    "# Rules\n"
    "- Extract ONLY what is explicitly said. Never guess.\n"
    "- Use conversation history to resolve short affirmatives ('yes', 'ok') only when the prior AI turn asked about a specific slot.\n"
    "- Return None for anything not explicitly stated.\n"
    "- drinks: True if they want drinks at all.\n"
    "- bar_service: True if they want a bar setup.\n"
    "- bar_package: 'beer_wine' | 'beer_wine_signature' | 'full_open_bar'.\n"
    "- coffee_service: True if they want a coffee bar.\n"
    "- tableware: map these EXACT labels the frontend sends (also accept normalized keys):\n"
    "  'Standard Disposable (included)'/'standard_disposable' -> standard_disposable\n"
    "  'Silver Disposable'/'silver_disposable' -> silver_disposable\n"
    "  'Gold Disposable'/'gold_disposable' -> gold_disposable\n"
    "  'Premium Disposable (gold/silver)'/'Premium Disposable' -> gold_disposable\n"
    "  'Full China'/'china'/'real china' -> china\n"
    "  'No tableware needed'/'no_tableware'/'none' -> no_tableware\n"
    "- utensils: map these EXACT labels (also accept 1/2/3 only when the user is answering utensils):\n"
    "  'Standard plastic (included)'/'standard_plastic'/'1' -> standard_plastic\n"
    "  'Eco / biodegradable'/'eco_biodegradable'/'2' -> eco_biodegradable\n"
    "  'Bamboo'/'bamboo'/'3' -> bamboo\n"
    "- linens: True if they want linen rentals.\n"
    "- rentals: ALWAYS return as a JSON array of strings, never a single string.\n"
    "  - 'Tables and Chairs' -> ['Tables','Chairs']; 'none'/'no rentals' -> [].\n"
    "- labor_*: True if they want that staffing service.\n"
    "- travel_fee: 'tier1_150' < 30 min, 'tier2_250' < 1 hr, 'tier3_375plus' extended.\n\n"
    "# Examples\n"
    "1. User: 'yes' (after AI asked about linens)\n"
    "   Extract: linens=True\n"
    "2. User: 'Full China'\n"
    "   Extract: tableware='china'\n"
    "3. User: '2' (when asked utensils)\n"
    "   Extract: utensils='eco_biodegradable'\n"
    "4. User: 'Tables and chairs'\n"
    "   Extract: rentals=['Tables','Chairs']\n"
)


_LABOR_SLOTS = (
    "labor_ceremony_setup",
    "labor_table_setup",
    "labor_table_preset",
    "labor_cleanup",
    "labor_trash",
)

_LABOR_SERVICE_OPTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "labor_ceremony_setup",
        "Ceremony setup",
        (
            "labor_ceremony_setup",
            "yes_labor_ceremony_setup",
            "ceremony setup",
            "ceremony setup labor",
            "ceremony",
        ),
    ),
    (
        "labor_table_setup",
        "Table setup",
        (
            "labor_table_setup",
            "yes_labor_table_setup",
            "table setup",
            "tables setup",
            "table and chair setup",
            "tables and chairs setup",
        ),
    ),
    (
        "labor_table_preset",
        "Table preset",
        (
            "labor_table_preset",
            "yes_labor_table_preset",
            "table preset",
            "table preset service",
            "preset tables",
            "tables preset",
        ),
    ),
    (
        "labor_cleanup",
        "Cleanup",
        (
            "labor_cleanup",
            "yes_labor_cleanup",
            "cleanup",
            "clean up",
            "event cleanup",
            "cleanup after the event",
        ),
    ),
    (
        "labor_trash",
        "Trash removal",
        (
            "labor_trash",
            "yes_labor_trash",
            "trash",
            "trash removal",
            "trash service",
        ),
    ),
)

_YES = {"yes", "y", "yeah", "yep", "sure", "yes please"}
_NO = {"no", "n", "nah", "nope", "no thanks", "skip"}

_BAR_PACKAGE_MAP: dict[str, str] = {
    "beer_wine": "beer_wine",
    "beer & wine": "beer_wine",
    "beer and wine": "beer_wine",
    "beer_wine_signature": "beer_wine_signature",
    "beer, wine + 2 signature drinks": "beer_wine_signature",
    "beer wine signature": "beer_wine_signature",
    "signature": "beer_wine_signature",
    "full_open_bar": "full_open_bar",
    "full open bar": "full_open_bar",
    "open bar": "full_open_bar",
}

_TABLEWARE_MAP: dict[str, str] = {
    "standard_disposable": "standard_disposable",
    "standard disposable": "standard_disposable",
    "standard disposable (included)": "standard_disposable",
    "standard disposable (included, no upgrade)": "standard_disposable",
    "silver_disposable": "silver_disposable",
    "silver disposable": "silver_disposable",
    "silver disposable (+$1/pp)": "silver_disposable",
    "gold_disposable": "gold_disposable",
    "gold disposable": "gold_disposable",
    "gold disposable (+$1/pp)": "gold_disposable",
    "china": "china",
    "full china": "china",
    "real china": "china",
    "no_tableware": "no_tableware",
    "no tableware": "no_tableware",
    "no tableware needed": "no_tableware",
    "none": "no_tableware",
}

_UTENSILS_MAP: dict[str, str] = {
    "standard_plastic": "standard_plastic",
    "standard plastic": "standard_plastic",
    "standard plastic (included)": "standard_plastic",
    "eco_biodegradable": "eco_biodegradable",
    "eco / biodegradable": "eco_biodegradable",
    "eco-friendly / biodegradable": "eco_biodegradable",
    "eco friendly / biodegradable": "eco_biodegradable",
    "bamboo": "bamboo",
}
def _history_for_llm(history: list[BaseMessage]) -> list[dict]:
    return history_for_llm(history)


def _phase_of(slots: dict) -> str:
    target = _next_target(slots)
    if target.startswith("ask_drinks_") or target == "ask_bar_package":
        return PHASE_DRINKS_BAR
    if target in {"ask_tableware_gate", "ask_tableware", "ask_utensils"}:
        return PHASE_TABLEWARE
    if target in {"ask_rentals_gate", "ask_rentals_items"}:
        return PHASE_RENTALS
    if target == "ask_labor_services":
        return PHASE_LABOR
    return PHASE_SPECIAL_REQUESTS


class AddOnsTool:
    name = "add_ons_tool"

    async def run(
        self,
        *,
        message: str,
        history: list[BaseMessage],
        state: dict,
    ) -> ToolResult:
        slots = state["slots"]
        service_type = get_slot_value(slots, "service_type")
        current_target = _next_target(slots)

        fills: list[tuple[str, Any]] = []
        effects: list[tuple[str, str]] = []
        extracted = None

        # Deterministic handling for structured UI answers. Keep this target-aware
        # so bare "yes"/"no" can never bleed into the wrong add-on slot.
        _msg_lower = message.strip().lower()
        skip_extraction = _apply_structured_answer(
            target=current_target,
            message_lower=_msg_lower,
            slots=slots,
            fills=fills,
            effects=effects,
        )

        if not skip_extraction:
            extracted = await extract(
                schema=AddOnsExtraction,
                system=_SYSTEM_PROMPT,
                user_message=message,
                history=_history_for_llm(history),
            )

        allowed_fields = _allowed_fields_for_target(current_target)
        if extracted is not None and allowed_fields:
            dump = extracted.model_dump(exclude_none=True)

            for field_name, value in dump.items():
                if field_name not in allowed_fields:
                    continue
                if field_name in _LABOR_SLOTS and service_type == "Dropoff":
                    continue
                if field_name == "rentals" and isinstance(value, list):
                    normalized = _normalize_rentals(value)
                    if not normalized:
                        continue
                    has_linens = "Linens" in normalized
                    fill_slot(slots, "linens", has_linens)
                    fills.append(("linens", has_linens))
                    final_value = ", ".join(normalized) if normalized else "none"
                    fill_slot(slots, "rentals", final_value)
                    fills.append(("rentals", final_value))
                    continue

                if field_name == "bar_package" and isinstance(value, str):
                    value = _BAR_PACKAGE_MAP.get(value.lower().strip())
                    if not value:
                        continue

                old_value = get_slot_value(slots, field_name)
                fill_slot(slots, field_name, value)
                fills.append((field_name, value))
                effects.extend(apply_cascade(field_name, old_value, value, slots))

        next_target = _next_target(slots)
        next_phase = _phase_of(slots)
        state["conversation_phase"] = next_phase

        # Store which yes/no question is pending so the router can resolve
        # bare "yes"/"no" replies without an LLM call.
        _GATE_TARGETS = {
            "ask_drinks_interest": (None, "drinks"),
            "ask_tableware_gate": ("__gate_tableware", "tableware"),
            "ask_rentals_gate": ("__gate_rentals", "rentals"),
        }
        if next_target in _GATE_TARGETS:
            gate_slot, content_slot = _GATE_TARGETS[next_target]
            fill_slot(slots, "__pending_confirmation", {
                "question_id": next_target,
                "tool": "add_ons_tool",
                "yes_action": "open_gate" if gate_slot else "set_true",
                "no_action": "skip",
                "gate_slot": gate_slot,
                "content_slot": content_slot,
            })
        else:
            if is_filled(slots, "__pending_confirmation"):
                clear_slot(slots, "__pending_confirmation")

        response_context = {
            "tool": self.name,
            "filled_this_turn": fills,
            "cascade_effects": effects,
            "next_phase": next_phase,
            "skip_labor": service_type == "Dropoff",
            "bartender_auto_set": any(f[0] == "bartender" for f in effects),
            "meal_style": get_slot_value(slots, "meal_style"),
            "next_question_target": next_target,
        }

        input_hint = _input_hint_for_target(next_target, slots)

        return ToolResult(
            state=state,
            response_context=response_context,
            input_hint=input_hint,
        )


def _has_unfilled_labor(slots: dict) -> bool:
    return any(not is_filled(slots, slot) for slot in _LABOR_SLOTS)


def _next_target(slots: dict) -> str:
    if not is_filled(slots, "drinks"):
        return "ask_drinks_interest"

    if get_slot_value(slots, "drinks"):
        if not is_filled(slots, "coffee_service") and not is_filled(slots, "bar_service"):
            return "ask_drinks_setup"
        if get_slot_value(slots, "bar_service") and not is_filled(slots, "bar_package"):
            return "ask_bar_package"

    if not is_filled(slots, "tableware"):
        if not is_filled(slots, "__gate_tableware"):
            return "ask_tableware_gate"
        return "ask_tableware"

    if not is_filled(slots, "utensils"):
        return "ask_utensils"

    if not is_filled(slots, "__gate_rentals"):
        return "ask_rentals_gate"
    if get_slot_value(slots, "__gate_rentals") and not is_filled(slots, "rentals"):
        return "ask_rentals_items"

    service_type = get_slot_value(slots, "service_type")
    if service_type != "Dropoff" and _has_unfilled_labor(slots):
        return "ask_labor_services"

    return "transition_to_special_requests"


def _allowed_fields_for_target(target: str) -> set[str]:
    if target == "ask_drinks_interest":
        return {"drinks"}
    if target == "ask_drinks_setup":
        return {"coffee_service", "bar_service"}
    if target == "ask_bar_package":
        return {"bar_package"}
    if target in {"ask_tableware_gate", "ask_tableware"}:
        return {"tableware"}
    if target == "ask_utensils":
        return {"utensils"}
    if target == "ask_rentals_gate":
        return set()
    if target == "ask_rentals_items":
        return {"rentals"}
    if target == "ask_labor_services":
        return set(_LABOR_SLOTS)
    return set()


def _apply_structured_answer(
    *,
    target: str,
    message_lower: str,
    slots: dict,
    fills: list[tuple[str, Any]],
    effects: list[tuple[str, str]],
) -> bool:
    message_lower = normalize_structured_choice(message_lower)

    if target == "ask_drinks_interest":
        if message_lower in _YES or message_lower in {"yes, add drinks"}:
            old = get_slot_value(slots, "drinks")
            fill_slot(slots, "drinks", True)
            fills.append(("drinks", True))
            effects.extend(apply_cascade("drinks", old, True, slots))
            return True
        if message_lower in _NO:
            old = get_slot_value(slots, "drinks")
            fill_slot(slots, "drinks", False)
            fills.append(("drinks", False))
            effects.extend(apply_cascade("drinks", old, False, slots))
            return True

    if target == "ask_drinks_setup":
        if "coffee and bar" in message_lower or "both coffee & bar" in message_lower or message_lower == "both":
            fill_slot(slots, "coffee_service", True)
            fills.append(("coffee_service", True))
            old = get_slot_value(slots, "bar_service")
            fill_slot(slots, "bar_service", True)
            fills.append(("bar_service", True))
            effects.extend(apply_cascade("bar_service", old, True, slots))
            return True
        if "coffee only" in message_lower or (message_lower == "coffee" and "bar" not in message_lower):
            fill_slot(slots, "coffee_service", True)
            fills.append(("coffee_service", True))
            old = get_slot_value(slots, "bar_service")
            fill_slot(slots, "bar_service", False)
            fills.append(("bar_service", False))
            effects.extend(apply_cascade("bar_service", old, False, slots))
            return True
        if "bar only" in message_lower or "bar service only" in message_lower:
            fill_slot(slots, "coffee_service", False)
            fills.append(("coffee_service", False))
            old = get_slot_value(slots, "bar_service")
            fill_slot(slots, "bar_service", True)
            fills.append(("bar_service", True))
            effects.extend(apply_cascade("bar_service", old, True, slots))
            return True
        if "neither" in message_lower or message_lower in _NO:
            fill_slot(slots, "coffee_service", False)
            fills.append(("coffee_service", False))
            old = get_slot_value(slots, "bar_service")
            fill_slot(slots, "bar_service", False)
            fills.append(("bar_service", False))
            effects.extend(apply_cascade("bar_service", old, False, slots))
            return True

    if target == "ask_bar_package":
        normalized = _BAR_PACKAGE_MAP.get(message_lower)
        if normalized:
            fill_slot(slots, "bar_package", normalized)
            fills.append(("bar_package", normalized))
            return True

    if target == "ask_tableware_gate":
        normalized = _TABLEWARE_MAP.get(message_lower)
        if normalized:
            fill_slot(slots, "tableware", normalized)
            fills.append(("tableware", normalized))
            return True
        if message_lower in {"upgrade", "yes i'd like to upgrade", "yes, i'd like to upgrade"} or message_lower in _YES:
            fill_slot(slots, "__gate_tableware", True)
            fills.append(("__gate_tableware", True))
            return True

    if target == "ask_tableware":
        normalized = _TABLEWARE_MAP.get(message_lower)
        if normalized:
            fill_slot(slots, "tableware", normalized)
            fills.append(("tableware", normalized))
            return True

    if target == "ask_utensils":
        normalized = _UTENSILS_MAP.get(message_lower)
        if normalized:
            fill_slot(slots, "utensils", normalized)
            fills.append(("utensils", normalized))
            return True

    if target == "ask_rentals_gate":
        if message_lower in _YES or message_lower == "yes, add rentals":
            fill_slot(slots, "__gate_rentals", True)
            fills.append(("__gate_rentals", True))
            return True
        if message_lower in _NO or message_lower == "no rentals needed":
            fill_slot(slots, "__gate_rentals", False)
            fills.append(("__gate_rentals", False))
            fill_slot(slots, "linens", False)
            fills.append(("linens", False))
            fill_slot(slots, "rentals", "none")
            fills.append(("rentals", "none"))
            return True

    if target == "ask_rentals_items":
        normalized_rentals = _normalize_rentals([message_lower])
        if normalized_rentals == ["none"]:
            fill_slot(slots, "linens", False)
            fills.append(("linens", False))
            fill_slot(slots, "rentals", "none")
            fills.append(("rentals", "none"))
            return True
        if normalized_rentals:
            has_linens = "Linens" in normalized_rentals
            fill_slot(slots, "linens", has_linens)
            fills.append(("linens", has_linens))
            final_value = ", ".join(normalized_rentals) if normalized_rentals else "none"
            fill_slot(slots, "rentals", final_value)
            fills.append(("rentals", final_value))
            return True

    if target == "ask_labor_services":
        selected_slots = _normalize_labor_services([message_lower])
        if selected_slots is not None:
            for labor_slot in _LABOR_SLOTS:
                wants_service = labor_slot in selected_slots
                fill_slot(slots, labor_slot, wants_service)
                fills.append((labor_slot, wants_service))
            return True

    return False


def _normalize_rentals(values: list[str]) -> list[str]:
    joined = ", ".join(v for v in values if v).lower()
    if not joined:
        return []
    if joined in {"none", "no additional rentals", "no rentals", "no"}:
        return ["none"]

    found: list[str] = []
    if "linen" in joined:
        found.append("Linens")
    if "table" in joined:
        found.append("Tables")
    if "chair" in joined:
        found.append("Chairs")
    return found


def _normalize_labor_services(values: list[str]) -> set[str] | None:
    tokens: list[str] = []
    for value in values:
        text = normalize_structured_choice(value)
        if not text:
            continue
        for part in text.split(","):
            part = part.strip()
            if part:
                tokens.append(part)

    if not tokens:
        return None

    joined = ", ".join(tokens)
    if joined in {"none", "no", "skip", "no labor", "no staffing", "no labor needed", "no staffing needed"}:
        return set()

    selected: set[str] = set()
    recognized = False
    for token in tokens:
        if token in {"none", "no", "skip", "no labor", "no staffing"}:
            recognized = True
            continue
        for slot_name, _label, aliases in _LABOR_SERVICE_OPTIONS:
            if any(alias in token for alias in aliases):
                selected.add(slot_name)
                recognized = True
                break

    return selected if recognized else None


def _input_hint_for_target(target: str, slots: dict) -> dict | None:
    if target == "ask_drinks_interest":
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes, add drinks"},
                {"value": "no", "label": "No thanks"},
            ],
        }
    if target == "ask_drinks_setup":
        return {
            "type": "options",
            "options": [
                {"value": "coffee only", "label": "Coffee bar only"},
                {"value": "bar only", "label": "Bar service only"},
                {"value": "coffee and bar", "label": "Both coffee & bar"},
                {"value": "neither", "label": "Neither"},
            ],
        }
    if target == "ask_bar_package":
        return {
            "type": "options",
            "options": [
                {"value": "beer_wine", "label": "Beer & wine"},
                {"value": "beer_wine_signature", "label": "Beer, wine + 2 signature drinks"},
                {"value": "full_open_bar", "label": "Full open bar"},
            ],
        }
    if target == "ask_tableware_gate":
        return {
            "type": "options",
            "options": [
                {"value": "standard_disposable", "label": "Standard disposable (included, no upgrade)"},
                {"value": "upgrade", "label": "Yes, I'd like to upgrade"},
                {"value": "no_tableware", "label": "No tableware needed"},
            ],
        }
    if target == "ask_tableware":
        return {
            "type": "options",
            "options": [
                {"value": "silver_disposable", "label": "Silver disposable (+$1/pp)"},
                {"value": "gold_disposable", "label": "Gold disposable (+$1/pp)"},
                {"value": "china", "label": "China"},
            ],
        }
    if target == "ask_utensils":
        return {
            "type": "options",
            "options": [
                {"value": "standard_plastic", "label": "Standard plastic (included)"},
                {"value": "eco_biodegradable", "label": "Eco / biodegradable"},
                {"value": "bamboo", "label": "Bamboo"},
            ],
        }
    if target == "ask_rentals_gate":
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes, show rental options"},
                {"value": "no", "label": "No rentals needed"},
            ],
        }
    if target == "ask_rentals_items":
        return {
            "type": "options",
            "options": [
                {"value": "Linens", "label": "Linens"},
                {"value": "Tables", "label": "Tables"},
                {"value": "Chairs", "label": "Chairs"},
                {"value": "none", "label": "No additional rentals"},
            ],
            "multi": True,
        }
    if target == "ask_labor_services":
        return {
            "type": "options",
            "options": [
                {"value": slot_name, "label": label}
                for slot_name, label, _aliases in _LABOR_SERVICE_OPTIONS
            ],
            "multi": True,
        }
    if target == "transition_to_special_requests":
        return {
            "type": "options",
            "options": [
                {"value": "yes", "label": "Yes"},
                {"value": "no", "label": "No"},
            ],
        }
    return None


def _direct_response_for_target(target: str, slots: dict) -> str | None:
    if target == "ask_drinks_interest":
        return "Would you like to add drinks or bar service for the event?"
    if target == "ask_drinks_setup":
        return "Would you like coffee service, bar service, both, or neither?"
    if target == "ask_bar_package":
        return "Which bar package would you like?"
    if target == "ask_tableware_gate":
        return "For tableware, would you like the standard included option, an upgrade, or no tableware at all?"
    if target == "ask_tableware":
        return "Which tableware upgrade would you like?"
    if target == "ask_utensils":
        return "What utensils would you like to add?"
    if target == "ask_rentals_gate":
        return "Do you need any rentals like linens, tables, or chairs?"
    if target == "ask_rentals_items":
        return "Which rentals would you like to add?"
    if target == "ask_labor_services":
        return "Which service staff would you like us to handle? Select everything you need."
    if target == "transition_to_special_requests":
        return "Do you have any special requests we should note?"
    return None



__all__ = ["AddOnsTool", "normalize_structured_choice", "_normalize_labor_services"]

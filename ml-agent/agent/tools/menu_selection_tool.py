"""
MenuSelectionTool — HIGHEST-PRIORITY TOOL.

Owns: cocktail_hour, appetizers, appetizer_style, meal_style, selected_dishes,
custom_menu, desserts, menu_notes.

Every user-named food item is resolved through `resolve_to_db_items()` — no
exceptions. This preserves the ML_AGENT_MIGRATION_POSTMORTEM rule: extracted
names must map to REAL menu_items PK rows before they touch state.

What this Tool does NOT own:
- Removing or replacing already-selected items → ModificationTool
- Changing meal_style after the fact → ModificationTool
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import BaseMessage

from agent.ambiguous_choice import (
    replace_query_with_selection,
    resolve_choice_selection,
)
from agent.cascade import apply_cascade
from agent.instructor_client import extract
from agent.menu_resolver import (
    format_items,
    load_appetizer_menu,
    load_main_dish_menu,
    load_dessert_menu_expanded,
    parse_slot_items,
    resolve_dessert_choices,
    resolve_menu_items,
)
from agent.models import MenuSelectionExtraction
from agent.state import (
    PHASE_COCKTAIL,
    PHASE_DESSERT,
    PHASE_DRINKS_BAR,
    PHASE_MAIN_MENU,
    PHASE_TRANSITION,
    clear_slot,
    fill_slot,
    get_slot_value,
    is_filled,
)
from agent.tools.base import ToolResult, history_for_llm
from agent.tools.structured_choice import normalize_structured_choice


_SYSTEM_PROMPT = (
    "# Role\n"
    "You parse food selections from a catering customer's message. Context: they're being asked to pick items from a numbered catalog.\n\n"
    "# Rules\n"
    "- Extract ONLY what is explicitly stated. Never invent dish names.\n"
    "- raw_items: list item names or numbers the user mentioned. Accept shorthand ('charcuterie', 'tikka').\n"
    "  - If user says 'option 2' or just '2', include that digit as a string.\n"
    "  - CRITICAL: split multiple items into separate entries. Never collapse a list into one compound string.\n"
    "- If user says 'all of them' or 'everything', return raw_items=['ALL'].\n"
    "- is_decline: True only if user explicitly skips a course ('no appetizers', 'skip dessert', 'reception only').\n"
    "- menu_notes: prep/dietary instruction about the whole menu ('no pork in any dish'). Do NOT put item names here.\n"
    "- custom_menu: True only if user asks for a fully custom menu.\n"
    "- meal_style: always lowercase 'plated' or 'buffet'.\n"
    "- appetizer_style: always lowercase 'passed' or 'station'.\n"
    "- cocktail_hour: True if user wants cocktail hour or 'both'. False for 'reception only' / 'full reception'.\n"
    "- category_hint: 'appetizers' | 'dishes' | 'desserts' (infer from context).\n\n"
    "# Examples\n"
    "1. User: 'Mac Shooters, White Bean Crostini, Parmesan Dip'\n"
    "   Extract: raw_items=['Mac Shooters','White Bean Crostini','Parmesan Dip']\n"
    "2. User: 'option 2 and 5'\n"
    "   Extract: raw_items=['2','5']\n"
    "3. User: 'all of them'\n"
    "   Extract: raw_items=['ALL']\n"
    "4. User: 'PLATED'\n"
    "   Extract: meal_style='plated'\n"
    "5. User: 'reception only'\n"
    "   Extract: cocktail_hour=False, is_decline=True\n"
)


def _history_for_llm(history: list[BaseMessage]) -> list[dict]:
    return history_for_llm(history)


def _phase_of(slots: dict) -> str:
    """Which menu phase are we in — drives what we extract against."""
    if not is_filled(slots, "cocktail_hour"):
        return PHASE_COCKTAIL
    # Appetizers are always shown regardless of cocktail_hour/reception/both.
    # The cocktail_hour flag only affects UI labeling + service_style; it no
    # longer gates whether we collect appetizer picks.
    if not is_filled(slots, "appetizers"):
        return PHASE_COCKTAIL
    # Ask passed/station after appetizers are picked (captured via options card)
    if not is_filled(slots, "appetizer_style"):
        return PHASE_COCKTAIL
    # Show main menu first; ask plated/buffet after dishes are confirmed
    if not is_filled(slots, "selected_dishes") and not get_slot_value(slots, "custom_menu"):
        return PHASE_MAIN_MENU
    if not is_filled(slots, "meal_style"):
        return PHASE_MAIN_MENU
    if not is_filled(slots, "desserts"):
        return PHASE_DESSERT
    return PHASE_DRINKS_BAR


class MenuSelectionTool:
    name = "menu_selection_tool"

    async def run(
        self,
        *,
        message: str,
        history: list[BaseMessage],
        state: dict,
    ) -> ToolResult:
        slots = state["slots"]
        before_lists = {
            "appetizers": parse_slot_items(get_slot_value(slots, "appetizers") or ""),
            "selected_dishes": parse_slot_items(get_slot_value(slots, "selected_dishes") or ""),
            "desserts": parse_slot_items(get_slot_value(slots, "desserts") or ""),
        }
        forced_extracted: MenuSelectionExtraction | None = None

        # Override category_hint from conversation phase so the extractor
        # and the resolver agree on which menu to hit.
        phase = state.get("conversation_phase") or _phase_of(slots)
        if phase == PHASE_TRANSITION:
            phase = _phase_of(slots)
        forced_category = _forced_category_from_phase(phase)
        current_target = _next_target([], phase, slots)
        expecting_appetizer_style = current_target == "ask_appetizer_style"
        expecting_meal_style = current_target == "ask_meal_style"

        effects: list[tuple[str, str]] = []
        fills: list[tuple[str, Any]] = []
        unmatched_items: list[str] = []

        pending_choice = get_slot_value(slots, "__pending_menu_choice")
        if pending_choice:
            if not isinstance(pending_choice, dict):
                clear_slot(slots, "__pending_menu_choice")
            else:
                matches = [str(v) for v in pending_choice.get("matches") or [] if str(v).strip()]
                selected = resolve_choice_selection(message, matches)
                if not selected:
                    return self._repeat_pending_menu_choice_result(
                        state=state,
                        pending_choice=pending_choice,
                    )

                clear_slot(slots, "__pending_menu_choice")
                forced_extracted = MenuSelectionExtraction(
                    raw_items=replace_query_with_selection(
                        [str(v) for v in (pending_choice.get("raw_items") or []) if str(v).strip()],
                        query=str(pending_choice.get("query") or ""),
                        selection=selected,
                    ),
                    category_hint=str(pending_choice.get("category") or "") or forced_category,
                )

        # ----------------------------------------------------------------
        # Pre-process style button sentinel values BEFORE LLM extraction.
        # The frontend sends title-case labels ("Plated", "Passed Around",
        # "Buffet", "Station") which Pydantic's Literal validators reject
        # if the LLM echoes them without lowercasing. Intercept here so
        # the extraction path never sees these ambiguous strings.
        # ----------------------------------------------------------------
        _msg_lower = normalize_structured_choice(message)

        _MEAL_STYLE_MAP = {
            "plated": "plated", "plated-style": "plated", "plated style": "plated",
            "buffet": "buffet", "buffet-style": "buffet", "buffet style": "buffet",
            "buffet-styled": "buffet",
        }
        _SERVICE_STYLE_MAP = {
            "cocktail hour": ("cocktail_hour", True),
            "cocktail": ("cocktail_hour", True),
            "reception": ("reception", False),
            "reception only": ("reception", False),
            "full reception": ("reception", False),
            "both": ("both", True),
            "cocktail hour + reception": ("both", True),
        }
        _APP_STYLE_MAP = {
            "passed around": "passed", "passed": "passed", "pass": "passed",
            "station": "station", "stations": "station",
        }

        if _msg_lower in _MEAL_STYLE_MAP and expecting_meal_style and not is_filled(slots, "meal_style"):
            val = _MEAL_STYLE_MAP[_msg_lower]
            old = get_slot_value(slots, "meal_style")
            fill_slot(slots, "meal_style", val)
            fills.append(("meal_style", val))
            effects.extend(apply_cascade("meal_style", old, val, slots))

        if _msg_lower in _APP_STYLE_MAP and expecting_appetizer_style and not is_filled(slots, "appetizer_style"):
            val = _APP_STYLE_MAP[_msg_lower]
            fill_slot(slots, "appetizer_style", val)
            fills.append(("appetizer_style", val))

        if (
            phase == PHASE_COCKTAIL
            and not is_filled(slots, "cocktail_hour")
            and _msg_lower in _SERVICE_STYLE_MAP
        ):
            service_style, wants_cocktail = _SERVICE_STYLE_MAP[_msg_lower]
            fill_slot(slots, "service_style", service_style)
            fills.append(("service_style", service_style))
            old = get_slot_value(slots, "cocktail_hour")
            fill_slot(slots, "cocktail_hour", wants_cocktail)
            fills.append(("cocktail_hour", wants_cocktail))
            effects.extend(apply_cascade("cocktail_hour", old, wants_cocktail, slots))

        # Skip LLM extraction when the entire message was a style-only sentinel;
        # avoids the LLM re-interpreting an already-resolved click.
        _style_only = (
            _msg_lower in _MEAL_STYLE_MAP
            or _msg_lower in _APP_STYLE_MAP
            or _msg_lower in _SERVICE_STYLE_MAP
        )

        if (
            phase == PHASE_DESSERT
            and not is_filled(slots, "desserts")
            and get_slot_value(slots, "__gate_desserts") is not True
            and _msg_lower in {"yes", "yes please", "show desserts", "show me desserts", "desserts", "add desserts"}
        ):
            fill_slot(slots, "__gate_desserts", True)
            fills.append(("__gate_desserts", True))
            _style_only = True

        extracted = forced_extracted
        if not _style_only and phase == PHASE_DESSERT and not is_filled(slots, "desserts"):
            _dessert_decline_re = re.compile(
                r"(\bno(?:\s+thanks)?\b|\bnone\b|\bskip\b|\bpass\b|\bwithout\b).*desserts?"
                r"|\bdon'?t\b.*\b(?:need|want|do)\b.*desserts?"
                r"|\bno desserts?\b"
                r"|\bskip desserts?\b",
                re.IGNORECASE,
            )
            if _dessert_decline_re.search(_msg_lower):
                fill_slot(slots, "desserts", "none")
                fills.append(("desserts", "none"))
                next_phase = _phase_of(slots)
                state["conversation_phase"] = next_phase
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "filled_this_turn": fills,
                        "cascade_effects": effects,
                        "unmatched_items": [],
                        "next_phase": next_phase,
                        "current_selections": {
                            "appetizers": get_slot_value(slots, "appetizers"),
                            "selected_dishes": get_slot_value(slots, "selected_dishes"),
                            "desserts": get_slot_value(slots, "desserts"),
                        },
                        "needs_custom_menu_call": bool(get_slot_value(slots, "custom_menu")),
                        "next_question_target": _next_target(fills, next_phase, slots),
                    },
                )

        if extracted is None and not _style_only:
            extracted = await extract(
                schema=MenuSelectionExtraction,
                system=_SYSTEM_PROMPT,
                user_message=message,
                history=_history_for_llm(history),
            )

        # Auto-set cocktail_hour only for non-weddings. Weddings need the
        # explicit cocktail hour / reception / both choice, so we must not
        # silently skip that question.
        if not is_filled(slots, "cocktail_hour") and phase == PHASE_COCKTAIL:
            event_type = (get_slot_value(slots, "event_type") or "").lower()
            # Non-weddings skip the cocktail-hour-vs-reception distinction entirely:
            # appetizers are just appetizers, no style sub-question. Only weddings
            # get the cocktail hour / reception / both card.
            if "wedding" not in event_type:
                fill_slot(slots, "cocktail_hour", True)
                fills.append(("cocktail_hour", True))
                # Auto-fill appetizer_style too — non-weddings don't need the
                # passed-vs-station follow-up either.
                if not is_filled(slots, "appetizer_style"):
                    fill_slot(slots, "appetizer_style", "station")
                    fills.append(("appetizer_style", "station"))

        if extracted is not None:
            category = extracted.category_hint or forced_category

            # ---- cocktail_hour declared explicitly ----
            if extracted.cocktail_hour is not None:
                old = get_slot_value(slots, "cocktail_hour")
                fill_slot(slots, "cocktail_hour", extracted.cocktail_hour)
                fills.append(("cocktail_hour", extracted.cocktail_hour))
                if not is_filled(slots, "service_style"):
                    fill_slot(
                        slots,
                        "service_style",
                        "cocktail_hour" if extracted.cocktail_hour else "reception",
                    )
                    fills.append(("service_style", get_slot_value(slots, "service_style")))
                effects.extend(apply_cascade("cocktail_hour", old, extracted.cocktail_hour, slots))

            # ---- meal_style ----
            if (
                extracted.meal_style is not None
                and (expecting_meal_style or not extracted.raw_items)
            ):
                old = get_slot_value(slots, "meal_style")
                fill_slot(slots, "meal_style", extracted.meal_style)
                fills.append(("meal_style", extracted.meal_style))
                effects.extend(apply_cascade("meal_style", old, extracted.meal_style, slots))

            # ---- appetizer_style ----
            if (
                extracted.appetizer_style is not None
                and (expecting_appetizer_style or not extracted.raw_items)
            ):
                fill_slot(slots, "appetizer_style", extracted.appetizer_style)
                fills.append(("appetizer_style", extracted.appetizer_style))

            # ---- menu_notes ----
            if extracted.menu_notes is not None:
                fill_slot(slots, "menu_notes", extracted.menu_notes)
                fills.append(("menu_notes", extracted.menu_notes))

            # ---- custom_menu ----
            if extracted.custom_menu is True:
                old = get_slot_value(slots, "custom_menu")
                fill_slot(slots, "custom_menu", True)
                fills.append(("custom_menu", True))
                effects.extend(apply_cascade("custom_menu", old, True, slots))
                # Force followup call per spec
                fill_slot(slots, "followup_call_requested", True)
                effects.append(("followup_call_requested", "mandatory for custom menu"))

            # ---- is_decline ----
            # Guard: a short affirmative ("yes", "ok", "looks good", "sounds good",
            # "yes looks good") MUST NOT be treated as a dessert/appetizer decline.
            # These come from "want to keep going?" Yes/No cards and should be routed
            # as a proceed signal, not a skip. Decline requires explicit language
            # ("no desserts", "skip desserts", "no thanks", "none").
            _EXPLICIT_DECLINE_RE = re.compile(
                r"\b(no|none|skip|nah|nope|not (now|today|needed)|no dessert|"
                r"no appetizer|no thanks|pass on|without|skip dessert)\b",
                re.IGNORECASE,
            )
            _is_real_decline = (
                extracted.is_decline
                and bool(_EXPLICIT_DECLINE_RE.search(message))
            )
            if _is_real_decline:
                target_slot = _slot_for_category(category)
                if target_slot == "appetizers":
                    fill_slot(slots, "cocktail_hour", False)
                    fills.append(("cocktail_hour", False))
                    effects.extend(apply_cascade("cocktail_hour", True, False, slots))
                elif target_slot == "desserts":
                    fill_slot(slots, "desserts", "none")
                    fills.append(("desserts", "none"))

            # Fallback: the extractor sometimes collapses a clearly-listed set
            # of items into a single raw_item. Re-split ONLY when we have
            # strong evidence of a list — the user's message has ≥2 commas, or
            # the single raw_item value itself contains commas.
            if (
                extracted.raw_items
                and not extracted.is_decline
                and len(extracted.raw_items) == 1
            ):
                single = extracted.raw_items[0]
                msg_commas = message.count(",")
                if msg_commas >= 2 or single.count(",") >= 1:
                    _parsed = _split_user_items(message)
                    if len(_parsed) > 1:
                        extracted.raw_items = _parsed

            # ---- raw_items → DB resolution ----
            if extracted.raw_items and not extracted.is_decline:
                resolved_result = await self._resolve_raw_items(
                    extracted.raw_items, category, slots
                )
                for target_slot, resolved_value, matched_count in resolved_result:
                    if target_slot == "__ambiguous__":
                        pending_choice = get_slot_value(slots, "__pending_menu_choice") or {}
                        return self._repeat_pending_menu_choice_result(
                            state=state,
                            pending_choice=pending_choice,
                        )
                    if target_slot == "__dessert_overflow__":
                        # Hard cap exceeded — reject selection and reshow the menu
                        state["conversation_phase"] = PHASE_DESSERT
                        overflow_hint = await _input_hint_for_menu_phase(PHASE_DESSERT, slots)
                        menu_text = (
                            _format_menu_response(PHASE_DESSERT, overflow_hint, slots)
                            if overflow_hint else ""
                        )
                        return ToolResult(
                            state=state,
                            response_context={
                                "tool": self.name,
                                "filled_this_turn": [],
                                "cascade_effects": [],
                                "unmatched_items": [],
                                "next_phase": PHASE_DESSERT,
                                "current_selections": {
                                    "appetizers": get_slot_value(slots, "appetizers"),
                                    "selected_dishes": get_slot_value(slots, "selected_dishes"),
                                    "desserts": get_slot_value(slots, "desserts"),
                                },
                                "needs_custom_menu_call": bool(get_slot_value(slots, "custom_menu")),
                                "next_question_target": "show_dessert_menu",
                                "dessert_overflow": matched_count,
                            },
                            input_hint=overflow_hint,
                            direct_response=(
                                f"You picked {matched_count} desserts, but the max is 4. "
                                f"Please narrow it down and pick up to 4.\n\n{menu_text}"
                            ),
                        )
                    if matched_count > 0:
                        fill_slot(slots, target_slot, resolved_value)
                        fills.append((target_slot, resolved_value))
                    else:
                        unmatched_items.extend(extracted.raw_items)

        # ---- Advance phase ----
        next_phase = _phase_of(slots)
        state["conversation_phase"] = next_phase

        response_context = {
            "tool": self.name,
            "filled_this_turn": fills,
            "cascade_effects": effects,
            "unmatched_items": unmatched_items,
            "next_phase": next_phase,
            "current_selections": {
                "appetizers": get_slot_value(slots, "appetizers"),
                "selected_dishes": get_slot_value(slots, "selected_dishes"),
                "desserts": get_slot_value(slots, "desserts"),
            },
            "needs_custom_menu_call": bool(get_slot_value(slots, "custom_menu")),
            "next_question_target": _next_target(fills, next_phase, slots),
        }

        # ---- Desserts gate — ask Yes/No before showing the full menu ----
        # First time we land on PHASE_DESSERT with nothing resolved yet, show a
        # simple affirmation card. After user says yes (gate is set), show the menu.
        # If user says "no/skip", is_decline sets desserts="none" and phase advances.
        if next_phase == PHASE_DESSERT and not is_filled(slots, "desserts"):
            if get_slot_value(slots, "__gate_desserts") is not True:
                fill_slot(slots, "__gate_desserts", "asked")
                state["conversation_phase"] = PHASE_DESSERT
                return ToolResult(
                    state=state,
                    response_context={**response_context, "asking_gate": "desserts"},
                    input_hint={
                        "type": "options",
                        "options": [
                            {"value": "yes", "label": "Yes, add desserts"},
                            {"value": "skip dessert", "label": "No thanks, skip"},
                        ],
                    },
                    direct_response="Would you like to add desserts, or skip them?",
                )

        input_hint = await _input_hint_for_menu_phase(next_phase, slots)
        if response_context["next_question_target"] == "transition_to_addons":
            input_hint = _addons_transition_hint()

        # Show numbered menu list when no items were selected this turn AND we are
        # not at a style-question sub-phase (those are handled by the LLM via
        # detectInlineChoices on the frontend).
        no_items_selected = not any(
            s for s, _ in fills if s in ("appetizers", "selected_dishes", "desserts")
        )
        asking_style = (
            (next_phase == PHASE_COCKTAIL and not is_filled(slots, "cocktail_hour"))
            or (next_phase == PHASE_COCKTAIL and is_filled(slots, "appetizers") and not is_filled(slots, "appetizer_style"))
            or (next_phase == PHASE_MAIN_MENU and is_filled(slots, "selected_dishes") and not is_filled(slots, "meal_style"))
        )
        direct_response: str | None = None
        progress_response = _build_menu_turn_response(
            before_lists=before_lists,
            fills=fills,
            next_phase=next_phase,
            next_target=response_context["next_question_target"],
            input_hint=input_hint,
            slots=slots,
        )
        if progress_response:
            response_context["menu_progress"] = progress_response
        elif no_items_selected and input_hint and not asking_style:
            # Show DB-driven numbered menu list — LLM can't generate real item names.
            # Style question turns and acks are handled by the LLM naturally.
            menu_text = _format_menu_response(next_phase, input_hint, slots)
            if menu_text:
                direct_response = menu_text
        return ToolResult(
            state=state,
            response_context=response_context,
            input_hint=input_hint,
            direct_response=direct_response,
        )

    def _repeat_pending_menu_choice_result(
        self,
        *,
        state: dict,
        pending_choice: dict[str, Any],
    ) -> ToolResult:
        matches = [str(v) for v in pending_choice.get("matches") or [] if str(v).strip()]
        options = [{"value": item, "label": item} for item in matches]
        category = _slot_for_category(str(pending_choice.get("category") or ""))
        label = {
            "appetizers": "appetizer",
            "selected_dishes": "main dish",
            "desserts": "dessert",
        }.get(category, "menu item")
        query = str(pending_choice.get("query") or "")
        prompt = (
            f"I found more than one {label} match for '{query}'. Which one do you want?\n\n"
            + "\n".join(f"{idx}. {item}" for idx, item in enumerate(matches, 1))
        )
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "error": "ambiguous_menu_item",
                "ambiguous_query": query,
                "ambiguous_matches": matches,
            },
            input_hint={
                "type": "options",
                "options": options,
            },
            direct_response=prompt,
        )

    # ------------------------------------------------------------------
    # Resolution paths — each category has its own menu scope
    # ------------------------------------------------------------------

    async def _resolve_raw_items(
        self,
        raw_items: list[str],
        category: str | None,
        slots: dict,
    ) -> list[tuple[str, str, int]]:
        """Resolve raw_items into (slot_name, formatted_value, matched_count).

        Returns a list because 'ALL' on a multi-category context may spread to
        multiple slots, but in practice we return a single entry.
        """
        if not raw_items:
            return []

        target_slot = _slot_for_category(category)

        # Load the correct scoped menu
        if target_slot == "appetizers":
            scoped_menu = await load_appetizer_menu()
        elif target_slot == "selected_dishes":
            scoped_menu = await load_main_dish_menu()
        elif target_slot == "desserts":
            return await self._resolve_desserts(raw_items, slots)
        else:
            # Unknown target — skip
            return []

        existing_names = parse_slot_items(get_slot_value(slots, target_slot) or "")

        if len(raw_items) == 1 and raw_items[0].strip().upper() == "ALL":
            resolution = await resolve_menu_items(
                ", ".join(item["name"] for catitems in scoped_menu.values() for item in catitems),
                menu=scoped_menu,
            )
        else:
            resolution = await resolve_menu_items(
                raw_items,
                menu=scoped_menu,
                existing_names=existing_names,
            )

        if resolution.ambiguous_choices:
            ambiguous = resolution.ambiguous_choices[0]
            fill_slot(
                slots,
                "__pending_menu_choice",
                {
                    "category": category or ("desserts" if target_slot == "desserts" else "dishes"),
                    "query": ambiguous.query,
                    "matches": ambiguous.matches,
                    "raw_items": raw_items,
                },
            )
            return [("__ambiguous__", ambiguous.query, len(ambiguous.matches))]

        matched = resolution.matched_items
        resolved_text = resolution.formatted_value

        # Merge with existing — never replace silently
        if existing_names and matched:
            cur_val = get_slot_value(slots, target_slot) or ""
            if cur_val and cur_val.lower() not in ("none", "no", ""):
                resolved_text = cur_val + ", " + resolved_text

        return [(target_slot, resolved_text, len(matched))]

    async def _resolve_desserts(
        self,
        raw_items: list[str],
        slots: dict,
    ) -> list[tuple[str, str, int]]:
        event_type = (get_slot_value(slots, "event_type") or "").lower()
        is_wedding = "wedding" in event_type
        existing_names = parse_slot_items(get_slot_value(slots, "desserts") or "")
        resolution = await resolve_dessert_choices(
            raw_items,
            is_wedding=is_wedding,
            existing_names=existing_names,
        )
        if resolution.ambiguous_choices:
            ambiguous = resolution.ambiguous_choices[0]
            fill_slot(
                slots,
                "__pending_menu_choice",
                {
                    "category": "desserts",
                    "query": ambiguous.query,
                    "matches": ambiguous.matches,
                    "raw_items": raw_items,
                },
            )
            return [("__ambiguous__", ambiguous.query, len(ambiguous.matches))]
        matched = resolution.matched_items

        # Dedup + merge with existing
        existing_lower = {n.lower() for n in existing_names}
        combined_names = list(existing_names) + [
            m["name"] for m in matched if m["name"].lower() not in existing_lower
        ]

        # Hard cap: 4 desserts max. Return a special signal when exceeded so
        # the caller can reject and reshow the menu.
        _MAX_DESSERTS = 4
        if len(combined_names) > _MAX_DESSERTS:
            return [("__dessert_overflow__", str(len(combined_names)), len(combined_names))]

        if not combined_names:
            return [("desserts", get_slot_value(slots, "desserts") or "", 0)]

        # Look up price rows for formatted output
        expanded = await load_dessert_menu_expanded(is_wedding=is_wedding)
        by_name = {i["name"].lower(): i for i in expanded}
        final_items = [by_name[n.lower()] for n in combined_names if n.lower() in by_name]
        return [("desserts", format_items(final_items), len(matched))]


# ----------------------------------------------------------------------------

def _split_user_items(message: str) -> list[str]:
    """Split the user's message into candidate item names.

    Comma-safe: 'Meatballs (BBQ, Swedish)' stays intact because we only split on
    top-level commas. Also handles ' and ' joins and semicolons.
    """
    import re as _re

    if not message:
        return []
    text = message.strip()
    parts = _re.split(r"[;\n]+|,(?![^(]*\))", text)
    expanded: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if " and " in p and "(" not in p:
            expanded.extend(x.strip() for x in p.split(" and ") if x.strip())
        else:
            expanded.append(p)
    # Drop very short fragments that are almost certainly noise
    return [e for e in expanded if len(e) >= 3]


def _slot_for_category(category: str | None) -> str:
    if category == "appetizers":
        return "appetizers"
    if category == "desserts":
        return "desserts"
    return "selected_dishes"


def _forced_category_from_phase(phase: str) -> str | None:
    if phase == PHASE_COCKTAIL:
        return "appetizers"
    if phase == PHASE_MAIN_MENU:
        return "dishes"
    if phase == PHASE_DESSERT:
        return "desserts"
    return None


def _next_target(fills: list[tuple[str, Any]], next_phase: str, slots: dict) -> str:
    if next_phase == PHASE_COCKTAIL:
        if not is_filled(slots, "cocktail_hour"):
            return "ask_service_style"  # cocktail hour / reception / both
        if is_filled(slots, "appetizers") and not is_filled(slots, "appetizer_style"):
            return "ask_appetizer_style"
        return "show_appetizer_menu"
    if next_phase == PHASE_MAIN_MENU:
        if is_filled(slots, "selected_dishes") and not is_filled(slots, "meal_style"):
            return "ask_meal_style"
        return "show_main_menu"
    if next_phase == PHASE_DESSERT:
        return "show_dessert_menu"
    if next_phase == PHASE_DRINKS_BAR:
        return "transition_to_addons"
    return "continue"


def _addons_transition_hint() -> dict:
    return {
        "type": "options",
        "options": [
            {"value": "yes", "label": "Yes, add drinks"},
            {"value": "no", "label": "No thanks"},
        ],
    }


async def _input_hint_for_menu_phase(phase: str, slots: dict) -> dict | None:
    if phase == PHASE_COCKTAIL:
        if not is_filled(slots, "cocktail_hour"):
            # Wedding only — ask cocktail hour vs reception
            return {
                "type": "options",
                "options": [
                    {"value": "cocktail hour", "label": "Cocktail hour"},
                    {"value": "reception", "label": "Reception"},
                    {"value": "both", "label": "Both"},
                ],
            }
        if is_filled(slots, "appetizers") and not is_filled(slots, "appetizer_style"):
            return {
                "type": "options",
                "options": [
                    {"value": "passed", "label": "Passed around"},
                    {"value": "station", "label": "At a station"},
                ],
            }
        menu = await load_appetizer_menu()
        return {"type": "menu_picker", "category": "appetizers", "menu": _serialize_menu(menu)}
    if phase == PHASE_MAIN_MENU:
        if is_filled(slots, "selected_dishes") and not is_filled(slots, "meal_style"):
            return {
                "type": "options",
                "options": [
                    {"value": "plated", "label": "Plated"},
                    {"value": "buffet", "label": "Buffet-style"},
                ],
            }
        menu = await load_main_dish_menu()
        return {"type": "menu_picker", "category": "dishes", "menu": _serialize_menu(menu)}
    if phase == PHASE_DESSERT:
        items = await load_dessert_menu_expanded(
            is_wedding="wedding" in (get_slot_value(slots, "event_type") or "").lower()
        )
        return {"type": "menu_picker", "category": "desserts", "items": items, "max_select": 4}
    return None


def _serialize_menu(menu: dict[str, list[dict]]) -> list[dict]:
    return [
        {
            "category": cat,
            "items": [
                {
                    "name": item["name"],
                    "unit_price": item.get("unit_price"),
                    "price_type": item.get("price_type"),
                    "description": item.get("description"),
                }
                for item in items
            ],
        }
        for cat, items in menu.items()
    ]





def _format_menu_response(phase: str, hint: dict, slots: dict) -> str | None:
    """Return a numbered-list menu string — frontend parses this into selectable cards."""
    if phase == PHASE_COCKTAIL:
        menu_cats = hint.get("menu", [])
        lines: list[str] = []
        n = 1
        for cat in menu_cats:
            for item in cat.get("items", []):
                price = item.get("unit_price")
                price_type = item.get("price_type", "per_person")
                price_str = f"(${price:.2f}/{price_type})" if price else ""
                lines.append(f"{n}. {item['name']} {price_str}".strip())
                n += 1
        if not lines:
            return None
        return "Here are the appetizer options:\n" + "\n".join(lines) + "\nPick as many as you'd like!"

    if phase == PHASE_MAIN_MENU:
        menu_cats = hint.get("menu", [])
        lines = []
        n = 1
        for cat in menu_cats:
            cat_name = cat.get("category", "")
            if cat_name:
                lines.append(f"\n{cat_name}")
            for item in cat.get("items", []):
                price = item.get("unit_price")
                price_type = item.get("price_type", "per_person")
                price_str = f"(${price:.2f}/{price_type})" if price else ""
                lines.append(f"{n}. {item['name']} {price_str}".strip())
                n += 1
        if not lines:
            return None
        return "Here's the main menu:\n" + "\n".join(lines) + "\nPick 3 to 5 dishes!"

    if phase == PHASE_DESSERT:
        items = hint.get("items", [])
        lines = []
        for i, item in enumerate(items, 1):
            price = item.get("unit_price")
            price_type = item.get("price_type", "per_person")
            if price_type == "flat":
                price_str = f"(${price:.2f})" if price else ""
            elif price_type == "per_unit":
                price_str = f"(${price:.2f}/per_unit)" if price else ""
            else:
                price_str = f"(${price:.2f}/per_person)" if price else ""
            lines.append(f"{i}. {item['name']} {price_str}".strip())
        if not lines:
            return None
        max_s = hint.get("max_select", 4)
        return "Awesome, let's add some desserts! Here are the dessert options:\n" + "\n".join(lines) + f"\nPick up to {max_s}!"

    return None


def _build_menu_turn_response(
    *,
    before_lists: dict[str, list[str]],
    fills: list[tuple[str, Any]],
    next_phase: str,
    next_target: str,
    input_hint: dict | None,
    slots: dict,
) -> str | None:
    filled_slots = {slot for slot, _ in fills}

    if "service_style" in filled_slots or "cocktail_hour" in filled_slots:
        service_style = str(get_slot_value(slots, "service_style") or "").lower()
        if service_style == "both":
            lead = "Got it — we will plan for both cocktail hour and reception."
        elif service_style == "reception":
            lead = "Got it — we will plan for the reception."
        else:
            lead = "Got it — we will plan for cocktail hour."
        menu_text = _format_menu_response(next_phase, input_hint, slots) if input_hint else None
        return lead + ("\n\n" + menu_text if menu_text else "")

    if "appetizers" in filled_slots:
        lead = _list_progress_message(
            label="appetizers",
            before=before_lists["appetizers"],
            after=parse_slot_items(get_slot_value(slots, "appetizers") or ""),
        )
        if next_target == "ask_appetizer_style":
            return (
                lead
                + "\n\nHow would you like the appetizers served: passed around by servers, or set up at a station?"
            )
        return lead

    if "appetizer_style" in filled_slots:
        style = str(get_slot_value(slots, "appetizer_style") or "").lower()
        lead = (
            "Perfect — we will have the appetizers passed around."
            if style == "passed"
            else "Perfect — we will set the appetizers at a station."
        )
        menu_text = _format_menu_response(next_phase, input_hint, slots) if input_hint else None
        return lead + ("\n\n" + menu_text if menu_text else "")

    if "selected_dishes" in filled_slots:
        lead = _list_progress_message(
            label="main dishes",
            before=before_lists["selected_dishes"],
            after=parse_slot_items(get_slot_value(slots, "selected_dishes") or ""),
        )
        if next_target == "ask_meal_style":
            return lead + "\n\nWould you like the meal served plated or buffet-style?"
        return lead

    if "meal_style" in filled_slots:
        meal_style = str(get_slot_value(slots, "meal_style") or "").lower()
        if meal_style == "plated":
            return "Perfect — we will serve the meal plated."
        if meal_style == "buffet":
            return "Perfect — we will serve the meal buffet-style."

    if "desserts" in filled_slots:
        lead = _list_progress_message(
            label="desserts",
            before=before_lists["desserts"],
            after=parse_slot_items(get_slot_value(slots, "desserts") or ""),
        )
        if next_target == "transition_to_addons":
            return lead + "\n\nWould you like to add drinks or bar service for the event?"
        return lead

    if next_target == "ask_service_style":
        return "For the wedding, would you like to have a cocktail hour before the main meal, a reception for the main meal, or both?"
    if next_target == "ask_appetizer_style":
        return "How would you like the appetizers served? Would you like servers to walk around with them, or have them set up at a station?"
    if next_target == "ask_meal_style":
        return "Would you like the meal served plated at the tables, or as a buffet where guests serve themselves?"
    if next_target == "transition_to_addons":
        return "Would you like to add drinks, coffee, or bar service for the event?"
    return None


def _list_progress_message(*, label: str, before: list[str], after: list[str]) -> str:
    before_lower = {item.lower() for item in before}
    after_lower = {item.lower() for item in after}
    added = [item for item in after if item.lower() not in before_lower]
    removed = [item for item in before if item.lower() not in after_lower]

    if added and removed:
        lead = (
            f"Updated your {label}: removed {', '.join(removed)} and added {', '.join(added)}."
        )
    elif added:
        lead = f"Added {', '.join(added)}."
    elif removed:
        lead = f"Removed {', '.join(removed)}."
    else:
        lead = f"Your {label} are set."

    if after:
        return lead + f" Your {label} are now: {', '.join(after)}."
    return lead + f" Your {label} list is empty now."


__all__ = ["MenuSelectionTool"]

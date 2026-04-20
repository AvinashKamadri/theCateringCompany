"""
ModificationTool — handles every change/correction/mid-flow edit.

Replaces the old `check_modifications.py` regex soup. Uses Instructor to
extract (target_slot, action, items_to_remove, items_to_add) in a single
structured call. Applies via the cascade map so dependents stay consistent.

Rules this tool enforces:
- `target_slot` must be in SLOT_NAMES. Unknown slot → reject, ask clarifying.
- `bartender` and `conversation_status` are locked — never modifiable.
- List slots (appetizers, selected_dishes, desserts, rentals) support
  remove / replace / add with resolution through the menu resolver.
- Scalar slot changes go through the BasicInfoTool / AddOnsTool extraction
  paths so validators (future date, enum literals) still run.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import BaseMessage

from agent.cascade import apply_cascade
from agent.instructor_client import extract
from agent.menu_resolver import (
    format_items,
    load_appetizer_menu,
    load_dessert_menu_expanded,
    load_main_dish_menu,
    parse_slot_items,
    resolve_desserts,
    resolve_to_db_items,
)
from agent.models import (
    EventDetailsExtraction,
    ModificationExtraction,
)
from agent.state import (
    LOCKED_SLOTS,
    PHASE_COCKTAIL,
    PHASE_CONDITIONAL_FOLLOWUP,
    PHASE_DESSERT,
    PHASE_DIETARY,
    PHASE_DRINKS_BAR,
    PHASE_EVENT_DATE,
    PHASE_EVENT_TYPE,
    PHASE_FOLLOWUP,
    PHASE_GREETING,
    PHASE_GUEST_COUNT,
    PHASE_LABOR,
    PHASE_MAIN_MENU,
    PHASE_RENTALS,
    PHASE_REVIEW,
    PHASE_SERVICE_TYPE,
    PHASE_SPECIAL_REQUESTS,
    PHASE_TABLEWARE,
    PHASE_TRANSITION,
    PHASE_VENUE,
    SLOT_NAMES,
    clear_slot,
    fill_slot,
    get_slot_value,
    is_filled,
)
from agent.tools.add_ons_tool import (
    _direct_response_for_target as _addons_direct_response_for_target,
    _input_hint_for_target as _addons_input_hint_for_target,
    _next_target as _addons_next_target,
)
from agent.tools.basic_info_tool import _normalize_tbd_venue
from agent.tools.basic_info_tool import (
    _input_hint_for_phase as _basic_input_hint_for_phase,
    _phase_to_question as _basic_phase_to_question,
)
from agent.tools.base import ToolResult
from agent.tools.finalization_tool import (
    _client_facing_summary as _finalization_client_facing_summary,
    _direct_response_for_target as _finalization_direct_response_for_target,
    _input_hint_for_target as _finalization_input_hint_for_target,
    _next_target as _finalization_next_target,
    _render_review_recap as _render_final_review_recap,
)
from agent.tools.menu_selection_tool import (
    _addons_transition_hint,
    _format_menu_response as _format_menu_turn_response,
    _input_hint_for_menu_phase as _menu_input_hint_for_menu_phase,
    _next_target as _menu_next_target,
)


_SYSTEM_PROMPT = (
    "The customer wants to change a previously provided answer. "
    "Figure out WHICH slot and HOW.\n\n"
    "target_slot MUST be one of:\n"
    f"{', '.join(SLOT_NAMES)}\n\n"
    "Map natural language to slot names:\n"
    "- 'name / first name / my name' → name\n"
    "- 'email' → email | 'phone' → phone\n"
    "- 'date / when' → event_date | 'venue / location / place' → venue\n"
    "- 'guests / headcount' → guest_count\n"
    "- 'apps / appetizers / starters' → appetizers\n"
    "- 'mains / main dishes / entrees / menu' → selected_dishes\n"
    "- 'dessert / desserts / coffee bar / cookies' → desserts\n"
    "- 'bar / bar service' → bar_service | 'bar package' → bar_package\n"
    "- 'drinks' → drinks | 'coffee' → coffee_service\n"
    "- 'plates / tableware / china / disposable' → tableware\n"
    "- 'utensils / cutlery' → utensils\n"
    "- 'linens' → linens\n\n"
    "action: 'add', 'remove', or 'replace'.\n"
    "items_to_remove: for list slots on remove/replace, the exact items.\n"
    "items_to_add: for list slots on add/replace, the exact items.\n"
    "new_value: for scalar slots, the new value as a string."
)

_LIST_SLOTS = {"appetizers", "selected_dishes", "desserts", "rentals"}
_APPENDABLE_TEXT_SLOTS = {"special_requests", "dietary_concerns", "additional_notes"}


def _infer_note_slot_from_message(message: str) -> str | None:
    msg = (message or "").strip().lower()
    if not msg:
        return None
    if any(term in msg for term in {"dietary", "allerg", "allergy", "kosher", "vegan", "gluten", "diabet"}):
        return "dietary_concerns"
    if any(term in msg for term in {"special request", "bouquet", "flowers", "flower", "decor"}):
        return "special_requests"
    if any(term in msg for term in {"additional note", "final note", "note for the team", "keep in mind"}):
        return "additional_notes"
    return None


def _history_for_llm(history: list[BaseMessage]) -> list[dict]:
    out: list[dict] = []
    for m in history[-6:]:
        role = "user" if getattr(m, "type", "") == "human" else "assistant"
        out.append({"role": role, "content": m.content})
    return out


class ModificationTool:
    name = "modification_tool"

    async def run(
        self,
        *,
        message: str,
        history: list[BaseMessage],
        state: dict,
    ) -> ToolResult:
        slots = state["slots"]

        # Surface the current list contents to the LLM so it can pick the
        # right target_slot and item names regardless of which phase we're in.
        context_block = _current_lists_context(slots)
        system_with_ctx = _SYSTEM_PROMPT + "\n\n" + context_block if context_block else _SYSTEM_PROMPT

        extracted = await extract(
            schema=ModificationExtraction,
            system=system_with_ctx,
            user_message=message,
            history=_history_for_llm(history),
            max_tokens=1000,
        )

        if extracted is None:
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "error": "could_not_parse",
                    "message": "What would you like to change?",
                },
            )

        inferred_note_slot = _infer_note_slot_from_message(message)
        if inferred_note_slot and extracted.target_slot in {"special_requests", "dietary_concerns", "additional_notes"}:
            extracted.target_slot = inferred_note_slot

        target_slot = extracted.target_slot

        # Membership-based correction: if the items to remove/replace appear in
        # a DIFFERENT list slot than the LLM picked, re-route. The router-picked
        # target is often biased by conversation phase (e.g. phase=main_menu
        # makes the LLM assume selected_dishes) but the user may be editing an
        # already-filled appetizer or dessert.
        if target_slot in _LIST_SLOTS or target_slot in SLOT_NAMES:
            corrected = _reroute_by_membership(extracted, slots)
            if corrected and corrected != target_slot:
                extracted.target_slot = corrected
                target_slot = corrected

        # Reject unknown or locked slots
        if target_slot not in SLOT_NAMES:
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "error": "unknown_slot",
                    "target_slot": target_slot,
                },
            )
        if target_slot in LOCKED_SLOTS:
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "error": "locked_slot",
                    "target_slot": target_slot,
                },
            )

        if target_slot in _LIST_SLOTS:
            # If user asked to change a list slot without naming specific items
            # (e.g. "change my appetizers"), clear the slot and bounce back to
            # the menu selector so they can re-pick from the catalog.
            if _is_unspecified_list_change(extracted) or _is_generic_list_reopen_request(message, extracted):
                return await self._reopen_list_slot(target_slot, slots, state)
            return await self._apply_list_modification(extracted, slots, state)

        return await self._apply_scalar_modification(extracted, message, slots, state, history)

    # ------------------------------------------------------------------

    async def _apply_list_modification(
        self,
        mod: ModificationExtraction,
        slots: dict,
        state: dict,
    ) -> ToolResult:
        target_slot = mod.target_slot
        current_value = get_slot_value(slots, target_slot) or ""
        current_items = parse_slot_items(current_value)

        menu = await self._menu_for_slot(target_slot, slots)

        # Compute remove + add sets
        remove_texts = list(mod.items_to_remove or [])
        add_texts = list(mod.items_to_add or [])
        if mod.action == "remove" and not remove_texts and mod.new_value:
            remove_texts = [str(mod.new_value)]
        if mod.action == "add" and not add_texts and mod.new_value:
            add_texts = [str(mod.new_value)]
        if mod.action == "replace" and not add_texts and mod.new_value:
            add_texts = [str(mod.new_value)]

        # --- Remove phase ---
        remaining = list(current_items)
        if remove_texts:
            remove_keywords = [t.strip().lower() for t in remove_texts if t.strip()]
            remaining = [
                name for name in remaining
                if not any(
                    kw and (kw in name.lower() or name.lower() in kw)
                    for kw in remove_keywords
                )
            ]

        # --- Add / replace phase ---
        added_items_resolved: list[dict] = []
        if add_texts:
            add_joined = ", ".join(add_texts)
            if target_slot == "desserts":
                event_type = (get_slot_value(slots, "event_type") or "").lower()
                matched = await resolve_desserts(
                    add_texts,
                    is_wedding="wedding" in event_type,
                    existing_names=remaining,
                )
                added_items_resolved = matched
            else:
                matched, _ = await resolve_to_db_items(
                    add_joined, menu=menu, existing_names=remaining
                )
                added_items_resolved = matched

        # Combine
        combined_names = list(remaining) + [i["name"] for i in added_items_resolved]

        # Format using canonical menu prices
        final_value: str
        if target_slot == "desserts":
            expanded = await load_dessert_menu_expanded(
                is_wedding="wedding" in (get_slot_value(slots, "event_type") or "").lower()
            )
            by_name = {i["name"].lower(): i for i in expanded}
            final_items = [by_name[n.lower()] for n in combined_names if n.lower() in by_name]
            final_value = format_items(final_items) if final_items else "none"
        elif target_slot == "rentals":
            final_value = ", ".join(combined_names) if combined_names else "none"
        else:
            # appetizers / selected_dishes — re-resolve through main menu for prices
            if combined_names:
                joined = ", ".join(combined_names)
                _, final_value = await resolve_to_db_items(joined, menu=menu)
            else:
                final_value = "none"

        old_value = get_slot_value(slots, target_slot)
        fill_slot(slots, target_slot, final_value)
        effects = apply_cascade(target_slot, old_value, final_value, slots)

        direct = _list_mod_ack(
            target_slot=target_slot,
            removed=remove_texts,
            added=[i["name"] for i in added_items_resolved],
            new_value=final_value,
        )
        next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
            slots=slots,
            state=state,
        )
        direct_response = _compose_direct_response(direct, resume_prompt)

        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "modification": {
                    "target_slot": target_slot,
                    "action": mod.action,
                    "removed": remove_texts,
                    "added": [i["name"] for i in added_items_resolved],
                    "old_value": old_value,
                    "new_value": final_value,
                    "mod_ack_text": direct,
                },
                "cascade_effects": effects,
                "next_phase": next_phase,
                "next_question_target": next_target,
            },
            direct_response=direct_response,
            input_hint=input_hint,
        )

    async def _apply_scalar_modification(
        self,
        mod: ModificationExtraction,
        message: str,
        slots: dict,
        state: dict,
        history: list[BaseMessage],
    ) -> ToolResult:
        target_slot = mod.target_slot
        new_value = mod.new_value

        # For slots that have validators (date, enums), re-run full extraction
        # so Pydantic rejects invalid values instead of corrupting state.
        if target_slot in {
            "event_date", "event_type", "service_type", "guest_count",
            "email", "phone", "venue", "name",
            "partner_name", "company_name", "honoree_name",
        }:
            if target_slot == "venue":
                normalized_tbd_venue = _normalize_tbd_venue(message.strip().lower())
                if normalized_tbd_venue:
                    old = get_slot_value(slots, "venue")
                    fill_slot(slots, "venue", normalized_tbd_venue)
                    apply_cascade("venue", old, normalized_tbd_venue, slots)

                    ack_text = _scalar_mod_ack_text(
                        target_slot=target_slot,
                        action=mod.action,
                        new_value=normalized_tbd_venue,
                    )
                    next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                        slots=slots,
                        state=state,
                    )
                    return ToolResult(
                        state=state,
                        response_context={
                            "tool": self.name,
                            "modification": {
                                "target_slot": target_slot,
                                "action": mod.action,
                                "new_value": normalized_tbd_venue,
                                "mod_ack_text": ack_text,
                            },
                            "next_phase": next_phase,
                            "next_question_target": next_target,
                        },
                        direct_response=_compose_direct_response(ack_text, resume_prompt),
                        input_hint=input_hint,
                    )
            # Use BasicInfoTool's extractor. Pass the raw user message for best parsing.
            event_extracted = await extract(
                schema=EventDetailsExtraction,
                system=(
                    "Extract the new value for an existing event detail. "
                    "Only fill the field the user is changing. "
                    "Apply all validators (future dates only, positive guest count)."
                ),
                user_message=message,
                history=_history_for_llm(history),
            )
            if event_extracted is not None:
                for fname, value in event_extracted.model_dump(exclude_none=True).items():
                    if fname != target_slot:
                        # Accept any field the extractor picked up confidently
                        pass
                    if fname == "event_date" and hasattr(value, "isoformat"):
                        value = value.isoformat()
                    old = get_slot_value(slots, fname)
                    fill_slot(slots, fname, value)
                    apply_cascade(fname, old, value, slots)

                final_value = get_slot_value(slots, target_slot)
                ack_text = _scalar_mod_ack_text(
                    target_slot=target_slot,
                    action=mod.action,
                    new_value=final_value,
                )
                next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                    slots=slots,
                    state=state,
                )

                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "modification": {
                            "target_slot": target_slot,
                            "action": mod.action,
                            "new_value": final_value,
                            "mod_ack_text": ack_text,
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                    },
                    direct_response=_compose_direct_response(ack_text, resume_prompt),
                    input_hint=input_hint,
                )
            else:
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "error": "invalid_new_value",
                        "target_slot": target_slot,
                    },
                )

        # Plain scalar — just write
        old_value = get_slot_value(slots, target_slot)
        if mod.action == "remove":
            clear_slot(slots, target_slot)
            final = None
        elif new_value is None:
            next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                slots=slots,
                state=state,
            )
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "error": "invalid_new_value",
                    "modification": {
                        "target_slot": target_slot,
                        "action": mod.action,
                        "old_value": old_value,
                        "new_value": old_value,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                },
                direct_response=resume_prompt,
                input_hint=input_hint,
            )
        else:
            if (
                target_slot in _APPENDABLE_TEXT_SLOTS
                and mod.action == "add"
                and old_value not in (None, "", "none")
            ):
                old_text = str(old_value).strip()
                new_text = str(new_value).strip()
                if new_text.lower() in old_text.lower():
                    final = old_text
                else:
                    final = f"{old_text}; {new_text}"
                fill_slot(slots, target_slot, final)
            else:
                fill_slot(slots, target_slot, new_value)
                final = new_value

        effects = apply_cascade(target_slot, old_value, final, slots)
        ack_text = _scalar_mod_ack_text(
            target_slot=target_slot,
            action=mod.action,
            new_value=final,
        )
        next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
            slots=slots,
            state=state,
        )
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "modification": {
                    "target_slot": target_slot,
                    "action": mod.action,
                    "old_value": old_value,
                    "new_value": final,
                    "mod_ack_text": ack_text,
                },
                "cascade_effects": effects,
                "next_phase": next_phase,
                "next_question_target": next_target,
            },
            direct_response=_compose_direct_response(ack_text, resume_prompt),
            input_hint=input_hint,
        )

    async def _reopen_list_slot(
        self,
        target_slot: str,
        slots: dict,
        state: dict,
    ) -> ToolResult:
        """Clear the requested list slot and hand control back to menu selection
        so the user can re-pick from the catalog. Dependent style slots (e.g.
        appetizer_style, meal_style) also reset so the follow-up prompt fires."""
        old_value = get_slot_value(slots, target_slot)
        clear_slot(slots, target_slot)
        if target_slot == "desserts" and is_filled(slots, "__gate_desserts"):
            clear_slot(slots, "__gate_desserts")
        if target_slot == "appetizers" and is_filled(slots, "appetizer_style"):
            clear_slot(slots, "appetizer_style")
        if target_slot == "selected_dishes" and is_filled(slots, "meal_style"):
            clear_slot(slots, "meal_style")

        next_phase = _LIST_SLOT_TO_PHASE.get(target_slot)
        if next_phase:
            state["conversation_phase"] = next_phase

        pretty = _SLOT_PRETTY.get(target_slot, target_slot)
        menu_text, input_hint = await self._render_slot_menu(target_slot, slots)
        header = f"No problem — let's redo your {pretty}. Pick whatever you'd like:"
        direct = header + "\n\n" + menu_text if menu_text else header

        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "modification": {
                    "target_slot": target_slot,
                    "action": "reopen",
                    "old_value": old_value,
                    "new_value": None,
                },
                "next_phase": next_phase,
            },
            direct_response=direct,
            input_hint=input_hint,
        )

    async def _render_slot_menu(
        self,
        target_slot: str,
        slots: dict,
    ) -> tuple[str | None, dict | None]:
        """Format the catalog for `target_slot` as a numbered list (so the
        frontend renders selectable cards) plus an input_hint."""
        if target_slot == "appetizers":
            menu = await load_appetizer_menu()
            return _format_scoped_menu(menu, "appetizers"), {
                "type": "menu_picker",
                "category": "appetizers",
                "menu": _serialize_menu(menu),
            }
        if target_slot == "selected_dishes":
            menu = await load_main_dish_menu()
            return _format_scoped_menu(menu, "dishes"), {
                "type": "menu_picker",
                "category": "dishes",
                "menu": _serialize_menu(menu),
            }
        if target_slot == "desserts":
            is_wedding = "wedding" in (get_slot_value(slots, "event_type") or "").lower()
            items = await load_dessert_menu_expanded(is_wedding=is_wedding)
            return _format_flat_menu(items), {
                "type": "menu_picker",
                "category": "desserts",
                "items": items,
                "max_select": 4,
            }
        return None, None

    async def _menu_for_slot(self, slot: str, slots: dict) -> dict[str, list[dict]]:
        if slot == "appetizers":
            return await load_appetizer_menu()
        if slot == "selected_dishes":
            return await load_main_dish_menu()
        if slot == "desserts":
            # Desserts use the expanded list — return empty so callers use
            # `resolve_desserts` directly.
            return {}
        return {}


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


def _format_scoped_menu(menu: dict[str, list[dict]], kind: str) -> str:
    lines: list[str] = []
    n = 1
    for cat, items in menu.items():
        if cat:
            lines.append(f"\n{cat}")
        for item in items:
            price = item.get("unit_price")
            price_type = item.get("price_type", "per_person")
            price_str = f"(${price:.2f}/{price_type})" if price else ""
            lines.append(f"{n}. {item['name']} {price_str}".strip())
            n += 1
    if not lines:
        return ""
    header = "Here are the appetizer options:" if kind == "appetizers" else "Here's the main menu:"
    return header + "\n" + "\n".join(lines)


def _format_flat_menu(items: list[dict]) -> str:
    lines: list[str] = []
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
        return ""
    return "Here are the dessert options:\n" + "\n".join(lines)


_LIST_SLOT_TO_PHASE = {
    "appetizers": PHASE_COCKTAIL,
    "selected_dishes": PHASE_MAIN_MENU,
    "desserts": PHASE_DESSERT,
    "rentals": PHASE_RENTALS,
}


def _is_unspecified_list_change(mod: ModificationExtraction) -> bool:
    """The user wants to edit a list slot but didn't name items — we should
    clear the slot and re-show the picker instead of writing an empty list."""
    if mod.target_slot not in _LIST_SLOTS:
        return False
    has_remove = bool(mod.items_to_remove)
    has_add = bool(mod.items_to_add)
    has_value = mod.new_value is not None and str(mod.new_value).strip() != ""
    return not (has_remove or has_add or has_value)


def _is_generic_list_reopen_request(message: str, mod: ModificationExtraction) -> bool:
    """Detect requests to reopen a list picker without naming concrete items.

    Examples:
    - "show me desserts menu"
    - "changed my mind, let's have some desserts"
    - "redo the rentals"
    """
    if mod.target_slot not in _LIST_SLOTS:
        return False

    msg = (message or "").strip().lower()
    if not msg:
        return False

    generic_phrases = {
        "desserts": (
            "dessert menu", "desserts menu", "show me desserts", "show desserts",
            "some desserts", "have desserts", "want desserts", "add desserts",
        ),
        "appetizers": (
            "appetizer menu", "appetizers menu", "show appetizers", "some appetizers",
        ),
        "selected_dishes": (
            "main menu", "mains menu", "show mains", "show main dishes",
            "some mains", "main dishes",
        ),
        "rentals": (
            "rentals", "rental menu", "show rentals",
        ),
    }
    patterns = generic_phrases.get(mod.target_slot, ())
    if not any(p in msg for p in patterns):
        return False

    generic_pronouns = {"it", "them", "that", "those", "these", "it back", "them back", "add them back"}

    explicit_items = bool(
        [v for v in (mod.items_to_add or []) if str(v).strip().lower() not in generic_pronouns]
        or [v for v in (mod.items_to_remove or []) if str(v).strip().lower() not in generic_pronouns]
    )
    if mod.new_value is not None and str(mod.new_value).strip():
        raw = str(mod.new_value).strip().lower()
        if raw not in {
            "dessert", "desserts", "some desserts", "appetizer", "appetizers",
            "mains", "main dishes", "menu", "rentals", "them", "it", "them back", "it back",
        }:
            explicit_items = True

    return not explicit_items


def _current_lists_context(slots: dict) -> str:
    """Snapshot of the list slots the user may be editing, passed to the LLM
    so it names items correctly and picks the right target_slot."""
    lines: list[str] = ["CURRENT FILLED LISTS (use these exact item names):"]
    any_content = False
    for slot in ("appetizers", "selected_dishes", "desserts", "rentals"):
        val = get_slot_value(slots, slot)
        if not val or str(val).lower() == "none":
            continue
        names = parse_slot_items(str(val))
        if not names:
            continue
        any_content = True
        lines.append(f"- {slot}: {', '.join(names)}")
    if not any_content:
        return ""
    lines.append(
        "When the user says 'remove X' or 'replace X with Y', pick the slot whose "
        "list contains X — do NOT guess based on the current conversation phase."
    )
    return "\n".join(lines)


def _reroute_by_membership(mod: "ModificationExtraction", slots: dict) -> str | None:
    """If the items being removed/replaced live in a different list slot than
    the LLM picked, return that slot's name so we can correct before applying.
    Returns None if nothing matched or if the LLM's choice is already best.
    """
    probe_items = [t for t in (mod.items_to_remove or []) if t]
    if not probe_items and mod.action == "remove" and mod.new_value:
        probe_items = [str(mod.new_value)]
    if not probe_items:
        return None

    probe_lower = [p.strip().lower() for p in probe_items if p and p.strip()]
    scores: dict[str, int] = {}
    for slot in ("appetizers", "selected_dishes", "desserts"):
        val = get_slot_value(slots, slot)
        if not val or str(val).lower() == "none":
            continue
        names = [n.lower() for n in parse_slot_items(str(val))]
        hits = 0
        for p in probe_lower:
            if any(p in n or n in p for n in names):
                hits += 1
        if hits:
            scores[slot] = hits

    if not scores:
        return None
    # Prefer the slot with the most matches. Tie-break: keep the LLM's pick.
    best_slot = max(scores, key=lambda s: scores[s])
    if scores[best_slot] == scores.get(mod.target_slot, 0):
        return None
    return best_slot


_SLOT_PRETTY = {
    "appetizers": "appetizers",
    "selected_dishes": "main dishes",
    "desserts": "desserts",
    "rentals": "rentals",
}


def _list_mod_ack(
    *,
    target_slot: str,
    removed: list[str],
    added: list[str],
    new_value: str,
) -> str | None:
    """Chat-visible confirmation of a list modification, listing what's left."""
    label = _SLOT_PRETTY.get(target_slot)
    if not label:
        return None
    parts: list[str] = []
    if removed:
        parts.append(f"Removed {', '.join(removed)}")
    if added:
        parts.append(f"added {', '.join(added)}")
    if not parts:
        return None
    head = " and ".join(parts).capitalize() + "."
    remaining = parse_slot_items(new_value) if new_value and str(new_value).lower() != "none" else []
    if remaining:
        return f"{head} Your {label} are now: {', '.join(remaining)}."
    return f"{head} Your {label} list is empty now — want to pick something else?"


def _scalar_mod_ack_text(*, target_slot: str, action: str, new_value: Any) -> str:
    label = _SLOT_LABELS.get(target_slot, target_slot.replace("_", " "))
    if action == "remove" or new_value in (None, ""):
        return f"Removed your {label}."
    if action == "add" and target_slot in _APPENDABLE_TEXT_SLOTS:
        return f"Added to your {label}: {_pretty_slot_value(target_slot, new_value)}."
    return f"Updated your {label} to {_pretty_slot_value(target_slot, new_value)}."


def _pretty_slot_value(target_slot: str, value: Any) -> str:
    text = str(value)
    if target_slot == "event_date":
        return text
    if target_slot == "service_type":
        return "drop-off" if text.lower() == "dropoff" else text
    if target_slot == "tableware":
        return {
            "standard_disposable": "standard disposable",
            "silver_disposable": "silver disposable",
            "gold_disposable": "gold disposable",
            "china": "full china",
            "no_tableware": "no tableware",
        }.get(text.lower(), text)
    if target_slot == "utensils":
        return {
            "standard_plastic": "standard plastic",
            "eco_biodegradable": "eco / biodegradable",
            "bamboo": "bamboo",
        }.get(text.lower(), text)
    return text


def _compose_direct_response(ack_text: str | None, resume_prompt: str | None) -> str | None:
    if ack_text and resume_prompt:
        return f"{ack_text}\n\n{resume_prompt}"
    return ack_text or resume_prompt


async def _resume_after_modification(
    *,
    slots: dict,
    state: dict,
) -> tuple[str | None, str | None, dict | None, str | None]:
    phase = state.get("conversation_phase")

    if phase in {
        PHASE_GREETING,
        PHASE_EVENT_TYPE,
        PHASE_CONDITIONAL_FOLLOWUP,
        PHASE_SERVICE_TYPE,
        PHASE_EVENT_DATE,
        PHASE_VENUE,
        PHASE_GUEST_COUNT,
    }:
        target = _basic_phase_to_question(phase, slots)
        return phase, target, _basic_input_hint_for_phase(phase), None

    if phase in {PHASE_TRANSITION, PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT}:
        if phase == PHASE_TRANSITION:
            return phase, "transition_to_menu", None, None
        target = _menu_next_target([], phase, slots)
        if phase == PHASE_DESSERT and not is_filled(slots, "desserts") and get_slot_value(slots, "__gate_desserts") is not True:
            return (
                phase,
                "ask_dessert_gate",
                {
                    "type": "options",
                    "options": [
                        {"value": "yes", "label": "Yes, add desserts"},
                        {"value": "skip dessert", "label": "No thanks, skip"},
                    ],
                },
                "Would you like to add desserts, or skip them?",
            )
        input_hint = _addons_transition_hint() if target == "transition_to_addons" else await _menu_input_hint_for_menu_phase(phase, slots)
        resume_prompt = None
        if target in {"show_appetizer_menu", "show_main_menu", "show_dessert_menu"} and input_hint:
            resume_prompt = _format_menu_turn_response(phase, input_hint, slots)
        elif target == "ask_service_style":
            resume_prompt = "For the wedding, would you like a cocktail hour, the main reception, or both?"
        elif target == "ask_appetizer_style":
            resume_prompt = "How would you like the appetizers served: passed around or set up at a station?"
        elif target == "ask_meal_style":
            resume_prompt = "Would you like the meal served plated or buffet-style?"
        elif target == "transition_to_addons":
            resume_prompt = "Would you like to add drinks or bar service for the event?"
        return phase, target, input_hint, resume_prompt

    if phase in {PHASE_DRINKS_BAR, PHASE_TABLEWARE, PHASE_RENTALS, PHASE_LABOR}:
        target = _addons_next_target(slots)
        return (
            phase,
            target,
            _addons_input_hint_for_target(target, slots),
            _addons_direct_response_for_target(target, slots),
        )

    if phase in {PHASE_SPECIAL_REQUESTS, PHASE_DIETARY, PHASE_FOLLOWUP, PHASE_REVIEW}:
        target = _finalization_next_target(slots)
        if target == "review":
            summary = _finalization_client_facing_summary(slots)
            return (
                phase,
                target,
                _finalization_input_hint_for_target(target),
                _render_final_review_recap(summary),
            )
        return (
            phase,
            target,
            _finalization_input_hint_for_target(target),
            _finalization_direct_response_for_target(target),
        )

    return phase, None, None, None


_SLOT_LABELS = {
    "name": "name",
    "email": "email",
    "phone": "phone number",
    "event_type": "event type",
    "event_date": "date",
    "venue": "venue",
    "guest_count": "guest count",
    "partner_name": "partner name",
    "company_name": "company name",
    "honoree_name": "honoree",
    "service_type": "service",
    "drinks": "drinks",
    "bar_service": "bar service",
    "bar_package": "bar package",
    "coffee_service": "coffee service",
    "tableware": "tableware",
    "utensils": "utensils",
    "linens": "linens",
    "rentals": "rentals",
    "special_requests": "special requests",
    "dietary_concerns": "dietary concerns",
    "additional_notes": "notes",
}


__all__ = ["ModificationTool"]

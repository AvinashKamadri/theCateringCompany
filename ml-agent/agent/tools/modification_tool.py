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

import json
import re
import datetime
from typing import Any

from langchain_core.messages import BaseMessage

from agent.ambiguous_choice import (
    normalize_choice_text,
    replace_query_with_selection,
    resolve_choice_selection,
    resolve_multi_choice_selection,
)
from agent.cascade import apply_cascade
from agent.event_identity import filter_identity_fields
from agent.instructor_client import MODEL_ROUTER, extract, filter_extraction_fields
from agent.list_slot_reopen import (
    GENERIC_REOPEN_MARKERS,
    LIST_SLOT_MENTION_PATTERNS,
    LIST_SLOT_REOPEN_PHRASES,
    LIST_SLOT_TO_PHASE,
    explicit_reopen_list_slot,
    menu_section_for_phase,
)
from agent.menu_resolver import (
    filter_menu_items_by_tags,
    format_items,
    load_appetizer_menu,
    load_dessert_menu_expanded,
    load_main_dish_menu,
    menu_item_tags,
    parse_slot_items,
    resolve_dessert_choices,
    resolve_menu_items,
    resolve_to_db_items,
)
from agent.models import (
    EventDetailsExtraction,
    ModificationExtraction,
    SelectedItemGrounding,
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
    PHASE_WEDDING_CAKE,
    SLOT_NAMES,
    clear_slot,
    fill_slot,
    get_slot_value,
    is_filled,
    initialize_empty_slots,
)
from agent.modification_picker import make_modification_picker_result
from agent.tools.add_ons_tool import (
    _direct_response_for_target as _addons_direct_response_for_target,
    _input_hint_for_target as _addons_input_hint_for_target,
    _next_target as _addons_next_target,
)
from agent.tools.basic_info_tool import _normalize_tbd_venue
from agent.tools.basic_info_tool import (
    _input_hint_for_phase as _basic_input_hint_for_phase,
    _next_phase as _basic_next_phase,
    _phase_to_question as _basic_phase_to_question,
)
from agent.tools.base import ToolResult, history_for_llm
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
    "# Role\n"
    "You are a modification intent extractor. The customer wants to change a previously provided answer. "
    "Figure out WHICH slot and HOW.\n\n"
    "# Rules\n"
    "CRITICAL: Extract target_slot, action, and new_value ONLY. Do not guess or infer other changes.\n\n"
    "target_slot MUST be one of:\n"
    f"{', '.join(SLOT_NAMES)}\n\n"
    "Map natural language to slot names:\n"
    "- 'name / first name / my name' → name\n"
    "- 'email' → email | 'phone' → phone\n"
    "- 'date / when' → event_date | 'venue / location / place' → venue\n"
    "- 'guests / headcount' → guest_count\n"
    "- 'wedding cake / cake' → wedding_cake\n"
    "- 'apps / appetizers / starters' → appetizers\n"
    "- 'mains / main dishes / entrees / menu' → selected_dishes\n"
    "- 'dessert / desserts / coffee bar / cookies' → desserts\n"
    "- 'bar / bar service' → bar_service | 'bar package' → bar_package\n"
    "- 'drinks' → drinks | 'coffee' → coffee_service\n"
    "- 'plates / tableware / china / disposable' → tableware\n"
    "- 'utensils / cutlery' → utensils\n"
    "- 'linens' → rentals\n\n"
    "action: 'add', 'remove', 'replace', or 'reopen'.\n"
    "Use 'reopen' when the user wants to reselect an entire menu section, "
    "see that menu again, or start over on appetizers, mains, desserts, or rentals "
    "without naming concrete items.\n"
    "items_to_remove: for list slots on remove/replace, the exact items.\n"
    "items_to_add: for list slots on add/replace, the exact items.\n"
    "new_value: for scalar slots, the new value as a string.\n\n"
    "The user may be correcting a slot unrelated to current_phase. Do not let the phase bias target_slot selection.\n\n"
    "# Examples\n"
    "1. User: 'hey im sorry it is a birthday'\n"
    "   Output: target_slot='event_type', action='replace', new_value='Birthday'\n"
    "2. User: 'ADD DESSERTS'\n"
    "   Output: target_slot='desserts', action='reopen'\n"
    "3. User: 'add 7 layer bars'\n"
    "   Output: target_slot='desserts', action='add', items_to_add=['7-Layer Bars']\n"
    "4. User: 'remove the soup'\n"
    "   Output: target_slot='appetizers', action='remove', items_to_remove=['soup']\n"
    "5. User: 'actually change the date to may 5'\n"
    "   Output: target_slot='event_date', action='replace', new_value='May 5'\n"
    "6. User: 'swap the chicken for fish'\n"
    "   Output: target_slot='selected_dishes', action='replace', items_to_remove=['chicken'], items_to_add=['fish']\n"
    "7. User: 'start over on the rentals'\n"
    "   Output: target_slot='rentals', action='reopen'\n"
    "8. User: 'no i want 50 guests'\n"
    "   Output: target_slot='guest_count', action='replace', new_value='50'\n"
    "9. User: 'hey i was thinking if we can drop the cake'\n"
    "   Output: target_slot='wedding_cake', action='remove', new_value=None\n"
    "   (NOTE: 'drop the cake' = remove wedding_cake. NOT related to drop-off service.)\n"
    "10. User: 'actually skip the wedding cake'\n"
    "    Output: target_slot='wedding_cake', action='remove', new_value=None\n"
)


_YES_TOKENS = frozenset({
    "yes", "y", "yeah", "yep", "yup", "sure", "ok", "okay", "please",
    "go ahead", "do it", "proceed", "continue", "sounds good",
})
_NO_TOKENS = frozenset({
    "no", "n", "nope", "nah", "skip", "cancel", "don't", "do not", "stop",
})


_LABOR_SLOTS = frozenset({
    "labor_ceremony_setup",
    "labor_table_setup",
    "labor_table_preset",
    "labor_cleanup",
    "labor_trash",
})

_LABOR_SLOT_ALIASES: dict[str, tuple[str, ...]] = {
    "labor_ceremony_setup": ("ceremony", "ceremony setup"),
    "labor_table_setup": ("table setup", "tables setup"),
    "labor_table_preset": ("preset", "table preset", "tables preset"),
    "labor_cleanup": ("cleanup", "clean up"),
    "labor_trash": ("trash", "trash removal", "garbage"),
}


def _normalize_yes_no(message: str) -> str | None:
    msg = normalize_choice_text(message or "").strip().lower()
    if not msg:
        return None
    if msg in _YES_TOKENS:
        return "yes"
    if msg in _NO_TOKENS:
        return "no"
    return None


def _normalize_bool_value(message: str, *, truthy_markers: tuple[str, ...] = (), falsy_markers: tuple[str, ...] = ()) -> bool | None:
    msg = normalize_choice_text(message or "").strip().lower()
    if not msg:
        return None
    yn = _normalize_yes_no(msg)
    if yn == "yes":
        return True
    if yn == "no":
        return False
    if truthy_markers and any(m in msg for m in truthy_markers):
        return True
    if falsy_markers and any(m in msg for m in falsy_markers):
        return False
    return None


def _normalize_meal_style_value(raw: Any) -> str | None:
    msg = normalize_choice_text(str(raw or "")).strip().lower()
    if not msg:
        return None
    if "buffet" in msg:
        return "buffet"
    if "plated" in msg:
        return "plated"
    return None


def _normalize_bar_package_value(raw: Any) -> str | None:
    msg = normalize_choice_text(str(raw or "")).strip().lower()
    if not msg:
        return None
    # Canonical keys
    if msg in {"beer_wine", "beer_wine_signature", "full_open_bar"}:
        return msg
    # Common natural language
    if "full" in msg and "bar" in msg:
        return "full_open_bar"
    if "open bar" in msg:
        return "full_open_bar"
    if "signature" in msg:
        return "beer_wine_signature"
    if ("beer" in msg and "wine" in msg) or "beer+wine" in msg or "beer & wine" in msg:
        return "beer_wine"
    return None


def _extract_multi_scalar_updates(message: str) -> dict[str, Any]:
    """Best-effort deterministic multi-field updates from a single message.

    This avoids an extra LLM call for common "change X and Y" commands and
    ensures we can update multiple slots in one turn.
    """
    text = (message or "").strip()
    raw_lower = text.lower()
    low = normalize_choice_text(text)
    if not text or not low:
        return {}

    updates: dict[str, Any] = {}

    # Email
    email_match = re.search(r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})", raw_lower, flags=re.IGNORECASE)
    if email_match and ("email" in raw_lower or "mail" in raw_lower):
        updates["email"] = email_match.group(1)

    # Phone
    if "phone" in low or "number" in low or "contact" in low:
        phone_match = re.search(r"(\+?\d[\d\s()\-\u2010\u2011\u2012\u2013]{7,}\d)", text)
        if phone_match:
            updates["phone"] = re.sub(r"\s+", "", phone_match.group(1)).replace("(", "").replace(")", "").replace("-", "")

    # Meal style
    meal_style = _normalize_meal_style_value(low)
    if meal_style:
        updates["meal_style"] = meal_style

    # Service type
    if "drop" in low or "onsite" in low or "on-site" in low or "on site" in low:
        if "drop" in low:
            updates["service_type"] = "Dropoff"
        elif "onsite" in low or "on-site" in low or "on site" in low:
            updates["service_type"] = "Onsite"

    # Drinks/bar package in same utterance ("Beer+Wine", "full open bar", "no drinks")
    pkg = _normalize_bar_package_value(low)
    if pkg:
        updates["drinks"] = True
        updates["bar_service"] = True
        updates["bar_package"] = pkg
    elif "no drinks" in low or ("drinks" in low and _normalize_yes_no(low) == "no"):
        updates["drinks"] = False

    # Coffee / bar booleans
    if "coffee" in low:
        yn = _normalize_yes_no(low)
        if yn == "yes":
            updates["coffee_service"] = True
        elif yn == "no":
            updates["coffee_service"] = False
    if "bar service" in low or (("bar" in low) and ("package" not in low) and ("open bar" not in low)):
        yn = _normalize_yes_no(low)
        if yn == "yes":
            updates["bar_service"] = True
            updates.setdefault("drinks", True)
        elif yn == "no":
            updates["bar_service"] = False

    # Guest count
    if "guest" in low or "headcount" in low:
        m = re.search(r"\b(\d{1,4})\b", low)
        if m:
            updates["guest_count"] = int(m.group(1))
        elif "tbd" in low or "confirm" in low:
            updates["guest_count"] = "TBD"

    # Event date (YYYY-MM-DD only here; natural language dates use BasicInfoTool validator path)
    if "date" in low:
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", low)
        if m:
            try:
                y, mo, d = (int(p) for p in m.group(1).split("-"))
                dt = datetime.date(y, mo, d)
                if dt > datetime.date.today():
                    updates["event_date"] = dt.isoformat()
            except Exception:
                pass

    return updates


def _normalize_event_type_display(raw: Any) -> str | None:
    """Best-effort canonicalization for display and comparisons.

    State can occasionally contain typos (e.g. "Weddimg") from user input.
    We normalize only the canonical categories; free-text event types are left
    untouched.
    """
    msg = str(raw or "").strip()
    if not msg:
        return None
    low = normalize_choice_text(msg).strip().lower()
    if not low:
        return msg
    if low in {"wedding", "weddimg", "weding", "weddding"} or low.startswith("wedd"):
        return "Wedding"
    if low in {"birthday", "bday"} or "birthday" in low or low.startswith("birth"):
        return "Birthday"
    if low in {"corporate", "corp"} or "corporate" in low or "company" in low:
        return "Corporate"
    if low in {"other", "others"}:
        return "Other"
    return msg


def _looks_like_decline(msg_lower: str) -> bool:
    msg = normalize_choice_text(msg_lower or "").strip().lower()
    return msg in {"no", "nope", "nah", "skip", "none", "not needed", "no thanks"} or msg.startswith("no ")


_EVENT_TYPE_RESET_SENSITIVE_SLOTS = frozenset({
    # Event identity + service style
    "event_type_other",
    "partner_name",
    "company_name",
    "honoree_name",
    "service_style",
    "cocktail_hour",
    # Menu + menu style
    "appetizers",
    "appetizer_style",
    "selected_dishes",
    "meal_style",
    "desserts",
    # Wedding cake
    "wedding_cake",
    "__wedding_cake_gate",
    "__wedding_cake_flavor",
    "__wedding_cake_filling",
    "__wedding_cake_buttercream",
    # Remaining basics
    "event_date",
    "venue",
    "guest_count",
    "service_type",
    # Add-ons
    "drinks",
    "coffee_service",
    "bar_service",
    "bar_package",
    "tableware",
    "utensils",
    "rentals",
    "linens",
    # Labor/finalization (even if you later skip, it is still "progress")
    "labor_ceremony_setup",
    "labor_table_setup",
    "labor_table_preset",
    "labor_cleanup",
    "labor_trash",
    "special_requests",
    "dietary_concerns",
    "additional_notes",
    "followup_call_requested",
})


def _event_type_change_requires_reset(slots: dict) -> bool:
    return any(is_filled(slots, s) for s in _EVENT_TYPE_RESET_SENSITIVE_SLOTS)


def _reset_slots_for_new_event_type(*, old_slots: dict, new_event_type: str) -> dict:
    """Clear event-related slots, keep contact info, and set the new event_type."""
    kept: dict[str, Any] = {}
    for field in ("name", "email", "phone"):
        if is_filled(old_slots, field):
            kept[field] = get_slot_value(old_slots, field)

    new_slots = initialize_empty_slots()
    for field, value in kept.items():
        fill_slot(new_slots, field, value)
    fill_slot(new_slots, "event_type", new_event_type)
    return new_slots

_SELECTION_GROUNDING_PROMPT = (
    "You resolve a user's remove/replace request against the exact items they "
    "currently have selected for a catering order.\n"
    "Return status='resolved' only when you can map the user's request to the "
    "exact selected item names.\n"
    "Return status='ambiguous' when the user used a fuzzy reference and multiple "
    "selected items plausibly match.\n"
    "Return status='no_match' when no currently selected item clearly matches.\n"
    "Critical rules:\n"
    "- matched_names must contain ONLY exact names from CURRENT_SELECTED_ITEMS.\n"
    "- Prefer title/name evidence first.\n"
    "- Use description/category only when it clearly identifies the main item, "
    "not a tiny garnish or side ingredient.\n"
    "- Example: if the user says 'remove egg' and the selected items are "
    "'Deviled Egg', 'Caviar Egg', and 'Caviar and Cream Crisp', return "
    "status='ambiguous' with the two items whose names contain egg. Do not "
    "include 'Caviar and Cream Crisp'.\n"
    "- Example: if the user says 'remove chicken' and several selected mains "
    "include chicken in their title or description, return status='ambiguous' "
    "with every plausible selected match.\n"
    "- reference_text should be the short phrase you are grounding, such as "
    "'egg' or 'chicken'."
)

_LIST_SLOTS = {"appetizers", "selected_dishes", "desserts", "rentals"}
_APPENDABLE_TEXT_SLOTS = {"special_requests", "dietary_concerns", "additional_notes"}
_ADD_VERBS = r"add(?:\s+back)?|readd|bring\s+back|put\s+back|include"
_REMOVE_VERBS = r"remove|delete|drop|take\s+off|take\s+out|cancel"
_GENERIC_MODIFICATION_VERBS = {
    "change",
    "changes",
    "modify",
    "modification",
    "update",
    "edit",
    "alter",
}
_MODIFICATION_SUBJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "my name", "first name", "last name", "full name"),
    "email": ("email", "email address"),
    "phone": ("phone", "phone number", "number", "mobile", "cell"),
    "event_type": ("event type", "type of event", "event"),
    "event_type_other": ("other event", "event (other)", "event details", "event description", "what kind of event"),
    "event_date": ("event date", "date", "day", "when"),
    "venue": ("venue", "location", "place"),
    "guest_count": ("guest count", "guests", "headcount", "attendees"),
    "partner_name": ("partner", "partner name", "fiance", "fiancee"),
    "company_name": ("company", "company name", "organization"),
    "honoree_name": ("honoree", "celebrant", "birthday person"),
    "wedding_cake": ("wedding cake", "cake"),
    "service_type": ("service", "service type", "dropoff", "drop-off", "onsite", "on-site"),
    "appetizers": ("appetizers", "appetizer", "apps", "starters"),
    "selected_dishes": ("main dishes", "main dish", "mains", "entrees", "entree", "main menu", "menu"),
    "desserts": ("desserts", "dessert", "sweets", "coffee bar"),
    "drinks": ("drinks", "drink service"),
    "bar_service": ("bar service", "bar"),
    "bar_package": ("bar package", "bar plan"),
    "coffee_service": ("coffee service", "coffee"),
    "tableware": ("tableware", "plates", "china", "disposable"),
    "utensils": ("utensils", "cutlery", "flatware"),
    "rentals": ("rentals", "rental", "linens", "linen"),
    "special_requests": ("special requests", "special request"),
    "dietary_concerns": ("dietary", "dietary concerns", "allergies", "allergy"),
    "additional_notes": ("additional notes", "notes", "final notes", "note"),
}


def _name_is_ambiguous(state: dict, slots: dict) -> bool:
    """Return True when 'name' and 'partner_name' are both plausible targets.

    For weddings, 'the name is X' is always ambiguous — users routinely say
    this at any point in the flow when correcting their partner's name.
    """
    event_type = (get_slot_value(slots, "event_type") or "").lower()
    if "wedding" not in event_type:
        return False
    # For weddings, always ask rather than silently writing the wrong slot.
    return True


def _sanitize_slot_value(value: str) -> str:
    """Strip JSON/schema artifacts that the LLM occasionally leaks into values.

    Patterns seen in prod: trailing `}.`, `}`, `).` after a real value.
    """
    return re.sub(r'[\}\)]+\.?\s*$', '', value).strip()


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
    return history_for_llm(history)


def _normalize_mod_list_texts(texts: list[str], *, action: str) -> list[str]:
    """Clean extractor output like 'ravioli menu and add soup/salad'."""
    if not texts:
        return []

    verbs = _ADD_VERBS if action == "add" else _REMOVE_VERBS
    normalized: list[str] = []
    for raw in texts:
        cleaned = re.sub(r"\s+", " ", str(raw or "")).strip(" ,.")
        if not cleaned:
            continue
        cleaned = re.sub(
            rf"\s+(?:and|also)\s+(?:{verbs})\s+",
            " and ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(
            rf"^(?:please\s+)?(?:and\s+)?(?:also\s+)?(?:{verbs})\s+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip(" ,.")
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _contains_specific_modification_details(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    if explicit_reopen_list_slot(msg):
        return True
    for slot, aliases in _MODIFICATION_SUBJECT_ALIASES.items():
        if any(re.search(rf"\b{re.escape(alias)}\b", msg) for alias in aliases):
            return True
    return False


def _is_remove_all_request(message: str, *, target_slot: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    if not re.search(r"\b(remove|delete|drop|clear)\b", msg):
        return False
    if " all " not in f" {msg} " and not msg.endswith(" all"):
        return False
    mentions = LIST_SLOT_MENTION_PATTERNS.get(target_slot, ())
    return any(re.search(rf"\b{re.escape(term)}\b", msg) for term in mentions)


def _needs_cross_category_confirmation(*, remove_slot: str, add_slot: str | None) -> bool:
    """Return True when a replace would move between desserts and non-desserts.

    We allow some cross-slot "replace" moves (e.g. mains->apps) as a convenience,
    but desserts are constrained (max 4) and mixing categories is commonly a user
    mistake ("replace brownies with chicken satay").
    """
    if not add_slot:
        return False
    slots = {remove_slot, add_slot}
    return "desserts" in slots and len(slots) > 1


def _looks_like_direct_modification_command(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    if explicit_reopen_list_slot(msg):
        return True
    if _mentions_wedding_cake_reopen(msg):
        return True
    return bool(
        re.search(
            r"\b(change|update|replace|swap|remove|delete|drop|edit|fix|correct|cancel|add|bring back|put back|take off|take out)\b",
            msg,
        )
    )


def _is_generic_modification_request(message: str) -> bool:
    raw = str(message or "").strip()
    if not raw:
        return False
    if _contains_specific_modification_details(raw):
        return False
    tokens = set(normalize_choice_text(raw).split())
    return bool(tokens & _GENERIC_MODIFICATION_VERBS)


def _resolve_modification_subject_slot(message: str) -> str | None:
    msg = (message or "").strip().lower()
    if not msg:
        return None

    # Allow direct slot-name selection from UI option chips.
    if msg in SLOT_NAMES:
        if msg == "linens":
            return "rentals"
        return msg

    for slot, aliases in _MODIFICATION_SUBJECT_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", msg):
                return slot
    return None


def _mentions_wedding_cake_reopen(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    if "wedding cake" not in msg and "cake" not in msg:
        return False

    revisit_markers = {
        "again",
        "add back",
        "bring back",
        "put back",
        "redo",
        "reselect",
        "choose",
    }
    return any(marker in msg for marker in revisit_markers)


class ModificationTool:
    name = "modification_tool"

    def _return_to_final_review(self, *, slots: dict, state: dict) -> ToolResult:
        """Exit the modification picker and re-show the final review recap.

        Used when the user says they don't actually want to change anything
        (e.g. "nothing", "all good", "send it") while the tool is waiting for a
        modification target/value.
        """
        summary = _finalization_client_facing_summary(slots)
        state["conversation_phase"] = PHASE_REVIEW
        if is_filled(slots, "__return_to_review_after_edit"):
            clear_slot(slots, "__return_to_review_after_edit")
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "next_phase": PHASE_REVIEW,
                "next_question_target": "review",
                "client_summary": summary,
                "awaiting_confirm": True,
            },
            direct_response=_render_final_review_recap(summary),
            input_hint=_finalization_input_hint_for_target("review"),
        )

    async def run(
        self,
        *,
        message: str,
        history: list[BaseMessage],
        state: dict,
    ) -> ToolResult:
        slots = state["slots"]

        # Deterministic multi-field edits in one message (common UX pattern).
        multi = _extract_multi_scalar_updates(message)
        if len(multi) >= 2 and not get_slot_value(slots, "__pending_modification_request") and not get_slot_value(slots, "__pending_modification_choice"):
            applied: list[str] = []
            for slot_name, value in multi.items():
                if slot_name in LOCKED_SLOTS or slot_name.startswith("__"):
                    continue
                old = get_slot_value(slots, slot_name)
                fill_slot(slots, slot_name, value)
                apply_cascade(slot_name, old, value, slots)
                applied.append(slot_name)

            ack_parts = []
            for slot_name in applied:
                label = _SLOT_LABELS.get(slot_name, slot_name.replace("_", " "))
                if slot_name == "bar_package":
                    ack_parts.append(f"Bar package: {_pretty_slot_value('bar_package', get_slot_value(slots, 'bar_package'))}.")
                elif slot_name == "meal_style":
                    ack_parts.append(f"Meal style: {_pretty_slot_value('meal_style', get_slot_value(slots, 'meal_style'))}.")
                elif slot_name == "service_type":
                    ack_parts.append(f"Service: {_pretty_slot_value('service_type', get_slot_value(slots, 'service_type'))}.")
                else:
                    ack_parts.append(f"Updated {label}.")

            next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                slots=slots,
                state=state,
            )
            direct = " ".join(ack_parts).strip()
            if resume_prompt:
                direct = f"{direct}\n\n{resume_prompt}"

            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "modification": {
                        "target_slot": applied[0] if applied else "selection",
                        "action": "replace",
                        "also_updated": applied[1:],
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=direct,
            )

        pending_confirmation = get_slot_value(slots, "__pending_confirmation")
        if isinstance(pending_confirmation, dict) and pending_confirmation.get("tool") == "modification_tool":
            if pending_confirmation.get("question_id") == "confirm_event_type_reset":
                decision = _normalize_yes_no(message)
                if decision is None:
                    return ToolResult(
                        state=state,
                        response_context={
                            "tool": self.name,
                            "error": "needs_yes_no",
                            "next_phase": state.get("conversation_phase"),
                            "next_question_target": "confirm_event_type_reset",
                        },
                        input_hint={
                            "type": "options",
                            "options": [{"value": "yes", "label": "Yes, reset"}, {"value": "no", "label": "No, keep as-is"}],
                        },
                        direct_response=(
                            "Just to confirm — should I reset your details for the new event type?\n\n"
                            "Switching the event type usually means redoing the event details (menu, service style, add-ons, etc).\n\n"
                            "Do you want to reset everything and start over for the new event type?\n\n"
                            "Yes, reset everything\n"
                            "No, keep everything"
                        ),
                    )

                old_event_type = str(pending_confirmation.get("old_event_type") or get_slot_value(slots, "event_type") or "")
                requested_event_type = str(pending_confirmation.get("new_event_type") or "").strip() or old_event_type

                clear_slot(slots, "__pending_confirmation")

                if decision == "no":
                    next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                        slots=slots,
                        state=state,
                    )
                    return ToolResult(
                        state=state,
                        response_context={
                            "tool": self.name,
                            "next_phase": next_phase,
                            "next_question_target": next_target,
                            "next_question_prompt": resume_prompt,
                        },
                        input_hint=input_hint,
                        direct_response=(
                            f"Got it — we’ll keep your event type as {old_event_type or 'is'}.\n\n"
                            + (resume_prompt or "")
                        ).strip(),
                    )

                # yes: reset
                new_slots = _reset_slots_for_new_event_type(
                    old_slots=slots,
                    new_event_type=requested_event_type,
                )
                state["slots"] = new_slots
                state["conversation_phase"] = PHASE_CONDITIONAL_FOLLOWUP

                next_target = _basic_phase_to_question(PHASE_CONDITIONAL_FOLLOWUP, new_slots)
                prompt = ""
                if next_target:
                    from agent.prompt_registry import fallback_prompt_for_target

                    prompt = fallback_prompt_for_target("basic_info_tool", next_target)

                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "next_phase": PHASE_CONDITIONAL_FOLLOWUP,
                        "next_question_target": next_target,
                        "next_question_prompt": prompt,
                        "event_type_reset": True,
                        "event_type": requested_event_type,
                    },
                    input_hint=_basic_input_hint_for_phase(PHASE_CONDITIONAL_FOLLOWUP, new_slots),
                    direct_response=("Okay — I’ll reset the details for the new event type.\n\n" + prompt).strip(),
                )

        pending_choice = get_slot_value(slots, "__pending_modification_choice")
        if pending_choice:
            resumed = await self._resume_pending_choice(
                pending_choice=pending_choice,
                message=message,
                slots=slots,
                state=state,
            )
            if resumed is not None:
                return resumed

        pending_request = get_slot_value(slots, "__pending_modification_request")
        if pending_request:
            resumed = await self._resume_pending_request(
                pending_request=pending_request,
                message=message,
                slots=slots,
                state=state,
                history=history,
            )
            if resumed is not None:
                return resumed

        if _is_generic_modification_request(message):
            return self._ask_modification_target(slots, state)

        explicit_reopen_slot = explicit_reopen_list_slot(
            message,
            state.get("conversation_phase"),
        )
        if explicit_reopen_slot:
            return await self._reopen_list_slot(explicit_reopen_slot, slots, state, message=message)
        if _mentions_wedding_cake_reopen(message):
            return self._reopen_wedding_cake(slots, state)

        # Surface the current list contents to the LLM so it can pick the
        # right target_slot and item names regardless of which phase we're in.
        # Context goes in the user message — keeps the system prompt static
        # so OpenAI's prompt cache hits across turns.
        context_block = _modification_context_block(slots, state)
        user_payload = (
            f"User message: {message}\n\nContext:\n{context_block}"
            if context_block
            else message
        )

        extracted = await extract(
            schema=ModificationExtraction,
            system=_SYSTEM_PROMPT,
            user_message=user_payload,
            history=_history_for_llm(history),
            model=MODEL_ROUTER,
            max_tokens=5000,
        )

        if extracted is None:
            return self._ask_modification_target(slots, state)

        inferred_note_slot = _infer_note_slot_from_message(message)
        if inferred_note_slot and extracted.target_slot in {"special_requests", "dietary_concerns", "additional_notes"}:
            extracted.target_slot = inferred_note_slot

        target_slot = extracted.target_slot

        # Name disambiguation: if the LLM picked "name" but we're in a wedding/
        # conditional phase where partner_name is also a valid candidate, ask
        # rather than silently overwriting the wrong slot.
        if target_slot == "name" and _name_is_ambiguous(state, slots):
            return self._ask_name_disambiguation(slots, state)

        # Cross-section disambiguation: if "remove chicken" matches items in MORE
        # than one slot (e.g. appetizers AND mains), ask the user to pick rather
        # than silently guessing the wrong section.
        if (
            target_slot in _LIST_SLOTS
            and extracted.action in {"remove", "replace"}
            and extracted.items_to_remove
        ):
            probe = [t for t in extracted.items_to_remove if t]
            cross_matches = _find_cross_slot_matches(probe, slots)
            if cross_matches:
                return self._cross_slot_choice_result(
                    original_target=target_slot,
                    action=extracted.action,
                    query=probe[0],
                    cross_matches=cross_matches,
                    items_to_remove=probe,
                    items_to_add=list(extracted.items_to_add or []),
                    slots=slots,
                    state=state,
                )

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
            # the menu selector so they can re-pick from the catalog. Also
            # reopen when the LLM hallucinated items not actually named in the
            # message (e.g. "ADD DESSERTS" -> LLM invents Fruit Tarts).
            #
            # CATALOG CHECK: before firing the reopen gate, verify whether any
            # items_to_add actually resolve against the real menu catalog. If
            # they do, the user is making an incremental add (e.g. "add maple
            # bacon to appetizer menu") — not asking to reopen the picker.
            # This prevents "menu" appearing in the message from triggering a
            # full reopen when the user just wants to add a specific item.
            should_reopen = (
                extracted.action == "reopen"
                or _is_unspecified_list_change(extracted)
                or _is_generic_list_reopen_request(message, extracted)
                or _has_hallucinated_list_items(extracted, message)
            )
            if should_reopen and extracted.items_to_add and extracted.action in {"add", "replace"}:
                # Desserts use a separate resolver — skip the catalog check
                # for desserts and let the normal path handle them.
                if target_slot != "desserts":
                    menu = await self._menu_for_slot(target_slot, slots)
                    resolution = await resolve_menu_items(
                        extraction=", ".join(str(i) for i in extracted.items_to_add),
                        menu=menu,
                    )
                    if resolution.matched_items:
                        # At least one item resolved to a real catalog entry —
                        # treat as incremental add, not a reopen.
                        should_reopen = False
            if should_reopen:
                return await self._reopen_list_slot(target_slot, slots, state, message=message)
            return await self._apply_list_modification(extracted, slots, state, message=message)

        if target_slot == "wedding_cake":
            # Wedding cake is a multi-step sub-flow. Any attempt to "add" or
            # "change" the wedding cake should reopen the sub-questions instead
            # of storing raw command text like "add wedding cake".
            if extracted.action == "remove" or _looks_like_decline(message):
                old_value = get_slot_value(slots, "wedding_cake")
                for slot_name in (
                    "wedding_cake",
                    "__wedding_cake_gate",
                    "__wedding_cake_flavor",
                    "__wedding_cake_filling",
                    "__wedding_cake_buttercream",
                ):
                    if is_filled(slots, slot_name):
                        clear_slot(slots, slot_name)
                fill_slot(slots, "__wedding_cake_gate", False)
                fill_slot(slots, "wedding_cake", "none")
                ack_text = _scalar_mod_ack_text(
                    target_slot="wedding_cake",
                    action="remove",
                    new_value=None,
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
                            "target_slot": "wedding_cake",
                            "action": "remove",
                            "old_value": old_value,
                            "new_value": "none",
                            "mod_ack_text": ack_text,
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                        "next_question_prompt": resume_prompt,
                    },
                    input_hint=input_hint,
                    direct_response=_compose_direct_response(ack_text, resume_prompt),
                )
            return self._reopen_wedding_cake(slots, state)

        return await self._apply_scalar_modification(extracted, message, slots, state, history)

    # ------------------------------------------------------------------

    async def _apply_list_modification(
        self,
        mod: ModificationExtraction,
        slots: dict,
        state: dict,
        message: str | None = None,
    ) -> ToolResult:
        target_slot = mod.target_slot
        current_value = get_slot_value(slots, target_slot) or ""
        current_items = parse_slot_items(current_value)

        menu = await self._menu_for_slot(target_slot, slots)
        cross_add_slot: str | None = None
        add_instead_slot: str | None = None

        # Bulk remove-all: "remove all desserts/appetizers/mains"
        if (
            message
            and mod.action == "remove"
            and target_slot in _LIST_SLOTS
            and _is_remove_all_request(message, target_slot=target_slot)
        ):
            pretty = _SLOT_PRETTY.get(target_slot, target_slot)
            if not current_items:
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
                            "action": "remove_all",
                            "old_value": current_value,
                            "new_value": current_value,
                            "removed": [],
                            "added": [],
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                        "next_question_prompt": resume_prompt,
                    },
                    input_hint=input_hint,
                    direct_response=_compose_direct_response(f"You don't have any {pretty} added.", resume_prompt),
                )

            old_value = get_slot_value(slots, target_slot)
            fill_slot(slots, target_slot, "none")
            effects = apply_cascade(target_slot, old_value, "none", slots)
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
                        "action": "remove_all",
                        "old_value": old_value,
                        "new_value": "none",
                        "removed": list(current_items),
                        "added": [],
                    },
                    "cascade_effects": effects,
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response(f"Removed all {pretty}.", resume_prompt),
            )

        # Compute remove + add sets
        remove_texts = _normalize_mod_list_texts(list(mod.items_to_remove or []), action="remove")
        add_texts = _normalize_mod_list_texts(list(mod.items_to_add or []), action="add")
        if mod.action == "remove" and not remove_texts and mod.new_value:
            remove_texts = _normalize_mod_list_texts([str(mod.new_value)], action="remove")
        if mod.action == "add" and not add_texts and mod.new_value:
            add_texts = _normalize_mod_list_texts([str(mod.new_value)], action="add")
        if mod.action == "replace" and not add_texts and mod.new_value:
            add_texts = _normalize_mod_list_texts([str(mod.new_value)], action="add")

        def _normalize_menu_category_hint(raw: str) -> str | None:
            text = normalize_choice_text(raw or "")
            if not text:
                return None
            if any(kw in text for kw in ("appetizer", "appetizers", "apps", "starter", "starters")):
                return "appetizers"
            if any(kw in text for kw in ("dessert", "desserts")):
                return "desserts"
            if any(kw in text for kw in ("main", "mains", "main menu", "main dish", "main dishes", "dish", "dishes", "entree", "entrees")):
                return "selected_dishes"
            return None

        def _split_freeform_items(text: str) -> list[str]:
            if not text:
                return []
            parts = re.split(r",(?![^(]*\))", text)
            out: list[str] = []
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if re.search(r"\b(and|&)\b", part, flags=re.IGNORECASE) and "(" not in part:
                    out.extend(
                        p.strip()
                        for p in re.split(r"\b(?:and|&)\b", part, flags=re.IGNORECASE)
                        if p and p.strip()
                    )
                else:
                    out.append(part)
            return [o for o in out if o]

        def _parse_remove_all_except(message_text: str) -> tuple[list[str], str | None] | None:
            msg = normalize_choice_text(message_text or "")
            if not msg:
                return None
            m = re.match(
                r"^(?:remove|delete|drop|clear)\s+(?:all|everything)"
                r"(?:\s+(?:in|from|on|for)\s+(?P<cat>"
                r"appetizers?|apps?|starters?|mains?|main(?:\s+menu)?|main(?:\s+dishes)?|"
                r"dishes?|entrees?|desserts?))?"
                r"\s+(?:except|but(?:\s+not)?)\s+(?P<rest>.+)$",
                msg,
                flags=re.IGNORECASE,
            )
            if not m:
                return None
            category = _normalize_menu_category_hint(m.group("cat") or "")
            rest = (m.group("rest") or "").strip()
            items = _split_freeform_items(rest)
            if not items:
                return None
            return items, category

        # Deterministic "remove all ... except X" for list slots.
        if mod.action in {"remove", "replace"} and current_items and isinstance(menu, dict):
            parsed = _parse_remove_all_except(message or "")
            if not parsed and remove_texts:
                parsed = _parse_remove_all_except(remove_texts[0])
            if parsed:
                keep_terms, category_override = parsed
                if category_override and category_override != target_slot:
                    # If the user explicitly referenced a different list slot,
                    # let the normal path handle it (cross-slot disambiguation).
                    parsed = None
                else:
                    keep_res = await resolve_menu_items(keep_terms, menu=menu, existing_names=None)
                    if keep_res.matched_items and not keep_res.ambiguous_choices:
                        keep_names = [i["name"] for i in keep_res.matched_items if str(i.get("name") or "").strip()]
                        keep_lower = {n.lower() for n in keep_names}
                        removed_names = [n for n in current_items if n.lower() not in keep_lower]
                        kept = [n for n in current_items if n.lower() in keep_lower]
                        new_value = await self._format_value_for_slot(slot=target_slot, combined_names=kept, slots=slots)
                        old_value = get_slot_value(slots, target_slot)
                        fill_slot(slots, target_slot, new_value)
                        effects = apply_cascade(target_slot, old_value, new_value, slots)
                        next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                            slots=slots, state=state,
                        )
                        ack = _list_mod_ack(
                            target_slot=target_slot,
                            removed=removed_names,
                            added=[],
                            new_value=new_value,
                        ) or "Updated your selection."
                        return ToolResult(
                            state=state,
                            response_context={
                                "tool": self.name,
                                "modification": {
                                    "target_slot": target_slot,
                                    "action": "remove_all_except",
                                    "removed": removed_names,
                                    "added": [],
                                    "old_value": old_value,
                                    "new_value": new_value,
                                    "remaining_items": parse_slot_items(new_value) if new_value and str(new_value).lower() != "none" else [],
                                    "mod_ack_text": ack,
                                },
                                "cascade_effects": effects,
                                "next_phase": next_phase,
                                "next_question_target": next_target,
                                "next_question_prompt": resume_prompt,
                            },
                            input_hint=input_hint,
                            direct_response=_compose_direct_response(ack, resume_prompt),
                        )

        def _tags_in(text: str) -> set[str]:
            t = (text or "").lower()
            tags: set[str] = set()
            non_veg = bool(re.search(r"\bnon[\s-]?veg\b|\bnon[\s-]?vegetarian\b", t))
            if non_veg:
                tags.add("non_veg")
            elif re.search(r"\bveg\b|\bvegetarian\b", t):
                tags.add("veg")
            if re.search(r"\begg\b", t):
                tags.add("egg")
            if re.search(r"\bseafood\b|\bfish\b", t):
                tags.add("seafood")
            if re.search(r"\bchicken\b", t):
                tags.add("chicken")
            if re.search(r"\bpork\b", t):
                tags.add("pork")
            if re.search(r"\bbeef\b", t):
                tags.add("beef")
            return tags

        def _looks_like_group_selector(text: str) -> bool:
            cleaned = re.sub(r"[^a-z\s-]+", " ", (text or "").lower()).strip()
            if not cleaned:
                return False
            if re.search(r"\bnon[\s-]?veg\b|\bnon[\s-]?vegetarian\b", cleaned):
                return True
            group_words = {"veg", "vegetarian", "egg", "seafood", "fish", "chicken", "pork", "beef"}
            tokens = [t for t in re.split(r"\s+", cleaned) if t]
            stop = {"remove", "add", "delete", "drop", "take", "off", "all", "items", "item", "except", "but", "not", "and", "&"}

            if cleaned in group_words:
                return True
            if " items" in cleaned and any(w in cleaned for w in group_words):
                return True
            if re.search(r"\ball\b", cleaned) and any(w in cleaned for w in group_words | {"non-veg", "non veg"}):
                return True
            # Allow short action phrases like "remove seafood" / "add egg", but
            # avoid treating specific dish names ("remove chicken satay") as a group.
            if tokens and tokens[0] in {"remove", "add", "delete", "drop"} and any(t in group_words for t in tokens):
                meaningful = [t for t in tokens if t not in stop and t not in group_words]
                if not meaningful:
                    return True
            return False

        def _parse_group_selector(text: str) -> tuple[set[str], set[str]] | None:
            if not _looks_like_group_selector(text):
                return None
            parts = re.split(r"\b(?:except|but(?:\s+not)?)\b", (text or "").lower(), maxsplit=1)
            include = _tags_in(parts[0] if parts else "")
            if not include:
                return None
            exclude = _tags_in(parts[1]) if len(parts) > 1 else set()
            return include, exclude

        if target_slot in {"appetizers", "selected_dishes"} and isinstance(menu, dict):
            # Bulk remove: "remove non-veg/seafood/egg/etc"
            if mod.action in {"remove", "replace"} and current_items:
                group = None
                for txt in ([message] if message else []) + list(remove_texts):
                    group = _parse_group_selector(str(txt or ""))
                    if group:
                        break
                if group:
                    include, exclude = group
                    tags_by_name: dict[str, set[str]] = {}
                    for cat, items in (menu or {}).items():
                        for it in items or []:
                            name = str(it.get("name") or "").strip()
                            if name:
                                tags_by_name[name.lower()] = menu_item_tags(name, str(cat))

                    def _match(name: str) -> bool:
                        tags = tags_by_name.get(name.lower()) or menu_item_tags(name, "")
                        return any(t in tags for t in include) and not any(t in tags for t in exclude)

                    removed_names = [n for n in current_items if _match(n)]
                    if removed_names:
                        kept = [n for n in current_items if n not in set(removed_names)]
                        new_value = await self._format_value_for_slot(slot=target_slot, combined_names=kept, slots=slots)
                        old_value = get_slot_value(slots, target_slot)
                        fill_slot(slots, target_slot, new_value)
                        effects = apply_cascade(target_slot, old_value, new_value, slots)
                        next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                            slots=slots, state=state,
                        )
                        ack = _list_mod_ack(
                            target_slot=target_slot,
                            removed=removed_names,
                            added=[],
                            new_value=new_value,
                        ) or "Updated your selection."
                        return ToolResult(
                            state=state,
                            response_context={
                                "tool": self.name,
                                "modification": {
                                    "target_slot": target_slot,
                                    "action": "remove_group",
                                    "removed": removed_names,
                                    "added": [],
                                    "old_value": old_value,
                                    "new_value": new_value,
                                    "mod_ack_text": ack,
                                },
                                "cascade_effects": effects,
                                "next_phase": next_phase,
                                "next_question_target": next_target,
                                "next_question_prompt": resume_prompt,
                            },
                            input_hint=input_hint,
                            direct_response=_compose_direct_response(ack, resume_prompt),
                        )

            # Bulk add: "add all non-veg except pork and chicken"
            if mod.action in {"add", "replace"}:
                group = None
                for txt in ([message] if message else []) + list(add_texts):
                    group = _parse_group_selector(str(txt or ""))
                    if group:
                        break
                if group:
                    include, exclude = group
                    candidates = filter_menu_items_by_tags(menu, include_tags=include, exclude_tags=exclude)
                    candidate_names = [str(i.get("name") or "").strip() for i in candidates if str(i.get("name") or "").strip()]
                    existing_lower = {n.lower() for n in current_items}
                    added_names = [n for n in candidate_names if n.lower() not in existing_lower]
                    if added_names:
                        combined = list(current_items) + added_names
                        new_value = await self._format_value_for_slot(slot=target_slot, combined_names=combined, slots=slots)
                        old_value = get_slot_value(slots, target_slot)
                        fill_slot(slots, target_slot, new_value)
                        effects = apply_cascade(target_slot, old_value, new_value, slots)
                        next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                            slots=slots, state=state,
                        )
                        ack = _list_mod_ack(
                            target_slot=target_slot,
                            removed=[],
                            added=added_names,
                            new_value=new_value,
                        ) or "Updated your selection."
                        return ToolResult(
                            state=state,
                            response_context={
                                "tool": self.name,
                                "modification": {
                                    "target_slot": target_slot,
                                    "action": "add_group",
                                    "removed": [],
                                    "added": added_names,
                                    "old_value": old_value,
                                    "new_value": new_value,
                                    "mod_ack_text": ack,
                                },
                                "cascade_effects": effects,
                                "next_phase": next_phase,
                                "next_question_target": next_target,
                                "next_question_prompt": resume_prompt,
                            },
                            input_hint=input_hint,
                            direct_response=_compose_direct_response(ack, resume_prompt),
                        )

        # Replace no-op: "replace X with X"
        if (
            mod.action == "replace"
            and len(remove_texts) == 1
            and len(add_texts) == 1
            and remove_texts[0].strip().lower() == add_texts[0].strip().lower()
            and any(remove_texts[0].strip().lower() == ci.lower() for ci in current_items)
        ):
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
                        "action": "no_op",
                        "old_value": current_value,
                        "new_value": current_value,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response("That's already selected.", resume_prompt),
            )

        if message and current_items and mod.action in {"remove", "replace"} and remove_texts:
            # Restrict grounding to items whose names contain the query tokens.
            # This prevents description-based false matches (e.g. "egg" matching
            # "Caviar and Cream Crisp" because its description mentions roe/eggs).
            # Fall back to full list only when no name-level match exists.
            name_matched = [
                item for item in current_items
                if any(rt.lower() in item.lower() for rt in remove_texts)
            ]
            grounded = await self._ground_selected_removals(
                target_slot=target_slot,
                message=message,
                remove_texts=remove_texts,
                current_items=name_matched if name_matched else current_items,
                menu=menu,
            )
            if grounded is not None:
                if grounded.status == "resolved" and grounded.matched_names:
                    remove_texts = grounded.matched_names
                    # If grounding resolved to multiple items, the user's query
                    # was a partial word (e.g. "bacon") that hit several entries.
                    # Force disambiguation regardless of what the LLM said.
                    if len(remove_texts) > 1:
                        ambiguous_query = grounded.reference_text or ", ".join(remove_texts)
                        return self._ambiguous_list_choice_result(
                            target_slot=target_slot,
                            action=mod.action,
                            choice_kind="remove",
                            query=ambiguous_query,
                            matches=grounded.matched_names,
                            items_to_remove=remove_texts,
                            items_to_add=add_texts,
                            slots=slots,
                            state=state,
                        )
                elif grounded.status == "ambiguous" and grounded.matched_names:
                    ambiguous_query = grounded.reference_text or ", ".join(remove_texts)
                    return self._ambiguous_list_choice_result(
                        target_slot=target_slot,
                        action=mod.action,
                        choice_kind="remove",
                        query=ambiguous_query,
                        matches=grounded.matched_names,
                        items_to_remove=[ambiguous_query],
                        items_to_add=add_texts,
                        slots=slots,
                        state=state,
                    )

        ambiguous_choice = _find_ambiguous_removal_choice(current_items, remove_texts)
        if ambiguous_choice:
            return self._ambiguous_list_choice_result(
                target_slot=target_slot,
                action=mod.action,
                choice_kind="remove",
                query=ambiguous_choice["query"],
                matches=ambiguous_choice["matches"],
                items_to_remove=remove_texts,
                items_to_add=add_texts,
                slots=slots,
                state=state,
            )

        # --- Remove phase ---
        remaining = list(current_items)
        removed_names: list[str] = []
        if remove_texts:
            removed_names = _resolve_names_to_remove(current_items, remove_texts)
            removed_lower = {name.lower() for name in removed_names}
            remaining = [
                name for name in remaining
                if name.lower() not in removed_lower
            ]

        # --- Add / replace phase ---
        added_items_resolved: list[dict] = []
        already_selected: list[str] = []
        unavailable: list[str] = []
        if add_texts:
            # Track items the user requested that are already in their selection.
            for t in add_texts:
                already_selected.extend(_matching_names(current_items, t))

            if target_slot == "desserts":
                event_type = (get_slot_value(slots, "event_type") or "").lower()
                dessert_resolution = await resolve_dessert_choices(
                    add_texts,
                    is_wedding="wedding" in event_type,
                    existing_names=remaining,
                )
                if dessert_resolution.ambiguous_choices:
                    ambiguous = dessert_resolution.ambiguous_choices[0]
                    return self._ambiguous_list_choice_result(
                        target_slot=target_slot,
                        action=mod.action,
                        choice_kind="add",
                        query=ambiguous.query,
                        matches=ambiguous.matches,
                        items_to_remove=remove_texts,
                        items_to_add=add_texts,
                        slots=slots,
                        state=state,
                    )
                added_items_resolved = dessert_resolution.matched_items
            else:
                menu_resolution = await resolve_menu_items(
                    add_texts,
                    menu=menu,
                    existing_names=remaining,
                )
                if menu_resolution.ambiguous_choices:
                    ambiguous = menu_resolution.ambiguous_choices[0]
                    return self._ambiguous_list_choice_result(
                        target_slot=target_slot,
                        action=mod.action,
                        choice_kind="add",
                        query=ambiguous.query,
                        matches=ambiguous.matches,
                        items_to_remove=remove_texts,
                        items_to_add=add_texts,
                        slots=slots,
                        state=state,
                    )
                added_items_resolved = menu_resolution.matched_items

            # Item not found in stated slot — find the slot it actually belongs to.
            # For "add" with no removals, re-route the whole modification.
            # For "replace", allow remove-from-A + add-to-B so users can move an item
            # between menu sections in one turn.
            if not added_items_resolved:
                correct_slot = await self._find_correct_slot_for_items(
                    add_texts=add_texts,
                    exclude_slot=target_slot,
                    slots=slots,
                )
                if correct_slot:
                    if mod.action == "replace" and removed_names:
                        cross_add_slot = correct_slot
                        added_items_resolved = await self._resolve_items_for_slot(
                            slot=cross_add_slot,
                            add_texts=add_texts,
                            slots=slots,
                        )
                    elif mod.action == "replace" and not removed_names:
                        add_instead_slot = correct_slot
                        added_items_resolved = await self._resolve_items_for_slot(
                            slot=add_instead_slot,
                            add_texts=add_texts,
                            slots=slots,
                        )
                    elif not removed_names:
                        return await self._apply_list_modification(
                            ModificationExtraction(
                                target_slot=correct_slot,
                                action=mod.action,
                                items_to_add=list(mod.items_to_add or []),
                                items_to_remove=list(mod.items_to_remove or []),
                                new_value=mod.new_value,
                            ),
                            slots,
                            state,
                            message=message,
                        )
                # Nothing resolved anywhere and it isn't already selected: treat as unavailable.
                for t in add_texts:
                    if _matching_names(current_items, t):
                        continue
                    unavailable.append(t)

        # Cross-category confirmation: desserts <-> non-desserts in a replace
        if (
            mod.action == "replace"
            and removed_names
            and add_texts
            and _needs_cross_category_confirmation(remove_slot=target_slot, add_slot=cross_add_slot)
            and get_slot_value(slots, "__allow_cross_category_replace") is not True
        ):
            fill_slot(
                slots,
                "__pending_modification_request",
                {
                    "stage": "confirm_cross_category_replace",
                    "mod": {
                        "target_slot": mod.target_slot,
                        "action": mod.action,
                        "items_to_remove": list(mod.items_to_remove or []),
                        "items_to_add": list(mod.items_to_add or []),
                        "new_value": mod.new_value,
                    },
                    "remove_slot": target_slot,
                    "add_slot": cross_add_slot,
                    "removed": list(removed_names),
                    "add_texts": list(add_texts),
                },
            )
            removed_label = ", ".join(removed_names)
            add_slot_pretty = _SLOT_PRETTY.get(str(cross_add_slot), str(cross_add_slot))
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "next_question_target": "confirm_cross_category_replace",
                },
                input_hint={
                    "type": "options",
                    "options": [
                        {"value": "yes", "label": "Yes, do both"},
                        {"value": "no", "label": "No"},
                    ],
                },
                direct_response=(
                    f"{removed_label} is in your desserts, but \"{', '.join(add_texts)}\" looks like it belongs in {add_slot_pretty}. "
                    f"Do you want me to remove {removed_label} from desserts and add \"{', '.join(add_texts)}\" to {add_slot_pretty}?"
                ),
            )

        # Replace but the item-to-replace isn't currently selected: offer "add instead"
        if mod.action == "replace" and remove_texts and not removed_names:
            if added_items_resolved:
                add_slot = add_instead_slot or cross_add_slot or target_slot
                missing = remove_texts[0]
                missing_on_menu = False
                try:
                    missing_on_menu = bool(
                        await self._resolve_items_for_slot(
                            slot=target_slot,
                            add_texts=[missing],
                            slots=slots,
                        )
                    )
                except Exception:
                    # If menu resolution fails for any reason, fall back to the
                    # prior "not in current selection" language.
                    missing_on_menu = False
                fill_slot(
                    slots,
                    "__pending_modification_request",
                    {
                        "stage": "confirm_add_instead",
                        "add_slot": add_slot,
                        "items_to_add": [i["name"] for i in added_items_resolved],
                        "missing_text": missing,
                    },
                )
                pretty = _SLOT_PRETTY.get(add_slot, add_slot)
                add_names = ", ".join(i["name"] for i in added_items_resolved)
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "next_question_target": "confirm_add_instead",
                        "modification_target_slot": add_slot,
                    },
                    input_hint={
                        "type": "options",
                        "options": [
                            {"value": "yes", "label": f"Yes, add to {pretty}"},
                            {"value": "no", "label": "No"},
                        ],
                    },
                    direct_response=(
                        f"'{missing}' isn't {'in your current selection' if missing_on_menu else 'on our menu'}. "
                        f"Want to add {add_names} to your {pretty} instead?"
                    ),
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
                        "action": "no_match",
                        "old_value": current_value,
                        "new_value": current_value,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response(
                    f"'{remove_texts[0]}' isn't in your current selection.",
                    resume_prompt,
                ),
            )

        # No-op guard: nothing was removed or added — skip the write entirely
        if not removed_names and not added_items_resolved:
            next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                slots=slots, state=state,
            )
            ack_text: str | None = None
            if add_texts and mod.action in {"add", "replace"}:
                # Distinguish "already selected" from "not on the menu".
                # `resolve_menu_items(..., existing_names=...)` filters out items
                # already selected, which would otherwise look like "no match"
                # and trigger the wrong error message.
                already = []
                for t in add_texts:
                    already.extend(_matching_names(current_items, t))
                if already:
                    unique = []
                    seen = set()
                    for name in already:
                        key = name.lower()
                        if key in seen:
                            continue
                        unique.append(name)
                        seen.add(key)
                    if len(unique) == 1:
                        ack_text = f"{unique[0]} is already selected."
                    else:
                        preview = ", ".join(unique[:6])
                        suffix = "…" if len(unique) > 6 else ""
                        ack_text = f"Already selected: {preview}{suffix}."
                else:
                    missing = ", ".join(add_texts)
                    ack_text = f"'{missing}' isn't on the menu."
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response(ack_text, resume_prompt),
            )

        # Semantic no-op: "replace X with x" where both resolve to the same
        # canonical menu item (even if the user omitted suffixes like "w/ ...").
        if mod.action == "replace" and removed_names and added_items_resolved and not cross_add_slot:
            added_names = [str(i.get("name") or "").strip() for i in added_items_resolved if str(i.get("name") or "").strip()]
            if added_names:
                removed_norm = {normalize_choice_text(n) for n in removed_names if n}
                added_norm = {normalize_choice_text(n) for n in added_names if n}
                if removed_norm == added_norm:
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
                                "action": "no_op",
                                "old_value": current_value,
                                "new_value": current_value,
                            },
                            "next_phase": next_phase,
                            "next_question_target": next_target,
                            "next_question_prompt": resume_prompt,
                        },
                        input_hint=input_hint,
                        direct_response=_compose_direct_response("That's already selected.", resume_prompt),
                    )

        # Combine
        combined_names = list(remaining)
        if not cross_add_slot:
            combined_names = combined_names + [i["name"] for i in added_items_resolved]

        # Enforce dessert cap across modifications (menu_selection_tool already
        # caps to 4). Without this, a previous "add dessert" modification can
        # silently create 5+ desserts, and a later removal makes a hidden item
        # appear in the UI (feels like we "added" something on remove).
        if target_slot == "desserts":
            _MAX_DESSERTS = 4
            if len(combined_names) > _MAX_DESSERTS:
                attempted = [i["name"] for i in added_items_resolved if i.get("name")]
                attempted_text = f" (trying to add {', '.join(attempted)})" if attempted else ""
                current_text = ", ".join(remaining) if remaining else "none"
                prompt = (
                    f"Desserts are limited to {_MAX_DESSERTS} items{attempted_text}. "
                    f"Right now you have: {current_text}. "
                    "Tell me which dessert to remove first."
                )
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "error": "dessert_overflow",
                        "max_desserts": _MAX_DESSERTS,
                        "current_desserts": remaining,
                        "attempted_additions": attempted,
                    },
                    input_hint={
                        "type": "options",
                        "options": [
                            {"value": f"remove {name}", "label": f"Remove {name}"}
                            for name in remaining
                        ],
                    }
                    if remaining
                    else None,
                    direct_response=prompt,
                )

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
            # appetizers / selected_dishes — use exact-name catalog lookup for
            # existing items so we never re-resolve through fuzzy matching.
            # Only newly added items come from `added_items_resolved` (already resolved).
            final_value = _rebuild_list_value(combined_names, menu, added_items_resolved)

        old_value = get_slot_value(slots, target_slot)
        fill_slot(slots, target_slot, final_value)
        effects = apply_cascade(target_slot, old_value, final_value, slots)

        cross_old_value = None
        cross_new_value = None
        if cross_add_slot and added_items_resolved:
            existing = parse_slot_items(get_slot_value(slots, cross_add_slot) or "")
            cross_names = existing + [i["name"] for i in added_items_resolved]
            cross_new_value = await self._format_value_for_slot(
                slot=cross_add_slot,
                combined_names=cross_names,
                slots=slots,
            )
            cross_old_value = get_slot_value(slots, cross_add_slot)
            fill_slot(slots, cross_add_slot, cross_new_value)
            effects.extend(apply_cascade(cross_add_slot, cross_old_value, cross_new_value, slots))

        added_names = [i["name"] for i in added_items_resolved]
        if cross_add_slot and added_names:
            pretty_from = _SLOT_PRETTY.get(target_slot, target_slot)
            pretty_to = _SLOT_PRETTY.get(cross_add_slot, cross_add_slot)
            direct = (
                f"Updated your {pretty_from}: removed {', '.join(removed_names)}. "
                f"Added {', '.join(added_names)} to your {pretty_to}."
            )
        else:
            direct = _list_mod_ack(
                target_slot=target_slot,
                removed=removed_names,
                added=added_names,
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
                    "removed": removed_names,
                    "added": added_names,
                    "already_selected": sorted({n for n in already_selected if n}),
                    "unavailable": [t for t in unavailable if t],
                    "additional_changes": (
                        [
                            {
                                "target_slot": cross_add_slot,
                                "action": "add",
                                "added": added_names,
                                "old_value": cross_old_value,
                                "new_value": cross_new_value,
                                "remaining_items": (
                                    parse_slot_items(str(cross_new_value))
                                    if cross_new_value and str(cross_new_value).lower() != "none"
                                    else []
                                ),
                            }
                        ]
                        if cross_add_slot and cross_new_value is not None
                        else []
                    ),
                    "old_value": old_value,
                    "new_value": final_value,
                    "remaining_items": parse_slot_items(final_value) if final_value and str(final_value).lower() != "none" else [],
                    "mod_ack_text": direct,
                },
                "cascade_effects": effects,
                "next_phase": next_phase,
                "next_question_target": next_target,
                "next_question_prompt": resume_prompt,
            },
            input_hint=input_hint,
        )

    async def _resume_pending_choice(
        self,
        *,
        pending_choice: Any,
        message: str,
        slots: dict,
        state: dict,
    ) -> ToolResult | None:
        if not isinstance(pending_choice, dict):
            clear_slot(slots, "__pending_modification_choice")
            return None

        matches = [str(v) for v in pending_choice.get("matches") or [] if str(v).strip()]
        is_cross_slot_multi = (
            pending_choice.get("type") == "cross_slot"
            and pending_choice.get("multi")
        )

        if is_cross_slot_multi:
            # Multi-select: message is comma-separated item names (e.g. "A, B, C")
            raw_selections = [s.strip() for s in message.split(",") if s.strip()]
            match_slots: dict = pending_choice.get("match_slots") or {}
            # Resolve each raw selection against the known match names
            match_key = {normalize_choice_text(k): k for k in match_slots}
            resolved: list[str] = []
            for raw in raw_selections:
                canonical = match_key.get(normalize_choice_text(raw))
                if canonical:
                    resolved.append(canonical)
            if not resolved:
                return self._repeat_ambiguous_choice_result(
                    state=state,
                    target_slot=str(pending_choice.get("target_slot") or ""),
                    choice_kind="remove",
                    query=str(pending_choice.get("query") or ""),
                    matches=matches,
                )
            clear_slot(slots, "__pending_modification_choice")
            # Group selections by their slot and remove each group
            by_slot: dict[str, list[str]] = {}
            for item in resolved:
                by_slot.setdefault(match_slots[item], []).append(item)
            for slot_name, items in by_slot.items():
                current = parse_slot_items(get_slot_value(slots, slot_name) or "")
                norm_remove = {normalize_choice_text(i) for i in items}
                kept = [i for i in current if normalize_choice_text(i) not in norm_remove]
                fill_slot(slots, slot_name, ", ".join(kept) if kept else "")
            # Build confirmation and resume
            removed_summary = ", ".join(resolved)
            _, next_target, input_hint, resume_prompt = await _resume_after_modification(
                slots=slots, state=state,
            )
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "action": "remove",
                    "removed_items": resolved,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response(f"Removed {removed_summary}.", resume_prompt),
            )

        multi = resolve_multi_choice_selection(message, matches) or []
        selects_all = bool(multi and len(multi) == len(matches))
        selected = None if selects_all or len(multi) != 1 else multi[0]
        if not multi:
            return self._repeat_ambiguous_choice_result(
                state=state,
                target_slot=str(pending_choice.get("target_slot") or ""),
                choice_kind=str(pending_choice.get("choice_kind") or "remove"),
                query=str(pending_choice.get("query") or ""),
                matches=matches,
            )

        clear_slot(slots, "__pending_modification_choice")
        query = str(pending_choice.get("query") or "")
        choice_kind = str(pending_choice.get("choice_kind") or "remove")
        items_to_remove = [
            str(v) for v in (pending_choice.get("items_to_remove") or []) if str(v).strip()
        ]
        items_to_add = [
            str(v) for v in (pending_choice.get("items_to_add") or []) if str(v).strip()
        ]

        # For single cross-slot choice — derive the correct slot from match_slots.
        target_slot = str(pending_choice.get("target_slot") or "")
        if pending_choice.get("type") == "cross_slot":
            match_slots = pending_choice.get("match_slots") or {}
            target_slot = match_slots.get(selected, target_slot)

        if choice_kind == "remove":
            if selects_all or len(multi) > 1:
                query_key = normalize_choice_text(query)
                replaced = False
                updated: list[str] = []
                for value in items_to_remove:
                    if not replaced and normalize_choice_text(value) == query_key:
                        updated.extend(multi)
                        replaced = True
                    else:
                        updated.append(value)
                if not replaced:
                    updated.extend(multi)
                items_to_remove = updated
            else:
                items_to_remove = replace_query_with_selection(
                    items_to_remove,
                    query=query,
                    selection=str(selected),
                )
        else:
            if selects_all or len(multi) > 1:
                query_key = normalize_choice_text(query)
                replaced = False
                updated: list[str] = []
                for value in items_to_add:
                    if not replaced and normalize_choice_text(value) == query_key:
                        updated.extend(multi)
                        replaced = True
                    else:
                        updated.append(value)
                if not replaced:
                    updated.extend(multi)
                items_to_add = updated
            else:
                items_to_add = replace_query_with_selection(
                    items_to_add,
                    query=query,
                    selection=str(selected),
                )

        return await self._apply_list_modification(
            ModificationExtraction(
                target_slot=target_slot,
                action=str(pending_choice.get("action") or "remove"),
                items_to_remove=items_to_remove,
                items_to_add=items_to_add,
            ),
            slots,
            state,
            # When the user replies "all" to an ambiguity, we already resolved
            # the concrete item list. Passing the literal "all" back into the
            # grounding step can re-trigger ambiguity loops.
            message="" if selects_all or len(multi) > 1 else message,
        )

    async def _resume_pending_request(
        self,
        *,
        pending_request: Any,
        message: str,
        slots: dict,
        state: dict,
        history: list[BaseMessage],
    ) -> ToolResult | None:
        if not isinstance(pending_request, dict):
            clear_slot(slots, "__pending_modification_request")
            return None

        stage = str(pending_request.get("stage") or "target")
        msg_lower = normalize_choice_text(message or "")
        cancel_exact = {
            "nothing",
            "no change",
            "no changes",
            "nevermind",
            "never mind",
            "all good",
            "actually all good",
            "send it",
            "submit",
            "proceed",
            "go ahead",
            "confirm",
            "done",
            "cancel",
        }
        cancel_prefixes = (
            "looks good",
        )

        def _is_cancel(msg: str) -> bool:
            msg = (msg or "").strip()
            if not msg:
                return False
            if msg in cancel_exact:
                return True
            return any(msg.startswith(p) for p in cancel_prefixes)
        if stage == "confirm_add_instead":
            add_slot = str(pending_request.get("add_slot") or "")
            items_to_add = [str(v) for v in (pending_request.get("items_to_add") or []) if str(v).strip()]
            clear_slot(slots, "__pending_modification_request")
            if msg_lower in {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "go ahead"}:
                return await self._apply_list_modification(
                    ModificationExtraction(
                        target_slot=add_slot,
                        action="add",
                        items_to_add=items_to_add,
                    ),
                    slots,
                    state,
                    message=message,
                )
            # Default to no-op and resume the flow.
            next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                slots=slots,
                state=state,
            )
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response("No problem — keeping your current selection.", resume_prompt),
            )
        if stage == "confirm_cross_category_replace":
            payload = pending_request.get("mod") or {}
            clear_slot(slots, "__pending_modification_request")
            if msg_lower in {"yes", "y", "yeah", "yep", "sure", "ok", "okay", "confirm", "go ahead"}:
                fill_slot(slots, "__allow_cross_category_replace", True)
                try:
                    result = await self._apply_list_modification(
                        ModificationExtraction(
                            target_slot=str(payload.get("target_slot") or ""),
                            action=str(payload.get("action") or "replace"),
                            items_to_remove=list(payload.get("items_to_remove") or []),
                            items_to_add=list(payload.get("items_to_add") or []),
                            new_value=payload.get("new_value"),
                        ),
                        slots,
                        state,
                        message=message,
                    )
                finally:
                    clear_slot(slots, "__allow_cross_category_replace")
                return result

            # Ask for clarification on what they want to do.
            next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                slots=slots,
                state=state,
            )
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response(
                    "Okay — tell me if you want to remove the dessert, add the new item to another section, or do both.",
                    resume_prompt,
                ),
            )
        if stage == "name_disambiguation":
            clear_slot(slots, "__pending_modification_request")
            target_slot = "partner_name" if "partner" in msg_lower else "name"
            return self._ask_for_target_value(
                target_slot=target_slot,
                slots=slots,
                state=state,
            )
        if stage == "target":
            if _is_cancel(msg_lower):
                clear_slot(slots, "__pending_modification_request")
                return self._return_to_final_review(slots=slots, state=state)
            if _looks_like_direct_modification_command(message):
                clear_slot(slots, "__pending_modification_request")
                return None

            origin_phase = str(pending_request.get("origin_phase") or state.get("conversation_phase") or "")
            target_slot = _resolve_modification_subject_slot(message)
            if not target_slot:
                return self._ask_modification_target(slots, state)

            clear_slot(slots, "__pending_modification_request")
            if origin_phase == PHASE_REVIEW:
                fill_slot(slots, "__return_to_review_after_edit", {"slot": target_slot, "return_to": "picker"})
            if target_slot == "wedding_cake":
                return self._reopen_wedding_cake(slots, state)
            if target_slot in _LIST_SLOTS:
                return await self._reopen_list_slot(target_slot, slots, state, message=message)
            return self._ask_for_target_value(
                target_slot=target_slot,
                slots=slots,
                state=state,
                origin_phase=origin_phase,
            )

        target_slot = str(pending_request.get("target_slot") or "")
        origin_phase = str(pending_request.get("origin_phase") or state.get("conversation_phase") or "")
        if _is_cancel(msg_lower):
            clear_slot(slots, "__pending_modification_request")
            return self._return_to_final_review(slots=slots, state=state)
        clear_slot(slots, "__pending_modification_request")
        result = await self._apply_scalar_modification(
            ModificationExtraction(
                target_slot=target_slot,
                action="replace",
                new_value=message,
            ),
            message,
            slots,
            state,
            history,
        )
        if origin_phase == PHASE_REVIEW:
            # The user was editing from the recap. Usually we return them to the
            # recap immediately after the edit; BUT if the edit triggered a
            # confirmation step (e.g., event_type reset), we must surface that
            # prompt instead of swallowing it.
            pending = get_slot_value(slots, "__pending_confirmation")
            if isinstance(pending, dict) and pending.get("question_id") == "confirm_event_type_reset":
                return result
            if isinstance(result, ToolResult):
                ctx = result.response_context or {}
                if ctx.get("next_question_target") == "confirm_event_type_reset":
                    return result
            # The review-stage edit is done; keep them in the "change" picker so
            # they can quickly edit another field without re-reading the recap.
            if is_filled(slots, "__return_to_review_after_edit"):
                clear_slot(slots, "__return_to_review_after_edit")
            return make_modification_picker_result(
                slots=slots,
                state=state,
                prompt="Anything else you want to change?",
                include_done=True,
                origin_phase=PHASE_REVIEW,
            )
        return result

    def _ask_modification_target(
        self,
        slots: dict,
        state: dict,
    ) -> ToolResult:
        include_done = (state.get("conversation_phase") == PHASE_REVIEW)
        return make_modification_picker_result(
            slots=slots,
            state=state,
            prompt=(
                "What would you like to change? "
                "Pick one below, or type it (date, guest count, venue, menu, desserts, etc)."
            ),
            include_done=include_done,
            origin_phase=state.get("conversation_phase"),
        )

    def _ask_for_target_value(
        self,
        *,
        target_slot: str,
        slots: dict,
        state: dict,
        origin_phase: str | None = None,
    ) -> ToolResult:
        fill_slot(
            slots,
            "__pending_modification_request",
            {
                "stage": "value",
                "target_slot": target_slot,
                "origin_phase": origin_phase or state.get("conversation_phase"),
            },
        )
        label = _SLOT_LABELS.get(target_slot, target_slot.replace("_", " "))
        input_hint = None
        prompt = f"What would you like to change for your {label}?"
        if target_slot == "meal_style":
            input_hint = {
                "type": "options",
                "options": [
                    {"value": "buffet", "label": "Buffet-style"},
                    {"value": "plated", "label": "Plated"},
                ],
            }
            prompt = "How should the main meal be served — buffet or plated?"
        if target_slot == "drinks":
            input_hint = {
                "type": "options",
                "options": [
                    {"value": "no", "label": "No drinks/bar"},
                    {"value": "beer_wine", "label": "Beer & wine"},
                    {"value": "beer_wine_signature", "label": "Beer, wine + 2 signature drinks"},
                    {"value": "full_open_bar", "label": "Full open bar"},
                ],
            }
            prompt = "What drink/bar setup do you want?"
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "next_question_target": "ask_modification_value",
                "modification_target_slot": target_slot,
            },
            input_hint=input_hint,
            direct_response=prompt,
        )

    def _ask_name_disambiguation(
        self,
        slots: dict,
        state: dict,
    ) -> ToolResult:
        fill_slot(slots, "__pending_modification_request", {
            "stage": "name_disambiguation",
        })
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "next_question_target": "ask_name_disambiguation",
            },
            input_hint={
                "type": "options",
                "options": [
                    {"value": "my own name", "label": "My own name"},
                    {"value": "my partner's name", "label": "My partner's name"},
                ],
            },
            direct_response="Just to confirm — are you updating your own name or your partner's?",
        )

    def _reopen_wedding_cake(
        self,
        slots: dict,
        state: dict,
    ) -> ToolResult:
        old_value = get_slot_value(slots, "wedding_cake")
        for slot_name in (
            "wedding_cake",
            "__wedding_cake_gate",
            "__wedding_cake_flavor",
            "__wedding_cake_filling",
            "__wedding_cake_buttercream",
        ):
            if is_filled(slots, slot_name):
                clear_slot(slots, slot_name)

        state["conversation_phase"] = PHASE_WEDDING_CAKE
        target = _basic_phase_to_question(PHASE_WEDDING_CAKE, slots)
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "modification": {
                    "target_slot": "wedding_cake",
                    "action": "reopen",
                    "old_value": old_value,
                    "new_value": None,
                },
                "next_phase": PHASE_WEDDING_CAKE,
                "next_question_target": target,
            },
            direct_response="Let's choose your wedding cake again. Would you like to include one?",
            input_hint=_basic_input_hint_for_phase(PHASE_WEDDING_CAKE, slots),
        )

    async def _resolve_cross_slot_addition(
        self,
        *,
        add_texts: list[str],
        source_slot: str,
        slots: dict,
    ) -> dict[str, Any] | None:
        if not add_texts:
            return None

        best_slot: str | None = None
        best_items: list[dict] = []
        for candidate in ("appetizers", "selected_dishes", "desserts"):
            if candidate == source_slot:
                continue
            matched = await self._resolve_items_for_slot(
                slot=candidate,
                add_texts=add_texts,
                slots=slots,
            )
            if matched and len(matched) > len(best_items):
                best_slot = candidate
                best_items = matched

        if not best_slot or not best_items:
            return None

        current_names = parse_slot_items(get_slot_value(slots, best_slot) or "")
        combined_names = list(current_names) + [item["name"] for item in best_items]
        final_value = await self._format_value_for_slot(
            slot=best_slot,
            combined_names=combined_names,
            slots=slots,
        )
        old_value = get_slot_value(slots, best_slot)
        fill_slot(slots, best_slot, final_value)
        effects = apply_cascade(best_slot, old_value, final_value, slots)
        return {
            "target_slot": best_slot,
            "action": "add",
            "added": [item["name"] for item in best_items],
            "removed": [],
            "old_value": old_value,
            "new_value": final_value,
            "remaining_items": parse_slot_items(final_value) if final_value and str(final_value).lower() != "none" else [],
            "effects": effects,
        }

    async def _find_correct_slot_for_items(
        self,
        *,
        add_texts: list[str],
        exclude_slot: str,
        slots: dict,
    ) -> str | None:
        """Find which list slot the items actually belong to, excluding the already-tried slot.

        Returns the first slot where at least one item resolves, or None if no match found.
        One modification = one slot. Callers re-route the whole modification here instead of
        doing a silent cross-slot write.
        """
        for candidate in ("appetizers", "selected_dishes", "desserts"):
            if candidate == exclude_slot:
                continue
            matched = await self._resolve_items_for_slot(
                slot=candidate,
                add_texts=add_texts,
                slots=slots,
            )
            if matched:
                return candidate
        return None

    async def _resolve_items_for_slot(
        self,
        *,
        slot: str,
        add_texts: list[str],
        slots: dict,
    ) -> list[dict]:
        existing_names = parse_slot_items(get_slot_value(slots, slot) or "")
        if slot == "desserts":
            event_type = (get_slot_value(slots, "event_type") or "").lower()
            dessert_resolution = await resolve_dessert_choices(
                add_texts,
                is_wedding="wedding" in event_type,
                existing_names=existing_names,
            )
            return dessert_resolution.matched_items
        menu = await self._menu_for_slot(slot, slots)
        menu_resolution = await resolve_menu_items(
            add_texts,
            menu=menu,
            existing_names=existing_names,
        )
        return menu_resolution.matched_items

    async def _format_value_for_slot(
        self,
        *,
        slot: str,
        combined_names: list[str],
        slots: dict,
    ) -> str:
        if slot == "desserts":
            expanded = await load_dessert_menu_expanded(
                is_wedding="wedding" in (get_slot_value(slots, "event_type") or "").lower()
            )
            by_name = {i["name"].lower(): i for i in expanded}
            final_items = [by_name[n.lower()] for n in combined_names if n.lower() in by_name]
            return format_items(final_items) if final_items else "none"
        if slot == "rentals":
            return ", ".join(combined_names) if combined_names else "none"
        if not combined_names:
            return "none"
        menu = await self._menu_for_slot(slot, slots)
        _, final_value = await resolve_to_db_items(", ".join(combined_names), menu=menu)
        return final_value

    def _ambiguous_list_choice_result(
        self,
        *,
        target_slot: str,
        action: str,
        choice_kind: str,
        query: str,
        matches: list[str],
        items_to_remove: list[str],
        items_to_add: list[str],
        slots: dict,
        state: dict,
    ) -> ToolResult:
        fill_slot(slots, "__pending_modification_choice", {
            "target_slot": target_slot,
            "action": action,
            "choice_kind": choice_kind,
            "query": query,
            "matches": matches,
            "items_to_remove": items_to_remove,
            "items_to_add": items_to_add,
        })
        return self._repeat_ambiguous_choice_result(
            state=state,
            target_slot=target_slot,
            choice_kind=choice_kind,
            query=query,
            matches=matches,
        )

    def _cross_slot_choice_result(
        self,
        *,
        original_target: str,
        action: str,
        query: str,
        cross_matches: dict[str, str],
        items_to_remove: list[str],
        items_to_add: list[str],
        slots: dict,
        state: dict,
    ) -> ToolResult:
        fill_slot(slots, "__pending_modification_choice", {
            "type": "cross_slot",
            "multi": True,
            "target_slot": original_target,
            "action": action,
            "choice_kind": "remove",
            "query": query,
            "matches": list(cross_matches.keys()),
            "match_slots": cross_matches,
            "items_to_remove": items_to_remove,
            "items_to_add": items_to_add,
        })
        # Group items by section for display
        grouped: dict[str, list[str]] = {}
        for name, slot in cross_matches.items():
            grouped.setdefault(slot, []).append(name)
        menu_groups = [
            {
                "category": _SLOT_PRETTY.get(slot, slot).title(),
                "items": [{"name": name} for name in names],
            }
            for slot, names in grouped.items()
        ]
        verb = "remove" if action in {"remove", "replace"} else "update"
        prompt = f"I found '{query}' in multiple sections. Pick which ones to {verb}:"
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "error": "cross_slot_ambiguous",
                "ambiguous_query": query,
                "ambiguous_matches": list(cross_matches.keys()),
            },
            input_hint={"type": "menu_picker", "menu": menu_groups},
            direct_response=prompt,
        )

    def _repeat_ambiguous_choice_result(
        self,
        *,
        state: dict,
        target_slot: str,
        choice_kind: str,
        query: str,
        matches: list[str],
    ) -> ToolResult:
        options = [{"value": item, "label": item} for item in matches]
        pretty_slot = _SLOT_PRETTY.get(target_slot, target_slot.replace("_", " "))
        verb = "remove" if choice_kind == "remove" else "add"
        prompt = (
            f"I found more than one {pretty_slot} match for '{query}'.\n"
            f"Reply with a number (or '1,2'), the exact name, or 'all' to {verb} all of them.\n\n"
            + "\n".join(f"{idx}. {item}" for idx, item in enumerate(matches, 1))
        )
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "error": "ambiguous_list_item",
                "ambiguous_query": query,
                "ambiguous_matches": matches,
            },
            input_hint={
                "type": "options",
                "options": options,
            },
            direct_response=prompt,
        )

    async def _ground_selected_removals(
        self,
        *,
        target_slot: str,
        message: str,
        remove_texts: list[str],
        current_items: list[str],
        menu: dict[str, list[dict]],
    ) -> SelectedItemGrounding | None:
        catalog = _selected_item_catalog(current_items, menu)
        if not catalog:
            catalog = [{"name": name} for name in current_items]

        try:
            result = await extract(
                schema=SelectedItemGrounding,
                system=_SELECTION_GROUNDING_PROMPT,
                user_message=json.dumps(
                    {
                        "action": "remove",
                        "target_slot": target_slot,
                        "user_message": message,
                        "extractor_candidate_removals": remove_texts,
                        "current_selected_items": catalog,
                    },
                    ensure_ascii=True,
                ),
                model=MODEL_ROUTER,
            )
            if isinstance(result, SelectedItemGrounding):
                return result
        except Exception:
            return None
        return None

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
        old_value = get_slot_value(slots, target_slot)

        if target_slot in {"bar_service", "coffee_service", "linens", "followup_call_requested", "cocktail_hour"}:
            wants = _normalize_bool_value(
                str(new_value or message or ""),
                truthy_markers=(
                    "yes",
                    "include",
                    "add",
                    "want",
                    "need",
                    "coffee" if target_slot == "coffee_service" else "",
                    "bar" if target_slot == "bar_service" else "",
                    "linen" if target_slot == "linens" else "",
                    "cocktail" if target_slot == "cocktail_hour" else "",
                ),
                falsy_markers=("no", "skip", "none", "not needed", "don't", "do not"),
            )
            if wants is None:
                label = _SLOT_LABELS.get(target_slot, target_slot.replace("_", " "))
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "error": "invalid_new_value",
                        "modification_target_slot": target_slot,
                        "next_phase": state.get("conversation_phase"),
                        "next_question_target": "ask_modification_value",
                    },
                    direct_response=f"For {label}, reply yes or no.",
                )

            old = get_slot_value(slots, target_slot)
            fill_slot(slots, target_slot, wants)
            effects = apply_cascade(target_slot, old, wants, slots)

            # bar/coffee imply drinks=True
            if target_slot in {"bar_service", "coffee_service"} and wants is True:
                old_drinks = get_slot_value(slots, "drinks")
                fill_slot(slots, "drinks", True)
                apply_cascade("drinks", old_drinks, True, slots)

            ack_text = _scalar_mod_ack_text(target_slot=target_slot, action=mod.action, new_value=wants)
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
                        "new_value": wants,
                        "mod_ack_text": ack_text,
                        "effects": effects,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response(ack_text, resume_prompt),
            )

        if target_slot == "wedding_cake":
            # Always reopen the wedding cake sub-flow for any non-removal edit.
            # The actual cake value is composed from flavor/filling/buttercream.
            if mod.action == "remove" or _looks_like_decline(message):
                for slot_name in (
                    "wedding_cake",
                    "__wedding_cake_gate",
                    "__wedding_cake_flavor",
                    "__wedding_cake_filling",
                    "__wedding_cake_buttercream",
                ):
                    if is_filled(slots, slot_name):
                        clear_slot(slots, slot_name)
                fill_slot(slots, "__wedding_cake_gate", False)
                fill_slot(slots, "wedding_cake", "none")
                ack_text = _scalar_mod_ack_text(target_slot="wedding_cake", action="remove", new_value=None)
                next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                    slots=slots,
                    state=state,
                )
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "modification": {
                            "target_slot": "wedding_cake",
                            "action": "remove",
                            "old_value": old_value,
                            "new_value": "none",
                            "mod_ack_text": ack_text,
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                        "next_question_prompt": resume_prompt,
                    },
                    input_hint=input_hint,
                    direct_response=_compose_direct_response(ack_text, resume_prompt),
                )
            return self._reopen_wedding_cake(slots, state)

        if target_slot in _LABOR_SLOTS:
            msg = normalize_choice_text(str(new_value or message or "")).strip().lower()
            yn = _normalize_yes_no(msg)
            wants: bool | None = None
            if yn == "yes":
                wants = True
            elif yn == "no":
                wants = False
            else:
                aliases = _LABOR_SLOT_ALIASES.get(target_slot, ())
                if any(a in msg for a in aliases):
                    wants = True
                if msg in {"none", "no labor", "no staffing"}:
                    wants = False

            if wants is None:
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "error": "invalid_new_value",
                        "next_phase": state.get("conversation_phase"),
                        "next_question_target": "ask_labor_services",
                    },
                    direct_response="For staffing, reply yes/no for that service (or say none to skip staffing).",
                )

            old = get_slot_value(slots, target_slot)
            fill_slot(slots, target_slot, wants)
            apply_cascade(target_slot, old, wants, slots)
            ack_text = _scalar_mod_ack_text(target_slot=target_slot, action=mod.action, new_value=wants)
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
                        "new_value": wants,
                        "mod_ack_text": ack_text,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
                direct_response=_compose_direct_response(ack_text, resume_prompt),
            )

        # For slots that have validators (date, enums), re-run full extraction
        # so Pydantic rejects invalid values instead of corrupting state.
        multi_update_candidates = {
            "name",
            "partner_name",
            "company_name",
            "honoree_name",
            "email",
            "phone",
            "venue",
            "guest_count",
        }
        if (
            target_slot in multi_update_candidates
            and normalize_choice_text(message or "")
            and any(kw in (message or "").lower() for kw in ("change", "update"))
            and (("email" in (message or "").lower() and ("phone" in (message or "").lower() or "number" in (message or "").lower()))
                 or ("partner" in (message or "").lower() and "name" in (message or "").lower())
                 or ("guest" in (message or "").lower() and "venue" in (message or "").lower()))
        ):
            extracted = await extract(
                schema=EventDetailsExtraction,
                system=(
                    "Extract ONLY these fields if explicitly present: "
                    "name, partner_name, company_name, honoree_name, email, phone, venue, guest_count. "
                    "Set all other fields to None. Apply validators (positive guest count; venue not a meta-command)."
                ),
                user_message=message,
                history=_history_for_llm(history),
                model=MODEL_ROUTER,
            )
            applied: list[str] = []
            if extracted is not None:
                values = extracted.model_dump(exclude_none=True)
                # Apply identity gating (partner/company/honoree) based on current event_type
                values = filter_identity_fields(values, event_type=get_slot_value(slots, "event_type"))

                for field in ("name", "email", "phone", "partner_name", "company_name", "honoree_name", "venue", "guest_count"):
                    if field not in values:
                        continue
                    value = values[field]
                    if field == "venue":
                        venue_text = str(value).strip()
                        normalized_tbd = _normalize_tbd_venue(venue_text.lower())
                        value = normalized_tbd or venue_text
                    if field == "guest_count":
                        value = int(value)
                    old = get_slot_value(slots, field)
                    fill_slot(slots, field, value)
                    apply_cascade(field, old, value, slots)
                    applied.append(field)

            if applied:
                parts = [
                    _scalar_mod_ack_text(
                        target_slot=s,
                        action=mod.action,
                        new_value=get_slot_value(slots, s),
                    )
                    for s in applied
                ]
                ack_text = " ".join(p for p in parts if p).strip()
                next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                    slots=slots,
                    state=state,
                )
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "modification": {
                            "target_slot": applied[0],
                            "action": mod.action,
                            "old_value": old_value,
                            "new_value": get_slot_value(slots, applied[0]),
                            "mod_ack_text": ack_text,
                            "also_updated": applied[1:],
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                        "next_question_prompt": resume_prompt,
                    },
                    input_hint=input_hint,
                )

        if target_slot == "event_type":
            # Prefer the extractor's parsed value when present. The raw message
            # often contains extra words ("change my event type to wedding"),
            # which should not be stored verbatim.
            candidate_raw = str(mod.new_value or message or "").strip()
            msg_lower = normalize_choice_text(candidate_raw)
            event_type_map = {
                "wedding": "Wedding",
                "birthday": "Birthday",
                "bday": "Birthday",
                "corporate": "Corporate",
                "company": "Corporate",
                "office": "Corporate",
            }
            confirm_values = {
                "confirm on call",
                "confirm later",
                "tbd",
                "skip",
                "tbd - confirm on call",
            }

            requested = None

            # Pull the actual value out of phrases like "event type to wedding"
            # or "change my event type to wedding".
            extracted_value = None
            m = re.search(
                r"(?:event\s*type|type\s*of\s*event|event)\s*(?:is|to|=|:)\s*(.+)$",
                msg_lower,
            )
            if m:
                extracted_value = m.group(1).strip()
            if extracted_value:
                msg_lower = extracted_value

            # Handle leading fillers like "to wedding".
            msg_lower = re.sub(r"^(?:to|a|an|the)\s+", "", msg_lower).strip()

            # If the user is clearly asking to change the event type but did not
            # provide a new value (e.g. "change my event type"), ask for it
            # instead of storing the command text as the slot value.
            if (
                "event type" in msg_lower
                and any(v in msg_lower for v in ("change", "update", "edit", "modify"))
                and not any(
                    k in msg_lower
                    for k in (
                        "wedding",
                        "birthday",
                        "bday",
                        "corporate",
                        "company",
                        "office",
                        "confirm",
                        "tbd",
                        "other",
                    )
                )
            ):
                return self._ask_for_target_value(
                    target_slot="event_type",
                    slots=slots,
                    state=state,
                )

            if msg_lower in confirm_values or "confirm on call" in msg_lower:
                requested = "TBD - Confirm on call"
            elif msg_lower in event_type_map:
                requested = event_type_map[msg_lower]
            elif msg_lower in {"other", "others"}:
                # Not a useful value by itself.
                requested = None
            else:
                # Preserve free-text values (e.g., "graduation party") but
                # strip common leading scaffolding so we don't store "to X".
                requested = candidate_raw or None
                if requested:
                    requested = re.sub(r"^\s*(?:to)\s+", "", requested, flags=re.IGNORECASE).strip() or None

            if not requested:
                return self._ask_for_target_value(
                    target_slot="event_type",
                    slots=slots,
                    state=state,
                )

            current = str(get_slot_value(slots, "event_type") or "").strip()
            current = _normalize_event_type_display(current) or current

            # If the event type changes mid-flow and downstream slots are filled,
            # warn before resetting — but only for canonical types.
            canonical = {"Wedding", "Birthday", "Corporate"}
            if (
                requested
                and current
                and requested != current
                and _event_type_change_requires_reset(slots)
                and (state.get("conversation_phase") not in {PHASE_GREETING, PHASE_EVENT_TYPE})
                and requested in canonical
            ):
                fill_slot(slots, "__pending_confirmation", {
                    "question_id": "confirm_event_type_reset",
                    "tool": "modification_tool",
                    "old_event_type": current,
                    "new_event_type": requested,
                })
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "next_phase": state.get("conversation_phase"),
                        "next_question_target": "confirm_event_type_reset",
                        "pending_event_type": requested,
                    },
                    input_hint={
                        "type": "options",
                        "options": [
                            {"value": "yes", "label": "Yes, reset everything"},
                            {"value": "no", "label": "No, keep current details"},
                        ],
                    },
                    direct_response=(
                        f"Changing your event type from {current} to {requested} "
                        "will require redoing the event details.\n\n"
                        "Do you want to reset everything and start over for the new event type? (yes/no)"
                    ),
                )

            old = get_slot_value(slots, "event_type")
            fill_slot(slots, "event_type", requested)
            apply_cascade("event_type", old, requested, slots)
            ack_text = _scalar_mod_ack_text(
                target_slot="event_type",
                action=mod.action,
                new_value=requested,
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
                        "target_slot": "event_type",
                        "action": mod.action,
                        "old_value": old_value,
                        "new_value": requested,
                        "mod_ack_text": ack_text,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
            )

        if target_slot == "meal_style":
            normalized = _normalize_meal_style_value(new_value or message)
            if not normalized:
                return self._ask_for_target_value(
                    target_slot="meal_style",
                    slots=slots,
                    state=state,
                )
            old = get_slot_value(slots, "meal_style")
            fill_slot(slots, "meal_style", normalized)
            apply_cascade("meal_style", old, normalized, slots)
            ack_text = _scalar_mod_ack_text(
                target_slot="meal_style",
                action=mod.action,
                new_value=normalized,
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
                        "target_slot": "meal_style",
                        "action": mod.action,
                        "old_value": old_value,
                        "new_value": normalized,
                        "mod_ack_text": ack_text,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
            )

        if target_slot == "bar_package":
            normalized = _normalize_bar_package_value(new_value or message)
            if not normalized:
                return self._ask_for_target_value(
                    target_slot="drinks",
                    slots=slots,
                    state=state,
                )
            old_pkg = get_slot_value(slots, "bar_package")
            old_drinks = get_slot_value(slots, "drinks")
            fill_slot(slots, "drinks", True)
            apply_cascade("drinks", old_drinks, True, slots)
            fill_slot(slots, "bar_package", normalized)
            # bar_service should be on if they picked a package.
            old_bar = get_slot_value(slots, "bar_service")
            fill_slot(slots, "bar_service", True)
            apply_cascade("bar_service", old_bar, True, slots)
            ack_text = _scalar_mod_ack_text(
                target_slot="bar_package",
                action=mod.action,
                new_value=normalized,
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
                        "target_slot": "bar_package",
                        "action": mod.action,
                        "old_value": old_pkg,
                        "new_value": normalized,
                        "mod_ack_text": ack_text,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
            )

        if target_slot == "drinks":
            msg = normalize_choice_text(str(new_value or message or "")).strip().lower()
            if not msg:
                return self._ask_for_target_value(
                    target_slot="drinks",
                    slots=slots,
                    state=state,
                )

            yn = _normalize_yes_no(msg)
            pkg = _normalize_bar_package_value(msg)

            if yn == "no" or msg in {"no", "none", "no drinks", "no drinks/bar"}:
                old = get_slot_value(slots, "drinks")
                fill_slot(slots, "drinks", False)
                apply_cascade("drinks", old, False, slots)
                ack_text = _scalar_mod_ack_text(
                    target_slot="drinks",
                    action=mod.action,
                    new_value=False,
                )
            elif pkg:
                # Drinks + bar with a chosen package.
                old_drinks = get_slot_value(slots, "drinks")
                fill_slot(slots, "drinks", True)
                apply_cascade("drinks", old_drinks, True, slots)

                old_bar = get_slot_value(slots, "bar_service")
                fill_slot(slots, "bar_service", True)
                apply_cascade("bar_service", old_bar, True, slots)

                fill_slot(slots, "bar_package", pkg)

                ack_text = _scalar_mod_ack_text(
                    target_slot="drinks",
                    action=mod.action,
                    new_value=True,
                )
            elif yn == "yes":
                # User wants drinks, but didn't pick a bar package.
                old = get_slot_value(slots, "drinks")
                fill_slot(slots, "drinks", True)
                apply_cascade("drinks", old, True, slots)
                ack_text = _scalar_mod_ack_text(
                    target_slot="drinks",
                    action=mod.action,
                    new_value=True,
                )
            else:
                return self._ask_for_target_value(
                    target_slot="drinks",
                    slots=slots,
                    state=state,
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
                        "target_slot": "drinks",
                        "action": mod.action,
                        "old_value": old_value,
                        "new_value": get_slot_value(slots, "drinks"),
                        "mod_ack_text": ack_text,
                    },
                    "next_phase": next_phase,
                    "next_question_target": next_target,
                    "next_question_prompt": resume_prompt,
                },
                input_hint=input_hint,
            )

        if target_slot in {"email", "phone"}:
            # Use EventDetailsExtraction so a single message like
            # "my phone is X and email is Y" fills both fields at once.
            contact_extracted = await extract(
                schema=EventDetailsExtraction,
                system=(
                    "Extract ONLY contact info (phone and/or email) from the user message. "
                    "Set all other fields to None. Preserve the exact value the user provided."
                ),
                user_message=message,
                history=_history_for_llm(history),
                model=MODEL_ROUTER,
            )
            applied: list[str] = []
            if contact_extracted:
                for contact_slot in ("phone", "email"):
                    value = getattr(contact_extracted, contact_slot, None)
                    if value:
                        old = get_slot_value(slots, contact_slot)
                        fill_slot(slots, contact_slot, str(value).strip())
                        apply_cascade(contact_slot, old, value, slots)
                        applied.append(contact_slot)

            if not applied and new_value:
                old = get_slot_value(slots, target_slot)
                fill_slot(slots, target_slot, str(new_value).strip())
                apply_cascade(target_slot, old, new_value, slots)
                applied.append(target_slot)

            if applied:
                primary_slot = applied[0]
                final_value = get_slot_value(slots, primary_slot)
                if len(applied) == 1:
                    ack_text = _scalar_mod_ack_text(
                        target_slot=primary_slot,
                        action=mod.action,
                        new_value=final_value,
                    )
                else:
                    parts = [
                        _scalar_mod_ack_text(
                            target_slot=s,
                            action=mod.action,
                            new_value=get_slot_value(slots, s),
                        )
                        for s in applied
                    ]
                    ack_text = " ".join(parts)
                next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                    slots=slots,
                    state=state,
                )
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "modification": {
                            "target_slot": primary_slot,
                            "action": mod.action,
                            "old_value": old_value,
                            "new_value": final_value,
                            "mod_ack_text": ack_text,
                            "also_updated": applied[1:],
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                        "next_question_prompt": resume_prompt,
                    },
                    input_hint=input_hint,
                )

        if target_slot in {"venue", "guest_count"}:
            # Allow multi-field updates like:
            # "the venue is X and number of guests is 66"
            basic_extracted = await extract(
                schema=EventDetailsExtraction,
                system=(
                    "Extract ONLY venue and/or guest_count from the user message. "
                    "Set all other fields to None. "
                    "Apply validators (guest_count must be positive; venue must not be a meta-command)."
                ),
                user_message=message,
                history=_history_for_llm(history),
                model=MODEL_ROUTER,
            )

            applied: list[str] = []
            if basic_extracted is not None:
                # venue (with TBD normalization)
                venue_val = getattr(basic_extracted, "venue", None)
                if venue_val:
                    venue_text = str(venue_val).strip()
                    normalized_tbd = _normalize_tbd_venue(venue_text.lower())
                    final_venue = normalized_tbd or venue_text
                    old = get_slot_value(slots, "venue")
                    fill_slot(slots, "venue", final_venue)
                    apply_cascade("venue", old, final_venue, slots)
                    applied.append("venue")

                # guest_count
                guest_val = getattr(basic_extracted, "guest_count", None)
                if guest_val:
                    old = get_slot_value(slots, "guest_count")
                    fill_slot(slots, "guest_count", int(guest_val))
                    apply_cascade("guest_count", old, int(guest_val), slots)
                    applied.append("guest_count")

            if not applied and new_value:
                # Fallback to the original single-slot write if extraction found nothing.
                old = get_slot_value(slots, target_slot)
                fill_slot(slots, target_slot, str(new_value).strip())
                apply_cascade(target_slot, old, new_value, slots)
                applied.append(target_slot)

            if applied:
                primary_slot = applied[0]
                final_value = get_slot_value(slots, primary_slot)
                if len(applied) == 1:
                    ack_text = _scalar_mod_ack_text(
                        target_slot=primary_slot,
                        action=mod.action,
                        new_value=final_value,
                    )
                else:
                    parts = [
                        _scalar_mod_ack_text(
                            target_slot=s,
                            action=mod.action,
                            new_value=get_slot_value(slots, s),
                        )
                        for s in applied
                    ]
                    ack_text = " ".join(parts)
                next_phase, next_target, input_hint, resume_prompt = await _resume_after_modification(
                    slots=slots,
                    state=state,
                )
                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "modification": {
                            "target_slot": primary_slot,
                            "action": mod.action,
                            "old_value": old_value,
                            "new_value": final_value,
                            "mod_ack_text": ack_text,
                            "also_updated": applied[1:],
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                        "next_question_prompt": resume_prompt,
                    },
                    input_hint=input_hint,
                )

        if target_slot in {
            "event_date", "event_type", "service_type", "guest_count",
            "venue", "name",
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
                                "old_value": old,
                                "new_value": normalized_tbd_venue,
                                "mod_ack_text": ack_text,
                            },
                            "next_phase": next_phase,
                            "next_question_target": next_target,
                            "next_question_prompt": resume_prompt,
                        },
                        input_hint=input_hint,
                    )
            # Use BasicInfoTool's extractor. Pass the raw user message for best parsing.
            event_extracted = await extract(
                schema=EventDetailsExtraction,
                system=(
                    f"Extract the new value for {target_slot} ONLY. "
                    f"The user is changing {target_slot}. "
                    f"Extract ONLY the {target_slot} field from the user message. "
                    f"Set all other fields to None. "
                    "Apply all validators (future dates only, positive guest count)."
                ),
                user_message=message,
                history=_history_for_llm(history),
                model=MODEL_ROUTER,
            )
            if event_extracted is not None:
                extracted_values = event_extracted.model_dump(exclude_none=True)
                extracted_values = filter_extraction_fields(extracted_values, [target_slot])
                effective_event_type = extracted_values.get("event_type") or get_slot_value(slots, "event_type")
                extracted_values = filter_identity_fields(
                    extracted_values,
                    event_type=effective_event_type,
                )

                # Mid-flow event-type change can invalidate everything downstream.
                # Ask for explicit confirmation before clearing/resetting.
                if target_slot == "event_type" and "event_type" in extracted_values:
                    current_event_type = str(get_slot_value(slots, "event_type") or "").strip()
                    requested_event_type = str(extracted_values.get("event_type") or "").strip()
                    if (
                        requested_event_type
                        and current_event_type
                        and requested_event_type != current_event_type
                        and _event_type_change_requires_reset(slots)
                        and (state.get("conversation_phase") not in {PHASE_GREETING, PHASE_EVENT_TYPE})
                    ):
                        fill_slot(slots, "__pending_confirmation", {
                            "question_id": "confirm_event_type_reset",
                            "tool": "modification_tool",
                            "old_event_type": current_event_type,
                            "new_event_type": requested_event_type,
                        })
                        return ToolResult(
                            state=state,
                            response_context={
                                "tool": self.name,
                                "next_phase": state.get("conversation_phase"),
                                "next_question_target": "confirm_event_type_reset",
                                "pending_event_type": requested_event_type,
                            },
                            input_hint={
                                "type": "options",
                                "options": [
                                    {"value": "yes", "label": "Yes, reset everything"},
                                    {"value": "no", "label": "No, keep current details"},
                                ],
                            },
                            direct_response=(
                                f"Changing your event type from {current_event_type} to {requested_event_type} "
                                "usually means redoing the event details (menu, service style, add-ons, etc).\n\n"
                                "Do you want to reset everything and start over for the new event type? (yes/no)"
                            ),
                        )

                for fname, value in extracted_values.items():
                    if fname != target_slot:
                        continue
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
                    modified_slot=target_slot,
                )

                return ToolResult(
                    state=state,
                    response_context={
                        "tool": self.name,
                        "modification": {
                            "target_slot": target_slot,
                            "action": mod.action,
                            "old_value": old_value,
                            "new_value": final_value,
                            "mod_ack_text": ack_text,
                        },
                        "next_phase": next_phase,
                        "next_question_target": next_target,
                        "next_question_prompt": resume_prompt,
                    },
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
            new_value = _sanitize_slot_value(str(new_value))
            if (
                target_slot in _APPENDABLE_TEXT_SLOTS
                and mod.action == "add"
                and old_value not in (None, "", "none")
            ):
                old_text = str(old_value).strip()
                new_text = new_value
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
                "next_question_prompt": resume_prompt,
            },
            input_hint=input_hint,
        )

    async def _reopen_list_slot(
        self,
        target_slot: str,
        slots: dict,
        state: dict,
        *,
        message: str = "",
    ) -> ToolResult:
        """Clear the requested list slot and hand control back to menu selection
        so the user can re-pick from the catalog. Dependent style slots (e.g.
        appetizer_style, meal_style) also reset so the follow-up prompt fires."""
        old_value = get_slot_value(slots, target_slot)
        clear_slot(slots, target_slot)
        if target_slot == "rentals":
            # "Linens" is a rental subtype, stored separately for recap/UI. When
            # the user redoes rentals, clear both so the next selection is clean.
            if is_filled(slots, "linens"):
                clear_slot(slots, "linens")
            if is_filled(slots, "__gate_rentals"):
                clear_slot(slots, "__gate_rentals")
        if target_slot == "desserts" and is_filled(slots, "__gate_desserts"):
            clear_slot(slots, "__gate_desserts")
        if target_slot == "appetizers" and is_filled(slots, "appetizer_style"):
            clear_slot(slots, "appetizer_style")
        if target_slot == "selected_dishes" and is_filled(slots, "meal_style"):
            clear_slot(slots, "meal_style")

        next_phase = LIST_SLOT_TO_PHASE.get(target_slot)
        if next_phase:
            state["conversation_phase"] = next_phase

        pretty = _SLOT_PRETTY.get(target_slot, target_slot)
        menu_text, input_hint = await self._render_slot_menu(target_slot, slots)
        header = f"No problem — let's redo your {pretty}. Pick whatever you'd like:"
        if target_slot == "desserts":
            msg_lower = (message or "").strip().lower()
            if "dessert" in msg_lower and "all" in msg_lower:
                header = "We can only choose up to 4 desserts — please pick up to 4."
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


def _rebuild_list_value(
    combined_names: list[str],
    menu: dict[str, list[dict]],
    added_items: list[dict],
) -> str:
    """Build a formatted slot value without re-resolving existing items through fuzzy DB lookup.

    Strategy:
    - Newly added items already have full price data from the resolver — use them directly.
    - Remaining existing items are looked up by exact name in the menu catalog.
    - If an existing name isn't found in the catalog (custom/stale), keep it as a plain name.

    This prevents `resolve_to_db_items` fuzzy re-matching from corrupting data when
    existing item names don't exactly match the current catalog.
    """
    if not combined_names:
        return "none"

    # Build exact-name catalog from the menu (no fuzzy matching)
    catalog: dict[str, dict] = {}
    for items in menu.values():
        for item in items:
            name = str(item.get("name") or "").strip()
            if name:
                catalog[name.lower()] = item

    # Newly added items already resolved with full price data
    added_by_name: dict[str, dict] = {
        str(i.get("name") or "").lower(): i
        for i in added_items
        if i.get("name")
    }

    final_items: list[dict] = []
    for name in combined_names:
        name_lower = name.lower()
        if name_lower in added_by_name:
            final_items.append(added_by_name[name_lower])
        elif name_lower in catalog:
            final_items.append(catalog[name_lower])
        else:
            final_items.append({"name": name})

    return format_items(final_items) if final_items else "none"


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


def _selected_item_catalog(
    current_items: list[str],
    menu: dict[str, list[dict]],
) -> list[dict[str, Any]]:
    catalog_by_name: dict[str, dict[str, Any]] = {}
    for category, items in menu.items():
        for item in items:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            catalog_by_name[name.lower()] = {
                "name": name,
                "category": category,
                "description": item.get("description"),
            }

    out: list[dict[str, Any]] = []
    for name in current_items:
        entry = catalog_by_name.get(name.lower())
        if entry is None:
            out.append({"name": name})
            continue
        out.append(entry)
    return out


_PHASE_ACTIVE_SLOT: dict[str, str] = {
    PHASE_COCKTAIL: "appetizers",
    PHASE_MAIN_MENU: "selected_dishes",
    PHASE_DESSERT: "desserts",
}


def _modification_context_block(slots: dict, state: dict) -> str:
    lines: list[str] = []
    lines.append(
        "If the user says they want to reselect, redo, start over, or see a whole menu section again "
        "without naming concrete items, use action='reopen' for that list slot."
    )

    # Tell the LLM which list slot the user is currently filling so ambiguous
    # "add X" requests (e.g. "add soups/salad" at main-menu phase) target the
    # right slot instead of defaulting to appetizers.
    phase = state.get("conversation_phase", "")
    active_slot = _PHASE_ACTIVE_SLOT.get(phase)
    if active_slot:
        slot_label = {"appetizers": "appetizers", "selected_dishes": "main dishes", "desserts": "desserts"}[active_slot]
        lines.append(
            f"Current phase: {phase}. The user is actively building their {slot_label}. "
            f"For 'add' requests with no explicit slot context, prefer target_slot='{active_slot}'."
        )

    lists_context = _current_lists_context(slots)
    if lists_context:
        lines.append(lists_context)
    return "\n".join(line for line in lines if line)


def _is_unspecified_list_change(mod: ModificationExtraction) -> bool:
    """The user wants to edit a list slot but didn't name items — we should
    clear the slot and re-show the picker instead of writing an empty list."""
    if mod.target_slot not in _LIST_SLOTS:
        return False
    has_remove = bool(mod.items_to_remove)
    has_add = bool(mod.items_to_add)
    has_value = mod.new_value is not None and str(mod.new_value).strip() != ""
    return not (has_remove or has_add or has_value)


def _items_mentioned_in_message(items: list[str], message: str) -> bool:
    """Return True if any item string appears (case-insensitive, token-level)
    in the user's message. Used to detect LLM hallucination of list items."""
    if not items or not message:
        return False
    msg_lower = message.lower()
    for item in items:
        if not item:
            continue
        # Try full phrase, then any significant word from the item name.
        item_lower = str(item).lower().strip()
        if not item_lower:
            continue
        if item_lower in msg_lower:
            return True
        # Token overlap: if any 4+ char word from the item appears in msg.
        for token in re.split(r"[^a-z0-9]+", item_lower):
            if len(token) >= 4 and token in msg_lower:
                return True
    return False


def _has_hallucinated_list_items(mod: ModificationExtraction, message: str) -> bool:
    """The LLM returned item names for a list-slot add/replace, but NONE of
    them appear in the user's message. This happens when a vague command
    like 'ADD DESSERTS' primes the model to invent reasonable-looking items
    from the catalog instead of reopening the picker. Treat as unspecified."""
    if mod.target_slot not in _LIST_SLOTS:
        return False
    if mod.action not in {"add", "replace"}:
        return False
    items = list(mod.items_to_add or [])
    if mod.new_value and isinstance(mod.new_value, str):
        items.append(mod.new_value)
    if not items:
        return False
    return not _items_mentioned_in_message(items, message)


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

    patterns = LIST_SLOT_REOPEN_PHRASES.get(mod.target_slot, ())
    if not any(p in msg for p in patterns):
        mentions = LIST_SLOT_MENTION_PATTERNS.get(mod.target_slot, ())
        if not (
            any(re.search(rf"\b{re.escape(term)}\b", msg) for term in mentions)
            and any(marker in msg for marker in GENERIC_REOPEN_MARKERS)
        ):
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
            "reselect", "redo", "start over", "again",
        }:
            explicit_items = True

    return not explicit_items


def _should_reopen_wedding_cake(message: str, mod: ModificationExtraction) -> bool:
    if mod.target_slot != "wedding_cake":
        return False

    if mod.action == "reopen":
        return True

    return _mentions_wedding_cake_reopen(message)


def _current_lists_context(slots: dict) -> str:
    """Snapshot of the list slots the user may be editing, passed to the LLM
    so it names items correctly and picks the right target_slot."""
    lines: list[str] = ["CURRENT FILLED LISTS (use these exact item names):"]
    any_content = False
    for slot in ("appetizers", "desserts", "rentals", "selected_dishes"):
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


def _find_cross_slot_matches(probe_items: list[str], slots: dict) -> dict[str, str]:
    """Return {item_name: slot_name} for probe items that match across multiple list slots.

    Only populated when matches span MORE than one slot — single-slot hits return {}.
    """
    probe_lower = [p.strip().lower() for p in probe_items if p and p.strip()]
    if not probe_lower:
        return {}

    per_slot: dict[str, list[str]] = {}
    for slot in ("appetizers", "selected_dishes", "desserts"):
        val = get_slot_value(slots, slot)
        if not val or str(val).lower() == "none":
            continue
        for name in parse_slot_items(str(val)):
            name_lower = name.lower()
            for p in probe_lower:
                if p in name_lower or name_lower in p:
                    per_slot.setdefault(slot, []).append(name)
                    break

    if len(per_slot) < 2:
        return {}
    return {name: slot for slot, names in per_slot.items() for name in names}


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


def _matching_names(current_items: list[str], query: str) -> list[str]:
    needle = str(query or "").strip().lower()
    if not needle:
        return []
    return [
        name for name in current_items
        if needle == name.lower() or needle in name.lower() or name.lower() in needle
    ]


def _find_ambiguous_removal_choice(current_items: list[str], remove_texts: list[str]) -> dict[str, Any] | None:
    for query in remove_texts:
        matches = _matching_names(current_items, query)
        if len(matches) > 1 and query.strip().lower() not in {name.lower() for name in matches}:
            return {
                "query": query,
                "matches": matches,
            }
    return None


def _resolve_names_to_remove(current_items: list[str], remove_texts: list[str]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for query in remove_texts:
        for name in _matching_names(current_items, query):
            lowered = name.lower()
            if lowered in seen:
                continue
            names.append(name)
            seen.add(lowered)
    return names


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
    if target_slot == "drinks":
        if value is True:
            return "included"
        if value is False:
            return "not included"
        return text
    if target_slot == "meal_style":
        lowered = text.lower().strip()
        if lowered == "buffet":
            return "buffet-style"
        if lowered == "plated":
            return "plated"
        return text
    if target_slot == "service_type":
        return "drop-off" if text.lower() == "dropoff" else text
    if target_slot == "bar_package":
        return {
            "beer_wine": "beer & wine",
            "beer_wine_signature": "beer, wine + 2 signature drinks",
            "full_open_bar": "full open bar",
        }.get(text.lower().strip(), text)
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
    modified_slot: str | None = None,
) -> tuple[str | None, str | None, dict | None, str | None]:
    """
    Compute the best "resume" question after applying a modification.

    This is critical UX: after a mid-flow edit (including no-ops like "replace X with X"),
    we should re-ask whatever question was pending so the user can continue without
    guessing what to do next.
    """
    phase = state.get("conversation_phase")

    # Intake (basic-info) phases — ALWAYS recompute from the current slot state
    # rather than trusting the stale stored phase. A modification can flip
    # event_type and cascade-clear dependent slots, so the stored phase is
    # often wrong (e.g. pointing at service_type when wedding_cake is newly
    # unfilled). basic_info_tool._next_phase walks the required-slot order
    # and returns the true next gap.
    _INTAKE_PHASES = {
        PHASE_GREETING,
        PHASE_EVENT_TYPE,
        PHASE_CONDITIONAL_FOLLOWUP,
        PHASE_WEDDING_CAKE,
        PHASE_SERVICE_TYPE,
        PHASE_EVENT_DATE,
        PHASE_VENUE,
        PHASE_GUEST_COUNT,
    }
    # When event_type itself was just modified, the cascade may have cleared
    # partner_name / honoree_name / company_name / service_type. Always recheck
    # the full intake sequence in that case so the user is re-asked the now-
    # relevant conditional slots before continuing — regardless of current phase.
    if modified_slot == "event_type":
        recomputed = _basic_next_phase(slots)
        if recomputed in _INTAKE_PHASES:
            state["conversation_phase"] = recomputed
            target = _basic_phase_to_question(recomputed, slots)
            prompt = None
            if target:
                from agent.prompt_registry import fallback_prompt_for_target

                prompt = fallback_prompt_for_target("basic_info_tool", target)
            return recomputed, target, _basic_input_hint_for_phase(recomputed, slots), prompt
        if phase in _INTAKE_PHASES or phase is None:
            phase = recomputed
            state["conversation_phase"] = phase
    elif phase in _INTAKE_PHASES or phase is None:
        recomputed = _basic_next_phase(slots)
        if recomputed in _INTAKE_PHASES:
            state["conversation_phase"] = recomputed
            target = _basic_phase_to_question(recomputed, slots)
            prompt = None
            if target:
                from agent.prompt_registry import fallback_prompt_for_target

                prompt = fallback_prompt_for_target("basic_info_tool", target)
            return recomputed, target, _basic_input_hint_for_phase(recomputed, slots), prompt
        phase = recomputed
        state["conversation_phase"] = phase

    if phase in {PHASE_TRANSITION, PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT}:
        if phase == PHASE_TRANSITION:
            state["conversation_phase"] = phase
            return phase, "transition_to_menu", None, None
        target = _menu_next_target([], phase, slots)
        if phase == PHASE_DESSERT and not is_filled(slots, "desserts") and get_slot_value(slots, "__gate_desserts") is not True:
            state["conversation_phase"] = phase
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
            resume_prompt = "How should we serve the appetizers - passed or station?"
        elif target == "ask_meal_style":
            resume_prompt = "Would you like the meal served plated or buffet-style?"
        elif target == "transition_to_addons":
            resume_prompt = "Do you want drinks or bar service for the event?"
        state["conversation_phase"] = phase
        return phase, target, input_hint, resume_prompt

    if phase == PHASE_WEDDING_CAKE:
        target = _basic_phase_to_question(phase, slots)
        prompt = None
        if target:
            from agent.prompt_registry import fallback_prompt_for_target

            prompt = fallback_prompt_for_target("basic_info_tool", target)
        state["conversation_phase"] = phase
        return phase, target, _basic_input_hint_for_phase(phase, slots), prompt

    if phase in {PHASE_DRINKS_BAR, PHASE_TABLEWARE, PHASE_RENTALS, PHASE_LABOR}:
        target = _addons_next_target(slots)
        state["conversation_phase"] = phase
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
            state["conversation_phase"] = phase
            return (
                phase,
                target,
                _finalization_input_hint_for_target(target),
                _render_final_review_recap(summary),
            )
        state["conversation_phase"] = phase
        return (
            phase,
            target,
            _finalization_input_hint_for_target(target),
            _finalization_direct_response_for_target(target),
        )

    # As a last resort, keep the current phase but still try to provide a
    # concrete follow-up prompt if we know the next target. This prevents
    # "ack only + buttons" responses where the UI shows options but the user
    # never sees the question text.
    target = None
    input_hint = None
    resume_prompt = None
    try:
        # Attempt a best-effort next step from the current slot state.
        if phase in {PHASE_DRINKS_BAR, PHASE_TABLEWARE, PHASE_RENTALS, PHASE_LABOR}:
            target = _addons_next_target(slots)
            input_hint = _addons_input_hint_for_target(target, slots)
            resume_prompt = _addons_direct_response_for_target(target, slots)
        elif phase in {PHASE_TRANSITION, PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT}:
            target = _menu_next_target([], phase, slots)
            input_hint = await _menu_input_hint_for_menu_phase(phase, slots)
        elif phase in _INTAKE_PHASES:
            target = _basic_phase_to_question(phase, slots)
            input_hint = _basic_input_hint_for_phase(phase, slots)
    except Exception:
        # Never let resume logic crash the modification tool.
        target = None

    if target and not resume_prompt:
        from agent.prompt_registry import fallback_prompt_for_target

        resume_prompt = fallback_prompt_for_target("modification_tool", target)

    if phase is not None:
        state["conversation_phase"] = phase
    return phase, target, input_hint, resume_prompt


_SLOT_LABELS = {
    "name": "name",
    "email": "email",
    "phone": "phone number",
    "event_type": "event type",
    "event_type_other": "event (other)",
    "event_date": "date",
    "venue": "venue",
    "guest_count": "guest count",
    "partner_name": "partner name",
    "company_name": "company name",
    "honoree_name": "honoree",
    "appetizers": "appetizers",
    "selected_dishes": "main dishes",
    "meal_style": "meal style",
    "desserts": "desserts",
    "menu_notes": "menu notes",
    "wedding_cake": "wedding cake",
    "service_type": "service",
    "drinks": "drinks",
    "bar_service": "bar service",
    "bar_package": "bar package",
    "coffee_service": "coffee service",
    "tableware": "tableware",
    "utensils": "utensils",
    "linens": "rentals (linens)",
    "rentals": "rentals",
    "special_requests": "special requests",
    "dietary_concerns": "dietary concerns",
    "additional_notes": "notes",
    "followup_call_requested": "follow-up call",
}


__all__ = ["ModificationTool"]

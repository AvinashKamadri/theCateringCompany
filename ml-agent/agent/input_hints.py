"""
Node → input_hint mapping for the frontend.

FE reads this to render the right widget (calendar, choice buttons, email box, etc.)
independent of how the LLM phrased the question. Keeps UI stable even when the
assistant's wording varies.
"""

from typing import Any, Optional


_EVENT_TYPE_CHOICES = ["Wedding", "Birthday", "Corporate", "Social", "Custom"]
_SERVICE_TYPE_CHOICES = ["Drop-off (we deliver, no staff)", "Onsite (our team is there with you)"]
_SERVICE_STYLE_CHOICES = ["Cocktail hour", "Full reception", "Both"]
_MEAL_STYLE_CHOICES = ["Plated", "Buffet"]
_APPETIZER_STYLE_CHOICES = ["Passed", "Station"]
_UTENSILS_CHOICES = ["Standard Plastic", "Eco-friendly / Biodegradable", "Bamboo"]
_TABLEWARE_CHOICES = [
    "Standard Disposable (included)",
    "Premium Disposable (gold or silver) — $1 per person",
    "Full China — pricing based on guest count",
]
_RENTAL_CHOICES = ["Linens", "Tables", "Chairs"]
_DRINKS_CHOICES = ["Coffee Service", "Bar Service", "Both"]
_BAR_SERVICE_CHOICES = ["Beer & Wine", "Beer & Wine + Two Signature Drinks", "Full Open Bar"]
_LABOR_CHOICES = ["Chef", "Servers", "Bartenders", "All"]
_YES_NO = ["Yes", "No"]


# Static map: node name → hint descriptor (kind, slot, choices?)
_STATIC_HINTS: dict[str, dict[str, Any]] = {
    "collect_name":             {"kind": "text",          "slot": "name"},
    "collect_event_date":       {"kind": "date",          "slot": "event_date"},
    "collect_fiance_name":      {"kind": "text",          "slot": "partner_name"},
    "collect_birthday_person":  {"kind": "text",          "slot": "honoree_name"},
    "collect_company_name":     {"kind": "text",          "slot": "company_name"},
    "collect_venue":            {"kind": "text",          "slot": "venue"},
    "collect_guest_count":      {"kind": "number",        "slot": "guest_count", "min": 10, "max": 10000},
    "select_event_type":        {"kind": "choice",        "slot": "event_type",    "choices": _EVENT_TYPE_CHOICES},
    "select_service_type":      {"kind": "choice",        "slot": "service_type",  "choices": _SERVICE_TYPE_CHOICES},
    "select_service_style":     {"kind": "choice",        "slot": "service_style", "choices": _SERVICE_STYLE_CHOICES},
    "collect_meal_style":       {"kind": "choice",        "slot": "meal_style",    "choices": _MEAL_STYLE_CHOICES},
    "collect_appetizer_style":  {"kind": "choice",        "slot": "appetizer_style", "choices": _APPETIZER_STYLE_CHOICES},
    "ask_appetizers":           {"kind": "choice",        "slot": "appetizers",    "choices": _YES_NO},
    "select_appetizers":        {"kind": "multi_choice",  "slot": "appetizers"},
    "present_menu":             {"kind": "multi_choice",  "slot": "selected_dishes", "min": 3, "max": 5},
    "select_dishes":            {"kind": "multi_choice",  "slot": "selected_dishes", "min": 3, "max": 5},
    "ask_menu_changes":         {"kind": "choice",        "slot": "selected_dishes", "choices": _YES_NO},
    "collect_menu_changes":     {"kind": "text",          "slot": "selected_dishes"},
    "ask_utensils":             {"kind": "choice",        "slot": "utensils",      "choices": _YES_NO},
    "select_utensils":          {"kind": "choice",        "slot": "utensils",      "choices": _UTENSILS_CHOICES},
    "collect_tableware":        {"kind": "choice",        "slot": "tableware",     "choices": _TABLEWARE_CHOICES},
    "ask_desserts":             {"kind": "choice",        "slot": "desserts",      "choices": _YES_NO},
    "select_desserts":          {"kind": "multi_choice",  "slot": "desserts",      "max": 4},
    "ask_more_desserts":        {"kind": "choice",        "slot": "desserts",      "choices": _YES_NO},
    "ask_rentals":              {"kind": "multi_choice",  "slot": "rentals",       "choices": _RENTAL_CHOICES},
    "collect_drinks":           {"kind": "choice",        "slot": "drinks",        "choices": _DRINKS_CHOICES},
    "collect_bar_service":      {"kind": "choice",        "slot": "drinks",        "choices": _BAR_SERVICE_CHOICES},
    "collect_labor":            {"kind": "multi_choice",  "slot": "labor",         "choices": _LABOR_CHOICES},
    "ask_special_requests":     {"kind": "choice",        "slot": "special_requests", "choices": _YES_NO},
    "collect_special_requests": {"kind": "text",          "slot": "special_requests"},
    "collect_dietary":          {"kind": "choice",        "slot": "dietary_concerns", "choices": _YES_NO},
    "collect_dietary_details":  {"kind": "text",          "slot": "dietary_concerns"},
    "ask_anything_else":        {"kind": "choice",        "slot": "additional_notes", "choices": _YES_NO},
    "collect_anything_else":    {"kind": "text",          "slot": "additional_notes"},
    "offer_followup":           {"kind": "choice",        "slot": "followup_call", "choices": _YES_NO},
    "generate_contract":        {"kind": "text",          "slot": None},
    "start":                    {"kind": "text",          "slot": "name"},
}


def get_input_hint(current_node: str, state: Optional[dict] = None) -> Optional[dict]:
    """Return the input_hint dict for the next message given the current node.

    `state` is passed in so hints can be dynamic (e.g. collect_pending_details
    picks date/text/number based on which TBD slot is being asked).
    """
    if current_node == "collect_pending_details" and state is not None:
        asking = state.get("_pending_asking")
        if asking == "event_date":
            return {"kind": "date", "slot": "event_date"}
        if asking == "venue":
            return {"kind": "text", "slot": "venue"}
        if asking == "guest_count":
            return {"kind": "number", "slot": "guest_count", "min": 10, "max": 10000}
        return {"kind": "text", "slot": None}

    hint = _STATIC_HINTS.get(current_node)
    if hint is None:
        return None
    # Return a shallow copy so callers can't mutate our static table
    return dict(hint)

"""
Cascade dependency map — Section 7 of AGENT_SPEC.md.

When certain slots change value, dependent slots must be cleared or auto-set.
This keeps the state consistent without making every Tool re-implement the
rules.

Contract: `apply_cascade(slot_name, old_value, new_value, slots)` is called
AFTER `fill_slot()` writes the new value. It mutates `slots` in place and
returns a list of (slot_name, action) tuples describing what it did — so the
response generator can mention auto-changes ("switched to Dropoff, removed
labor add-ons").
"""

from __future__ import annotations

from typing import Any

from agent.state import clear_slot, fill_slot, get_slot_value


_LABOR_SLOTS = (
    "labor_ceremony_setup",
    "labor_table_setup",
    "labor_table_preset",
    "labor_cleanup",
    "labor_trash",
)

_WEDDING_CAKE_STAGE_SLOTS = (
    "__wedding_cake_gate",
    "__wedding_cake_flavor",
    "__wedding_cake_filling",
    "__wedding_cake_buttercream",
)


def apply_cascade(
    slot_name: str,
    old_value: Any,
    new_value: Any,
    slots: dict,
) -> list[tuple[str, str]]:
    """Apply Section 7 cascade rules. Returns list of side-effect descriptions.

    Caller is responsible for having already written the triggering slot via
    fill_slot(). This function only handles the dependents.
    """
    effects: list[tuple[str, str]] = []

    # --- event_type change clears the conditional-followup slots ---
    if slot_name == "event_type" and old_value != new_value:
        for dep, need in (
            ("partner_name", "Wedding"),
            ("company_name", "Corporate"),
            ("honoree_name", "Birthday"),
        ):
            if new_value != need and slots.get(dep, {}).get("filled"):
                clear_slot(slots, dep)
                effects.append((dep, "cleared (event type changed)"))
        if new_value != "Wedding":
            if slots.get("wedding_cake", {}).get("filled"):
                clear_slot(slots, "wedding_cake")
                effects.append(("wedding_cake", "cleared (event type changed)"))
            for dep in _WEDDING_CAKE_STAGE_SLOTS:
                if slots.get(dep, {}).get("filled"):
                    clear_slot(slots, dep)
                    effects.append((dep, "cleared (event type changed)"))
        # Service type chosen for one event kind may not apply to the new kind
        # (e.g. "drop-off" picked for a birthday becomes wrong for a wedding).
        # Clear it so the user gets re-asked for the new event type.
        if slots.get("service_type", {}).get("filled"):
            clear_slot(slots, "service_type")
            effects.append(("service_type", "cleared (event type changed — re-ask needed)"))

    # --- service_type == Dropoff clears ALL labor + disables bartender ---
    elif slot_name == "service_type":
        if new_value == "Dropoff":
            for s in _LABOR_SLOTS:
                if slots.get(s, {}).get("filled"):
                    fill_slot(slots, s, False)
                    effects.append((s, "set False (Dropoff — no onsite staff)"))
            # bartender can't be True if no staff onsite
            if get_slot_value(slots, "bartender"):
                fill_slot(slots, "bartender", False)
                effects.append(("bartender", "set False (Dropoff)"))

    # --- bar_service drives bartender + clears bar_package on False ---
    elif slot_name == "bar_service":
        # bartender auto-syncs — non-optional per spec
        fill_slot(slots, "bartender", bool(new_value))
        effects.append(("bartender", f"auto-set to {bool(new_value)}"))
        if not new_value and slots.get("bar_package", {}).get("filled"):
            clear_slot(slots, "bar_package")
            effects.append(("bar_package", "cleared (bar declined)"))

    # --- drinks == False clears bar + coffee ---
    elif slot_name == "drinks":
        if not new_value:
            # Always fill these — even if previously unfilled — so _phase_of()
            # never loops waiting for coffee_service/bar_service after drinks=False.
            for s in ("bar_service", "bartender", "coffee_service"):
                fill_slot(slots, s, False)
                effects.append((s, "set False (drinks declined)"))
            if slots.get("bar_package", {}).get("filled"):
                clear_slot(slots, "bar_package")
                effects.append(("bar_package", "cleared (drinks declined)"))

    # cocktail_hour no longer cascades. Appetizers are always collected
    # regardless of whether the wedding has a cocktail hour, reception only,
    # or both — the flag now only drives service_style / UI labeling.

    # --- custom_menu == True clears the catalog dish picks ---
    elif slot_name == "custom_menu":
        if new_value and slots.get("selected_dishes", {}).get("filled"):
            clear_slot(slots, "selected_dishes")
            effects.append(("selected_dishes", "cleared (custom menu requested)"))

    # --- wedding_cake removal clears hidden cake-stage slots ---
    elif slot_name == "wedding_cake":
        if new_value in (None, "", "none"):
            for dep in _WEDDING_CAKE_STAGE_SLOTS:
                if slots.get(dep, {}).get("filled"):
                    clear_slot(slots, dep)
                    effects.append((dep, "cleared (wedding cake removed)"))

    # --- meal_style == plated auto-notes china ---
    elif slot_name == "meal_style":
        if new_value == "plated":
            current_tw = get_slot_value(slots, "tableware")
            if current_tw is None:
                fill_slot(slots, "tableware", "china")
                effects.append(("tableware", "auto-set china (plated meal)"))

    return effects


__all__ = ["apply_cascade"]

"""Shared intent helpers for reopening previously visited list sections."""

from __future__ import annotations

import re

from agent.state import (
    PHASE_COCKTAIL,
    PHASE_DESSERT,
    PHASE_MAIN_MENU,
    PHASE_RENTALS,
)


LIST_SLOT_TO_PHASE: dict[str, str] = {
    "appetizers": PHASE_COCKTAIL,
    "selected_dishes": PHASE_MAIN_MENU,
    "desserts": PHASE_DESSERT,
    "rentals": PHASE_RENTALS,
}


LIST_SLOT_REOPEN_PHRASES: dict[str, tuple[str, ...]] = {
    "desserts": (
        "dessert menu",
        "desserts menu",
        "show desserts",
        "show me desserts",
        "reselect desserts",
        "reselect the desserts",
        "redo desserts",
        "redo the desserts",
        "desserts back",
        "add desserts back",
        "want desserts",
        "have desserts",
    ),
    "appetizers": (
        "appetizer menu",
        "appetizers menu",
        "show appetizers",
        "show me appetizers",
        "reselect appetizers",
        "reselect the appetizers",
        "reselect my appetizers",
        "redo appetizers",
        "redo the appetizers",
        "appetizers back",
        "add appetizers back",
        "pick appetizers again",
        "choose appetizers again",
        "start over on appetizers",
    ),
    "selected_dishes": (
        "main menu",
        "mains menu",
        "show mains",
        "show main dishes",
        "main dishes back",
        "add mains back",
        "add main dishes back",
        "reselect mains",
        "reselect main dishes",
        "redo mains",
        "redo main dishes",
        "pick mains again",
        "choose mains again",
    ),
    "rentals": (
        "rental menu",
        "rentals menu",
        "show rentals",
        "show me rentals",
        "rentals back",
        "add rentals back",
        "reselect rentals",
        "redo rentals",
    ),
}


LIST_SLOT_MENTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "desserts": ("dessert", "desserts"),
    "appetizers": ("appetizer", "appetizers", "apps", "starters"),
    "selected_dishes": ("main dish", "main dishes", "mains", "entree", "entrees"),
    "rentals": ("rental", "rentals"),
}


GENERIC_REOPEN_MARKERS = (
    "reselect",
    "select again",
    "pick again",
    "choose again",
    "start over",
    "go back",
    "redo",
    "reopen",
    "revisit",
    "reshow",
    "show",
    "add back",
    "bring back",
    "put back",
    "again",
    "back",
)


STRONG_REOPEN_MARKERS = (
    "reselect",
    "pick again",
    "choose again",
    "start over",
    "go back",
    "redo",
    "reopen",
)


def menu_section_for_phase(phase: str | None) -> str | None:
    for slot, slot_phase in LIST_SLOT_TO_PHASE.items():
        if slot_phase == phase:
            return slot
    return None


def explicit_reopen_list_slot(message: str, phase: str | None = None) -> str | None:
    """Return the list slot the user wants to revisit, if explicit."""
    msg = (message or "").strip().lower()
    if not msg:
        return None

    for slot, phrases in LIST_SLOT_REOPEN_PHRASES.items():
        if any(phrase in msg for phrase in phrases):
            return slot

    if not any(marker in msg for marker in GENERIC_REOPEN_MARKERS):
        return None

    for slot, mentions in LIST_SLOT_MENTION_PATTERNS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", msg) for term in mentions):
            return slot

    phase_slot = menu_section_for_phase(phase)
    if phase_slot and any(marker in msg for marker in STRONG_REOPEN_MARKERS):
        return phase_slot

    return None


__all__ = [
    "GENERIC_REOPEN_MARKERS",
    "LIST_SLOT_MENTION_PATTERNS",
    "LIST_SLOT_REOPEN_PHRASES",
    "LIST_SLOT_TO_PHASE",
    "STRONG_REOPEN_MARKERS",
    "explicit_reopen_list_slot",
    "menu_section_for_phase",
]

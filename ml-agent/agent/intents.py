"""
Centralized intent classification for the router.

Before this module, decline/skip detection was duplicated across 4 files
(router.py, menu_selection_tool.py, basic_info_tool.py, modification_tool.py)
with subtly different logic — a chronic source of bugs where "skip dessert"
got reopen-treatment from one path and decline-treatment from another.

This module owns ONE canonical answer to:
  - Does this message decline a section?    → classify_decline()
  - Does this message skip a gate question? → classify_skip_gate()
  - Is this message clearly an intake answer  → ...

Tools and the router import from here. Don't add per-tool skip lists elsewhere.
"""

from __future__ import annotations

import re
from typing import NamedTuple

from agent.list_slot_reopen import LIST_SLOT_MENTION_PATTERNS
from agent.state import (
    PHASE_DESSERT,
    PHASE_DRINKS_BAR,
    PHASE_LABOR,
    PHASE_RENTALS,
    PHASE_SERVICE_TYPE,
    PHASE_SPECIAL_REQUESTS,
    PHASE_TABLEWARE,
    PHASE_WEDDING_CAKE,
    get_slot_value,
    is_filled,
)


# ---------------------------------------------------------------------------
# Skip / decline value sources of truth
# ---------------------------------------------------------------------------

# Generic "no" tokens — used as a fallback when the message is just a plain no.
_GENERIC_NO_TOKENS = frozenset({
    "no", "nope", "nah", "n", "no thanks", "no thank you",
    "skip", "skip it", "skip that", "pass", "none",
    "not really", "no need", "nothing", "neither",
    "i dont", "i don't", "we don't", "we dont",
})

# Per-section skip values — checked by phase. Includes section-specific phrasings.
_SECTION_SKIP_VALUES: dict[str, frozenset[str]] = {
    "desserts": frozenset({
        "skip", "skip dessert", "skip desserts", "skip them", "skip the dessert",
        "no thanks", "no", "none", "pass", "no desserts", "no dessert",
        "i'll skip", "ill skip", "let's skip", "lets skip",
    }),
    "wedding_cake": frozenset({
        "skip", "skip cake", "skip the cake", "no thanks", "no", "nope", "nah",
        "none", "no cake", "no wedding cake", "pass", "no need",
    }),
    "rentals": frozenset({
        "skip", "no", "no thanks", "none", "no rentals", "skip rentals",
    }),
    "tableware": frozenset({
        "skip", "no", "no thanks", "none", "no tableware", "no_tableware",
    }),
    "drinks": frozenset({
        "skip", "no", "no thanks", "none", "no drinks", "skip drinks", "neither",
    }),
    "labor": frozenset({
        "skip", "no", "no thanks", "none", "no labor", "no staffing", "no staff",
    }),
    "special_requests": frozenset({
        "skip", "no", "no thanks", "none", "nothing", "no special requests",
    }),
    "dietary_concerns": frozenset({
        "skip", "no", "no thanks", "none", "nothing", "no allergies", "no dietary",
    }),
    "followup_call_requested": frozenset({
        "skip", "no", "no thanks", "no call", "no call needed", "not needed",
    }),
}

# Phase → section mapping for gate-skip lookups
_PHASE_TO_SECTION: dict[str, str] = {
    PHASE_DESSERT: "desserts",
    PHASE_WEDDING_CAKE: "wedding_cake",
    PHASE_RENTALS: "rentals",
    PHASE_TABLEWARE: "tableware",
    PHASE_DRINKS_BAR: "drinks",
    PHASE_LABOR: "labor",
    PHASE_SPECIAL_REQUESTS: "special_requests",
}


class DeclineIntent(NamedTuple):
    """Result of classify_decline / classify_skip_gate."""
    section: str           # canonical section name ("desserts", "wedding_cake", etc.)
    target_slot: str       # the slot to clear or set to "none"
    confidence: float      # 1.0 = exact match, 0.7 = pattern-based


def _normalize(message: str) -> str:
    return (message or "").strip().lower()


def classify_skip_gate(message: str, phase: str, slots: dict) -> DeclineIntent | None:
    """User answered a gate question with a skip/no. Returns None if not applicable.

    Use this from the router BEFORE any LLM call — fast, deterministic, no
    cross-talk between phases.
    """
    section = _PHASE_TO_SECTION.get(phase)
    if not section:
        return None
    msg = _normalize(message)
    if not msg:
        return None

    # Section already has a value? Then this isn't a gate skip — could be a mod.
    target_slot = section if section in {"desserts", "rentals", "tableware", "wedding_cake"} else None
    if target_slot and is_filled(slots, target_slot):
        return None

    skip_values = _SECTION_SKIP_VALUES.get(section, frozenset())
    if msg in skip_values:
        return DeclineIntent(section=section, target_slot=target_slot or section, confidence=1.0)
    return None


def classify_decline(message: str, slots: dict) -> DeclineIntent | None:
    """Detects 'i dont want desserts' / 'no cake' / 'skip the appetizers' style
    full-section declines, regardless of phase. Returns None if not a decline.

    Used by modification_tool to override LLM action=reopen when the user
    really meant action=remove-all on a section.
    """
    msg = _normalize(message)
    if not msg:
        return None

    # Iterate sections that have menu-mention patterns (appetizers, mains,
    # desserts, rentals, plus wedding_cake which has its own mention list).
    for section, mentions in (
        ("desserts", LIST_SLOT_MENTION_PATTERNS.get("desserts", ())),
        ("appetizers", LIST_SLOT_MENTION_PATTERNS.get("appetizers", ())),
        ("selected_dishes", LIST_SLOT_MENTION_PATTERNS.get("selected_dishes", ())),
        ("rentals", LIST_SLOT_MENTION_PATTERNS.get("rentals", ())),
        ("wedding_cake", ("cake", "wedding cake")),
    ):
        if not mentions:
            continue
        if not any(re.search(rf"\b{re.escape(t)}\b", msg) for t in mentions):
            continue
        # Section is mentioned. Check for decline language.
        decline_pattern = (
            r"\b(?:dont|don[\s']?t|do\s+not)\s+(?:want|need|include|have)\b"
            r"|\bno\s+(?:more\s+)?(?:" + "|".join(re.escape(t) for t in mentions) + r")\b"
            r"|\bskip\s+(?:the\s+)?(?:" + "|".join(re.escape(t) for t in mentions) + r")\b"
            r"|\bcancel\s+(?:the\s+)?(?:" + "|".join(re.escape(t) for t in mentions) + r")\b"
            r"|\b(?:remove|delete|drop|clear)\s+(?:all\s+)?(?:my\s+|the\s+)?(?:" + "|".join(re.escape(t) for t in mentions) + r")\b"
        )
        if re.search(decline_pattern, msg):
            return DeclineIntent(section=section, target_slot=section, confidence=0.9)

    return None


def is_generic_no(message: str) -> bool:
    """True if message is a bare 'no' / 'nope' / 'skip' / etc.

    Used by gate handlers that want to accept these without phase-specific
    section keywords.
    """
    return _normalize(message) in _GENERIC_NO_TOKENS


__all__ = [
    "DeclineIntent",
    "classify_skip_gate",
    "classify_decline",
    "is_generic_no",
]

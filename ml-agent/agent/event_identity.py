"""Helpers for event-type-specific identity fields."""

from __future__ import annotations

from typing import Any, Mapping


EVENT_IDENTITY_SLOT_BY_TYPE: dict[str, str] = {
    "Wedding": "partner_name",
    "Corporate": "company_name",
    "Birthday": "honoree_name",
}

EVENT_IDENTITY_SLOTS = frozenset(EVENT_IDENTITY_SLOT_BY_TYPE.values())


def normalize_event_type(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def allowed_identity_slot_for_event_type(event_type: Any) -> str | None:
    normalized = normalize_event_type(event_type)
    if not normalized:
        return None
    return EVENT_IDENTITY_SLOT_BY_TYPE.get(normalized)


def filter_identity_fields(
    values: Mapping[str, Any],
    *,
    event_type: Any,
) -> dict[str, Any]:
    allowed_slot = allowed_identity_slot_for_event_type(event_type)
    filtered: dict[str, Any] = {}

    for key, value in values.items():
        if key not in EVENT_IDENTITY_SLOTS or key == allowed_slot:
            filtered[key] = value

    return filtered


__all__ = [
    "EVENT_IDENTITY_SLOT_BY_TYPE",
    "EVENT_IDENTITY_SLOTS",
    "allowed_identity_slot_for_event_type",
    "filter_identity_fields",
    "normalize_event_type",
]

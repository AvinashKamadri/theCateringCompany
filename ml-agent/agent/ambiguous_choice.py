"""Shared helpers for resolving ambiguous option selections."""

from __future__ import annotations

import re


def normalize_choice_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").lower()).strip()


def resolve_choice_selection(message: str, options: list[str]) -> str | None:
    raw = str(message or "").strip()
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(options):
            return options[idx]

    normalized = normalize_choice_text(raw)
    if not normalized:
        return None

    for option in options:
        if normalize_choice_text(option) == normalized:
            return option
    return None


def replace_query_with_selection(
    values: list[str],
    *,
    query: str,
    selection: str,
) -> list[str]:
    query_key = normalize_choice_text(query)
    replaced = False
    updated: list[str] = []

    for value in values:
        if not replaced and normalize_choice_text(value) == query_key:
            updated.append(selection)
            replaced = True
        else:
            updated.append(value)

    if not replaced:
        updated.append(selection)

    return updated


__all__ = [
    "normalize_choice_text",
    "resolve_choice_selection",
    "replace_query_with_selection",
]

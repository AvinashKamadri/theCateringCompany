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


def resolve_multi_choice_selection(message: str, options: list[str]) -> list[str] | None:
    """Resolve potentially-multiple selections from an option list.

    Supports:
    - "all" / "all of them" -> all options
    - numeric lists: "1,20" or "1 20" or "1, 2, 3"
    - name lists: "Firecracker Shrimp, Grilled Shrimp Cocktail"

    Returns the selected canonical option strings in the order provided by
    the user (numeric order for numeric lists), or None if nothing resolved.
    """
    raw = str(message or "").strip()
    if not raw:
        return None

    normalized = normalize_choice_text(raw)
    if not normalized:
        return None

    if normalized in {"all", "all of them", "everything"}:
        return list(options)

    # Phrases like "I want all", "remove all", "take all"
    if re.search(r"\ball\b", normalized) and any(v in normalized for v in {"want", "take", "select", "remove", "add", "pick"}):
        return list(options)

    # Numeric list (comma/space separated)
    nums = [p for p in re.split(r"[^0-9]+", raw) if p.strip().isdigit()]
    if nums:
        seen: set[int] = set()
        out: list[str] = []
        for token in nums:
            idx = int(token) - 1
            if idx in seen:
                continue
            if 0 <= idx < len(options):
                out.append(options[idx])
                seen.add(idx)
        return out or None

    # Name list (comma separated) — but do NOT split on commas inside parentheses
    # so items like "Meatballs (BBQ, Swedish, Sweet and Sour)" remain a single token.
    parts = [p.strip() for p in re.split(r",(?![^(]*\))", raw) if p and p.strip()]
    if len(parts) > 1:
        key = {normalize_choice_text(o): o for o in options}
        out: list[str] = []
        for part in parts:
            opt = key.get(normalize_choice_text(part))
            if opt and opt not in out:
                out.append(opt)
        return out or None

    # Fall back to single-choice logic
    one = resolve_choice_selection(raw, options)
    return [one] if one else None


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
    "resolve_multi_choice_selection",
    "replace_query_with_selection",
]

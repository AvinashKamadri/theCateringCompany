from __future__ import annotations

import re


_PREFIX_PATTERNS = (
    r"^(?:actually|ok(?:ay)?|sure|yeah|yep|yup|please)\s+",
    r"^(?:let'?s|lets)\s+(?:do|go with|pick)\s+",
    r"^(?:we(?:'ll| will)?|i(?:'ll| will)?)\s+(?:do|go with|pick)\s+",
    r"^(?:go with|pick|choose|make it)\s+",
)


def normalize_structured_choice(message: str) -> str:
    """Normalize short option-card replies before exact matching.

    This keeps conversational wrappers like "actually", "let's do", or
    "go with" from bypassing deterministic routing and slot filling.
    """
    msg = (message or "").strip().lower()
    if not msg:
        return ""

    for pattern in _PREFIX_PATTERNS:
        updated = re.sub(pattern, "", msg, flags=re.IGNORECASE).strip()
        if updated:
            msg = updated

    return msg.strip(" .,!?")


__all__ = ["normalize_structured_choice"]

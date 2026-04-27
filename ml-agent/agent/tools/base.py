"""
Tool base class + shared result shape.

Each domain Tool inherits `Tool` and implements `run()`. The orchestrator
calls exactly one tool per turn and feeds its `ToolResult.response_context`
to the Response Generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from langchain_core.messages import BaseMessage

_HISTORY_MAX_CHARS = 4_000  # ~1000 tokens; keeps long-conversation cost bounded


def history_for_llm(history: list[BaseMessage], max_messages: int = 6) -> list[dict]:
    """Convert LangChain messages to role/content dicts, capped by char budget.

    Takes the most recent `max_messages`, then drops oldest entries until the
    total character count fits in `_HISTORY_MAX_CHARS`. A single menu listing
    can be 800+ chars, so a message-count cap alone doesn't bound token cost.
    """
    candidates = []
    for m in history[-max_messages:]:
        role = "user" if getattr(m, "type", "") == "human" else "assistant"
        candidates.append({"role": role, "content": str(m.content or "")})

    total = sum(len(m["content"]) for m in candidates)
    while total > _HISTORY_MAX_CHARS and len(candidates) > 1:
        dropped = candidates.pop(0)
        total -= len(dropped["content"])
    return candidates


def tight_history_for_llm(history: list[BaseMessage]) -> list[dict]:
    """Minimal history window for entity extractors — last AI question + last user message only.

    Why: when an extractor LLM sees the last 6 messages, it often hallucinates
    items from past turns. E.g. after offering "Dragon Chicken" 3 turns ago,
    a `remove platter` request gets extracted as `items_to_add=["Dragon Chicken"]`
    because the LLM "remembers" the earlier offer. Tight context = no leakage.

    Drops AI menu listings (e.g. "Here are the appetizer options: 1. ...") since
    the extractor doesn't need the catalog — the slot value already has it.
    """
    candidates: list[dict] = []
    last_ai_added = False
    for m in reversed(history):
        role = "user" if getattr(m, "type", "") == "human" else "assistant"
        content = str(m.content or "").strip()
        if not content:
            continue
        if role == "user":
            # Always include user messages until we hit one we already kept.
            candidates.insert(0, {"role": role, "content": content[:500]})
        else:  # assistant
            if last_ai_added:
                continue
            # Drop long catalog listings — keep only the last short question/ack.
            short = content
            if len(short) > 600:
                # Take the last 200 chars (likely the question) only.
                short = short[-200:]
            candidates.insert(0, {"role": role, "content": short})
            last_ai_added = True
        if len(candidates) >= 3:  # at most: user, ai, user
            break
    return candidates


@dataclass
class ToolResult:
    """What every Tool returns.

    - `state` is the mutated ConversationState (slots updated, phase advanced).
    - `response_context` is a dict the Response Generator turns into user-facing
      text. Tools propose facts, not phrasing — the generator handles tone.
    - `input_hint` optionally tells the frontend what input widget to show
      next (e.g. category accordion, numbered list, date picker).
    """

    state: dict
    response_context: dict[str, Any] = field(default_factory=dict)
    input_hint: Optional[dict] = None
    # Set True if this tool produced a natural complete response already —
    # used by the orchestrator to short-circuit the generator when appropriate.
    direct_response: Optional[str] = None


class Tool(Protocol):
    """Every Tool must implement this shape."""

    name: str

    async def run(
        self,
        *,
        message: str,
        history: list[BaseMessage],
        state: dict,
    ) -> ToolResult:
        ...


__all__ = ["Tool", "ToolResult"]

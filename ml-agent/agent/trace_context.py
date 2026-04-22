"""Lightweight per-turn trace context for logging and OpenAI request metadata."""

from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator


logger = logging.getLogger(__name__)

_TRACE_CONTEXT: ContextVar[dict[str, str]] = ContextVar("agent_trace_context", default={})
_TURN_LLM_CALLS: ContextVar[list[int]] = ContextVar("agent_turn_llm_calls", default=[])
_TURN_TOKEN_USAGE: ContextVar[dict[str, int]] = ContextVar("agent_turn_token_usage", default={})


def record_token_usage(*, input_tokens: int = 0, output_tokens: int = 0, cached_input_tokens: int = 0) -> None:
    """Accumulate token usage for the current turn and conversation.

    Called from the LLM client after each response. A no-op when no turn
    scope is active.
    """
    usage = _TURN_TOKEN_USAGE.get()
    if not usage:
        return
    usage["input"] = usage.get("input", 0) + int(input_tokens or 0)
    usage["output"] = usage.get("output", 0) + int(output_tokens or 0)
    usage["cached_input"] = usage.get("cached_input", 0) + int(cached_input_tokens or 0)


def increment_llm_call() -> int:
    """Increment the per-turn LLM call counter. Returns the new total.

    Safe to call outside a turn scope — returns 0 when no scope is active.
    """
    counter = _TURN_LLM_CALLS.get()
    if not counter:
        return 0
    counter[0] += 1
    return counter[0]


def current_llm_call_count() -> int:
    counter = _TURN_LLM_CALLS.get()
    return counter[0] if counter else 0


_CUMULATIVE_TOKENS: dict[str, dict[str, int]] = {}


@contextmanager
def turn_scope(thread_id: str | None = None) -> Iterator[list[int]]:
    """Wrap a single user turn so LLM calls + tokens can be tracked and logged.

    On exit, emits:
      - turn_llm_calls total=N
      - turn_tokens input=I output=O cached_input=C
      - conversation_tokens_cumulative input=... output=... (per thread)
    """
    counter = [0]
    usage: dict[str, int] = {"input": 0, "output": 0, "cached_input": 0}
    token_calls = _TURN_LLM_CALLS.set(counter)
    token_usage = _TURN_TOKEN_USAGE.set(usage)
    try:
        yield counter
    finally:
        logger.info("turn_llm_calls total=%d", counter[0])
        logger.info(
            "turn_tokens input=%d output=%d cached_input=%d",
            usage["input"], usage["output"], usage["cached_input"],
        )
        if thread_id:
            cum = _CUMULATIVE_TOKENS.setdefault(
                thread_id, {"input": 0, "output": 0, "cached_input": 0, "turns": 0}
            )
            cum["input"] += usage["input"]
            cum["output"] += usage["output"]
            cum["cached_input"] += usage["cached_input"]
            cum["turns"] += 1
            logger.info(
                "conversation_tokens_cumulative thread=%s turns=%d input=%d output=%d cached_input=%d total=%d",
                thread_id,
                cum["turns"],
                cum["input"],
                cum["output"],
                cum["cached_input"],
                cum["input"] + cum["output"],
            )
        _TURN_LLM_CALLS.reset(token_calls)
        _TURN_TOKEN_USAGE.reset(token_usage)

_TRACE_KEYS = (
    "thread_id",
    "project_id",
    "conversation_id",
    "user_id",
    "author_id",
    "phase",
    "tool",
    "target",
    "source_tool",
    "route_stage",
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def current_trace_context() -> dict[str, str]:
    return dict(_TRACE_CONTEXT.get())


@contextmanager
def trace_scope(**updates: Any) -> Iterator[dict[str, str]]:
    current = current_trace_context()
    merged = dict(current)
    for key, value in updates.items():
        cleaned = _clean(value)
        if cleaned is None:
            merged.pop(key, None)
            continue
        merged[str(key)] = cleaned
    token = _TRACE_CONTEXT.set(merged)
    try:
        yield merged
    finally:
        _TRACE_CONTEXT.reset(token)


def build_openai_request_tags(
    *,
    operation: str,
    model: str,
    schema: str | None = None,
) -> dict[str, Any]:
    ctx = current_trace_context()
    metadata: dict[str, str] = {
        "app": "catering_ml_agent",
        "operation": operation,
        "model": model,
    }

    for key in ("thread_id", "project_id", "conversation_id", "phase", "tool", "target", "source_tool", "route_stage"):
        value = ctx.get(key)
        if value:
            metadata[key] = value[:120]

    if schema:
        metadata["schema"] = schema[:120]

    cache_bits = [
        metadata.get("app", "catering_ml_agent"),
        operation,
        model,
        schema or "text",
        ctx.get("tool", "-"),
        ctx.get("phase", "-"),
        ctx.get("target", "-"),
    ]
    full_key = "|".join(cache_bits)
    prompt_cache_key = hashlib.sha256(full_key.encode()).hexdigest()[:64]

    principal = ctx.get("user_id") or ctx.get("author_id") or ctx.get("thread_id") or "anonymous"
    safety_identifier = "catering_" + hashlib.sha256(principal.encode("utf-8")).hexdigest()[:32]

    return {
        "metadata": metadata,
        "prompt_cache_key": prompt_cache_key,
        "safety_identifier": safety_identifier,
    }


class TraceContextFilter(logging.Filter):
    """Inject current trace context into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = current_trace_context()
        record.trace_thread = ctx.get("thread_id", "-")
        record.trace_phase = ctx.get("phase", "-")
        record.trace_tool = ctx.get("tool", "-")
        record.trace_target = ctx.get("target", "-")
        return True


__all__ = [
    "TraceContextFilter",
    "build_openai_request_tags",
    "current_llm_call_count",
    "current_trace_context",
    "increment_llm_call",
    "record_token_usage",
    "trace_scope",
    "turn_scope",
]

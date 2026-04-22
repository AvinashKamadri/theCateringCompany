"""Lightweight per-turn trace context for logging and OpenAI request metadata."""

from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator


logger = logging.getLogger(__name__)

_TRACE_CONTEXT: ContextVar[dict[str, str]] = ContextVar("agent_trace_context", default={})

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
    # OpenAI caps prompt_cache_key at 64 chars. Hash to stay deterministic + short.
    prompt_cache_key = hashlib.sha256("|".join(cache_bits).encode("utf-8")).hexdigest()[:64]

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
    "current_trace_context",
    "trace_scope",
]

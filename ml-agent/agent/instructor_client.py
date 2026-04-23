"""
Single source of truth for OpenAI client access.

Uses the Responses API as the shared runtime for structured extraction and
user-facing generation. All tools call `extract()` with a Pydantic schema,
which is translated into a strict JSON schema response format.

Model names are resolved from environment variables:
  ML_MODEL_EXTRACT   — used by all Tools (structured extraction)
  ML_MODEL_ROUTER    — used by the Orchestrator for routing decisions
  ML_MODEL_RESPONSE  — used by the Response Generator for user-facing text
  ML_MODEL_WARMUP    — used for startup pre-compilation
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, List, Optional, Type, TypeVar

from dotenv import load_dotenv
import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from agent.trace_context import (
    build_openai_request_tags,
    increment_llm_call,
    record_token_usage,
)

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise ValueError("OPENAI_API_KEY missing — cannot initialize OpenAI client.")


# ---- Pinned model snapshots (env-overridable) ------------------------------
MODEL_EXTRACT = os.getenv("ML_MODEL_EXTRACT", "gpt-5.4-mini-2026-03-17")
MODEL_ROUTER = os.getenv("ML_MODEL_ROUTER", "gpt-5.4-2026-03-05")
MODEL_RESPONSE = os.getenv("ML_MODEL_RESPONSE", "gpt-5.4-2026-03-05")
MODEL_WARMUP   = os.getenv("ML_MODEL_WARMUP",   MODEL_EXTRACT)


def filter_extraction_fields(extracted_dict: dict, allowed_fields: list[str] | None = None) -> dict:
    """Filter extracted fields to only include allowed ones (GPT-4.1 mini over-extraction fix)."""
    if allowed_fields is None:
        return extracted_dict
    return {k: v for k, v in extracted_dict.items() if k in allowed_fields}


# ---- Single raw async client -----------------------------------------------
# 30s total, 5s connect. Default is 600s — a hung OpenAI request would block
# the entire turn. On timeout the fallback path takes over.
_raw_async = AsyncOpenAI(
    api_key=_api_key,
    timeout=httpx.Timeout(30.0, connect=5.0),
)
raw_async_client = _raw_async

# Legacy aliases — some modules import these names directly
async_client = _raw_async
sync_client  = None  # unused after migration; kept so old imports don't crash


T = TypeVar("T", bound=BaseModel)


# Per-process cache: Pydantic schema class → fully-strict JSON schema dict.
# The schema never changes at runtime, so rebuilding it on every LLM call is
# wasted CPU. Hit rate approaches 100% after the first call per schema.
_SCHEMA_CACHE: dict[Type[BaseModel], dict[str, object]] = {}
_TEXT_FORMAT_CACHE: dict[Type[BaseModel], dict[str, object]] = {}
_TOOL_DEF_CACHE: dict[Type[BaseModel], dict[str, object]] = {}


def _record_response_usage(response: Any) -> None:
    """Pull token usage off an OpenAI response object (Responses or Chat) and
    record it in the per-turn counter. Silent on missing fields so this is
    safe to call on any response-like object."""
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        input_tokens = getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", 0) or 0
        cached = 0
        details = getattr(usage, "input_tokens_details", None) or getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0
        record_token_usage(
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            cached_input_tokens=int(cached),
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("token usage capture failed: %s", exc)


def _is_truncated_json_validation_error(exc: ValidationError) -> bool:
    """Heuristic: Pydantic failed to parse JSON due to EOF/unterminated string.

    This is almost always caused by the model being cut off at the output-token
    limit. In that case, retrying with a higher `max_output_tokens` is the most
    reliable fix.
    """
    try:
        for err in exc.errors() or []:
            if (err.get("type") or "") == "json_invalid":
                msg = str(err.get("msg") or "")
                if "EOF" in msg or "Unterminated" in msg or "while parsing" in msg:
                    return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _bump_max_tokens(max_tokens: int) -> int:
    # Minimum bump to escape common truncation cases while keeping a hard cap.
    # 200 -> 1000, 250 -> 1000, 500 -> 2000, 1000 -> 4000, ...
    bumped = max(max_tokens * 4, max_tokens + 500, 1000)
    return min(bumped, 8000)


def _build_json_schema(schema: Type[T]) -> dict[str, object]:
    """Convert a Pydantic model into a strict JSON schema payload (cached)."""
    cached = _SCHEMA_CACHE.get(schema)
    if cached is not None:
        return cached
    json_schema = schema.model_json_schema()
    json_schema.pop("title", None)
    _enforce_strict_schema(json_schema)
    _SCHEMA_CACHE[schema] = json_schema
    return json_schema


def _enforce_strict_schema(obj: Any) -> None:
    """Recursively add additionalProperties: false and required array to all objects."""
    if isinstance(obj, dict):
        if "type" in obj and obj["type"] == "object":
            obj["additionalProperties"] = False
            if "properties" in obj:
                obj["required"] = list(obj["properties"].keys())
        for composite_key in ("anyOf", "oneOf", "allOf"):
            if composite_key in obj and isinstance(obj[composite_key], list):
                for item in obj[composite_key]:
                    if isinstance(item, dict):
                        if "type" not in item and "enum" not in item and "$ref" not in item:
                            item["type"] = "string"
        for value in obj.values():
            _enforce_strict_schema(value)
    elif isinstance(obj, list):
        for item in obj:
            _enforce_strict_schema(item)


def _text_format_for_schema(schema: Type[T]) -> dict[str, object]:
    cached = _TEXT_FORMAT_CACHE.get(schema)
    if cached is not None:
        return cached
    fmt = {
        "format": {
            "type": "json_schema",
            "name": schema.__name__,
            "description": (schema.__doc__ or "").strip().split("\n")[0],
            "schema": _build_json_schema(schema),
            "strict": True,
        }
    }
    _TEXT_FORMAT_CACHE[schema] = fmt
    return fmt


def _build_function_tool_def(schema: Type[T]) -> dict[str, object]:
    cached = _TOOL_DEF_CACHE.get(schema)
    if cached is not None:
        return cached
    tool_def = {
        "type": "function",
        "function": {
            "name": schema.__name__,
            "description": (schema.__doc__ or "").strip().split("\n")[0],
            "parameters": _build_json_schema(schema),
            "strict": True,
        }
    }
    _TOOL_DEF_CACHE[schema] = tool_def
    return tool_def


def _response_input(
    *,
    user_message: str,
    history: Optional[List[dict]] = None,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for msg in history or []:
        role = str(msg.get("role") or "").strip()
        content = msg.get("content")
        if role not in {"user", "assistant", "developer", "system"}:
            continue
        if content in (None, ""):
            continue
        items.append({"role": role, "content": str(content)})
    items.append({"role": "user", "content": user_message})
    return items


async def _extract_via_chat_completions(
    *,
    schema: Type[T],
    system: str,
    user_message: str,
    history: Optional[List[dict]] = None,
    model: Optional[str] = None,
    max_tokens: int = 5000,
) -> Optional[T]:
    request_tags = build_openai_request_tags(
        operation="extract_fallback",
        model=model or MODEL_EXTRACT,
        schema=schema.__name__,
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})

    response = await _raw_async.chat.completions.create(
        model=model or MODEL_EXTRACT,
        tools=[_build_function_tool_def(schema)],
        tool_choice={"type": "function", "function": {"name": schema.__name__}},
        max_completion_tokens=max_tokens,
        messages=messages,
        user=request_tags["prompt_cache_key"],
        temperature=0,
    )
    _record_response_usage(response)
    choice = response.choices[0]
    tool_calls = choice.message.tool_calls
    if not tool_calls:
        return None
    return schema.model_validate_json(tool_calls[0].function.arguments)


async def _generate_text_via_chat_completions(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    max_tokens: int = 600,
    temperature: float = 0.8,
) -> str:
    request_tags = build_openai_request_tags(
        operation="generate_text_fallback",
        model=model or MODEL_RESPONSE,
    )
    resp = await _raw_async.chat.completions.create(
        model=model or MODEL_RESPONSE,
        max_completion_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        user=request_tags["prompt_cache_key"],
    )
    return (resp.choices[0].message.content or "").strip()


# ---- Core extraction API ---------------------------------------------------

async def extract(
    *,
    schema: Type[T],
    system: str,
    user_message: str,
    history: Optional[List[dict]] = None,
    model: Optional[str] = None,
    max_tokens: int = 5000,
    max_retries: int = 2,
) -> Optional[T]:
    """Extract structured data using the Responses API with strict JSON schema.

    Returns None if extraction fails after max_retries.
    """
    if max_retries > 2:
        max_retries = 2

    input_items = _response_input(
        user_message=user_message,
        history=history[-6:] if history else None,
    )
    _model = model or MODEL_EXTRACT
    request_tags = build_openai_request_tags(
        operation="extract",
        model=_model,
        schema=schema.__name__,
    )

    last_exc: Exception | None = None
    attempt_max_tokens = max_tokens
    for attempt in range(max_retries + 1):
        try:
            increment_llm_call()
            logger.info(
                "openai_extract_request schema=%s model=%s attempt=%d",
                schema.__name__,
                _model,
                attempt + 1,
            )
            _t0 = time.monotonic()
            response = await _raw_async.responses.create(
                model=_model,
                instructions=system,
                input=input_items,
                text=_text_format_for_schema(schema),
                max_output_tokens=attempt_max_tokens,
                metadata=request_tags["metadata"],
                prompt_cache_key=request_tags["prompt_cache_key"],
                safety_identifier=request_tags["safety_identifier"],
                service_tier="default",
                store=False,
                temperature=0,
            )
            _elapsed_ms = int((time.monotonic() - _t0) * 1000)
            _record_response_usage(response)
            output_text = (getattr(response, "output_text", None) or "").strip()
            if not output_text:
                logger.warning(
                    "No structured output in response for %s (attempt %d, %dms)",
                    schema.__name__, attempt + 1, _elapsed_ms,
                )
                continue
            result = schema.model_validate_json(output_text)
            logger.info(
                "openai_extract_response schema=%s model=%s response_id=%s elapsed_ms=%d",
                schema.__name__,
                _model,
                getattr(response, "id", None) or "-",
                _elapsed_ms,
            )
            return result
        except ValidationError as e:
            logger.warning("Validation failed for %s (attempt %d): %s", schema.__name__, attempt + 1, e)
            last_exc = e
            if attempt < max_retries and _is_truncated_json_validation_error(e):
                new_max = _bump_max_tokens(attempt_max_tokens)
                if new_max != attempt_max_tokens:
                    logger.info(
                        "Retrying %s with higher max_output_tokens (%d -> %d) due to truncated JSON",
                        schema.__name__,
                        attempt_max_tokens,
                        new_max,
                    )
                    attempt_max_tokens = new_max
        except Exception as e:
            logger.warning("Extraction error for %s (attempt %d): %s", schema.__name__, attempt + 1, e)
            last_exc = e

    logger.warning("Responses extraction error for %s: %s", schema.__name__, last_exc)
    try:
        logger.info("Falling back to chat.completions extraction for %s", schema.__name__)
        return await _extract_via_chat_completions(
            schema=schema,
            system=system,
            user_message=user_message,
            history=history,
            model=_model,
            max_tokens=attempt_max_tokens,
        )
    except Exception as fallback_exc:
        logger.warning("Chat completions fallback failed for %s: %s", schema.__name__, fallback_exc)
        return None


# ---- Warmup ----------------------------------------------------------------

_WARMUP_DONE = False


async def warmup() -> None:
    """Pre-flight check: verify the model is reachable and structured outputs work.

    Disabled by default in production. Set ML_ENABLE_WARMUP=true to run at boot.
    The OpenAI prompt cache has a 5-minute TTL so warmup goes cold before the
    first real turn arrives anyway — pay the cost only when iterating locally.
    """
    global _WARMUP_DONE
    if _WARMUP_DONE:
        return
    if os.getenv("ML_ENABLE_WARMUP", "false").strip().lower() not in {"1", "true", "yes"}:
        _WARMUP_DONE = True
        logger.info("Warmup skipped (set ML_ENABLE_WARMUP=true to enable)")
        return

    from agent.models import (
        AddOnsExtraction,
        EventDetailsExtraction,
        FinalizationExtraction,
        MenuSelectionExtraction,
        ModificationExtraction,
        OrchestratorDecision,
    )

    schemas: list[Type[BaseModel]] = [
        EventDetailsExtraction,
        MenuSelectionExtraction,
        AddOnsExtraction,
        ModificationExtraction,
        FinalizationExtraction,
        OrchestratorDecision,
    ]

    import asyncio

    async def _warm_one(schema: Type[BaseModel]) -> None:
        try:
            await _raw_async.responses.create(
                model=MODEL_WARMUP,
                instructions="warmup",
                input=[{"role": "user", "content": "hello"}],
                text=_text_format_for_schema(schema),
                max_output_tokens=100,
                store=False,
            )
        except Exception as e:
            logger.debug("Warmup failed for %s: %s", schema.__name__, e)

    await asyncio.gather(*(_warm_one(s) for s in schemas), return_exceptions=True)
    _WARMUP_DONE = True
    logger.info("Instructor warmup complete for %d schemas", len(schemas))


# ---- Raw text generation (response generator) -----------------------------

async def generate_text(
    *,
    system: str,
    user: str,
    model: Optional[str] = None,
    max_tokens: int = 600,
    temperature: float = 0.8,
) -> str:
    """Generate unstructured text (for the response generator)."""
    _model = model or MODEL_RESPONSE
    request_tags = build_openai_request_tags(
        operation="generate_text",
        model=_model,
    )
    try:
        increment_llm_call()
        logger.info("openai_text_request model=%s", _model)
        _t0 = time.monotonic()
        resp = await _raw_async.responses.create(
            model=_model,
            instructions=system,
            input=[{"role": "user", "content": user}],
            max_output_tokens=max_tokens,
            metadata=request_tags["metadata"],
            prompt_cache_key=request_tags["prompt_cache_key"],
            safety_identifier=request_tags["safety_identifier"],
            service_tier="default",
            temperature=temperature,
            store=False,
        )
        _record_response_usage(resp)
        logger.info(
            "openai_text_response model=%s response_id=%s elapsed_ms=%d",
            _model,
            getattr(resp, "id", None) or "-",
            int((time.monotonic() - _t0) * 1000),
        )
        return (getattr(resp, "output_text", None) or "").strip()
    except Exception as e:
        logger.error("generate_text via Responses failed: %s", e)
    try:
        logger.info("Falling back to chat.completions text generation")
        return await _generate_text_via_chat_completions(
            system=system,
            user=user,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as fallback_exc:
        logger.error("generate_text fallback failed: %s", fallback_exc)
        return ""


__all__ = [
    "extract",
    "generate_text",
    "warmup",
    "async_client",
    "sync_client",
    "raw_async_client",
    "MODEL_EXTRACT",
    "MODEL_ROUTER",
    "MODEL_RESPONSE",
]

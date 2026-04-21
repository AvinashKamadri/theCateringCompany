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
from pathlib import Path
from typing import Any, List, Optional, Type, TypeVar

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from agent.trace_context import build_openai_request_tags

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise ValueError("OPENAI_API_KEY missing — cannot initialize OpenAI client.")


# ---- Pinned model snapshots (env-overridable) ------------------------------
MODEL_EXTRACT  = os.getenv("ML_MODEL_EXTRACT",  "gpt-5.4-mini-2026-03-17")
MODEL_ROUTER   = os.getenv("ML_MODEL_ROUTER",   "gpt-5.4-2026-03-05")
MODEL_RESPONSE = os.getenv("ML_MODEL_RESPONSE", "gpt-5.4-2026-03-05")
MODEL_WARMUP   = os.getenv("ML_MODEL_WARMUP",   MODEL_EXTRACT)


# ---- Single raw async client -----------------------------------------------
_raw_async = AsyncOpenAI(api_key=_api_key)
raw_async_client = _raw_async

# Legacy aliases — some modules import these names directly
async_client = _raw_async
sync_client  = None  # unused after migration; kept so old imports don't crash


T = TypeVar("T", bound=BaseModel)


def _build_json_schema(schema: Type[T]) -> dict[str, object]:
    """Convert a Pydantic model into a strict JSON schema payload."""
    json_schema = schema.model_json_schema()
    json_schema.pop("title", None)
    json_schema["additionalProperties"] = False
    # Ensure all properties are in required array for strict mode
    if "properties" in json_schema:
        json_schema["required"] = list(json_schema["properties"].keys())
    return json_schema


def _text_format_for_schema(schema: Type[T]) -> dict[str, object]:
    return {
        "format": {
            "type": "json_schema",
            "name": schema.__name__,
            "description": (schema.__doc__ or "").strip().split("\n")[0],
            "schema": _build_json_schema(schema),
            "strict": True,
        }
    }


def _build_function_tool_def(schema: Type[T]) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": schema.__name__,
            "description": (schema.__doc__ or "").strip().split("\n")[0],
            "parameters": _build_json_schema(schema),
            "strict": True,
        }
    }


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
    max_tokens: int = 500,
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
    )
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
    max_tokens: int = 500,
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
    for attempt in range(max_retries + 1):
        try:
            logger.info(
                "openai_extract_request schema=%s model=%s attempt=%d",
                schema.__name__,
                _model,
                attempt + 1,
            )
            response = await _raw_async.responses.create(
                model=_model,
                instructions=system,
                input=input_items,
                text=_text_format_for_schema(schema),
                max_output_tokens=max_tokens,
                metadata=request_tags["metadata"],
                prompt_cache_key=request_tags["prompt_cache_key"],
                safety_identifier=request_tags["safety_identifier"],
                service_tier="auto",
                store=False,
            )
            output_text = (getattr(response, "output_text", None) or "").strip()
            if not output_text:
                logger.warning("No structured output in response for %s (attempt %d)", schema.__name__, attempt + 1)
                continue
            result = schema.model_validate_json(output_text)
            logger.info(
                "openai_extract_response schema=%s model=%s response_id=%s",
                schema.__name__,
                _model,
                getattr(response, "id", None) or "-",
            )
            return result
        except ValidationError as e:
            logger.warning("Validation failed for %s (attempt %d): %s", schema.__name__, attempt + 1, e)
            last_exc = e
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
            max_tokens=max_tokens,
        )
    except Exception as fallback_exc:
        logger.warning("Chat completions fallback failed for %s: %s", schema.__name__, fallback_exc)
        return None


# ---- Warmup ----------------------------------------------------------------

_WARMUP_DONE = False


async def warmup() -> None:
    """Pre-flight check: verify the model is reachable and structured outputs work."""
    global _WARMUP_DONE
    if _WARMUP_DONE:
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
        logger.info("openai_text_request model=%s", _model)
        resp = await _raw_async.responses.create(
            model=_model,
            instructions=system,
            input=[{"role": "user", "content": user}],
            max_output_tokens=max_tokens,
            metadata=request_tags["metadata"],
            prompt_cache_key=request_tags["prompt_cache_key"],
            safety_identifier=request_tags["safety_identifier"],
            service_tier="auto",
            temperature=temperature,
            store=False,
        )
        logger.info(
            "openai_text_response model=%s response_id=%s",
            _model,
            getattr(resp, "id", None) or "-",
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

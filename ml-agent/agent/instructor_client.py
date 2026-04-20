"""
Single source of truth for OpenAI client access.

Uses GPT-5.4's native function/tool-calling API instead of Instructor.
All Tools call `extract()` with a Pydantic schema — the schema is converted
to an OpenAI function definition automatically via model_json_schema().

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
from typing import List, Optional, Type, TypeVar

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise ValueError("OPENAI_API_KEY missing — cannot initialize OpenAI client.")


# ---- Pinned model snapshots (env-overridable) ------------------------------
MODEL_EXTRACT  = os.getenv("ML_MODEL_EXTRACT",  "gpt-5.4-2026-03-05")
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


def _build_tool_def(schema: Type[T]) -> dict:
    """Convert a Pydantic model into an OpenAI function-tool definition."""
    json_schema = schema.model_json_schema()
    # Strip Pydantic's title from the top-level — OpenAI doesn't need it
    json_schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": schema.__name__,
            "description": (schema.__doc__ or "").strip().split("\n")[0],
            "parameters": json_schema,
        },
    }


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
    """Extract structured data using GPT-5.4 native tool calling.

    Returns None if extraction fails after max_retries.
    """
    if max_retries > 2:
        max_retries = 2

    messages: list[dict] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": user_message})

    tool_def = _build_tool_def(schema)
    tool_choice = {"type": "function", "function": {"name": schema.__name__}}
    _model = model or MODEL_EXTRACT

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            response = await _raw_async.chat.completions.create(
                model=_model,
                tools=[tool_def],
                tool_choice=tool_choice,
                max_completion_tokens=max_tokens,
                messages=messages,
            )
            choice = response.choices[0]
            tc = choice.message.tool_calls
            if not tc:
                logger.warning("No tool_calls in response for %s (attempt %d)", schema.__name__, attempt + 1)
                continue
            args_json = tc[0].function.arguments
            result = schema.model_validate_json(args_json)
            return result
        except ValidationError as e:
            logger.warning("Validation failed for %s (attempt %d): %s", schema.__name__, attempt + 1, e)
            last_exc = e
        except Exception as e:
            logger.warning("Extraction error for %s (attempt %d): %s", schema.__name__, attempt + 1, e)
            last_exc = e

    logger.warning("Instructor extraction error for %s: %s", schema.__name__, last_exc)
    return None


# ---- Warmup ----------------------------------------------------------------

_WARMUP_DONE = False


async def warmup() -> None:
    """Pre-flight check: verify the model is reachable and tool calling works."""
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
            tool_def = _build_tool_def(schema)
            tool_choice = {"type": "function", "function": {"name": schema.__name__}}
            await _raw_async.chat.completions.create(
                model=MODEL_WARMUP,
                tools=[tool_def],
                tool_choice=tool_choice,
                max_completion_tokens=100,
                messages=[
                    {"role": "system", "content": "warmup"},
                    {"role": "user", "content": "hello"},
                ],
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
    try:
        resp = await _raw_async.chat.completions.create(
            model=model or MODEL_RESPONSE,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice = resp.choices[0]
        if choice.finish_reason == "length":
            logger.warning("Response truncated — max_completion_tokens=%d too low", max_tokens)
        return (choice.message.content or "").strip()
    except Exception as e:
        logger.error("generate_text failed: %s", e)
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

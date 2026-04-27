"""
Redis session cache — hot layer in front of Postgres.

Architecture:
  Redis  → hot state (<1ms read/write, 24h TTL)
  Postgres → durable backup (written on conversation complete or on miss)

Graceful degradation: if Redis is not configured or unreachable, every
operation silently falls through to None so the orchestrator uses Postgres.
The service never crashes due to Redis unavailability.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "").strip()
_KEY_PREFIX = "ml_agent:state:"
_TTL_SECONDS = 86_400  # 24 hours

# Lazy singleton — created on first use, never re-created.
_redis_client: Any = None
_redis_available: bool = True  # flips to False after first connection failure


def _key(thread_id: str) -> str:
    return f"{_KEY_PREFIX}{thread_id}"


async def _get_client() -> Any:
    """Return the Redis client, initialising it on first call."""
    global _redis_client, _redis_available

    if not _redis_available:
        return None
    if _redis_client is not None:
        return _redis_client
    if not _REDIS_URL:
        _redis_available = False
        logger.info("Redis disabled — REDIS_URL not set. Using Postgres only.")
        return None

    try:
        import redis.asyncio as aioredis  # type: ignore[import]
        _redis_client = aioredis.from_url(
            _REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Verify connectivity.
        await _redis_client.ping()
        logger.info("Redis session cache connected: %s", _REDIS_URL.split("@")[-1])
    except Exception as exc:
        _redis_available = False
        _redis_client = None
        logger.warning("Redis unavailable (%s) — falling back to Postgres-only.", exc)

    return _redis_client


async def get_state(thread_id: str) -> Optional[dict[str, Any]]:
    """Return cached conversation state or None (cache miss / Redis down)."""
    client = await _get_client()
    if client is None:
        return None
    try:
        raw = await client.get(_key(thread_id))
        if raw is None:
            return None
        state = json.loads(raw)
        logger.debug("redis_cache_hit thread=%s", thread_id)
        return state
    except Exception as exc:
        logger.debug("Redis get failed for %s: %s", thread_id, exc)
        return None


async def set_state(thread_id: str, state: dict[str, Any]) -> None:
    """Write state to Redis with 24h TTL. Fire-and-forget — never raises."""
    client = await _get_client()
    if client is None:
        return
    try:
        await client.setex(_key(thread_id), _TTL_SECONDS, json.dumps(state, default=str))
        logger.debug("redis_cache_write thread=%s", thread_id)
    except Exception as exc:
        logger.debug("Redis set failed for %s: %s", thread_id, exc)


async def delete_state(thread_id: str) -> None:
    """Remove a session from Redis (e.g. after conversation completes)."""
    client = await _get_client()
    if client is None:
        return
    try:
        await client.delete(_key(thread_id))
    except Exception as exc:
        logger.debug("Redis delete failed for %s: %s", thread_id, exc)

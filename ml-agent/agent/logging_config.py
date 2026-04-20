"""
Centralized logging for the ML agent.

Call `configure_logging()` exactly once at FastAPI startup (lifespan). It:
- Sets root level from `ML_LOG_LEVEL` env (default INFO).
- Emits to stdout (good for container logs) AND to a rotating file when
  `ML_LOG_FILE` is set.
- Silences noisy third-party loggers that spam per-request output.

Each module should do `logger = logging.getLogger(__name__)` as usual — no
per-module handlers, no basicConfig() calls scattered around.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from agent.trace_context import TraceContextFilter


_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = os.getenv("ML_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-5s [%(name)s] "
        "[thread=%(trace_thread)s phase=%(trace_phase)s tool=%(trace_tool)s target=%(trace_target)s] "
        "%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    trace_filter = TraceContextFilter()

    root = logging.getLogger()
    root.setLevel(level)
    # Wipe any handlers FastAPI / uvicorn added at import time
    root.handlers.clear()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(fmt)
    stdout_handler.setLevel(level)
    stdout_handler.addFilter(trace_filter)
    root.addHandler(stdout_handler)

    log_file = os.getenv("ML_LOG_FILE")
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        file_handler.addFilter(trace_filter)
        root.addHandler(file_handler)

    # Silence noisy libraries — INFO-level request spam from these floods
    # the agent's own signal.
    for noisy in ("httpx", "httpcore", "openai._base_client", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
    logging.getLogger(__name__).info(
        "Logging configured — level=%s file=%s", level_name, log_file or "(stdout only)"
    )


__all__ = ["configure_logging"]

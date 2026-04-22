"""Golden-transcript regression harness.

Each JSON file under tests/golden/ is a canonical conversation. The harness
replays it through the full orchestrator and asserts that per-turn slot
deltas and the resulting phase match the fixture. Wording is free to vary —
only structure is pinned.

Purpose: catch silent regressions when swapping models or editing prompts.
The LLM's *reasoning* can drift; its *decisions* (slot fills, phase
transitions) cannot.

Run:
    pytest ml-agent/tests/test_golden_transcripts.py -v

Add a new fixture:
    cp tests/golden/wedding_happy_path.json tests/golden/my_case.json
    # edit with the turns you want to assert
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.asyncio


GOLDEN_DIR = Path(__file__).parent / "golden"

# Make `ml-agent/` importable so `import orchestrator` works when running pytest
# from repo root (which is how we run these fixtures locally).
ML_AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(ML_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_AGENT_ROOT))


def _fixture_files() -> list[Path]:
    if not GOLDEN_DIR.exists():
        return []
    return sorted(GOLDEN_DIR.glob("*.json"))


@pytest.mark.skipif(
    os.getenv("RUN_GOLDEN_TRANSCRIPTS", "").lower() not in {"1", "true", "yes"},
    reason="Set RUN_GOLDEN_TRANSCRIPTS=true to run (hits the real model).",
)
@pytest.mark.parametrize("fixture_path", _fixture_files(), ids=lambda p: p.stem)
async def test_golden_transcript(fixture_path: Path) -> None:
    """Replay a golden transcript and assert slot deltas + final phase match."""
    from orchestrator import AgentOrchestrator  # imported lazily for CI speed

    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    turns: list[dict[str, Any]] = fixture["turns"]
    preconditions = fixture.get("preconditions") or {}

    orch = AgentOrchestrator()
    import uuid
    thread_id = str(uuid.uuid4())
    # Seed slots / phase if the fixture declares preconditions. Skipped when
    # none present — that path still replays from a blank state.
    if preconditions:
        from agent.state import fill_slot
        from database.queries import (
            load_conversation_state,
            create_project_and_thread,
        )
        await orch._ensure_init()
        await create_project_and_thread(
            thread_id=thread_id,
            project_id=None,
            title="golden seed",
            user_id=None,
        )
        existing = await load_conversation_state(thread_id)
        slots = existing["slots"] if existing else {}
        for slot, value in (preconditions.get("slots") or {}).items():
            fill_slot(slots, slot, value)
        for slot, value in (preconditions.get("internal_slots") or {}).items():
            fill_slot(slots, slot, value)

    prev_slots: dict[str, Any] = {}
    for idx, turn in enumerate(turns):
        result = await orch.process_message(
            thread_id=thread_id,
            message=turn["user_message"],
            author_id="golden_test",
        )
        slots_now = {
            name: (data.get("value") if isinstance(data, dict) else data)
            for name, data in (result.get("slots") or {}).items()
            if (isinstance(data, dict) and data.get("filled"))
        }

        actual_delta = {
            k: v for k, v in slots_now.items()
            if prev_slots.get(k) != v
        }
        expected_delta = turn.get("expected_slot_deltas") or {}

        for key, expected_val in expected_delta.items():
            assert key in actual_delta, (
                f"[{fixture_path.stem} turn {idx}] expected slot '{key}' "
                f"to be set to {expected_val!r}, got nothing"
            )
            assert actual_delta[key] == expected_val, (
                f"[{fixture_path.stem} turn {idx}] slot '{key}' mismatch: "
                f"expected {expected_val!r}, got {actual_delta[key]!r}"
            )

        expected_phase = turn.get("expected_phase_after")
        if expected_phase:
            actual_phase = result.get("conversation_phase")
            assert actual_phase == expected_phase, (
                f"[{fixture_path.stem} turn {idx}] phase mismatch: "
                f"expected {expected_phase!r}, got {actual_phase!r}"
            )

        prev_slots = slots_now

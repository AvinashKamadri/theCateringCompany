"""Integration tests for the current orchestrator shell."""

import re
import sys
import uuid

import pytest


sys.path.insert(0, r"c:\Projects\CateringCompany\ml-agent")

import orchestrator as orchestrator_module
from agent.models import OrchestratorDecision, ToolCall
from agent.state import PHASE_EVENT_DATE, PHASE_GREETING, PHASE_VENUE, fill_slot, get_slot_value
from agent.tools.base import ToolResult


class _FakeBasicInfoTool:
    name = "basic_info_tool"

    async def run(self, *, message, history, state):
        slots = state["slots"]
        phase = state.get("conversation_phase") or PHASE_GREETING
        lowered = message.lower()
        fills: list[tuple[str, object]] = []

        if phase == PHASE_GREETING and not get_slot_value(slots, "name"):
            match = re.search(r"name is (.+)", message, re.IGNORECASE)
            name = match.group(1).strip() if match else message.strip()
            fill_slot(slots, "name", name)
            fills.append(("name", name))
            state["conversation_phase"] = PHASE_VENUE
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "filled_this_turn": fills,
                    "next_question_target": "ask_venue",
                },
                direct_response="What venue should I note?",
            )

        if phase == PHASE_VENUE and not get_slot_value(slots, "venue"):
            venue = message.strip()
            fill_slot(slots, "venue", venue)
            fills.append(("venue", venue))
            state["conversation_phase"] = PHASE_EVENT_DATE
            return ToolResult(
                state=state,
                response_context={
                    "tool": self.name,
                    "filled_this_turn": fills,
                    "next_question_target": "ask_event_date",
                },
                direct_response="What date is the event?",
            )

        date_value = message.strip()
        fill_slot(slots, "event_date", date_value)
        fills.append(("event_date", date_value))
        state["conversation_phase"] = "complete"
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "filled_this_turn": fills,
                "next_question_target": None,
            },
            direct_response="Thanks, I have the core event details.",
        )


class _FakeModificationTool:
    name = "modification_tool"

    async def run(self, *, message, history, state):
        slots = state["slots"]
        match = re.search(r"change my name to (.+)", message, re.IGNORECASE)
        new_name = match.group(1).strip() if match else "Updated Name"
        old_name = get_slot_value(slots, "name")
        fill_slot(slots, "name", new_name)
        return ToolResult(
            state=state,
            response_context={
                "tool": self.name,
                "modification": {
                    "target_slot": "name",
                    "action": "replace",
                    "old_value": old_name,
                    "new_value": new_name,
                },
                "next_question_target": "continue",
            },
            direct_response=f"I updated your name to {new_name}.",
        )


@pytest.fixture
def orchestrator_testbed(monkeypatch):
    state_store: dict[str, dict] = {}
    message_store: dict[str, list[dict]] = {}

    async def fake_init_db():
        return None

    async def fake_create_project_and_thread(*, thread_id, project_id, title, user_id):
        return project_id or str(uuid.uuid4()), thread_id, str(uuid.uuid4())

    async def fake_load_conversation_state(thread_id):
        return state_store.get(thread_id)

    async def fake_load_messages(thread_id):
        return list(message_store.get(thread_id, []))

    async def fake_save_conversation_state(*, thread_id, project_id, current_node, slots, is_completed):
        state_id = state_store.get(thread_id, {}).get("id") or str(uuid.uuid4())
        state_store[thread_id] = {
            "id": state_id,
            "project_id": project_id,
            "current_node": current_node,
            "slots": slots,
            "is_completed": is_completed,
        }
        return state_id

    async def fake_save_message(*, thread_id, project_id, author_id, sender_type, content, ai_conversation_state_id):
        sender = "user" if sender_type == "client" else "ai"
        message_store.setdefault(thread_id, []).append(
            {
                "sender_type": sender,
                "content": content,
            }
        )

    async def fake_render_response(*, tool_result, user_message, history):
        return tool_result.direct_response or "fallback render"

    async def fake_route_turn(*, message, history, state):
        lowered = message.lower()
        if "change my name to" in lowered:
            return OrchestratorDecision(
                action="tool_call",
                tool_calls=[ToolCall(tool_name="modification_tool", reason="test modification")],
                confidence=1.0,
            )
        if "??" in lowered:
            return OrchestratorDecision(
                action="clarify",
                tool_calls=[],
                confidence=0.9,
                clarifying_question="Could you clarify that?",
            )
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[ToolCall(tool_name="basic_info_tool", reason="test basic info")],
            confidence=1.0,
        )

    monkeypatch.setattr(orchestrator_module, "init_db", fake_init_db)
    monkeypatch.setattr(orchestrator_module, "create_project_and_thread", fake_create_project_and_thread)
    monkeypatch.setattr(orchestrator_module, "load_conversation_state", fake_load_conversation_state)
    monkeypatch.setattr(orchestrator_module, "load_messages", fake_load_messages)
    monkeypatch.setattr(orchestrator_module, "save_conversation_state", fake_save_conversation_state)
    monkeypatch.setattr(orchestrator_module, "save_message", fake_save_message)
    monkeypatch.setattr(orchestrator_module, "route_turn", fake_route_turn)
    monkeypatch.setattr(orchestrator_module, "render_response", fake_render_response)
    monkeypatch.setitem(orchestrator_module.TOOL_REGISTRY, "basic_info_tool", _FakeBasicInfoTool())
    monkeypatch.setitem(orchestrator_module.TOOL_REGISTRY, "modification_tool", _FakeModificationTool())

    return orchestrator_module.AgentOrchestrator(), state_store, message_store


@pytest.mark.asyncio
async def test_orchestrator_processes_and_persists_multi_turn_flow(orchestrator_testbed):
    orchestrator, state_store, message_store = orchestrator_testbed
    thread_id = str(uuid.uuid4())

    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is Sarah Johnson",
        author_id="user-1",
    )
    assert response["tool_used"] == "basic_info_tool"
    assert response["current_node"] == PHASE_VENUE
    assert get_slot_value(response["slots"], "name") == "Sarah Johnson"

    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="Pearluxe Tower",
        author_id="user-1",
    )
    assert response["current_node"] == PHASE_EVENT_DATE
    assert get_slot_value(response["slots"], "venue") == "Pearluxe Tower"

    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="2026-07-04",
        author_id="user-1",
    )
    assert response["current_node"] == "complete"
    assert response["is_complete"] is True
    assert get_slot_value(response["slots"], "event_date") == "2026-07-04"
    assert state_store[thread_id]["current_node"] == "complete"
    assert len(message_store[thread_id]) == 6


@pytest.mark.asyncio
async def test_orchestrator_applies_modification_tool_and_preserves_history(orchestrator_testbed):
    orchestrator, _, _ = orchestrator_testbed
    thread_id = str(uuid.uuid4())

    await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is John Doe",
        author_id="user-1",
    )
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="change my name to Jonathan Doe",
        author_id="user-1",
    )

    assert response["tool_used"] == "modification_tool"
    assert get_slot_value(response["slots"], "name") == "Jonathan Doe"
    assert len(response["slots"]["name"]["modification_history"]) >= 1


@pytest.mark.asyncio
async def test_orchestrator_resumes_from_persisted_state(orchestrator_testbed):
    orchestrator, _, _ = orchestrator_testbed
    thread_id = str(uuid.uuid4())

    await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is Bob",
        author_id="user-1",
    )
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="Amphoreus Ballroom",
        author_id="user-1",
    )

    assert get_slot_value(response["slots"], "name") == "Bob"
    assert get_slot_value(response["slots"], "venue") == "Amphoreus Ballroom"
    assert response["current_node"] == PHASE_EVENT_DATE


@pytest.mark.asyncio
async def test_orchestrator_clarify_path_uses_response_renderer(orchestrator_testbed):
    orchestrator, _, _ = orchestrator_testbed
    thread_id = str(uuid.uuid4())

    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="??",
        author_id="user-1",
    )

    assert response["tool_used"] is None
    assert response["content"] == "fallback render"

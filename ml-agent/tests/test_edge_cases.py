"""Current edge-case coverage for the orchestrator shell."""

import sys
import uuid

import pytest

import orchestrator as orchestrator_module
from agent.models import OrchestratorDecision, ToolCall
from agent.state import PHASE_GREETING, fill_slot, get_slot_value, initialize_empty_slots
from agent.tools.base import ToolResult

class _EchoTool:
    name = "basic_info_tool"

    def __init__(self, *, raise_error: bool = False) -> None:
        self.raise_error = raise_error

    async def run(self, *, message, history, state):
        if self.raise_error:
            raise RuntimeError("boom")
        slots = state["slots"]
        if not get_slot_value(slots, "name"):
            fill_slot(slots, "name", message.strip())
        return ToolResult(
            state=state,
            response_context={"tool": self.name, "next_question_target": "ask_event_type"},
            direct_response=f"Echoed: {message[:40]}",
        )

@pytest.fixture
def edge_testbed(monkeypatch):
    states: dict[str, dict] = {}

    async def fake_init_db():
        return None

    async def fake_create_project_and_thread(*, thread_id, project_id, title, user_id):
        return project_id or str(uuid.uuid4()), thread_id, str(uuid.uuid4())

    async def fake_load_conversation_state(thread_id):
        return states.get(thread_id)

    async def fake_load_messages(thread_id):
        return []

    async def fake_save_conversation_state(*, thread_id, project_id, current_node, slots, is_completed):
        state_id = states.get(thread_id, {}).get("id") or str(uuid.uuid4())
        states[thread_id] = {
            "id": state_id,
            "project_id": project_id,
            "current_node": current_node,
            "slots": slots,
            "is_completed": is_completed,
        }
        return state_id

    async def fake_save_message(**kwargs):
        return None

    async def fake_render_response(*, tool_result, user_message, history):
        return tool_result.direct_response or "rendered"

    async def fake_route_turn(*, message, history, state):
        lowered = message.lower()
        if lowered == "":
            return OrchestratorDecision(
                action="clarify",
                tool_calls=[],
                confidence=0.9,
                clarifying_question="Could you say that again?",
            )
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[ToolCall(tool_name="basic_info_tool", reason="edge test")],
            confidence=1.0,
        )

    monkeypatch.setattr(orchestrator_module, "init_db", fake_init_db)
    monkeypatch.setattr(orchestrator_module, "create_project_and_thread", fake_create_project_and_thread)
    monkeypatch.setattr(orchestrator_module, "load_conversation_state", fake_load_conversation_state)
    monkeypatch.setattr(orchestrator_module, "load_messages", fake_load_messages)
    monkeypatch.setattr(orchestrator_module, "save_conversation_state", fake_save_conversation_state)
    monkeypatch.setattr(orchestrator_module, "save_message", fake_save_message)
    monkeypatch.setattr(orchestrator_module, "render_response", fake_render_response)
    monkeypatch.setattr(orchestrator_module, "route_turn", fake_route_turn)
    monkeypatch.setitem(orchestrator_module.TOOL_REGISTRY, "basic_info_tool", _EchoTool())

    return orchestrator_module.AgentOrchestrator(), states

@pytest.mark.skip(reason="superseded by stability refactor (intents.py + tight history + pending TTL); see HANDOVER.md")
@pytest.mark.asyncio
async def test_empty_message_returns_graceful_reply(edge_testbed):
    orchestrator, _ = edge_testbed

    response = await orchestrator.process_message(
        thread_id=str(uuid.uuid4()),
        message="",
        author_id="user-1",
    )

    assert response["content"] == "rendered"
    assert response["is_complete"] is False

@pytest.mark.asyncio
async def test_very_long_message_does_not_crash(edge_testbed):
    orchestrator, _ = edge_testbed
    long_message = "My name is John " + ("Smith " * 1000)

    response = await orchestrator.process_message(
        thread_id=str(uuid.uuid4()),
        message=long_message,
        author_id="user-1",
    )

    assert response["content"].startswith("Echoed:")
    assert response.get("tool_used") == "basic_info_tool"

@pytest.mark.asyncio
async def test_unicode_input_is_preserved(edge_testbed):
    orchestrator, states = edge_testbed
    thread_id = str(uuid.uuid4())

    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="Jos\u00e9 Garc\u00eda-L\u00f3pez",
        author_id="user-1",
    )

    assert response["slots_filled"] >= 1
    assert get_slot_value(states[thread_id]["slots"], "name") == "Jos\u00e9 Garc\u00eda-L\u00f3pez"

@pytest.mark.asyncio
async def test_orchestrator_failure_path_returns_safe_fallback(monkeypatch):
    async def fake_init_db():
        return None

    async def fake_create_project_and_thread(*, thread_id, project_id, title, user_id):
        return project_id or str(uuid.uuid4()), thread_id, str(uuid.uuid4())

    async def fake_load_conversation_state(thread_id):
        return None

    async def fake_load_messages(thread_id):
        return []

    async def fake_save_conversation_state(*, thread_id, project_id, current_node, slots, is_completed):
        return str(uuid.uuid4())

    async def fake_save_message(**kwargs):
        return None

    async def fake_route_turn(*, message, history, state):
        return OrchestratorDecision(
            action="tool_call",
            tool_calls=[ToolCall(tool_name="basic_info_tool", reason="force error")],
            confidence=1.0,
        )

    monkeypatch.setattr(orchestrator_module, "init_db", fake_init_db)
    monkeypatch.setattr(orchestrator_module, "create_project_and_thread", fake_create_project_and_thread)
    monkeypatch.setattr(orchestrator_module, "load_conversation_state", fake_load_conversation_state)
    monkeypatch.setattr(orchestrator_module, "load_messages", fake_load_messages)
    monkeypatch.setattr(orchestrator_module, "save_conversation_state", fake_save_conversation_state)
    monkeypatch.setattr(orchestrator_module, "save_message", fake_save_message)
    monkeypatch.setattr(orchestrator_module, "route_turn", fake_route_turn)
    monkeypatch.setitem(orchestrator_module.TOOL_REGISTRY, "basic_info_tool", _EchoTool(raise_error=True))

    orchestrator = orchestrator_module.AgentOrchestrator()
    response = await orchestrator.process_message(
        thread_id=str(uuid.uuid4()),
        message="hello",
        author_id="user-1",
    )

    assert "snag" in response["content"].lower()
    assert response["current_node"] == PHASE_GREETING

import sys
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from agent import instructor_client as client_module
from agent.trace_context import TraceContextFilter, trace_scope

class _MiniSchema(BaseModel):
    value: str

@pytest.mark.asyncio
async def test_extract_uses_responses_api_with_json_schema(monkeypatch):
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_text='{"value":"ok"}')

    monkeypatch.setattr(client_module._raw_async.responses, "create", fake_create)

    with trace_scope(
        thread_id="thread-123",
        project_id="project-456",
        conversation_id="conv-789",
        user_id="user-abc",
        phase="S4_service_type",
        tool="router",
        target="ask_service_type",
    ):
        result = await client_module.extract(
            schema=_MiniSchema,
            system="You are strict.",
            user_message="hello",
            history=[
                {"role": "assistant", "content": "previous answer"},
                {"role": "user", "content": "older question"},
            ],
            model="gpt-test",
            max_tokens=123,
        )

    assert result == _MiniSchema(value="ok")
    assert captured["model"] == "gpt-test"
    assert captured["instructions"] == "You are strict."
    assert captured["max_output_tokens"] == 123
    assert captured["store"] is False
    assert captured["input"] == [
        {"role": "assistant", "content": "previous answer"},
        {"role": "user", "content": "older question"},
        {"role": "user", "content": "hello"},
    ]
    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["text"]["format"]["name"] == "_MiniSchema"
    assert captured["text"]["format"]["strict"] is True
    assert "schema" in captured["text"]["format"]
    assert captured["metadata"]["thread_id"] == "thread-123"
    assert captured["metadata"]["project_id"] == "project-456"
    assert captured["metadata"]["conversation_id"] == "conv-789"
    assert captured["metadata"]["phase"] == "S4_service_type"
    assert captured["metadata"]["tool"] == "router"
    assert captured["metadata"]["target"] == "ask_service_type"
    assert captured["metadata"]["schema"] == "_MiniSchema"
    assert len(captured["prompt_cache_key"]) == 64
    assert captured["safety_identifier"].startswith("catering_")

@pytest.mark.asyncio
async def test_generate_text_uses_responses_api(monkeypatch):
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output_text="hello there")

    monkeypatch.setattr(client_module._raw_async.responses, "create", fake_create)

    with trace_scope(thread_id="thread-1", user_id="user-1", phase="S16_special_requests", tool="response_generator"):
        text = await client_module.generate_text(
            system="You are helpful.",
            user="Write one line.",
            model="gpt-test",
            max_tokens=77,
            temperature=0.4,
        )

    assert text == "hello there"
    assert captured["model"] == "gpt-test"
    assert captured["instructions"] == "You are helpful."
    assert captured["input"] == [{"role": "user", "content": "Write one line."}]
    assert captured["max_output_tokens"] == 77
    assert captured["temperature"] == 0.4
    assert captured["store"] is False
    assert captured["metadata"]["operation"] == "generate_text"
    assert captured["metadata"]["tool"] == "response_generator"
    assert captured["metadata"]["phase"] == "S16_special_requests"
    assert captured["metadata"]["thread_id"] == "thread-1"
    assert len(captured["prompt_cache_key"]) == 64
    assert captured["safety_identifier"].startswith("catering_")

@pytest.mark.asyncio
async def test_extract_falls_back_to_chat_completions_when_responses_fails(monkeypatch):
    async def fail_create(**kwargs):
        raise RuntimeError("responses unavailable")

    async def fake_chat_create(**kwargs):
        tool_call = SimpleNamespace(function=SimpleNamespace(arguments='{"value":"fallback"}'))
        message = SimpleNamespace(tool_calls=[tool_call])
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    monkeypatch.setattr(client_module._raw_async.responses, "create", fail_create)
    monkeypatch.setattr(client_module._raw_async.chat.completions, "create", fake_chat_create)

    result = await client_module.extract(
        schema=_MiniSchema,
        system="Fallback system",
        user_message="hello",
        model="gpt-test",
    )

    assert result == _MiniSchema(value="fallback")

@pytest.mark.asyncio
async def test_extract_retries_with_higher_max_tokens_on_truncated_json(monkeypatch):
    calls: list[int] = []

    async def fake_create(**kwargs):
        calls.append(int(kwargs["max_output_tokens"]))
        # First attempt: truncated JSON (common when max_output_tokens too low)
        if len(calls) == 1:
            return SimpleNamespace(output_text='{"value":"oops')
        # Second attempt: valid JSON
        return SimpleNamespace(output_text='{"value":"ok"}')

    monkeypatch.setattr(client_module._raw_async.responses, "create", fake_create)

    result = await client_module.extract(
        schema=_MiniSchema,
        system="You are strict.",
        user_message="hello",
        model="gpt-test",
        max_tokens=200,
        max_retries=1,
    )

    assert result == _MiniSchema(value="ok")
    assert calls[0] == 200
    assert calls[1] > calls[0]
    assert calls[1] >= 1000

@pytest.mark.asyncio
async def test_generate_text_falls_back_to_chat_completions_when_responses_fails(monkeypatch):
    async def fail_create(**kwargs):
        raise RuntimeError("responses unavailable")

    async def fake_chat_create(**kwargs):
        message = SimpleNamespace(content="fallback text")
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])

    monkeypatch.setattr(client_module._raw_async.responses, "create", fail_create)
    monkeypatch.setattr(client_module._raw_async.chat.completions, "create", fake_chat_create)

    text = await client_module.generate_text(
        system="Fallback system",
        user="hello",
        model="gpt-test",
    )

    assert text == "fallback text"

def test_trace_context_filter_injects_defaults_and_current_scope():
    record = SimpleNamespace()
    filt = TraceContextFilter()
    assert filt.filter(record) is True
    assert record.trace_thread == "-"
    assert record.trace_phase == "-"
    assert record.trace_tool == "-"
    assert record.trace_target == "-"

    scoped = SimpleNamespace()
    with trace_scope(thread_id="thread-9", phase="S9", tool="menu_selection_tool", target="show_appetizer_menu"):
        assert filt.filter(scoped) is True
        assert scoped.trace_thread == "thread-9"
        assert scoped.trace_phase == "S9"
        assert scoped.trace_tool == "menu_selection_tool"
        assert scoped.trace_target == "show_appetizer_menu"

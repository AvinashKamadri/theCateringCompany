"""
Node functionality tests
"""

import pytest
from agent.nodes import (
    collect_name_node,
    collect_phone_node,
    collect_event_date_node,
    select_service_type_node,
    select_event_type_node,
)
from agent.state import initialize_empty_slots
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_collect_name_node():
    """Test name collection node"""
    state = {
        "messages": [HumanMessage(content="My name is John Smith")],
        "conversation_id": "test-1",
        "project_id": "proj-1",
        "thread_id": "thread-1",
        "current_node": "collect_name",
        "slots": initialize_empty_slots(),
        "next_action": None,
        "error": None
    }
    
    result = await collect_name_node(state)
    
    assert result["slots"]["name"]["filled"] == True
    assert "john" in result["slots"]["name"]["value"].lower()
    assert len(result["messages"]) > 1  # Added AI response


@pytest.mark.asyncio
async def test_collect_phone_node():
    """Test phone collection node"""
    state = {
        "messages": [HumanMessage(content="555-123-4567")],
        "conversation_id": "test-1",
        "project_id": "proj-1",
        "thread_id": "thread-1",
        "current_node": "collect_phone",
        "slots": initialize_empty_slots(),
        "next_action": None,
        "error": None
    }
    
    result = await collect_phone_node(state)
    
    assert result["slots"]["phone"]["filled"] == True
    assert result["slots"]["phone"]["value"] is not None


@pytest.mark.asyncio
async def test_collect_event_date_node():
    """Test event date collection node"""
    state = {
        "messages": [HumanMessage(content="June 15th, 2026")],
        "conversation_id": "test-1",
        "project_id": "proj-1",
        "thread_id": "thread-1",
        "current_node": "collect_event_date",
        "slots": initialize_empty_slots(),
        "next_action": None,
        "error": None
    }
    
    result = await collect_event_date_node(state)
    
    assert result["slots"]["event_date"]["filled"] == True
    assert "2026" in result["slots"]["event_date"]["value"]


@pytest.mark.asyncio
async def test_select_service_type_node():
    """Test service type selection node"""
    state = {
        "messages": [HumanMessage(content="on-site service please")],
        "conversation_id": "test-1",
        "project_id": "proj-1",
        "thread_id": "thread-1",
        "current_node": "select_service_type",
        "slots": initialize_empty_slots(),
        "next_action": None,
        "error": None
    }
    
    result = await select_service_type_node(state)
    
    assert result["slots"]["service_type"]["filled"] == True
    assert result["slots"]["service_type"]["value"] in ["on-site", "drop-off"]


@pytest.mark.asyncio
async def test_select_event_type_node():
    """Test event type selection node"""
    state = {
        "messages": [HumanMessage(content="It's a wedding")],
        "conversation_id": "test-1",
        "project_id": "proj-1",
        "thread_id": "thread-1",
        "current_node": "select_event_type",
        "slots": initialize_empty_slots(),
        "next_action": None,
        "error": None
    }
    
    result = await select_event_type_node(state)
    
    assert result["slots"]["event_type"]["filled"] == True
    assert result["slots"]["event_type"]["value"] in ["Wedding", "Corporate", "Birthday", "Social", "Custom"]

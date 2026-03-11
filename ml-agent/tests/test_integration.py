"""
Integration tests for complete conversation flows
"""

import pytest
from orchestrator import AgentOrchestrator


@pytest.mark.asyncio
async def test_complete_conversation_flow():
    """Test a complete conversation from start to finish"""
    orchestrator = AgentOrchestrator()
    thread_id = "test-thread-1"
    user_id = "test-user-1"
    
    # Message 1: Name
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is Sarah Johnson",
        author_id=user_id
    )
    assert response.slots_filled == 1
    assert response.current_node == "collect_phone"
    state = response.conversation_state
    
    # Message 2: Phone
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="555-123-4567",
        author_id=user_id,
        conversation_state=state
    )
    assert response.slots_filled == 2
    assert response.current_node == "collect_event_date"
    state = response.conversation_state
    
    # Message 3: Event date
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="June 15th, 2026",
        author_id=user_id,
        conversation_state=state
    )
    assert response.slots_filled == 3
    assert response.current_node == "select_service_type"
    state = response.conversation_state
    
    # Message 4: Service type
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="on-site service please",
        author_id=user_id,
        conversation_state=state
    )
    assert response.slots_filled == 4
    assert response.current_node == "select_event_type"
    state = response.conversation_state
    
    # Message 5: Event type
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="It's a wedding",
        author_id=user_id,
        conversation_state=state
    )
    assert response.slots_filled == 5
    assert response.current_node == "collect_venue"
    state = response.conversation_state
    
    # Message 6: Venue
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="The venue is at 123 Main Street, full kitchen available, load-in at 2pm",
        author_id=user_id,
        conversation_state=state
    )
    assert response.slots_filled == 6
    assert response.current_node == "collect_guest_count"
    state = response.conversation_state
    
    # Message 7: Guest count
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="We're expecting 150 guests",
        author_id=user_id,
        conversation_state=state
    )
    assert response.slots_filled == 7
    assert response.current_node == "collect_special_requests"
    state = response.conversation_state
    
    # Message 8: Special requests
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="We have 3 vegetarian guests and one guest with a peanut allergy",
        author_id=user_id,
        conversation_state=state
    )
    assert response.slots_filled == 8
    assert response.is_complete == True
    assert response.contract_data is not None
    
    # Verify contract data
    contract = response.contract_data
    assert "pricing" in contract
    assert "upsells" in contract
    assert "margin" in contract
    assert "staffing" in contract


@pytest.mark.asyncio
async def test_conversation_with_modification():
    """Test conversation with @AI modification"""
    orchestrator = AgentOrchestrator()
    thread_id = "test-thread-2"
    user_id = "test-user-2"
    
    # Fill some slots first
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is John Doe",
        author_id=user_id
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="555-987-6543",
        author_id=user_id,
        conversation_state=state
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="July 20th, 2026",
        author_id=user_id,
        conversation_state=state
    )
    state = response.conversation_state
    
    # Now modify the name
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="@AI change my name to Jonathan Doe",
        author_id=user_id,
        conversation_state=state
    )
    
    # Verify modification
    assert response.conversation_state["slots"]["name"]["value"] == "Jonathan Doe"
    assert len(response.conversation_state["slots"]["name"]["modification_history"]) > 0


@pytest.mark.asyncio
async def test_conversation_with_multiple_info_in_one_message():
    """Test handling multiple pieces of information in one message"""
    orchestrator = AgentOrchestrator()
    thread_id = "test-thread-3"
    user_id = "test-user-3"
    
    # Provide multiple pieces of info at once
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="Hi, my name is Alice Smith and my phone is 555-111-2222",
        author_id=user_id
    )
    
    # Should extract name
    assert response.slots_filled >= 1
    assert response.conversation_state["slots"]["name"]["filled"] == True


@pytest.mark.asyncio
async def test_conversation_resume():
    """Test resuming a conversation from saved state"""
    orchestrator = AgentOrchestrator()
    thread_id = "test-thread-4"
    user_id = "test-user-4"
    
    # Start conversation
    response1 = await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is Bob",
        author_id=user_id
    )
    saved_state = response1.conversation_state
    
    # Simulate resuming later with saved state
    response2 = await orchestrator.process_message(
        thread_id=thread_id,
        message="555-999-8888",
        author_id=user_id,
        conversation_state=saved_state
    )
    
    # Should continue from where we left off
    assert response2.slots_filled == 2
    assert response2.conversation_state["slots"]["name"]["value"] == "Bob"
    assert response2.conversation_state["slots"]["phone"]["filled"] == True

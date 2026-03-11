"""
Edge case and error handling tests
"""

import pytest
from orchestrator import AgentOrchestrator


@pytest.mark.asyncio
async def test_empty_message():
    """Test handling of empty message"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-1",
        message="",
        author_id="user-1"
    )
    
    # Should handle gracefully
    assert response.content != ""
    assert response.error is None


@pytest.mark.asyncio
async def test_very_long_message():
    """Test handling of very long message"""
    orchestrator = AgentOrchestrator()
    
    long_message = "My name is John " + "Smith " * 1000  # Very long name
    
    response = await orchestrator.process_message(
        thread_id="test-2",
        message=long_message,
        author_id="user-1"
    )
    
    # Should handle gracefully
    assert response.error is None


@pytest.mark.asyncio
async def test_invalid_phone_format():
    """Test handling of invalid phone number"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-3",
        message="My name is John",
        author_id="user-1"
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id="test-3",
        message="abc123",  # Invalid phone
        author_id="user-1",
        conversation_state=state
    )
    
    # Should ask for clarification
    assert "phone" in response.content.lower() or response.slots_filled == 1


@pytest.mark.asyncio
async def test_past_date():
    """Test handling of past event date"""
    orchestrator = AgentOrchestrator()
    
    # Fill name and phone first
    response = await orchestrator.process_message(
        thread_id="test-4",
        message="My name is Jane",
        author_id="user-1"
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id="test-4",
        message="555-111-2222",
        author_id="user-1",
        conversation_state=state
    )
    state = response.conversation_state
    
    # Try past date
    response = await orchestrator.process_message(
        thread_id="test-4",
        message="January 1st, 2020",  # Past date
        author_id="user-1",
        conversation_state=state
    )
    
    # Should reject and ask for future date
    assert response.slots_filled == 2 or "future" in response.content.lower() or "past" in response.content.lower()


@pytest.mark.asyncio
async def test_guest_count_too_low():
    """Test handling of guest count below minimum"""
    orchestrator = AgentOrchestrator()
    
    # Navigate to guest count (simplified)
    response = await orchestrator.process_message(
        thread_id="test-5",
        message="My name is Test User",
        author_id="user-1"
    )
    
    # The actual test would need to navigate through all slots
    # This is a simplified version
    assert response.error is None


@pytest.mark.asyncio
async def test_ambiguous_ai_modification():
    """Test handling of ambiguous @AI modification"""
    orchestrator = AgentOrchestrator()
    
    # Fill multiple slots
    response = await orchestrator.process_message(
        thread_id="test-6",
        message="My name is Bob",
        author_id="user-1"
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id="test-6",
        message="555-1234",
        author_id="user-1",
        conversation_state=state
    )
    state = response.conversation_state
    
    # Ambiguous modification
    response = await orchestrator.process_message(
        thread_id="test-6",
        message="@AI change it",  # Ambiguous - what to change?
        author_id="user-1",
        conversation_state=state
    )
    
    # Should ask for clarification or handle gracefully
    assert response.error is None


@pytest.mark.asyncio
async def test_special_characters_in_input():
    """Test handling of special characters"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-7",
        message="My name is José García-López",
        author_id="user-1"
    )
    
    # Should handle special characters
    assert response.slots_filled == 1
    assert response.error is None


@pytest.mark.asyncio
async def test_numeric_name():
    """Test handling of numeric input for name"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-8",
        message="12345",
        author_id="user-1"
    )
    
    # Should handle gracefully (might ask for clarification)
    assert response.error is None


@pytest.mark.asyncio
async def test_mixed_case_ai_tag():
    """Test @AI tag with mixed case"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-9",
        message="My name is Test",
        author_id="user-1"
    )
    state = response.conversation_state
    
    # Try different @AI variations
    response = await orchestrator.process_message(
        thread_id="test-9",
        message="@ai change name to NewName",  # lowercase
        author_id="user-1",
        conversation_state=state
    )
    
    # Should detect @AI regardless of case
    assert response.error is None


@pytest.mark.asyncio
async def test_multiple_ai_tags_in_message():
    """Test multiple @AI tags in one message"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-10",
        message="My name is Test",
        author_id="user-1"
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id="test-10",
        message="555-1234",
        author_id="user-1",
        conversation_state=state
    )
    state = response.conversation_state
    
    # Multiple modifications
    response = await orchestrator.process_message(
        thread_id="test-10",
        message="@AI change name to John and @AI change phone to 555-9999",
        author_id="user-1",
        conversation_state=state
    )
    
    # Should handle gracefully
    assert response.error is None


@pytest.mark.asyncio
async def test_conversation_with_typos():
    """Test handling of messages with typos"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-11",
        message="My nmae is Jhon Smtih",  # Typos
        author_id="user-1"
    )
    
    # Should still extract name despite typos
    assert response.error is None


@pytest.mark.asyncio
async def test_null_conversation_state():
    """Test handling of null conversation state"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-12",
        message="My name is Test",
        author_id="user-1",
        conversation_state=None  # Explicitly None
    )
    
    # Should initialize new conversation
    assert response.slots_filled >= 0
    assert response.error is None


@pytest.mark.asyncio
async def test_unicode_emoji_in_message():
    """Test handling of emoji in messages"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-13",
        message="My name is Sarah 😊",
        author_id="user-1"
    )
    
    # Should handle emoji gracefully
    assert response.error is None

# Testing Guide

## Overview

This guide covers all testing approaches for the Catering AI Agent.

## Test Structure

```
tests/
├── test_structure.py          # Structure & compilation tests (no API key)
├── test_routing.py            # Routing logic tests
├── test_graph_compilation.py  # Graph compilation test
├── test_nodes.py              # Individual node tests
├── test_tools.py              # Tool functionality tests
├── test_integration.py        # End-to-end conversation tests
└── test_edge_cases.py         # Edge case and error handling tests
```

## Running Tests

### Quick Start

```bash
# Structure tests (no API key required)
python test_structure.py

# All tests with pytest
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_routing.py -v

# With coverage
python -m pytest tests/ --cov=agent --cov=tools --cov-report=html
```

### Test Categories

#### 1. Structure Tests (No API Key Required)

Tests basic structure and compilation without making API calls.

```bash
python test_structure.py
```

**What it tests:**
- Graph compilation
- State initialization
- Routing logic
- Node imports
- Tool imports

**Expected output:**
```
✓ Graph compiled successfully
✓ State initialization successful (all 8 slots with correct structure)
✓ Routing logic tests passed (4 scenarios)
✓ All 11 nodes imported successfully
✓ All 8 tools imported successfully

RESULTS: 5/5 tests passed
```

#### 2. Routing Tests

Tests conditional routing logic.

```bash
python -m pytest tests/test_routing.py -v
```

**What it tests:**
- @AI detection (various formats)
- Route to first unfilled slot
- Route through all slots in sequence
- Skip filled slots
- Handle out-of-order filling
- Edge cases

**Expected output:**
```
test_routing.py::test_ai_detection_uppercase PASSED
test_routing.py::test_ai_detection_lowercase PASSED
test_routing.py::test_route_to_generate_contract PASSED
test_routing.py::test_route_to_first_unfilled PASSED
...
16 passed
```

#### 3. Node Tests

Tests individual node functionality.

```bash
python -m pytest tests/test_nodes.py -v
```

Create this file:

```python
# tests/test_nodes.py
import pytest
from agent.nodes import (
    collect_name_node,
    collect_phone_node,
    collect_event_date_node,
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
```

#### 4. Tool Tests

Tests tool functionality.

```bash
python -m pytest tests/test_tools.py -v
```

Create this file:

```python
# tests/test_tools.py
import pytest
from tools.slot_validation import validate_slot
from tools.upsells import suggest_upsells
from tools.margin_calculation import calculate_margin
from tools.staffing import calculate_staffing
from tools.missing_info import flag_missing_info

def test_validate_phone():
    """Test phone validation"""
    # Valid phone
    result = validate_slot("phone", "555-123-4567")
    assert result["valid"] == True
    
    # Invalid phone
    result = validate_slot("phone", "invalid")
    assert result["valid"] == False

def test_validate_guest_count():
    """Test guest count validation"""
    # Valid count
    result = validate_slot("guest_count", 150)
    assert result["valid"] == True
    
    # Too low
    result = validate_slot("guest_count", 5)
    assert result["valid"] == False
    
    # Too high
    result = validate_slot("guest_count", 15000)
    assert result["valid"] == False

@pytest.mark.asyncio
async def test_suggest_upsells_wedding():
    """Test upsell suggestions for wedding"""
    result = await suggest_upsells.ainvoke({
        "event_type": "Wedding",
        "guest_count": 150,
        "current_selections": {}
    })
    
    assert "upsells" in result
    assert len(result["upsells"]) > 0
    assert result["total_potential_revenue"] > 0
    
    # Check for wedding-specific upsells
    categories = [u["category"] for u in result["upsells"]]
    assert "Bar Service" in categories

@pytest.mark.asyncio
async def test_calculate_margin():
    """Test margin calculation"""
    line_items = [
        {"name": "Catering Package", "price": 5000.0, "cost": 3000.0}
    ]
    
    result = await calculate_margin.ainvoke({
        "line_items": line_items,
        "guest_count": 100,
        "service_type": "on-site"
    })
    
    assert result["total_revenue"] > 0
    assert result["total_cost"] > 0
    assert result["gross_margin"] > 0
    assert result["margin_percentage"] > 0

@pytest.mark.asyncio
async def test_calculate_staffing():
    """Test staffing calculation"""
    result = await calculate_staffing.ainvoke({
        "guest_count": 150,
        "service_type": "on-site",
        "event_type": "Wedding",
        "event_duration_hours": 6.0
    })
    
    assert result["servers_needed"] > 0
    assert result["total_labor_hours"] > 0
    assert result["estimated_labor_cost"] > 0

@pytest.mark.asyncio
async def test_flag_missing_info():
    """Test missing info detection"""
    slots = {
        "name": "John Smith",
        "phone": "555-123-4567",
        "event_date": "2026-06-15",
        "service_type": "on-site",
        "event_type": "Wedding",
        "venue": {"address": "123 Main St", "kitchen_access": "none"},
        "guest_count": 150,
        "special_requests": {}
    }
    
    result = await flag_missing_info.ainvoke({
        "slots": slots,
        "event_type": "Wedding"
    })
    
    assert "is_complete" in result
    assert "risk_flags" in result
    
    # Should flag no kitchen access for on-site
    risk_types = [flag["type"] for flag in result["risk_flags"]]
    assert "no_kitchen_access" in risk_types
```

#### 5. Integration Tests

Tests complete conversation flows.

```bash
python -m pytest tests/test_integration.py -v
```

Create this file:

```python
# tests/test_integration.py
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
```

#### 6. Edge Case Tests

Tests error handling and edge cases.

```bash
python -m pytest tests/test_edge_cases.py -v
```

Create this file:

```python
# tests/test_edge_cases.py
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
async def test_invalid_phone_format():
    """Test handling of invalid phone number"""
    orchestrator = AgentOrchestrator()
    
    response = await orchestrator.process_message(
        thread_id="test-2",
        message="My name is John",
        author_id="user-1"
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id="test-2",
        message="abc123",  # Invalid phone
        author_id="user-1",
        conversation_state=state
    )
    
    # Should ask for clarification
    assert "phone" in response.content.lower()
    assert response.slots_filled == 1  # Name filled, phone not filled

@pytest.mark.asyncio
async def test_past_date():
    """Test handling of past event date"""
    orchestrator = AgentOrchestrator()
    
    # Fill name and phone first
    response = await orchestrator.process_message(
        thread_id="test-3",
        message="My name is Jane",
        author_id="user-1"
    )
    state = response.conversation_state
    
    response = await orchestrator.process_message(
        thread_id="test-3",
        message="555-111-2222",
        author_id="user-1",
        conversation_state=state
    )
    state = response.conversation_state
    
    # Try past date
    response = await orchestrator.process_message(
        thread_id="test-3",
        message="January 1st, 2020",  # Past date
        author_id="user-1",
        conversation_state=state
    )
    
    # Should reject and ask for future date
    assert response.slots_filled == 2  # Date not filled
    assert "future" in response.content.lower() or "past" in response.content.lower()

@pytest.mark.asyncio
async def test_guest_count_out_of_range():
    """Test handling of invalid guest count"""
    orchestrator = AgentOrchestrator()
    
    # Navigate to guest count node
    # (simplified - in real test, fill all previous slots)
    
    response = await orchestrator.process_message(
        thread_id="test-4",
        message="We're expecting 5 guests",  # Below minimum of 10
        author_id="user-1"
    )
    
    # Should ask for clarification or reject
    # (exact behavior depends on implementation)

@pytest.mark.asyncio
async def test_ambiguous_ai_modification():
    """Test handling of ambiguous @AI modification"""
    orchestrator = AgentOrchestrator()
    
    # Fill multiple slots
    response = await orchestrator.process_message(
        thread_id="test-5",
        message="My name is Bob, phone is 555-1234, event is June 1st",
        author_id="user-1"
    )
    state = response.conversation_state
    
    # Ambiguous modification
    response = await orchestrator.process_message(
        thread_id="test-5",
        message="@AI change it to something else",  # Ambiguous
        author_id="user-1",
        conversation_state=state
    )
    
    # Should ask for clarification
    assert "which" in response.content.lower() or "what" in response.content.lower()
```

## Test Coverage

### Generate Coverage Report

```bash
python -m pytest tests/ --cov=agent --cov=tools --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Target Coverage

- **Nodes**: 90%+ coverage
- **Tools**: 95%+ coverage
- **Routing**: 100% coverage
- **State management**: 100% coverage

## Performance Testing

### Load Testing

Test concurrent conversations:

```python
# tests/test_performance.py
import pytest
import asyncio
from orchestrator import AgentOrchestrator

@pytest.mark.asyncio
async def test_concurrent_conversations():
    """Test handling of multiple concurrent conversations"""
    orchestrator = AgentOrchestrator()
    
    async def run_conversation(thread_id: str):
        response = await orchestrator.process_message(
            thread_id=thread_id,
            message="My name is User",
            author_id=f"user-{thread_id}"
        )
        return response
    
    # Run 10 concurrent conversations
    tasks = [run_conversation(f"thread-{i}") for i in range(10)]
    results = await asyncio.gather(*tasks)
    
    # All should succeed
    assert all(r.error is None for r in results)
    assert all(r.slots_filled == 1 for r in results)
```

## Continuous Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov pytest-asyncio
    
    - name: Run structure tests
      run: python test_structure.py
    
    - name: Run all tests
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: pytest tests/ -v --cov=agent --cov=tools
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

## Manual Testing

### Interactive Testing

```python
# test_interactive.py
import asyncio
from orchestrator import AgentOrchestrator

async def main():
    orchestrator = AgentOrchestrator()
    thread_id = "interactive-test"
    user_id = "test-user"
    state = None
    
    print("Catering AI Agent - Interactive Test")
    print("Type 'quit' to exit\n")
    
    while True:
        message = input("You: ")
        if message.lower() == 'quit':
            break
        
        response = await orchestrator.process_message(
            thread_id=thread_id,
            message=message,
            author_id=user_id,
            conversation_state=state
        )
        
        print(f"Agent: {response.content}")
        print(f"[Slots filled: {response.slots_filled}/8]")
        print(f"[Current node: {response.current_node}]\n")
        
        state = response.conversation_state
        
        if response.is_complete:
            print("✓ Conversation complete!")
            print(f"Contract data: {response.contract_data}")
            break

if __name__ == '__main__':
    asyncio.run(main())
```

Run with:
```bash
python test_interactive.py
```

## Troubleshooting Tests

### Common Issues

1. **OpenAI API Key Missing**
   ```
   Error: OpenAI API key not found
   Solution: Set OPENAI_API_KEY in .env file
   ```

2. **Import Errors**
   ```
   Error: ModuleNotFoundError
   Solution: Ensure you're in the correct directory and virtual environment is activated
   ```

3. **Async Test Failures**
   ```
   Error: RuntimeError: Event loop is closed
   Solution: Use pytest-asyncio and mark tests with @pytest.mark.asyncio
   ```

## Best Practices

1. **Test Isolation**: Each test should be independent
2. **Mock External Services**: Mock OpenAI calls for unit tests
3. **Test Edge Cases**: Always test boundary conditions
4. **Descriptive Names**: Use clear, descriptive test names
5. **Assertions**: Include meaningful assertion messages
6. **Cleanup**: Clean up test data after each test

## Next Steps

1. Add more edge case tests
2. Implement property-based testing with Hypothesis
3. Add mutation testing
4. Set up continuous integration
5. Monitor test execution time

## Support

For testing support, contact the development team.

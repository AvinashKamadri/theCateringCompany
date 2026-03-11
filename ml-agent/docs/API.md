# Agent API Documentation

## Overview

The Catering AI Agent provides a conversational interface for collecting event details and generating contracts. This document describes the API for backend integration.

## Main Interface: AgentOrchestrator

### Initialization

```python
from orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()
```

### Process Message

```python
async def process_message(
    thread_id: str,
    message: str,
    author_id: str,
    conversation_state: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
    project_id: Optional[str] = None
) -> AgentResponse
```

**Parameters:**
- `thread_id` (str, required): Unique identifier for the conversation thread
- `message` (str, required): User's message content
- `author_id` (str, required): ID of the user sending the message
- `conversation_state` (dict, optional): Existing conversation state for resuming
- `conversation_id` (str, optional): Conversation ID (auto-generated if not provided)
- `project_id` (str, optional): Project ID (auto-generated if not provided)

**Returns:** `AgentResponse` object

**Example:**

```python
response = await orchestrator.process_message(
    thread_id="thread-123",
    message="My name is Sarah Johnson",
    author_id="user-456"
)

print(response.content)  # "Great to meet you, Sarah! Could you share your phone number?"
print(response.current_node)  # "collect_phone"
print(response.slots_filled)  # 1
print(response.is_complete)  # False
```

## Response Schema

### AgentResponse

```python
class AgentResponse(BaseModel):
    content: str                    # Agent's response message
    current_node: str               # Current conversation node
    slots_filled: int               # Number of slots filled
    total_slots: int                # Total slots (always 8)
    is_complete: bool               # Whether conversation is complete
    conversation_id: str            # Conversation identifier
    project_id: str                 # Project identifier
    thread_id: str                  # Thread identifier
    conversation_state: Dict        # Full state for persistence
    contract_data: Optional[Dict]   # Contract data (when complete)
    error: Optional[str]            # Error message (if any)
```

## Conversation Flow

### Slot Collection Sequence

1. **start** → Welcome message
2. **collect_name** → Client name
3. **collect_phone** → Phone number
4. **collect_event_date** → Event date
5. **select_service_type** → Drop-off or on-site
6. **select_event_type** → Wedding/Corporate/Birthday/Social/Custom
7. **collect_venue** → Venue details
8. **collect_guest_count** → Number of guests
9. **collect_special_requests** → Dietary restrictions, allergies, special requests
10. **generate_contract** → Generate contract and complete

### Modification Flow

At any point, users can use `@AI` to modify previously filled slots:

```
User: "@AI change guest count to 200"
Agent: "I've updated the guest count to 200. Is there anything else you'd like to change?"
```

## State Management

### Conversation State Structure

```python
{
    "messages": [HumanMessage(...), AIMessage(...)],
    "conversation_id": "conv-123",
    "project_id": "proj-456",
    "thread_id": "thread-789",
    "current_node": "collect_phone",
    "slots": {
        "name": {
            "value": "Sarah Johnson",
            "filled": True,
            "modified_at": "2026-03-08T10:30:00",
            "modification_history": []
        },
        "phone": {
            "value": None,
            "filled": False,
            "modified_at": None,
            "modification_history": []
        },
        # ... other slots
    },
    "next_action": None,
    "error": None
}
```

### Slot Types

| Slot Name | Type | Validation |
|-----------|------|------------|
| name | string | Non-empty |
| phone | string | E.164 or local format |
| event_date | string | ISO date, future date |
| service_type | enum | "drop-off" or "on-site" |
| event_type | enum | "Wedding", "Corporate", "Birthday", "Social", "Custom" |
| venue | object | {address, kitchen_access, load_in_time} |
| guest_count | number | 10-10,000 |
| special_requests | object | {dietary_restrictions, allergies, special_requests} |

## Contract Data

When `is_complete=True`, the response includes `contract_data`:

```python
{
    "slots": {...},  # All slot values
    "pricing": {
        "package_name": "Standard Package",
        "base_price": 2000.0,
        "per_person_price": 45.0,
        "estimated_total": 8750.0
    },
    "upsells": {
        "upsells": [
            {
                "category": "Bar Service",
                "name": "Premium Open Bar",
                "price": 6750.0,
                "reasoning": "...",
                "priority": "high"
            }
        ],
        "total_potential_revenue": 12500.0
    },
    "margin": {
        "total_revenue": 8750.0,
        "total_cost": 5687.5,
        "gross_margin": 3062.5,
        "margin_percentage": 35.0,
        "warnings": [],
        "recommendations": []
    },
    "staffing": {
        "servers_needed": 8,
        "bartenders_needed": 2,
        "total_labor_hours": 60.0,
        "estimated_labor_cost": 1560.0,
        "reasoning": "..."
    },
    "missing_info": {
        "is_complete": True,
        "missing_required": [],
        "missing_recommended": [],
        "risk_flags": []
    },
    "generated_at": "2026-03-08T11:00:00"
}
```

## Tools

### Core Tools

#### extract_slot_value
Extracts slot values from user messages using OpenAI function calling.

#### validate_slot
Validates and normalizes slot values according to business rules.

#### detect_slot_modification
Detects @AI mentions and identifies which slot to modify.

### Business Logic Tools

#### query_pricing
Queries pricing data based on event details (mock - backend implements).

#### suggest_upsells
Generates AI-powered upsell recommendations.

#### calculate_margin
Calculates profit margins with warnings and recommendations.

#### calculate_staffing
Recommends staffing levels based on event size and type.

#### flag_missing_info
Identifies missing information and risk factors.

## Error Handling

Errors are returned in the `error` field of `AgentResponse`:

```python
if response.error:
    print(f"Error occurred: {response.error}")
    # Handle error appropriately
```

Common error scenarios:
- LLM API failures (OpenAI rate limits, timeouts)
- Invalid slot values
- State corruption
- Tool invocation failures

## Backend Integration Checklist

### Required Backend Implementation

1. **Database Persistence**
   - Save conversation state after each message
   - Load conversation state when resuming
   - Store contract data when complete

2. **WebSocket Gateway**
   - Real-time message delivery
   - Typing indicators
   - Agent response streaming

3. **API Endpoints**
   - POST /conversations - Create new conversation
   - POST /conversations/:id/messages - Send message
   - GET /conversations/:id - Get conversation state
   - GET /conversations/:id/contract - Get contract data

4. **Pricing Data**
   - Implement `query_pricing()` with real pricing logic
   - Connect to pricing database

5. **Contract Generation**
   - Generate PDF contracts from contract data
   - E-signature integration
   - Email delivery

### Example Backend Integration (NestJS)

```typescript
@Injectable()
export class AgentService {
  async processMessage(
    threadId: string,
    message: string,
    userId: string
  ): Promise<AgentResponse> {
    // Load existing state
    const state = await this.conversationRepo.findByThreadId(threadId);
    
    // Call Python agent
    const response = await this.pythonAgent.processMessage({
      thread_id: threadId,
      message: message,
      author_id: userId,
      conversation_state: state?.data
    });
    
    // Save updated state
    await this.conversationRepo.save({
      threadId,
      data: response.conversation_state,
      isComplete: response.is_complete
    });
    
    // If complete, generate contract
    if (response.is_complete) {
      await this.contractService.generate(response.contract_data);
    }
    
    return response;
  }
}
```

## Testing

See [TESTING.md](TESTING.md) for comprehensive testing guide.

## Support

For questions or issues, contact the development team.

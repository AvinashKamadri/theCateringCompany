# Chat API Integration Guide

**For Frontend & Backend Engineers**

This guide explains how to integrate with The Catering Company AI Chat API for conversational event intake.

---

## Table of Contents

1. [Overview](#overview)
2. [API Endpoint](#api-endpoint)
3. [Request Format](#request-format)
4. [Response Format](#response-format)
5. [Database Schema](#database-schema)
6. [Implementation Examples](#implementation-examples)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)
9. [Testing](#testing)

---

## Overview

The Chat API provides a conversational interface for gathering catering event requirements from clients. The AI agent:

- Collects 16 structured data points (slots) about the event
- Maintains conversation context across multiple messages
- Persists all data to PostgreSQL
- Tracks conversation state and progress
- Returns structured contract data when complete

**Key Features:**
- Thread-based conversations (resume previous conversations)
- Project-level organization
- Full conversation history in database
- Automatic slot extraction and validation
- Support for menu modifications and add-ons

---

## API Endpoint

### Base URL
```
http://localhost:8000
```

### POST /chat

Main endpoint for sending user messages and receiving AI responses.

**URL:** `POST /chat`

**Content-Type:** `application/json`

---

## Request Format

### ChatRequest Schema

```json
{
  "thread_id": "string | null",
  "message": "string (required)",
  "author_id": "string (UUID) | null",
  "project_id": "string (UUID) | null"
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | **Yes** | The user's message to the AI agent |
| `thread_id` | string (UUID) | No | Conversation thread ID. Omit for new conversations, provide to continue existing ones |
| `author_id` | string (UUID) | No | User ID. If not provided, defaults to AI system user |
| `project_id` | string (UUID) | No | Project ID for organizing conversations. Auto-generated if not provided |

### Example Requests

**New Conversation:**
```json
{
  "message": "I need catering for my wedding"
}
```

**Continue Existing Conversation:**
```json
{
  "thread_id": "91ff1a49-74da-415b-9027-afcbd68dbaf6",
  "message": "The wedding is on June 15th, 2024"
}
```

**With User Context:**
```json
{
  "thread_id": "91ff1a49-74da-415b-9027-afcbd68dbaf6",
  "message": "My name is Sarah Johnson",
  "author_id": "a3c5e7b9-1234-5678-9abc-def012345678",
  "project_id": "b4d6f8ca-2345-6789-abcd-ef0123456789"
}
```

---

## Response Format

### ChatResponse Schema

```json
{
  "thread_id": "string (UUID)",
  "message": "string",
  "current_node": "string",
  "slots_filled": "integer",
  "total_slots": "integer",
  "is_complete": "boolean",
  "contract_data": "object | null"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `thread_id` | string (UUID) | The conversation thread ID (use this in subsequent requests) |
| `message` | string | AI agent's response to the user |
| `current_node` | string | Current conversation node (e.g., "collect_name", "collect_date", "final") |
| `slots_filled` | integer | Number of data points collected (0-16) |
| `total_slots` | integer | Total slots to collect (always 16) |
| `is_complete` | boolean | True when all information is collected |
| `contract_data` | object \| null | Structured contract data (only when `is_complete: true`) |

### Example Response

```json
{
  "thread_id": "91ff1a49-74da-415b-9027-afcbd68dbaf6",
  "message": "Hello! I'm thrilled to help you plan your event. May I have your first and last name, please?",
  "current_node": "collect_name",
  "slots_filled": 0,
  "total_slots": 16,
  "is_complete": false,
  "contract_data": null
}
```

### Complete Conversation Response

When `is_complete: true`, the response includes structured contract data:

```json
{
  "thread_id": "91ff1a49-74da-415b-9027-afcbd68dbaf6",
  "message": "Perfect! I've gathered all the details for your wedding. Here's a summary...",
  "current_node": "final",
  "slots_filled": 16,
  "total_slots": 16,
  "is_complete": true,
  "contract_data": {
    "client_name": "Sarah Johnson",
    "contact_email": "sarah@example.com",
    "contact_phone": "+1-555-0123",
    "event_type": "wedding",
    "event_date": "2024-06-15",
    "guest_count": 150,
    "service_type": "full_service",
    "menu_items": ["Grilled Salmon", "Roasted Chicken", "Vegetable Medley"],
    "dietary_restrictions": ["vegetarian", "gluten-free"],
    "budget_range": "$8000-$10000",
    "venue_name": "The Grand Ballroom",
    "venue_address": "123 Main St, City, State 12345",
    "setup_time": "14:00",
    "service_time": "18:00",
    "addons": ["bartender_service", "cake_cutting"],
    "modifications": []
  }
}
```

---

## Database Schema

### Tables Used by Chat API

The chat API persists data across 4 main tables:

#### 1. **projects**
Organizes conversations and events at the project level.

```sql
CREATE TABLE projects (
  id               UUID        PRIMARY KEY,
  owner_user_id    UUID        NOT NULL REFERENCES users(id),
  title            TEXT        NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### 2. **threads**
Individual conversation threads within a project.

```sql
CREATE TABLE threads (
  id               UUID        PRIMARY KEY,
  project_id       UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  subject          TEXT        NULL,
  created_by       UUID        NULL REFERENCES users(id),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### 3. **ai_conversation_states**
Tracks the AI conversation progress and extracted slot data.

```sql
CREATE TABLE ai_conversation_states (
  id                UUID        PRIMARY KEY,
  thread_id         UUID        UNIQUE NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  project_id        UUID        NULL REFERENCES projects(id),
  current_node      TEXT        NOT NULL DEFAULT 'start',
  slots             JSONB       NOT NULL DEFAULT '{}',
  is_completed      BOOLEAN     NOT NULL DEFAULT false,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

**Slots Structure (JSONB):**
```json
{
  "client_name": {
    "value": "Sarah Johnson",
    "filled": true,
    "modified_at": "2024-01-15T10:30:00Z",
    "modification_history": []
  },
  "event_date": {
    "value": "2024-06-15",
    "filled": true,
    "modified_at": "2024-01-15T10:31:00Z",
    "modification_history": []
  }
  // ... 14 more slots
}
```

#### 4. **messages**
Stores all conversation messages (user and AI).

```sql
CREATE TABLE messages (
  id                       UUID        PRIMARY KEY,
  thread_id                UUID        NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
  project_id               UUID        NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  author_id                UUID        NULL REFERENCES users(id),
  sender_type              TEXT        NULL CHECK (sender_type IN ('user','ai','system')),
  content                  TEXT        NOT NULL,
  ai_conversation_state_id UUID        NULL REFERENCES ai_conversation_states(id),
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## Implementation Examples

### Frontend Integration (React/TypeScript)

```typescript
// types.ts
export interface ChatRequest {
  thread_id?: string;
  message: string;
  author_id?: string;
  project_id?: string;
}

export interface ChatResponse {
  thread_id: string;
  message: string;
  current_node: string;
  slots_filled: number;
  total_slots: number;
  is_complete: boolean;
  contract_data?: any;
}

// chatApi.ts
export class ChatAPI {
  private baseURL = 'http://localhost:8000';

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${this.baseURL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`Chat API error: ${response.status}`);
    }

    return await response.json();
  }
}

// ChatComponent.tsx
import React, { useState } from 'react';
import { ChatAPI, ChatResponse } from './chatApi';

export const ChatComponent: React.FC = () => {
  const [threadId, setThreadId] = useState<string | undefined>();
  const [messages, setMessages] = useState<Array<{role: 'user' | 'ai', content: string}>>([]);
  const [input, setInput] = useState('');
  const [progress, setProgress] = useState({ filled: 0, total: 16 });
  const chatAPI = new ChatAPI();

  const handleSend = async () => {
    if (!input.trim()) return;

    // Add user message to UI
    setMessages(prev => [...prev, { role: 'user', content: input }]);

    try {
      // Send to API
      const response = await chatAPI.sendMessage({
        thread_id: threadId,
        message: input,
      });

      // Update thread ID (for first message)
      if (!threadId) {
        setThreadId(response.thread_id);
      }

      // Add AI response to UI
      setMessages(prev => [...prev, { role: 'ai', content: response.message }]);

      // Update progress
      setProgress({
        filled: response.slots_filled,
        total: response.total_slots,
      });

      // Handle completion
      if (response.is_complete && response.contract_data) {
        console.log('Contract ready:', response.contract_data);
        // Navigate to contract review or submit to backend
      }

      setInput('');
    } catch (error) {
      console.error('Chat error:', error);
      // Show error to user
    }
  };

  return (
    <div className="chat-container">
      <div className="progress-bar">
        Progress: {progress.filled} / {progress.total}
      </div>

      <div className="messages">
        {messages.map((msg, idx) => (
          <div key={idx} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>

      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type your message..."
        />
        <button onClick={handleSend}>Send</button>
      </div>
    </div>
  );
};
```

### Backend Integration (Node.js/Express)

```javascript
// chatService.js
const axios = require('axios');

class ChatService {
  constructor() {
    this.baseURL = 'http://localhost:8000';
  }

  async sendMessage(threadId, message, userId, projectId) {
    try {
      const response = await axios.post(`${this.baseURL}/chat`, {
        thread_id: threadId,
        message: message,
        author_id: userId,
        project_id: projectId,
      });

      return response.data;
    } catch (error) {
      console.error('Chat API error:', error.response?.data || error.message);
      throw error;
    }
  }

  async saveContract(contractData) {
    // When is_complete: true, save contract_data to your contracts table
    // This is YOUR backend's responsibility
    const contractId = await db.contracts.create({
      client_name: contractData.client_name,
      event_type: contractData.event_type,
      event_date: contractData.event_date,
      guest_count: contractData.guest_count,
      // ... map all fields
    });

    return contractId;
  }
}

// routes/chat.js
const express = require('express');
const router = express.Router();
const ChatService = require('../services/chatService');

router.post('/api/chat', async (req, res) => {
  const { thread_id, message, user_id, project_id } = req.body;
  const chatService = new ChatService();

  try {
    const chatResponse = await chatService.sendMessage(
      thread_id,
      message,
      user_id,
      project_id
    );

    // If conversation is complete, save contract to main database
    if (chatResponse.is_complete && chatResponse.contract_data) {
      const contractId = await chatService.saveContract(chatResponse.contract_data);
      chatResponse.contract_id = contractId;
    }

    res.json(chatResponse);
  } catch (error) {
    res.status(500).json({ error: 'Chat service unavailable' });
  }
});

module.exports = router;
```

### Python/FastAPI Integration

```python
# chat_client.py
import httpx
from typing import Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    thread_id: Optional[str] = None
    message: str
    author_id: Optional[str] = None
    project_id: Optional[str] = None

class ChatResponse(BaseModel):
    thread_id: str
    message: str
    current_node: str
    slots_filled: int
    total_slots: int
    is_complete: bool
    contract_data: Optional[dict] = None

class ChatClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def send_message(self, request: ChatRequest) -> ChatResponse:
        response = await self.client.post(
            f"{self.base_url}/chat",
            json=request.dict(exclude_none=True)
        )
        response.raise_for_status()
        return ChatResponse(**response.json())

# Usage in your FastAPI backend
from fastapi import APIRouter, HTTPException
router = APIRouter()

@router.post("/proxy/chat")
async def proxy_chat(request: ChatRequest):
    chat_client = ChatClient()

    try:
        response = await chat_client.send_message(request)

        # Handle completion
        if response.is_complete and response.contract_data:
            # Save to your contracts table
            contract_id = await save_contract(response.contract_data)
            return {**response.dict(), "contract_id": contract_id}

        return response
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail="Chat API error")
```

---

## Error Handling

### HTTP Status Codes

| Status | Description | Action |
|--------|-------------|--------|
| 200 | Success | Process response normally |
| 422 | Validation Error | Check request format, missing required fields |
| 500 | Internal Server Error | Retry with exponential backoff, log error |

### Example Error Response

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "message"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### Error Handling Best Practices

```typescript
async function sendMessageWithRetry(
  request: ChatRequest,
  maxRetries = 3
): Promise<ChatResponse> {
  let lastError: Error;

  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await chatAPI.sendMessage(request);
    } catch (error) {
      lastError = error;

      // Don't retry validation errors (4xx)
      if (error.status >= 400 && error.status < 500) {
        throw error;
      }

      // Exponential backoff for server errors (5xx)
      const delay = Math.pow(2, attempt) * 1000;
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }

  throw lastError;
}
```

---

## Best Practices

### 1. **Thread Management**

- **Store `thread_id` in session/local storage** to resume conversations
- **Clear thread_id** when starting a new conversation
- **Display progress** using `slots_filled / total_slots`

### 2. **User Experience**

- **Show typing indicator** while waiting for AI response
- **Disable send button** during API calls
- **Scroll to latest message** automatically
- **Handle network errors gracefully** with retry mechanism

### 3. **Performance**

- **Debounce typing indicators** (don't send on every keystroke)
- **Implement request cancellation** if user navigates away
- **Cache thread_id and project_id** to avoid unnecessary lookups

### 4. **Security**

- **Validate user_id on backend** before forwarding to Chat API
- **Sanitize user input** to prevent injection attacks
- **Use HTTPS in production**
- **Implement rate limiting** to prevent abuse

### 5. **Data Handling**

When `is_complete: true`:
1. **Validate contract_data** structure
2. **Save to your contracts table** (backend responsibility)
3. **Link to user/project** in your database
4. **Send confirmation email** to client
5. **Trigger pricing calculations** if needed

---

## Testing

### Health Check

```bash
curl http://localhost:8000/health
# Response: {"status": "ok"}
```

### Test New Conversation

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need catering for a wedding"
  }'
```

### Test Resume Conversation

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "91ff1a49-74da-415b-9027-afcbd68dbaf6",
    "message": "The date is June 15th"
  }'
```

### Example Test Suite (Jest)

```typescript
describe('Chat API Integration', () => {
  let chatAPI: ChatAPI;
  let threadId: string;

  beforeEach(() => {
    chatAPI = new ChatAPI();
  });

  test('should start new conversation', async () => {
    const response = await chatAPI.sendMessage({
      message: 'I need catering for an event',
    });

    expect(response.thread_id).toBeDefined();
    expect(response.message).toContain('help');
    expect(response.slots_filled).toBe(0);
    expect(response.is_complete).toBe(false);

    threadId = response.thread_id;
  });

  test('should continue existing conversation', async () => {
    const response = await chatAPI.sendMessage({
      thread_id: threadId,
      message: 'My name is John Doe',
    });

    expect(response.thread_id).toBe(threadId);
    expect(response.slots_filled).toBeGreaterThan(0);
  });

  test('should handle errors gracefully', async () => {
    await expect(
      chatAPI.sendMessage({ message: '' })
    ).rejects.toThrow();
  });
});
```

---

## Database Queries for Backend Integration

### Get Conversation History

```sql
SELECT
  m.id,
  m.sender_type,
  m.content,
  m.created_at
FROM messages m
WHERE m.thread_id = $1
ORDER BY m.created_at ASC;
```

### Get Conversation State

```sql
SELECT
  acs.current_node,
  acs.slots,
  acs.is_completed,
  acs.updated_at
FROM ai_conversation_states acs
WHERE acs.thread_id = $1;
```

### Get All Conversations for Project

```sql
SELECT
  t.id as thread_id,
  t.subject,
  acs.is_completed,
  acs.slots_filled,
  COUNT(m.id) as message_count,
  MAX(m.created_at) as last_message_at
FROM threads t
LEFT JOIN ai_conversation_states acs ON acs.thread_id = t.id
LEFT JOIN messages m ON m.thread_id = t.id
WHERE t.project_id = $1
GROUP BY t.id, t.subject, acs.is_completed, acs.slots_filled
ORDER BY last_message_at DESC;
```

---

## Support

### Common Issues

**Q: API returns 500 error**
- Check if the ML API server is running (`http://localhost:8000/health`)
- Verify PostgreSQL database is accessible
- Check API server logs in `api_server.log`

**Q: Conversation state not persisting**
- Ensure you're passing the same `thread_id` in subsequent requests
- Check database connectivity

**Q: Missing contract data when `is_complete: true`**
- Contract data is only returned when all 16 slots are filled
- Check `slots_filled` count in response

### Contact

For technical support or questions:
- Check documentation: `ML_DATABASE_INTEGRATION_GUIDE.md`
- Review troubleshooting: `TROUBLESHOOTING_POSTGRESQL_MIGRATION.md`
- API implementation: `BACKEND_INTEGRATION_GUIDE.md`

---

## Appendix: 16 Required Slots

The AI agent collects these data points during conversation:

1. `client_name` - Client's full name
2. `contact_email` - Email address
3. `contact_phone` - Phone number
4. `event_type` - Type of event (wedding, corporate, etc.)
5. `event_date` - Event date (YYYY-MM-DD)
6. `guest_count` - Number of guests
7. `service_type` - Service type (buffet, plated, etc.)
8. `menu_items` - Selected menu items (array)
9. `dietary_restrictions` - Dietary requirements (array)
10. `budget_range` - Budget range
11. `venue_name` - Venue name
12. `venue_address` - Venue address
13. `setup_time` - Setup time (HH:MM)
14. `service_time` - Service start time (HH:MM)
15. `addons` - Additional services (array)
16. `modifications` - Menu modifications (array)

---

**Last Updated:** 2026-03-10
**API Version:** 1.0
**Author:** The Catering Company AI Team

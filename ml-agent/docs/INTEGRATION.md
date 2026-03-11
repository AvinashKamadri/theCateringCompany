# Backend Integration Guide

## Overview

This guide explains how to integrate the Catering AI Agent with your NestJS backend.

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│                 │         │                  │         │                 │
│  React Frontend │◄────────┤  NestJS Backend  │◄────────┤  Python Agent   │
│   (WebSocket)   │         │   (WebSocket +   │         │   (LangGraph)   │
│                 │         │    HTTP API)     │         │                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │                  │
                            │   PostgreSQL     │
                            │   (State + Data) │
                            │                  │
                            └──────────────────┘
```

## Integration Steps

### 1. Python Agent Setup

#### Install Dependencies

```bash
cd python-agent/
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

#### Configure Environment

```bash
cp .env.example .env
# Add OPENAI_API_KEY to .env
```

#### Test Agent

```bash
python test_structure.py
```

### 2. NestJS Backend Integration

#### Install Python Bridge

```bash
npm install python-shell
```

#### Create Agent Service

```typescript
// src/agent/agent.service.ts
import { Injectable } from '@nestjs/common';
import { PythonShell } from 'python-shell';

@Injectable()
export class AgentService {
  private pythonPath: string;
  
  constructor() {
    this.pythonPath = process.env.PYTHON_AGENT_PATH || '../python-agent';
  }
  
  async processMessage(
    threadId: string,
    message: string,
    userId: string,
    conversationState?: any
  ): Promise<AgentResponse> {
    const options = {
      mode: 'json' as const,
      pythonPath: 'python',
      pythonOptions: ['-u'],
      scriptPath: this.pythonPath,
      args: [
        '--thread-id', threadId,
        '--message', message,
        '--user-id', userId,
        '--state', JSON.stringify(conversationState || {})
      ]
    };
    
    const results = await PythonShell.run('run_agent.py', options);
    return results[0] as AgentResponse;
  }
}
```

#### Create Python Runner Script

```python
# python-agent/run_agent.py
import asyncio
import sys
import json
import argparse
from orchestrator import AgentOrchestrator

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--thread-id', required=True)
    parser.add_argument('--message', required=True)
    parser.add_argument('--user-id', required=True)
    parser.add_argument('--state', default='{}')
    args = parser.parse_args()
    
    orchestrator = AgentOrchestrator()
    
    state = json.loads(args.state) if args.state != '{}' else None
    
    response = await orchestrator.process_message(
        thread_id=args.thread_id,
        message=args.message,
        author_id=args.user_id,
        conversation_state=state
    )
    
    # Output JSON for NestJS to parse
    print(response.model_dump_json())

if __name__ == '__main__':
    asyncio.run(main())
```

### 3. Database Schema

#### Conversation States Table

```sql
CREATE TABLE conversation_states (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id VARCHAR(255) UNIQUE NOT NULL,
  project_id UUID NOT NULL,
  thread_id UUID NOT NULL,
  current_node VARCHAR(100) NOT NULL,
  slots JSONB NOT NULL,
  messages JSONB NOT NULL,
  metadata JSONB,
  is_completed BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  
  FOREIGN KEY (project_id) REFERENCES projects(id),
  FOREIGN KEY (thread_id) REFERENCES threads(id)
);

CREATE INDEX idx_conversation_thread ON conversation_states(thread_id);
CREATE INDEX idx_conversation_project ON conversation_states(project_id);
```

#### AI Tags Table (for @AI modifications)

```sql
CREATE TABLE ai_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID NOT NULL,
  message_id UUID NOT NULL,
  field VARCHAR(100) NOT NULL,
  old_value TEXT,
  new_value TEXT,
  field_content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  
  FOREIGN KEY (thread_id) REFERENCES threads(id),
  FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE INDEX idx_ai_tags_thread ON ai_tags(thread_id);
CREATE INDEX idx_ai_tags_message ON ai_tags(message_id);
```

#### Contracts Table

```sql
CREATE TABLE contracts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id VARCHAR(255) NOT NULL,
  project_id UUID NOT NULL,
  
  -- Client info
  client_name VARCHAR(255) NOT NULL,
  client_phone VARCHAR(50) NOT NULL,
  
  -- Event details
  event_type VARCHAR(50) NOT NULL,
  event_date DATE NOT NULL,
  service_type VARCHAR(50) NOT NULL,
  guest_count INTEGER NOT NULL,
  venue JSONB NOT NULL,
  special_requests JSONB,
  
  -- Financial data
  pricing_data JSONB NOT NULL,
  upsells_data JSONB,
  margin_data JSONB,
  staffing_data JSONB,
  
  -- Contract status
  status VARCHAR(50) DEFAULT 'draft',  -- draft, sent, signed, cancelled
  pdf_url TEXT,
  signed_at TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  
  FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX idx_contracts_project ON contracts(project_id);
CREATE INDEX idx_contracts_conversation ON contracts(conversation_id);
CREATE INDEX idx_contracts_status ON contracts(status);
```

### 4. WebSocket Gateway

```typescript
// src/chat/chat.gateway.ts
import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
  ConnectedSocket,
} from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { AgentService } from '../agent/agent.service';
import { ConversationService } from './conversation.service';

@WebSocketGateway({
  cors: { origin: '*' },
  namespace: '/chat',
})
export class ChatGateway {
  @WebSocketServer()
  server: Server;

  constructor(
    private agentService: AgentService,
    private conversationService: ConversationService,
  ) {}

  @SubscribeMessage('send_message')
  async handleMessage(
    @MessageBody() data: { threadId: string; message: string },
    @ConnectedSocket() client: Socket,
  ) {
    const userId = client.data.userId;
    
    // Load existing conversation state
    const state = await this.conversationService.getState(data.threadId);
    
    // Process message through agent
    const response = await this.agentService.processMessage(
      data.threadId,
      data.message,
      userId,
      state,
    );
    
    // Save updated state
    await this.conversationService.saveState(
      data.threadId,
      response.conversation_state,
    );
    
    // If conversation complete, generate contract
    if (response.is_complete) {
      await this.conversationService.generateContract(
        response.contract_data,
      );
      
      // Emit contract ready event
      this.server.to(data.threadId).emit('contract_ready', {
        contractId: response.contract_data.contract_id,
      });
    }
    
    // Send agent response to client
    this.server.to(data.threadId).emit('agent_message', {
      content: response.content,
      currentNode: response.current_node,
      slotsFilled: response.slots_filled,
      totalSlots: response.total_slots,
      isComplete: response.is_complete,
    });
  }

  @SubscribeMessage('join_thread')
  async handleJoinThread(
    @MessageBody() data: { threadId: string },
    @ConnectedSocket() client: Socket,
  ) {
    client.join(data.threadId);
    
    // Send conversation history
    const history = await this.conversationService.getHistory(data.threadId);
    client.emit('conversation_history', history);
  }
}
```

### 5. Conversation Service

```typescript
// src/chat/conversation.service.ts
import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { ConversationState } from './entities/conversation-state.entity';
import { Contract } from './entities/contract.entity';

@Injectable()
export class ConversationService {
  constructor(
    @InjectRepository(ConversationState)
    private conversationRepo: Repository<ConversationState>,
    @InjectRepository(Contract)
    private contractRepo: Repository<Contract>,
  ) {}

  async getState(threadId: string): Promise<any> {
    const conversation = await this.conversationRepo.findOne({
      where: { threadId },
    });
    
    return conversation?.data || null;
  }

  async saveState(threadId: string, state: any): Promise<void> {
    await this.conversationRepo.upsert(
      {
        threadId,
        conversationId: state.conversation_id,
        projectId: state.project_id,
        currentNode: state.current_node,
        slots: state.slots,
        messages: state.messages,
        isCompleted: state.current_node === 'done',
        data: state,
      },
      ['threadId'],
    );
  }

  async generateContract(contractData: any): Promise<Contract> {
    const contract = this.contractRepo.create({
      conversationId: contractData.slots.conversation_id,
      projectId: contractData.slots.project_id,
      clientName: contractData.slots.name,
      clientPhone: contractData.slots.phone,
      eventType: contractData.slots.event_type,
      eventDate: contractData.slots.event_date,
      serviceType: contractData.slots.service_type,
      guestCount: contractData.slots.guest_count,
      venue: contractData.slots.venue,
      specialRequests: contractData.slots.special_requests,
      pricingData: contractData.pricing,
      upsellsData: contractData.upsells,
      marginData: contractData.margin,
      staffingData: contractData.staffing,
      status: 'draft',
    });
    
    return await this.contractRepo.save(contract);
  }

  async getHistory(threadId: string): Promise<any[]> {
    const conversation = await this.conversationRepo.findOne({
      where: { threadId },
    });
    
    if (!conversation) return [];
    
    return conversation.messages || [];
  }
}
```

### 6. Environment Variables

```env
# .env
OPENAI_API_KEY=sk-...
PYTHON_AGENT_PATH=../python-agent
DATABASE_URL=postgresql://user:pass@localhost:5432/catering_db
REDIS_URL=redis://localhost:6379
```

### 7. Testing Integration

```typescript
// test/agent-integration.e2e-spec.ts
import { Test } from '@nestjs/testing';
import { AgentService } from '../src/agent/agent.service';

describe('Agent Integration', () => {
  let agentService: AgentService;

  beforeEach(async () => {
    const module = await Test.createTestingModule({
      providers: [AgentService],
    }).compile();

    agentService = module.get<AgentService>(AgentService);
  });

  it('should process a complete conversation', async () => {
    const threadId = 'test-thread-1';
    let state = null;

    // Message 1: Name
    let response = await agentService.processMessage(
      threadId,
      'My name is Sarah Johnson',
      'user-1',
      state,
    );
    expect(response.slots_filled).toBe(1);
    expect(response.current_node).toBe('collect_phone');
    state = response.conversation_state;

    // Message 2: Phone
    response = await agentService.processMessage(
      threadId,
      '555-123-4567',
      'user-1',
      state,
    );
    expect(response.slots_filled).toBe(2);
    expect(response.current_node).toBe('collect_event_date');
    state = response.conversation_state;

    // Continue through all slots...
    
    // Final message should complete conversation
    expect(response.is_complete).toBe(true);
    expect(response.contract_data).toBeDefined();
  });
});
```

## Deployment

### Docker Setup

```dockerfile
# Dockerfile.agent
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "run_agent.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/catering
      - REDIS_URL=redis://redis:6379
      - PYTHON_AGENT_URL=http://agent:8000
    depends_on:
      - db
      - redis
      - agent

  agent:
    build: ./python-agent
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    ports:
      - "8000:8000"

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=catering
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

## Monitoring

### Logging

```python
# python-agent/logging_config.py
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()
```

### Metrics

Track key metrics:
- Message processing time
- Slot fill rate
- Conversation completion rate
- Error rate
- LLM API costs

## Troubleshooting

### Common Issues

1. **Python agent not responding**
   - Check Python path configuration
   - Verify virtual environment is activated
   - Check OpenAI API key

2. **State not persisting**
   - Verify database connection
   - Check conversation_states table schema
   - Ensure proper serialization of JSONB fields

3. **WebSocket disconnections**
   - Check CORS configuration
   - Verify WebSocket namespace
   - Monitor connection timeouts

## Next Steps

1. Implement real pricing logic in `query_pricing()`
2. Add PDF contract generation
3. Integrate e-signature service
4. Set up monitoring and alerting
5. Load test with concurrent conversations

## Support

For integration support, contact the development team.

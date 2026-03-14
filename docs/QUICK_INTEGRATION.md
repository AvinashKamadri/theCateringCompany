# Quick Integration Checklist

Copy-paste ready code to integrate ML API with your backend and frontend.

---

## ⚡ Backend Integration (NestJS)

### 1. Install Dependencies
```bash
npm install axios
```

### 2. Add to `.env`
```env
ML_API_URL=http://localhost:8000
```

### 3. Create `src/ml/ml.service.ts`
```typescript
import { Injectable, HttpException, HttpStatus } from '@nestjs/common';
import axios, { AxiosInstance } from 'axios';

@Injectable()
export class MlService {
  private mlClient: AxiosInstance;

  constructor() {
    this.mlClient = axios.create({
      baseURL: process.env.ML_API_URL || 'http://localhost:8000',
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  async chat(data: { message: string; thread_id?: string; project_id?: string }) {
    try {
      const response = await this.mlClient.post('/chat', {
        message: data.message,
        thread_id: data.thread_id || null,
        author_id: 'user',
        project_id: data.project_id || null,
      });
      return response.data;
    } catch (error) {
      throw new HttpException(
        'ML service unavailable',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }
}
```

### 4. Create `src/ml/ml.module.ts`
```typescript
import { Module } from '@nestjs/common';
import { MlService } from './ml.service';

@Module({
  providers: [MlService],
  exports: [MlService],
})
export class MlModule {}
```

### 5. Update `src/app.module.ts`
```typescript
import { MlModule } from './ml/ml.module';

@Module({
  imports: [
    // ... other imports
    MlModule, // ← Add this
  ],
})
export class AppModule {}
```

### 6. Create/Update `src/messages/messages.controller.ts`
```typescript
import { Controller, Post, Body, UseGuards } from '@nestjs/common';
import { MlService } from '../ml/ml.service';

@Controller('api/messages')
export class MessagesController {
  constructor(private readonly mlService: MlService) {}

  @Post('ai-chat')
  async aiChat(@Body() dto: { message: string; threadId?: string; projectId?: string }) {
    const response = await this.mlService.chat({
      message: dto.message,
      thread_id: dto.threadId,
      project_id: dto.projectId,
    });

    return { success: true, data: response };
  }
}
```

---

## ⚡ Frontend Integration (Next.js)

### 1. Add to `.env.local`
```env
NEXT_PUBLIC_API_URL=http://localhost:3001
```

### 2. Create `lib/api/ml-client.ts`
```typescript
export const mlApiClient = {
  async chat(data: { message: string; threadId?: string; projectId?: string }) {
    const response = await fetch('http://localhost:3001/api/messages/ai-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        message: data.message,
        threadId: data.threadId,
        projectId: data.projectId,
      }),
    });

    if (!response.ok) throw new Error('Failed to send message');
    return response.json();
  },
};
```

### 3. Create `hooks/useChat.ts`
```typescript
import { useState, useCallback } from 'react';
import { mlApiClient } from '@/lib/api/ml-client';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const sendMessage = useCallback(async (text: string) => {
    // Add user message
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      // Call backend
      const { data } = await mlApiClient.chat({
        message: text,
        threadId: threadId || undefined,
      });

      setThreadId(data.thread_id);

      // Add AI message
      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.message,
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setIsLoading(false);
    }
  }, [threadId]);

  return { messages, sendMessage, isLoading };
}
```

### 4. Create `components/ChatInterface.tsx`
```tsx
'use client';

import { useState } from 'react';
import { useChat } from '@/hooks/useChat';

export function ChatInterface() {
  const [input, setInput] = useState('');
  const { messages, sendMessage, isLoading } = useChat();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    await sendMessage(input);
    setInput('');
  };

  return (
    <div className="flex flex-col h-screen max-w-2xl mx-auto p-4">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-2 mb-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`p-3 rounded-lg ${
              msg.role === 'user' ? 'bg-blue-100 ml-auto' : 'bg-gray-100'
            } max-w-sm`}
          >
            {msg.content}
          </div>
        ))}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={isLoading}
          className="flex-1 px-4 py-2 border rounded"
        />
        <button
          type="submit"
          disabled={isLoading}
          className="bg-blue-600 text-white px-6 py-2 rounded"
        >
          Send
        </button>
      </form>
    </div>
  );
}
```

### 5. Use in `app/chat/page.tsx`
```tsx
import { ChatInterface } from '@/components/ChatInterface';

export default function ChatPage() {
  return <ChatInterface />;
}
```

---

## 🚀 Start Everything

### Terminal 1: ML API
```bash
cd TheCateringCompanyAgent
.venv\Scripts\activate
python api.py
# → http://localhost:8000
```

### Terminal 2: Backend
```bash
cd cateringCo/backend
npm run start:dev
# → http://localhost:3001
```

### Terminal 3: Frontend
```bash
cd cateringCo/frontend
npm run dev
# → http://localhost:3000
```

---

## ✅ Test

1. Visit http://localhost:3000/chat
2. Type "hi"
3. See AI response!

---

## 🔍 Quick Debug

```bash
# Test ML API directly
curl http://localhost:8000/health

# Test backend → ML API
curl http://localhost:3001/api/messages/health

# Test full flow
curl -X POST http://localhost:3001/api/messages/ai-chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hi"}'
```

---

## 📊 Data Flow

```
Frontend (3000)
    ↓ fetch('/api/messages/ai-chat')
Backend (3001)
    ↓ axios.post('/chat')
ML API (8000)
    ↓ orchestrator.process_message()
LangGraph Agent
    ↓ saves to DB
PostgreSQL
```

---

**Done! Full integration in 6 files.** 🎉

See [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) for detailed explanation.

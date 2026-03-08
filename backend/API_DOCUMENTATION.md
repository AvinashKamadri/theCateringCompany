# CateringCo Platform - API Documentation

## Overview

This document describes all exposed API endpoints, WebSocket events, and default ports for the CateringCo platform.

## Default Ports

| Service | Port | Protocol |
|---------|------|----------|
| Backend API | 3001 | HTTP/HTTPS |
| Frontend | 3000 | HTTP/HTTPS |
| WebSocket | 3001 | WebSocket (socket.io) |
| PostgreSQL | 5432 | TCP |
| Redis | 6379 | TCP |

## Base URLs

- **Development Backend**: `http://localhost:3001`
- **Development Frontend**: `http://localhost:3000`
- **API Prefix**: `/api`

## Authentication

The API uses **HTTP-only JWT cookies** for authentication (not Bearer tokens).

- **Cookie Name**: `app_jwt`
- **Cookie Type**: HTTP-only, Secure (in production), SameSite=Strict
- **Token Expiration**: Configured via `JWT_SECRET` in environment

### Protected vs Public Endpoints

- **Public** (no auth required): Marked with 🌐
- **Protected** (auth required): All other endpoints require valid JWT cookie

---

## API Endpoints

### 1. Authentication (`/api/auth`)

#### 🌐 POST `/api/auth/signup`
Create a new user account and establish session.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+1234567890",
  "company_name": "Acme Corp"
}
```

**Response:** `200 OK`
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Side Effects:**
- Sets `app_jwt` HTTP-only cookie
- Creates `sessions` record
- Password hashed with argon2id

---

#### 🌐 POST `/api/auth/login`
Authenticate existing user and create session.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response:** `200 OK`
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  }
}
```

**Side Effects:**
- Sets `app_jwt` HTTP-only cookie
- Creates new `sessions` record

**Errors:**
- `401 Unauthorized`: Invalid credentials

---

#### POST `/api/auth/logout`
End current session and clear authentication.

**Response:** `200 OK`
```json
{
  "message": "Logged out successfully"
}
```

**Side Effects:**
- Deletes session from database
- Clears `app_jwt` cookie

---

#### GET `/api/auth/me`
Get current authenticated user profile.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+1234567890",
  "company_name": "Acme Corp",
  "role": "client",
  "created_at": "2026-03-07T10:00:00Z"
}
```

---

#### POST `/api/auth/refresh`
Rotate refresh token and extend session.

**Request Body:**
```json
{
  "refreshToken": "uuid"
}
```

**Response:** `200 OK`
```json
{
  "accessToken": "new-jwt-token",
  "refreshToken": "new-refresh-token-uuid"
}
```

---

### 2. Projects (`/api/projects`)

#### GET `/api/projects`
List all projects where user is owner or collaborator.

**Query Parameters:**
- `status` (optional): Filter by `project_status` enum (draft, active, completed, archived)

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "name": "Wedding Event - Smith",
    "description": "Full catering for 200 guests",
    "status": "active",
    "owner_id": "uuid",
    "signed_contract_id": "uuid",
    "created_at": "2026-03-01T10:00:00Z",
    "updated_at": "2026-03-07T10:00:00Z"
  }
]
```

---

#### GET `/api/projects/:id`
Get single project with contract metadata.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "name": "Wedding Event - Smith",
  "description": "Full catering for 200 guests",
  "status": "active",
  "owner_id": "uuid",
  "signed_contract_id": "uuid",
  "latest_active_contract": {
    "id": "uuid",
    "contract_group_id": "uuid",
    "version_number": 3,
    "status": "sent",
    "total_amount": 15000.00,
    "title": "Catering Agreement v3",
    "created_at": "2026-03-05T10:00:00Z"
  },
  "created_at": "2026-03-01T10:00:00Z",
  "updated_at": "2026-03-07T10:00:00Z"
}
```

---

#### POST `/api/projects`
Create a new project.

**Request Body:**
```json
{
  "name": "Wedding Event - Smith",
  "description": "Full catering for 200 guests",
  "status": "draft"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "name": "Wedding Event - Smith",
  "description": "Full catering for 200 guests",
  "status": "draft",
  "owner_id": "uuid",
  "created_at": "2026-03-07T10:00:00Z"
}
```

**Side Effects:**
- Adds creator to `project_collaborators` with role `owner`

---

### 3. Contracts (`/api/contracts`)

#### POST `/api/projects/:projectId/contracts`
Create a new contract version for a project.

**Request Body:**
```json
{
  "title": "Catering Agreement v3",
  "body": {
    "sections": [...],
    "terms": {...}
  },
  "status": "draft",
  "totalAmount": 15000.00,
  "contractGroupId": "uuid"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "contract_group_id": "uuid",
  "version_number": 3,
  "previous_version_id": "uuid",
  "title": "Catering Agreement v3",
  "body": {...},
  "status": "draft",
  "total_amount": 15000.00,
  "created_by": "uuid",
  "created_at": "2026-03-07T10:00:00Z"
}
```

**Notes:**
- If `contractGroupId` not provided, generates new UUID
- Auto-increments `version_number` within group
- Links to previous version via `previous_version_id`

---

#### POST `/api/contracts/:id/generate-pdf`
Queue PDF generation job for contract.

**Response:** `202 Accepted`
```json
{
  "message": "PDF generation queued"
}
```

**Side Effects:**
- Enqueues `pdf_generation` BullMQ job
- Worker will render contract JSON to PDF via Puppeteer
- Uploads PDF to R2 storage
- Updates `contracts.pdf_path` when complete

---

### 4. Messages & Threads (`/api/threads`, `/api/messages`)

#### GET `/api/projects/:projectId/threads`
List all threads (conversations) in a project.

**Query Parameters:**
- `limit` (optional, default: 50): Max threads to return
- `cursor` (optional): Pagination cursor (thread ID)

**Response:** `200 OK`
```json
{
  "threads": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "title": "Menu Discussion",
      "created_by": "uuid",
      "message_count": 12,
      "created_at": "2026-03-05T10:00:00Z",
      "updated_at": "2026-03-07T09:30:00Z"
    }
  ],
  "nextCursor": "uuid"
}
```

---

#### GET `/api/threads/:threadId`
Get single thread with paginated messages.

**Query Parameters:**
- `limit` (optional, default: 50): Max messages to return
- `cursor` (optional): Message ID for pagination

**Response:** `200 OK`
```json
{
  "thread": {
    "id": "uuid",
    "project_id": "uuid",
    "title": "Menu Discussion",
    "created_by": "uuid",
    "message_count": 12,
    "created_at": "2026-03-05T10:00:00Z"
  },
  "messages": [
    {
      "id": "uuid",
      "thread_id": "uuid",
      "user_id": "uuid",
      "body": "What about vegetarian options?",
      "attachments": [...],
      "created_at": "2026-03-07T09:30:00Z"
    }
  ],
  "nextCursor": "uuid"
}
```

---

#### POST `/api/projects/:projectId/threads`
Create a new thread in a project.

**Request Body:**
```json
{
  "title": "Menu Discussion",
  "initialMessage": "Let's discuss the menu options for the event"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "title": "Menu Discussion",
  "created_by": "uuid",
  "message_count": 1,
  "created_at": "2026-03-07T10:00:00Z"
}
```

---

#### POST `/api/threads/:threadId/messages`
Post a new message to a thread.

**Request Body:**
```json
{
  "body": "What about vegetarian options?",
  "attachmentIds": ["uuid", "uuid"]
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "thread_id": "uuid",
  "user_id": "uuid",
  "body": "What about vegetarian options?",
  "attachments": [...],
  "created_at": "2026-03-07T10:00:00Z"
}
```

**Side Effects:**
- Persists to `messages` table
- Publishes socket event `message.created` to:
  - Room: `thread:{threadId}`
  - Room: `project:{projectId}`
- Enqueues `vector_indexing` job if `VECTOR_ENABLED=true`
- Increments thread `message_count` via trigger

---

### 5. Attachments (`/api/attachments`)

#### POST `/api/attachments/sign`
Get signed upload URL for R2 storage.

**Request Body:**
```json
{
  "filename": "menu.pdf",
  "contentType": "application/pdf",
  "size": 1024000
}
```

**Response:** `200 OK`
```json
{
  "attachmentId": "uuid",
  "uploadUrl": "https://r2-bucket.cloudflare.com/...",
  "key": "attachments/uuid/menu.pdf"
}
```

**Side Effects:**
- Creates placeholder row in `attachments` table with `upload_status=pending`
- Returns pre-signed PUT URL valid for 15 minutes

---

#### POST `/api/attachments/complete`
Mark attachment upload as complete.

**Request Body:**
```json
{
  "attachmentId": "uuid"
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "filename": "menu.pdf",
  "upload_status": "uploaded",
  "virus_scan_status": "pending"
}
```

**Side Effects:**
- Sets `upload_status=uploaded`, `uploaded_at=now()`
- Enqueues `virus_scan` job

---

### 6. Payments (`/api/payments`)

#### POST `/api/payments/create-intent`
Create Stripe PaymentIntent or mock payment.

**Request Body:**
```json
{
  "projectId": "uuid",
  "contractId": "uuid",
  "amount": 15000.00,
  "currency": "usd",
  "description": "Deposit for catering services",
  "idempotencyKey": "uuid"
}
```

**Response:** `200 OK`

**If `STRIPE_ENABLED=false` (Mock):**
```json
{
  "paymentRequestId": "uuid",
  "paymentId": "uuid",
  "clientSecret": "mock_secret_<paymentRequestId>",
  "status": "pending"
}
```

**If `STRIPE_ENABLED=true` (Real):**
```json
{
  "paymentRequestId": "uuid",
  "clientSecret": "pi_xxx_secret_xxx",
  "stripe_payment_intent_id": "pi_xxx"
}
```

**Side Effects:**
- Always creates `payment_requests` row
- In mock mode: creates `payments` row with `status=pending`
- In real mode: calls Stripe API with idempotency header
- Idempotency enforced via `idempotencyKey`

---

### 7. Webhooks (`/api/webhooks`)

#### 🌐 POST `/api/webhooks/stripe`
Receive Stripe webhook events.

**Headers:**
- `stripe-signature`: Webhook signature (verified if `STRIPE_ENABLED=true`)

**Request Body:** Raw Stripe event JSON
```json
{
  "id": "evt_xxx",
  "type": "payment_intent.succeeded",
  "data": {...}
}
```

**Response:** `200 OK`
```json
{
  "received": true
}
```

**Side Effects:**
- Always persists to `webhook_events` table
- Enqueues `webhooks` BullMQ job for processing
- Worker updates domain tables and creates `events` rows

---

#### 🌐 POST `/api/webhooks/:provider`
Generic webhook receiver for other providers.

**Parameters:**
- `provider`: Provider name (e.g., "sendgrid", "twilio")

**Request Body:** Provider-specific JSON

**Response:** `200 OK`
```json
{
  "received": true
}
```

**Side Effects:**
- Persists to `webhook_events` with `provider`, `external_event_id`, `idempotency_hash`
- Enqueues worker job

---

### 8. Notifications (`/api/notifications`)

#### GET `/api/notifications`
List notifications for current user.

**Query Parameters:**
- `unreadOnly` (optional, boolean): Filter to unread notifications

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "event_id": "uuid",
    "type": "message_received",
    "is_read": false,
    "data": {
      "projectName": "Wedding Event - Smith",
      "threadTitle": "Menu Discussion"
    },
    "created_at": "2026-03-07T09:30:00Z"
  }
]
```

---

#### POST `/api/notifications/:id/ack`
Mark notification as read.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "is_read": true
}
```

**Side Effects:**
- Sets `is_read=true`, `read_at=now()`

---

## WebSocket (socket.io)

### Connection

**URL**: `ws://localhost:3001` (same port as HTTP server)

**Authentication**: JWT from HTTP-only cookie `app_jwt`

**Connection Flow:**
1. Client connects with cookie credentials
2. Gateway validates JWT from cookie
3. Gateway loads user's project memberships
4. Auto-joins rooms:
   - `user:{userId}` (personal notifications)
   - `project:{projectId}` (for each user project)

### Client → Server Events

#### `message.create`
Client sends new message.

**Payload:**
```json
{
  "threadId": "uuid",
  "body": "Message text",
  "attachmentIds": ["uuid"]
}
```

**Server Response:**
- Persists message to database
- Broadcasts `message.created` to thread and project rooms

---

#### `message.typing`
Client indicates user is typing.

**Payload:**
```json
{
  "threadId": "uuid",
  "isTyping": true
}
```

**Server Response:**
- Broadcasts `typing` event to thread room (except sender)

---

#### `thread.join`
Client joins thread room to receive messages.

**Payload:**
```json
{
  "threadId": "uuid"
}
```

**Server Response:**
- Adds socket to room `thread:{threadId}`

---

### Server → Client Events

#### `message.created`
New message posted to thread.

**Rooms**: `thread:{threadId}`, `project:{projectId}`

**Payload:**
```json
{
  "id": "uuid",
  "thread_id": "uuid",
  "project_id": "uuid",
  "user_id": "uuid",
  "body": "Message text",
  "attachments": [...],
  "created_at": "2026-03-07T10:00:00Z"
}
```

---

#### `thread.created`
New thread created in project.

**Room**: `project:{projectId}`

**Payload:**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "title": "New Discussion",
  "created_by": "uuid",
  "created_at": "2026-03-07T10:00:00Z"
}
```

---

#### `contract.updated`
Contract status or content changed.

**Room**: `project:{projectId}`

**Payload:**
```json
{
  "id": "uuid",
  "project_id": "uuid",
  "status": "signed",
  "pdf_path": "contracts/uuid.pdf"
}
```

---

#### `payment.updated`
Payment status changed.

**Room**: `project:{projectId}`, `user:{userId}`

**Payload:**
```json
{
  "id": "uuid",
  "payment_request_id": "uuid",
  "status": "completed",
  "amount": 15000.00,
  "paid_at": "2026-03-07T10:00:00Z"
}
```

---

#### `notification.created`
New notification for user.

**Room**: `user:{userId}`

**Payload:**
```json
{
  "id": "uuid",
  "type": "message_received",
  "data": {...},
  "created_at": "2026-03-07T10:00:00Z"
}
```

---

#### `typing`
Another user is typing in thread.

**Room**: `thread:{threadId}` (except sender)

**Payload:**
```json
{
  "userId": "uuid",
  "userName": "John Doe",
  "isTyping": true
}
```

---

## BullMQ Job Queues (Background Workers)

These queues run in the separate `workers/` service. Jobs are enqueued by the backend.

| Queue | Purpose | Trigger |
|-------|---------|---------|
| `webhooks` | Process webhook events | Webhook received |
| `payments` | Reconcile payment status | Stripe webhook |
| `pdf_generation` | Render contract PDFs | User requests PDF |
| `vector_indexing` | Create embeddings | Message created |
| `notifications` | Send emails/SMS | Event created |
| `virus_scan` | Scan attachments | Attachment uploaded |
| `pricing_recalc` | Update pricing | Contract changed |

**Worker Connection:**
- Workers connect to same Redis as backend
- Use separate Prisma connection with `connection_limit=5`
- Idempotency enforced via domain table status columns

---

## Error Responses

All endpoints return standard error format:

**4xx Client Errors:**
```json
{
  "statusCode": 400,
  "message": "Validation failed",
  "error": "Bad Request"
}
```

**401 Unauthorized:**
```json
{
  "statusCode": 401,
  "message": "Unauthorized"
}
```

**403 Forbidden:**
```json
{
  "statusCode": 403,
  "message": "Insufficient permissions"
}
```

**404 Not Found:**
```json
{
  "statusCode": 404,
  "message": "Resource not found"
}
```

**500 Server Errors:**
```json
{
  "statusCode": 500,
  "message": "Internal server error",
  "error": "Internal Server Error"
}
```

---

## Environment Configuration

Key environment variables affecting API behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_PORT` | 3001 | HTTP/WebSocket server port |
| `CORS_ORIGIN` | http://localhost:3000 | Allowed frontend origin |
| `JWT_SECRET` | (required) | Secret for signing JWT tokens |
| `STRIPE_ENABLED` | false | Enable real Stripe integration |
| `VECTOR_ENABLED` | false | Enable AI vector indexing |
| `NOTIFICATION_MOCK` | true | Use mock notification provider |
| `CLAM_AV_ENABLED` | false | Enable real virus scanning |

---

## Rate Limiting

Currently no rate limiting is implemented. In production, consider:
- Per-user request limits (e.g., 100 req/min)
- Per-IP limits for public endpoints (e.g., 20 req/min for signup/login)
- WebSocket message rate limits

---

## CORS Policy

**Allowed Origins:** `CORS_ORIGIN` environment variable (default: `http://localhost:3000`)

**Allowed Methods:** GET, POST, PUT, DELETE, OPTIONS

**Credentials:** Enabled (required for HTTP-only cookies)

---

## Testing the API

### Using cURL

**Signup:**
```bash
curl -X POST http://localhost:3001/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!",
    "first_name": "Test",
    "last_name": "User"
  }' \
  -c cookies.txt
```

**Create Project (with saved cookie):**
```bash
curl -X POST http://localhost:3001/api/projects \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "name": "Test Project",
    "description": "Testing the API"
  }'
```

### WebSocket Client (JavaScript)

```javascript
import { io } from 'socket.io-client';

const socket = io('http://localhost:3001', {
  withCredentials: true, // Send cookies
});

socket.on('connect', () => {
  console.log('Connected:', socket.id);

  // Join a thread
  socket.emit('thread.join', { threadId: 'uuid' });
});

socket.on('message.created', (data) => {
  console.log('New message:', data);
});
```

---

## Next Steps

1. **Apply Database Schema**: Run `npx prisma migrate deploy` to create tables
2. **Start Redis**: Required for workers and real-time features
3. **Test Endpoints**: Use cURL or Postman to test auth flow
4. **Start Frontend**: Run `npm run dev` in `frontend/` directory
5. **Enable Stripe**: Set `STRIPE_ENABLED=true` and add API keys for testing payments

---

## Support

For issues or questions, refer to:
- Main README.md
- sql/schema_final.sql (database schema reference)
- .env.example (configuration template)

# ML Agent ↔ Frontend Integration

**Agent:** `Desktop/TheCateringCompany` (v5-2026-03-10)
**Frontend:** Next.js 14 (`/chat` page)
**Backend:** NestJS (`POST /api/projects/ai-intake`)

---

## Overview

The chat intake page collects event details through a conversational AI agent. When the conversation finishes, the frontend fetches all collected slot values and saves them as a project + contract in the NestJS backend.

```
User (/chat)
  │
  ├─ message → POST /chat (ML API :8000)
  │              returns: { thread_id, is_complete, slots_filled, ... }
  │
  ├─ [when is_complete = true]
  │    └─ GET /conversation/{thread_id} (ML API)
  │         returns: { slots: { name, event_date, venue, ... } }
  │
  └─ POST /api/projects/ai-intake (NestJS :3001)
       returns: { project, contract, venue }
         │
         └─ router.push(`/projects/${project.id}`)
```

---

## ML Agent

**Path:** `C:\Users\avina\OneDrive\Desktop\TheCateringCompany`
**Runs on:** `http://localhost:8000`

### Slot Names (`SLOT_NAMES` in `agent/state.py`)

| Slot | Description | Example Value |
|------|-------------|---------------|
| `name` | Client full name | `"John Smith"` |
| `event_date` | Event date | `"2024-06-15"` |
| `service_type` | drop-off or on-site | `"on-site"` |
| `event_type` | Wedding / Corporate / Birthday / Social / Custom | `"Corporate"` |
| `venue` | Venue name + address | `"Grand Hall, 123 Main St"` |
| `guest_count` | Number of guests | `"50"` |
| `service_style` | cocktail hour / reception / both | `"reception"` |
| `selected_dishes` | List of 3–5 main dishes | `["Chicken Marsala", "Salmon"]` |
| `appetizers` | Appetizer selections or "none" | `"Bruschetta"` |
| `menu_notes` | Special menu design notes | `"no pork"` |
| `utensils` | Utensil package or "no" | `"Premium Set"` |
| `desserts` | Dessert selections or "no" | `"Chocolate Cake"` |
| `rentals` | Linen/table/chair selections or "no" | `"White linens"` |
| `florals` | Floral arrangements or "no" (wedding only) | `"no"` |
| `special_requests` | Special requests or "none" | `"vegan station"` |
| `dietary_concerns` | Dietary restrictions | `"nut allergy"` |
| `additional_notes` | Anything else | `"none"` |

### API Endpoints Used by Frontend

#### `POST /chat`
Sends a user message. Returns conversation progress.

**Request:**
```json
{
  "thread_id": "uuid | null",
  "message": "Hello, I need catering",
  "author_id": "user-uuid",
  "project_id": null
}
```

**Response:**
```json
{
  "thread_id": "abc-123",
  "project_id": "xyz-456",
  "message": "Great! What is your name?",
  "current_node": "collect_name",
  "slots_filled": 0,
  "total_slots": 17,
  "is_complete": false,
  "contract_id": null
}
```

#### `GET /conversation/{thread_id}`
Returns all filled slot values. Called once `is_complete = true`.

**Response:**
```json
{
  "thread_id": "abc-123",
  "project_id": "xyz-456",
  "current_node": "generate_contract",
  "is_completed": true,
  "slots_filled": 17,
  "slots": {
    "name": "John Smith",
    "event_date": "2024-06-15",
    "service_type": "on-site",
    "event_type": "Corporate",
    "venue": "Grand Hall, 123 Main St",
    "guest_count": "50",
    "service_style": "reception",
    "selected_dishes": ["Chicken Marsala", "Salmon", "Pasta"],
    "appetizers": "Bruschetta",
    "menu_notes": "none",
    "utensils": "Premium Set",
    "desserts": "Chocolate Cake",
    "rentals": "no",
    "florals": "no",
    "special_requests": "vegan station",
    "dietary_concerns": "nut allergy",
    "additional_notes": "none"
  },
  "messages": [...]
}
```

---

## Frontend Files

### `frontend/app/chat/page.tsx`
The intake page. Renders the `<AiChat>` component and handles the `onComplete` callback.

**`handleComplete(contractData: ContractData)`** — maps slot names to NestJS fields:

| Slot field | Backend field |
|-----------|---------------|
| `name` | `client_name` |
| `event_type` | `event_type` |
| `event_date` | `event_date` |
| `guest_count` | `guest_count` (cast to Number) |
| `service_type` | `service_type` |
| `venue` | `venue_name` + `venue_address` |
| `selected_dishes` | `menu_items` |
| `dietary_concerns` | `dietary_restrictions` (wrapped in array) |
| `utensils` / `desserts` / `rentals` / `florals` | `addons` (prefixed strings, filtered if "no") |
| `special_requests` | `modifications` (wrapped in array, filtered if "none") |

After saving, redirects to `/projects/{id}` (the newly created project).

### `frontend/components/chat/ai-chat.tsx`
Manages the chat UI and conversation state.

**Completion flow:**
```typescript
if (response.is_complete) {
  const conversation = await chatAiApi.getConversation(response.thread_id);
  const slots = { ...conversation.slots, thread_id: response.thread_id };
  onComplete?.(slots);
}
```

### `frontend/lib/api/chat-ai.ts`
API client for the ML agent.

| Method | Description |
|--------|-------------|
| `sendMessage(options)` | `POST /chat` |
| `sendMessageWithRetry(options, maxRetries)` | `POST /chat` with 3 retries + backoff |
| `getConversation(threadId)` | `GET /conversation/{thread_id}` |
| `checkHealth()` | `GET /health` |

### `frontend/types/chat-ai.types.ts`
TypeScript types for the integration.

| Type | Description |
|------|-------------|
| `ChatRequest` | Payload for `POST /chat` |
| `ChatResponse` | Response from `POST /chat` |
| `ContractData` | Filled slot values from `GET /conversation/{thread_id}` |
| `ConversationState` | Full response from `GET /conversation/{thread_id}` |
| `ChatState` | React state shape for the `AiChat` component |

### `frontend/components/chat/chat-sidebar.tsx`
Hover sidebar showing real-time progress as slots are filled during the conversation. Field labels map to the 17 `SLOT_NAMES`.

---

## NestJS Backend

**Endpoint:** `POST /api/projects/ai-intake`
**Auth:** JWT cookie required
**File:** `backend/src/projects/projects.controller.ts`

### Request Body

```typescript
{
  client_name?: string;
  contact_email?: string;
  contact_phone?: string;
  event_type?: string;
  event_date?: string;         // ISO date string
  guest_count?: number;
  service_type?: string;
  menu_items?: string[];
  dietary_restrictions?: string[];
  budget_range?: string;
  venue_name?: string;
  venue_address?: string;
  setup_time?: string;
  service_time?: string;
  addons?: string[];
  modifications?: string[];
  generate_contract?: boolean; // true = create contract immediately
}
```

### Response

```json
{
  "project": {
    "id": "uuid",
    "title": "Corporate - John Smith",
    "status": "draft",
    "event_date": "2024-06-15T00:00:00.000Z",
    "guest_count": 50
  },
  "venue": {
    "id": "uuid",
    "name": "Grand Hall"
  },
  "contract": {
    "id": "uuid",
    "status": "pending_staff_approval",
    "title": "Contract - Corporate for John Smith",
    "version_number": 1
  },
  "contract_data": { ... }
}
```

### What It Creates

1. **`projects`** — with `owner_user_id`, `title`, `event_date`, `guest_count`, `status: 'draft'`, `ai_event_summary` (full intake JSON)
2. **`venues`** — created if `venue_name` provided and not already existing
3. **`project_collaborators`** — authenticated user added as collaborator
4. **`contracts`** — if `generate_contract: true`, creates with `status: 'pending_staff_approval'`

**Files:** `backend/src/projects/projects.service.ts` → `createFromAiIntake()`

---

## Contract Lifecycle

```
pending_staff_approval  →  approved  →  sent (OpenSign)  →  signed
        ↑
  Created here (AI intake)
```

Staff review pending contracts at `/staff/contracts`. After approval, the contract is sent via OpenSign for e-signature.

**Staff endpoint:** `POST /api/staff/contracts/{id}/approve`
**File:** `backend/src/contracts/staff-contracts.controller.ts`

---

## Environment Variables

### Frontend (`.env.local`)
```bash
NEXT_PUBLIC_API_URL=http://localhost:3001       # NestJS backend
NEXT_PUBLIC_ML_API_URL=http://localhost:8000   # ML agent
```

### Backend (`.env`)
```bash
DATABASE_URL=postgresql://...
JWT_SECRET=...
OPENSIGN_ENABLED=false                          # true to send real e-signatures
OPENSIGN_API_KEY=...
OPENSIGN_API_URL=https://app.opensignlabs.com/api/v1
```

---

## Running Locally

```bash
# 1. ML Agent (Desktop version)
cd "C:\Users\avina\OneDrive\Desktop\TheCateringCompany"
python api.py                    # http://localhost:8000

# 2. Backend
cd cateringCo/backend
npm run start:dev                # http://localhost:3001

# 3. Frontend
cd cateringCo/frontend
npm run dev                      # http://localhost:3000
```

**Test the full flow:** Navigate to `http://localhost:3000/chat`

---

## Known Issues & Notes

- The Desktop agent's `generate_contract.py` lists `phone` as a required slot, but `phone` is not in `SLOT_NAMES`. Contract generation will fail if the phone node is not reached. The frontend handles this gracefully — `contact_phone` will simply be `undefined` in the backend payload.
- `florals` slot only appears for Wedding events.
- `guest_count` is returned as a string by the ML agent — the frontend casts it with `Number()`.
- OpenSign is currently in mock mode (`OPENSIGN_ENABLED=false`). The correct API endpoint is `POST /createdocument` with header `x-api-token`.

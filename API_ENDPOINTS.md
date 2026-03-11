# The Catering Company - API Endpoints

Base URL: `http://localhost:8000`

---

## Health & System

### `GET /health`

Health check.

**Response:**
```json
{
  "status": "ok"
}
```

### `GET /version`

Returns the running server code version.

**Response:**
```json
{
  "version": "v5-2026-03-10"
}
```

### `GET /`

Serves the test chat HTML UI. Returns `text/html`.

---

## Chat (Core Conversation)

### `POST /chat`

Send a message to the AI catering agent. Creates a new conversation on first call (when `thread_id` is omitted), or continues an existing one.

**Request Body:**
```json
{
  "thread_id": "uuid-string | null",
  "message": "string (required)",
  "author_id": "string (default: \"user\")",
  "project_id": "uuid-string | null"
}
```

| Field        | Type          | Required | Description                                                        |
|--------------|---------------|----------|--------------------------------------------------------------------|
| `thread_id`  | `string|null` | No       | UUID of existing conversation. Omit or `null` to start a new one.  |
| `message`    | `string`      | Yes      | The user's message. Prefix with `@AI` for mid-flow slot changes.   |
| `author_id`  | `string`      | No       | Identifier for the sender. Defaults to `"user"`.                   |
| `project_id` | `string|null` | No       | UUID to associate with a specific project. Auto-created if omitted.|

**Response (`200`):**
```json
{
  "thread_id": "c548e617-aa72-4030-aee9-6d153d5ca279",
  "project_id": "74a06981-14e9-4dc8-a1ef-3eecd763baca",
  "message": "Hello! I'm thrilled to help you plan your event. May I have your first and last name, please?",
  "current_node": "collect_name",
  "slots_filled": 0,
  "total_slots": 16,
  "is_complete": false,
  "contract_id": null
}
```

| Field          | Type          | Description                                                                 |
|----------------|---------------|-----------------------------------------------------------------------------|
| `thread_id`    | `string`      | UUID for this conversation thread. Use in subsequent calls.                 |
| `project_id`   | `string`      | UUID for the project (FK chain: project > thread > state).                  |
| `message`      | `string`      | The agent's response text.                                                  |
| `current_node` | `string`      | Current position in the conversation flow (see Node List below).            |
| `slots_filled` | `int`         | Number of slots filled so far.                                              |
| `total_slots`  | `int`         | Total slots to fill (currently 16).                                         |
| `is_complete`  | `bool`        | `true` when the contract has been generated and conversation is complete.   |
| `contract_id`  | `string|null` | UUID of the generated contract (only set when `is_complete` is `true`).     |

**@AI Modification Example:**
```json
{
  "thread_id": "c548e617-aa72-4030-aee9-6d153d5ca279",
  "message": "@AI change the event date to May 8th"
}
```
The agent detects `@AI`, updates the slot, confirms the change, and re-asks the pending question without advancing the flow.

---

## Conversation State

### `GET /conversation/{thread_id}`

Get full conversation state including all messages.

**Path Params:** `thread_id` (UUID)

**Response (`200`):**
```json
{
  "thread_id": "c548e617-aa72-4030-aee9-6d153d5ca279",
  "project_id": "74a06981-14e9-4dc8-a1ef-3eecd763baca",
  "current_node": "collect_venue",
  "is_completed": false,
  "slots_filled": 4,
  "slots": {
    "name": "Syed Alee",
    "event_date": "2026-05-08",
    "service_type": "on-site",
    "event_type": "Birthday"
  },
  "messages": [
    {
      "sender_type": "user",
      "content": "hello",
      "created_at": "2026-03-10T12:00:00.000000"
    },
    {
      "sender_type": "ai",
      "content": "Hello! I'm thrilled to help you plan your event...",
      "created_at": "2026-03-10T12:00:01.000000"
    }
  ]
}
```

**Error (`404`):**
```json
{
  "detail": "Conversation not found"
}
```

### `GET /conversation/{thread_id}/slots`

Get current slot values only (lighter than full conversation).

**Path Params:** `thread_id` (UUID)

**Response (`200`):**
```json
{
  "thread_id": "c548e617-aa72-4030-aee9-6d153d5ca279",
  "current_node": "collect_venue",
  "filled": {
    "name": "Syed Alee",
    "event_date": "2026-05-08",
    "service_type": "on-site",
    "event_type": "Birthday"
  },
  "unfilled": [
    "venue",
    "guest_count",
    "service_style",
    "selected_dishes",
    "appetizers",
    "menu_notes",
    "utensils",
    "desserts",
    "rentals",
    "special_requests",
    "dietary_concerns",
    "additional_notes"
  ],
  "slots_filled": 4,
  "total_slots": 16
}
```

---

## Contracts

### `GET /contract/{contract_id}`

Get a single contract by ID.

**Path Params:** `contract_id` (UUID)

**Response (`200`):**
```json
{
  "id": "a1b2c3d4-...",
  "contract_group_id": "e5f6g7h8-...",
  "version_number": 1,
  "project_id": "74a06981-...",
  "title": "@Syed Alee 2026.docx",
  "body": {
    "summary": "Catering contract for Syed Alee — Birthday on 2026-05-08",
    "slots": {
      "name": "Syed Alee",
      "event_date": "2026-05-08",
      "event_type": "Birthday"
    },
    "contract_text": "CATERING SERVICE CONTRACT\n\nContract Number: CC-20260310-A1B2C3..."
  },
  "total_amount": 8542.50,
  "status": "draft",
  "ai_generated": true,
  "created_at": "2026-03-10T14:30:00.000000"
}
```

**Error (`404`):**
```json
{
  "detail": "Contract not found"
}
```

### `GET /project/{project_id}/contracts`

Get all contracts for a project (newest first).

**Path Params:** `project_id` (UUID)

**Response (`200`):**
```json
{
  "project_id": "74a06981-...",
  "contracts": [
    {
      "id": "a1b2c3d4-...",
      "title": "@Syed Alee 2026.docx",
      "version_number": 1,
      "status": "draft",
      "ai_generated": true,
      "created_at": "2026-03-10T14:30:00.000000"
    }
  ]
}
```

---

## Menu

### `GET /menu`

Get the full menu grouped by category.

**Response (`200`):**
```json
{
  "categories": {
    "Entrees": [
      {
        "id": "uuid",
        "name": "Prime Rib",
        "description": "Slow-roasted prime rib with au jus",
        "unit_price": 42.25,
        "price_type": "per_person",
        "allergens": ["dairy"],
        "tags": ["premium", "wedding"],
        "is_upsell": false
      }
    ],
    "Hors D'oeuvres - Chicken": [
      {
        "id": "uuid",
        "name": "Chicken Satay",
        "description": "Grilled chicken skewers with peanut sauce",
        "unit_price": 3.50,
        "price_type": "per_person",
        "allergens": ["peanuts"],
        "tags": [],
        "is_upsell": false
      }
    ],
    "Desserts": []
  }
}
```

---

## Pricing

### `GET /pricing`

Get all active pricing packages.

**Response (`200`):**
```json
{
  "packages": [
    {
      "id": "uuid",
      "name": "Premium Wedding Package",
      "description": "Full-service wedding catering",
      "category": "wedding",
      "base_price": 85.00,
      "price_type": "per_person"
    }
  ]
}
```

### `POST /pricing/calculate`

Calculate a full pricing breakdown for given event selections.

**Request Body:**
```json
{
  "guest_count": 150,
  "event_type": "Birthday",
  "service_type": "on-site",
  "selected_dishes": "Prime Rib, Grilled Salmon, Caesar Salad",
  "appetizers": "Chicken Satay, Bruschetta",
  "desserts": "Chocolate Cake",
  "utensils": "Premium silverware",
  "rentals": "linens, tables"
}
```

| Field             | Type          | Required | Description                                |
|-------------------|---------------|----------|--------------------------------------------|
| `guest_count`     | `int`         | Yes      | Number of guests.                          |
| `event_type`      | `string`      | No       | Wedding, Corporate, Birthday, Social, Custom. |
| `service_type`    | `string`      | No       | `drop-off` or `on-site`.                   |
| `selected_dishes` | `string|null` | No       | Comma-separated dish names.                |
| `appetizers`      | `string|null` | No       | Comma-separated appetizer names.           |
| `desserts`        | `string|null` | No       | Comma-separated dessert names.             |
| `utensils`        | `string|null` | No       | Utensil/tableware selection.               |
| `rentals`         | `string|null` | No       | Comma-separated rental items.              |

**Response (`200`):**
```json
{
  "line_items": [
    {
      "name": "Prime Rib",
      "description": "Slow-roasted prime rib with au jus",
      "unit_price": 42.25,
      "price_type": "per_person",
      "total": 6337.50
    }
  ],
  "package": {
    "name": "Standard Package",
    "per_person_rate": 55.00
  },
  "food_subtotal": 9500.00,
  "service_surcharge": 750.00,
  "subtotal_before_fees": 10250.00,
  "tax": 963.50,
  "gratuity": 2050.00,
  "grand_total": 13263.50,
  "deposit": 6631.75,
  "balance": 6631.75
}
```

---

## Conversation Flow — Node List

The `current_node` field tracks position in this flow:

```
start
  -> collect_name
  -> collect_event_date
  -> select_service_type
  -> select_event_type
  -> wedding_message (weddings only)
  -> collect_venue
  -> collect_guest_count
  -> select_service_style (weddings only)
  -> select_dishes
  -> ask_appetizers
  -> select_appetizers
  -> menu_design
  -> ask_menu_changes
  -> collect_menu_changes
  -> ask_utensils
  -> select_utensils
  -> ask_desserts
  -> select_desserts
  -> ask_more_desserts
  -> ask_rentals
  -> ask_special_requests
  -> collect_special_requests
  -> collect_dietary
  -> ask_anything_else
  -> collect_anything_else
  -> generate_contract
  -> complete
```

Special node: `check_modifications` — triggered when a message contains `@AI`. Handles slot updates without advancing the flow.

---

## Slot Names (16 total)

| Slot               | Collected At            | Validation                                |
|--------------------|-------------------------|-------------------------------------------|
| `name`             | `collect_name`          | Non-empty string                          |
| `event_date`       | `collect_event_date`    | Future date, natural language parsed       |
| `service_type`     | `select_service_type`   | `drop-off` or `on-site`                   |
| `event_type`       | `select_event_type`     | Wedding, Corporate, Birthday, Social, Custom |
| `venue`            | `collect_venue`         | Non-empty string                          |
| `guest_count`      | `collect_guest_count`   | Integer 10-10,000                         |
| `service_style`    | `select_service_style`  | Cocktail Hour, Reception, Both (weddings) |
| `selected_dishes`  | `select_dishes`         | Comma-separated dish names                |
| `appetizers`       | `ask/select_appetizers` | Selections or "none"                      |
| `menu_notes`       | `collect_menu_changes`  | Free text                                 |
| `utensils`         | `ask/select_utensils`   | Selection or "no"                         |
| `desserts`         | `ask/select_desserts`   | Selections or "no"                        |
| `rentals`          | `ask_rentals`           | linens, tables, chairs, or "no"           |
| `special_requests` | `ask/collect_special`   | Free text or "none"                       |
| `dietary_concerns` | `collect_dietary`       | Free text or "none"                       |
| `additional_notes` | `collect_anything_else` | Free text                                 |

# Database Setup Guide

## Overview

This directory contains database setup for the Catering AI Agent. It supports both SQLite3 (for development/testing) and PostgreSQL (for production) via Prisma ORM.

## Quick Start with SQLite3

### 1. Setup Database

```bash
# Run setup script
python database/sqlite_setup.py
```

This creates `database/catering.db` with all required tables.

### 2. Test Database Operations

```bash
# Run comprehensive test
python database/test_database.py
```

This tests:
- Conversation state save/load
- Message history tracking
- AI tag modifications
- Contract generation and storage
- State recovery

### 3. Inspect Database

```bash
# Open SQLite3 CLI
sqlite3 database/catering.db

# View tables
.tables

# Query conversation states
SELECT * FROM conversation_states;

# Query contracts
SELECT * FROM contracts;

# Exit
.quit
```

## Database Schema

### Tables

1. **conversation_states** - Stores conversation state for each thread
   - `id` - UUID primary key
   - `conversation_id` - Unique conversation identifier
   - `project_id` - Project identifier
   - `thread_id` - Thread identifier (indexed)
   - `current_node` - Current conversation node
   - `slots` - JSON string of slot data
   - `messages` - JSON string of message history
   - `metadata` - JSON string of additional metadata
   - `is_completed` - Boolean flag
   - `created_at`, `updated_at` - Timestamps

2. **ai_tags** - Stores @AI modification history
   - `id` - UUID primary key
   - `thread_id` - Thread identifier (indexed)
   - `message_id` - Message identifier (indexed)
   - `field` - Field that was modified
   - `old_value` - Previous value
   - `new_value` - New value
   - `field_content` - Original modification text
   - `created_at`, `updated_at` - Timestamps

3. **contracts** - Stores generated contracts
   - `id` - UUID primary key
   - `conversation_id` - Associated conversation (indexed)
   - `project_id` - Project identifier (indexed)
   - Client information (name, phone)
   - Event details (type, date, service type, guest count, venue)
   - Financial data (pricing, upsells, margin, staffing) as JSON
   - `status` - Contract status (draft, sent, signed, cancelled)
   - `pdf_url` - URL to generated PDF
   - `signed_at` - Signature timestamp
   - `created_at`, `updated_at` - Timestamps

4. **messages** - Stores message history (optional)
   - `id` - UUID primary key
   - `thread_id` - Thread identifier (indexed)
   - `conversation_id` - Conversation identifier (indexed)
   - `author_id` - Author identifier
   - `author_type` - "user" or "agent"
   - `content` - Message content
   - `metadata` - JSON string of additional data
   - `created_at` - Timestamp (indexed)

## Using with Python (SQLite3)

```python
from database.sqlite_setup import CateringDatabase

# Initialize database
db = CateringDatabase()

# Save conversation state
db.save_conversation_state(state)

# Load conversation state
state = db.load_conversation_state(thread_id)

# Save contract
contract_id = db.save_contract(contract_data)

# Get contract
contract = db.get_contract(contract_id)

# Save message
message_id = db.save_message(
    thread_id="thread-123",
    conversation_id="conv-123",
    author_id="user-456",
    author_type="user",
    content="My name is Sarah"
)

# Get conversation history
history = db.get_conversation_history(thread_id)

# Close connection
db.close()
```

## Migrating to Prisma ORM

### 1. Install Prisma

```bash
# In your NestJS project
npm install @prisma/client
npm install -D prisma
```

### 2. Initialize Prisma

```bash
npx prisma init
```

### 3. Copy Schema

Copy `database/schema.prisma` to your NestJS project's `prisma/schema.prisma`.

### 4. Update Database URL

For SQLite (development):
```env
DATABASE_URL="file:./dev.db"
```

For PostgreSQL (production):
```env
DATABASE_URL="postgresql://user:password@localhost:5432/catering_db"
```

### 5. Generate Prisma Client

```bash
npx prisma generate
```

### 6. Create Database

```bash
# For SQLite
npx prisma db push

# For PostgreSQL (with migrations)
npx prisma migrate dev --name init
```

### 7. Use in NestJS

```typescript
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// Save conversation state
await prisma.conversationState.upsert({
  where: { conversationId: state.conversation_id },
  update: {
    currentNode: state.current_node,
    slots: JSON.stringify(state.slots),
    messages: JSON.stringify(state.messages),
    isCompleted: state.current_node === 'done',
    updatedAt: new Date()
  },
  create: {
    conversationId: state.conversation_id,
    projectId: state.project_id,
    threadId: state.thread_id,
    currentNode: state.current_node,
    slots: JSON.stringify(state.slots),
    messages: JSON.stringify(state.messages),
    isCompleted: false
  }
});

// Load conversation state
const conversation = await prisma.conversationState.findUnique({
  where: { threadId: thread_id }
});

// Save contract
const contract = await prisma.contract.create({
  data: {
    conversationId: contract_data.conversation_id,
    projectId: contract_data.project_id,
    clientName: contract_data.slots.name,
    clientPhone: contract_data.slots.phone,
    eventType: contract_data.slots.event_type,
    eventDate: contract_data.slots.event_date,
    serviceType: contract_data.slots.service_type,
    guestCount: contract_data.slots.guest_count,
    venue: JSON.stringify(contract_data.slots.venue),
    specialRequests: JSON.stringify(contract_data.slots.special_requests),
    pricingData: JSON.stringify(contract_data.pricing),
    upsellsData: JSON.stringify(contract_data.upsells),
    marginData: JSON.stringify(contract_data.margin),
    staffingData: JSON.stringify(contract_data.staffing),
    missingInfoData: JSON.stringify(contract_data.missing_info),
    status: 'draft'
  }
});
```

## Switching from SQLite to PostgreSQL

### 1. Update schema.prisma

Change:
```prisma
datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL")
}
```

To:
```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

### 2. Update DATABASE_URL

```env
DATABASE_URL="postgresql://user:password@localhost:5432/catering_db"
```

### 3. Run Migration

```bash
npx prisma migrate dev --name init
```

### 4. Generate Client

```bash
npx prisma generate
```

## Database Queries

### Common Queries

```sql
-- Get all conversations for a project
SELECT * FROM conversation_states 
WHERE project_id = 'proj-123' 
ORDER BY updated_at DESC;

-- Get incomplete conversations
SELECT * FROM conversation_states 
WHERE is_completed = 0;

-- Get all contracts for a project
SELECT * FROM contracts 
WHERE project_id = 'proj-123' 
ORDER BY created_at DESC;

-- Get contracts by status
SELECT * FROM contracts 
WHERE status = 'draft';

-- Get conversation with message count
SELECT 
  cs.*,
  COUNT(m.id) as message_count
FROM conversation_states cs
LEFT JOIN messages m ON cs.thread_id = m.thread_id
GROUP BY cs.id;

-- Get AI modifications for a thread
SELECT * FROM ai_tags 
WHERE thread_id = 'thread-123' 
ORDER BY created_at DESC;
```

## Backup and Restore

### SQLite Backup

```bash
# Backup
sqlite3 database/catering.db ".backup database/catering_backup.db"

# Restore
sqlite3 database/catering.db ".restore database/catering_backup.db"
```

### PostgreSQL Backup

```bash
# Backup
pg_dump catering_db > backup.sql

# Restore
psql catering_db < backup.sql
```

## Performance Tips

1. **Indexes**: All foreign keys and frequently queried fields are indexed
2. **JSON Storage**: Use JSON for flexible nested data (slots, venue, pricing)
3. **Pagination**: Use LIMIT and OFFSET for large result sets
4. **Connection Pooling**: Use connection pooling in production (Prisma handles this)

## Troubleshooting

### "Database is locked"

SQLite issue when multiple processes access the database:
```python
# Use timeout
conn = sqlite3.connect('database/catering.db', timeout=10.0)
```

### "Table already exists"

Drop and recreate:
```bash
rm database/catering.db
python database/sqlite_setup.py
```

### Prisma migration issues

Reset database:
```bash
npx prisma migrate reset
npx prisma migrate dev --name init
```

## Next Steps

1. ✅ Test with SQLite3 locally
2. ✅ Verify all operations work
3. 🔄 Integrate with Prisma ORM in NestJS
4. 🔄 Switch to PostgreSQL for production
5. 🔄 Add connection pooling
6. 🔄 Set up database backups

## Support

For questions or issues:
- Check SQLite3 documentation: https://www.sqlite.org/docs.html
- Check Prisma documentation: https://www.prisma.io/docs
- Review integration examples in docs/INTEGRATION.md

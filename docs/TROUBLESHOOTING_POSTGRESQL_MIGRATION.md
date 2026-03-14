# PostgreSQL Migration Issues & Solutions

## Overview

This document details the issues encountered during the migration from SQLite to PostgreSQL for the ML API, and how they were resolved.

---

## Issue 1: Prisma Client Not Generated

### Error
```
RuntimeError: The Client hasn't been generated yet, you must run `prisma generate`
```

### Cause
The Prisma client wasn't generated in the virtual environment (`.venv`). When we installed Prisma and generated the client globally, the code running in the virtual environment couldn't find it.

### Solution
Generate Prisma client **inside the activated virtual environment**:

```bash
# Activate virtual environment first
source .venv/Scripts/activate

# Then generate Prisma client
prisma generate --schema=./prisma/schema.prisma
```

### Prevention
Always activate the virtual environment before running Prisma commands. Updated `start_ml_api.bat` to automatically activate venv.

---

## Issue 2: Model Name Mismatch

### Error
```
AttributeError: 'Prisma' object has no attribute 'conversationstate'.
Did you mean: 'ai_conversation_states'?
```

### Cause
The `database/db_manager.py` was using SQLite schema model names:
- `client.conversationstate` (SQLite)
- `client.message` (SQLite)

But the Prisma client was generated from the backend PostgreSQL schema which uses:
- `client.ai_conversation_states` (PostgreSQL)
- `client.messages` (PostgreSQL)

### Root Cause
Two different schemas existed:
1. **Local SQLite schema**: `database/schema.prisma` (old)
2. **Backend PostgreSQL schema**: `prisma/schema.prisma` (new)

The chat endpoint code was written for SQLite but we generated Prisma client from PostgreSQL schema.

### Solution

**Step 1: Updated `database/db_manager.py`**

Changed all model references:
```python
# OLD (SQLite)
await client.conversationstate.find_first(...)
await client.message.create(...)

# NEW (PostgreSQL)
await client.ai_conversation_states.find_first(...)
await client.messages.create(...)
```

**Step 2: Updated field names to snake_case**
```python
# OLD (SQLite - camelCase)
where={"threadId": thread_id}
data={"currentNode": current_node, "isCompleted": is_completed}

# NEW (PostgreSQL - snake_case)
where={"thread_id": thread_id}
data={"current_node": current_node, "is_completed": is_completed}
```

**Step 3: Updated data handling**
```python
# OLD (SQLite - JSON as string)
slots_json = json.dumps(slots)
data={"slots": slots_json}

# NEW (PostgreSQL - JSON as dict)
data={"slots": slots}  # Prisma handles JSON automatically
```

**Step 4: Regenerated Prisma client from backend schema**
```bash
prisma generate --schema=./prisma/schema.prisma
```

**Step 5: Removed old SQLite schema**
```bash
mv database/schema.prisma database/schema.prisma.old-sqlite
rm database/*.db
```

### Prevention
- Use only ONE schema: `prisma/schema.prisma` (backend PostgreSQL schema)
- Backend team manages schema changes
- ML API regenerates client when schema updates

---

## Issue 3: Foreign Key Constraint Violation

### Error
```
prisma.errors.MissingRequiredValueError: Unable to match input value to any allowed input type for the field.
Parse errors: [`data.projects`: A value is required but not set, `data.project_id`: A value is required but not set]
```

### Cause
The `threads` table in PostgreSQL has a **required foreign key** to `projects`:

```prisma
model threads {
  id         String   @id
  project_id String   @db.Uuid  // REQUIRED!
  subject    String?
  // ...
  projects   projects @relation(fields: [project_id], references: [id])
}
```

The `ensure_project_and_thread()` function was trying to create a thread **before** creating the project, and wasn't providing `project_id`.

### Solution

**Updated `ensure_project_and_thread()` function:**

```python
async def ensure_project_and_thread(
    thread_id: str,
    project_id: str,
    owner_user_id: str = "ai-system"
):
    """
    Ensure thread and project exist in database.
    This is needed because backend schema has FK constraints.
    """
    client = _get_client()

    # STEP 1: Ensure project exists FIRST (threads requires it)
    if project_id:
        project = await client.projects.find_unique(where={"id": project_id})
        if not project:
            await client.projects.create(
                data={
                    "id": project_id,
                    "owner_user_id": owner_user_id,
                    "title": f"Chat Project {project_id[:8]}",
                }
            )
            logger.info(f"Created project: {project_id}")

    # STEP 2: Then create thread with project_id
    thread = await client.threads.find_unique(where={"id": thread_id})
    if not thread:
        await client.threads.create(
            data={
                "id": thread_id,
                "project_id": project_id,  # Required FK
                "subject": f"Chat {thread_id[:8]}",
                "created_by": owner_user_id,
            }
        )
        logger.info(f"Created thread: {thread_id}")
```

**Key Changes:**
1. ✅ Create **project first** (if needed)
2. ✅ Create **thread second** with `project_id`
3. ✅ Provide all required fields: `project_id`, `subject`, `created_by`

### Prevention
- Always check schema for required fields before creating records
- Understand FK constraints and creation order
- Create parent records before child records

---

## Database Schema Comparison

### SQLite Schema (OLD - Removed)

```prisma
// database/schema.prisma (old)
model ConversationState {
  id              String   @id @default(uuid())
  conversationId  String   @unique @map("conversation_id")
  projectId       String   @map("project_id")
  threadId        String   @map("thread_id")
  currentNode     String   @map("current_node")
  slots           String   // JSON string
  messages        String   // JSON string
  isCompleted     Boolean  @default(false) @map("is_completed")
  // ...
}

model Message {
  id              String   @id @default(uuid())
  threadId        String   @map("thread_id")
  conversationId  String   @map("conversation_id")
  authorId        String   @map("author_id")
  authorType      String   @map("author_type")
  content         String
  // ...
}
```

**Characteristics:**
- ❌ Local SQLite database
- ❌ No FK constraints
- ❌ JSON stored as strings
- ❌ Different table/field names

### PostgreSQL Schema (NEW - Current)

```prisma
// prisma/schema.prisma (backend)
model ai_conversation_states {
  id                     String     @id @default(dbgenerated("gen_random_uuid()"))
  thread_id              String     @unique @db.Uuid
  project_id             String?    @db.Uuid
  current_node           String     @default("start")
  slots                  Json       @default("{}")
  is_completed           Boolean    @default(false)
  created_at             DateTime   @default(now())
  updated_at             DateTime   @default(now())

  // Foreign Keys
  threads                threads    @relation(fields: [thread_id], references: [id])
  projects               projects?  @relation(fields: [project_id], references: [id])
  messages               messages[]
}

model messages {
  id                       String                  @id @default(dbgenerated("gen_random_uuid()"))
  thread_id                String                  @db.Uuid
  project_id               String                  @db.Uuid
  author_id                String?                 @db.Uuid
  sender_type              String?
  content                  String
  ai_conversation_state_id String?                 @db.Uuid
  created_at               DateTime                @default(now())

  // Foreign Keys
  ai_conversation_states   ai_conversation_states? @relation(fields: [ai_conversation_state_id], references: [id])
  users                    users?                  @relation(fields: [author_id], references: [id])
}

model threads {
  id                     String                  @id @default(dbgenerated("gen_random_uuid()"))
  project_id             String                  @db.Uuid  // REQUIRED!
  subject                String?
  created_by             String?                 @db.Uuid
  created_at             DateTime                @default(now())

  // Foreign Keys
  projects               projects                @relation(fields: [project_id], references: [id])
  users                  users?                  @relation(fields: [created_by], references: [id])
  ai_conversation_states ai_conversation_states?
  messages               messages[]
}

model projects {
  id                       String   @id @default(dbgenerated("gen_random_uuid()"))
  owner_user_id            String   @db.Uuid  // REQUIRED!
  title                    String               // REQUIRED!
  event_date               DateTime?
  guest_count              Int?
  status                   project_status @default(draft)
  created_at               DateTime @default(now())

  // Foreign Keys & Relations
  users                    users    @relation(fields: [owner_user_id], references: [id])
  threads                  threads[]
  ai_conversation_states   ai_conversation_states[]
  messages                 messages[]
  ai_generations           ai_generations[]
  // ... many more relations
}
```

**Characteristics:**
- ✅ PostgreSQL database (production-grade)
- ✅ FK constraints enforced
- ✅ JSON as native type
- ✅ Consistent snake_case naming
- ✅ Shared with TypeScript backend

---

## Key Differences: SQLite vs PostgreSQL

| Feature | SQLite (OLD) | PostgreSQL (NEW) |
|---------|--------------|------------------|
| **Database Type** | File-based | Client-server |
| **Schema Location** | `database/schema.prisma` | `prisma/schema.prisma` |
| **Model Names** | `ConversationState`, `Message` | `ai_conversation_states`, `messages` |
| **Field Naming** | camelCase (in code) | snake_case |
| **JSON Storage** | String (`json.dumps()`) | Native JSON type |
| **Foreign Keys** | None | Enforced |
| **UUID Generation** | `uuid.uuid4()` | `gen_random_uuid()` (DB) |
| **Shared with Backend** | ❌ No | ✅ Yes |
| **Production Ready** | ❌ No | ✅ Yes |

---

## Migration Checklist

✅ **Completed Steps:**

1. ✅ Installed Prisma Client Python
2. ✅ Copied backend schema to `prisma/schema.prisma`
3. ✅ Updated schema generator to `prisma-client-py`
4. ✅ Added `enable_experimental_decimal = true`
5. ✅ Fixed `global` enum value → `global_scope`
6. ✅ Updated `.env` with PostgreSQL connection string
7. ✅ Generated Prisma client in virtual environment
8. ✅ Updated `database/db_manager.py`:
   - Model names: `conversationstate` → `ai_conversation_states`
   - Model names: `message` → `messages`
   - Field names: camelCase → snake_case
   - JSON handling: string → dict
   - Added FK constraint handling
9. ✅ Removed old SQLite schema and databases
10. ✅ Fixed `ensure_project_and_thread()` function
11. ✅ Tested all endpoints

---

## Testing Guide

### 1. Start API
```bash
start_ml_api.bat
```

### 2. Test Chat Endpoint
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hi"}'
```

**Expected Response:**
```json
{
  "thread_id": "uuid-here",
  "message": "Hello! I'm thrilled to help you plan your event...",
  "current_node": "collect_name",
  "slots_filled": 0,
  "total_slots": 16,
  "is_complete": false
}
```

### 3. Test ML Endpoints
```bash
# Health check
curl http://localhost:8000/ml/health

# Upsells
curl -X POST http://localhost:8000/ml/upsells \
  -H "Content-Type: application/json" \
  -d '{"event_type": "Wedding", "guest_count": 150, "current_selections": {}}'
```

### 4. Verify PostgreSQL Data
```sql
psql -h localhost -U avinash -d caterDB_prod

-- Check created records
SELECT id, title, owner_user_id FROM projects ORDER BY created_at DESC LIMIT 3;
SELECT id, project_id, subject FROM threads ORDER BY created_at DESC LIMIT 3;
SELECT id, thread_id, current_node FROM ai_conversation_states ORDER BY created_at DESC LIMIT 3;
SELECT id, thread_id, sender_type, content FROM messages ORDER BY created_at DESC LIMIT 5;
```

---

## Common Errors & Solutions

### Error: "Client hasn't been generated yet"
**Solution:** Activate venv and regenerate:
```bash
source .venv/Scripts/activate
prisma generate --schema=./prisma/schema.prisma
```

### Error: "No attribute 'conversationstate'"
**Solution:** Using wrong model name. Update to `ai_conversation_states`

### Error: "A value is required but not set"
**Solution:** Check schema for required fields. Ensure all required fields are provided.

### Error: Foreign key constraint violation
**Solution:** Create parent records before child records. Check FK relationships in schema.

---

## Architecture After Migration

```
┌─────────────────────────────────────────────┐
│           Frontend                          │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│           Backend (TypeScript)              │
│  - NestJS                                   │
│  - Prisma (TypeScript)                      │
│  - Handles business logic                   │
└─────────────┬───────────────────────────────┘
              │
              ├──→ Calls ML API for calculations
              │
              ▼
┌─────────────────────────────────────────────┐
│           ML API (Python)                   │
│  - FastAPI                                  │
│  - Prisma (Python)                          │
│  - /chat: Conversational agent              │
│  - /ml/*: Calculation endpoints             │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│           PostgreSQL                        │
│           caterDB_prod                      │
│                                             │
│  Tables:                                    │
│  - projects                                 │
│  - threads                                  │
│  - ai_conversation_states                   │
│  - messages                                 │
│  - ai_generations                           │
│  - project_staff_requirements               │
│  - project_upsell_items                     │
│  - ... (50+ tables)                         │
└─────────────────────────────────────────────┘
```

**Both Python and TypeScript now share the same PostgreSQL database!**

---

## Best Practices Learned

### 1. Virtual Environment Management
✅ **Always activate venv before running Prisma commands**
```bash
source .venv/Scripts/activate
prisma generate
```

### 2. Schema Consistency
✅ **Use ONE source of truth for schema**
- Backend owns: `prisma/schema.prisma`
- ML API uses same schema
- No separate schemas

### 3. Foreign Key Handling
✅ **Understand and respect FK constraints**
- Check schema for required FKs
- Create parent records first
- Provide all required fields

### 4. Model Naming
✅ **Follow schema naming conventions**
- PostgreSQL: `snake_case` table names
- Python: Match schema exactly
- No manual camelCase conversion

### 5. JSON Handling
✅ **Let Prisma handle JSON**
- PostgreSQL: Native JSON type
- Prisma: Automatically serializes/deserializes
- Don't manually `json.dumps()`

### 6. Migration Testing
✅ **Test thoroughly after migration**
- Test all endpoints
- Check database records
- Verify FK relationships work

---

## Maintenance

### When Backend Updates Schema

If the backend team updates `prisma/schema.prisma`:

```bash
# 1. Pull latest changes
git pull

# 2. Activate venv
source .venv/Scripts/activate

# 3. Regenerate Prisma client
prisma generate --schema=./prisma/schema.prisma

# 4. Update code if model/field names changed

# 5. Test
python test_ml_endpoints.py
```

### Regular Checks

- ✅ Prisma client version matches backend
- ✅ Schema file is in sync with backend
- ✅ All tests pass after schema updates

---

## Resources

### Documentation Created
- [POSTGRESQL_MIGRATION_COMPLETE.md](POSTGRESQL_MIGRATION_COMPLETE.md) - Migration summary
- [RESTART_INSTRUCTIONS.md](RESTART_INSTRUCTIONS.md) - Quick restart guide
- [BACKEND_INTEGRATION_GUIDE.md](BACKEND_INTEGRATION_GUIDE.md) - Backend integration
- [SETUP_CHECKLIST.md](SETUP_CHECKLIST.md) - First-time setup
- This document - Troubleshooting guide

### External Resources
- [Prisma Client Python Docs](https://prisma-client-py.readthedocs.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## Summary

### Problems Encountered
1. ❌ Prisma client not generated in venv
2. ❌ Model name mismatch (SQLite vs PostgreSQL)
3. ❌ Foreign key constraint violations

### Solutions Applied
1. ✅ Generate Prisma in activated venv
2. ✅ Update all model/field names to match backend schema
3. ✅ Handle FK constraints with proper creation order

### Final Status
✅ **Migration Complete**
✅ **All Endpoints Working**
✅ **PostgreSQL Integration Successful**
✅ **Production Ready**

---

**Last Updated:** 2026-03-09
**Status:** ✅ Resolved

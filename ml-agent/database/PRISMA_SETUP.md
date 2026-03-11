# Prisma Client Python Setup Guide

## Overview

Prisma Client Python is a fully type-safe ORM that works with both SQLite (development) and PostgreSQL (production). It provides excellent autocompletion, async support, and a clean API.

## Installation

### 1. Install Prisma Client Python

```bash
pip install prisma
```

### 2. Verify Installation

```bash
prisma --version
```

## Setup for SQLite (Development)

### 1. Configure Environment

Create `.env` file:

```env
DATABASE_URL="file:./database/catering.db"
OPENAI_API_KEY=your-openai-api-key-here
```

### 2. Generate Prisma Client

```bash
# Push schema to database and generate client
prisma db push

# Or just generate client without modifying database
prisma generate
```

This will:
- Create the SQLite database file
- Create all tables based on schema.prisma
- Generate the Python client code

### 3. Verify Setup

```bash
python database/test_prisma.py
```

## Usage Examples

### Basic Usage

```python
import asyncio
from database.prisma_client_setup import PrismaDatabaseManager

async def main():
    # Initialize database manager
    db = PrismaDatabaseManager()
    await db.connect()
    
    # Save conversation state
    await db.save_conversation_state(state)
    
    # Load conversation state
    state = await db.load_conversation_state(thread_id)
    
    # Save contract
    contract = await db.save_contract(contract_data)
    
    # Get contract
    contract = await db.get_contract(contract_id)
    
    # Disconnect
    await db.disconnect()

asyncio.run(main())
```

### Direct Prisma Client Usage

```python
from prisma import Prisma
import asyncio

async def main():
    db = Prisma()
    await db.connect()
    
    # Create conversation state
    conversation = await db.conversationstate.create(
        data={
            "conversationId": "conv-123",
            "projectId": "proj-456",
            "threadId": "thread-789",
            "currentNode": "collect_name",
            "slots": "{}",
            "messages": "[]",
            "isCompleted": False
        }
    )
    
    # Find conversation
    conversation = await db.conversationstate.find_unique(
        where={
            "conversationId": "conv-123"
        }
    )
    
    # Update conversation
    conversation = await db.conversationstate.update(
        where={
            "conversationId": "conv-123"
        },
        data={
            "currentNode": "collect_phone",
            "isCompleted": False
        }
    )
    
    # Find many with filters
    conversations = await db.conversationstate.find_many(
        where={
            "isCompleted": False,
            "projectId": "proj-456"
        },
        order={
            "updatedAt": "desc"
        },
        take=10
    )
    
    # Count
    count = await db.conversationstate.count(
        where={
            "isCompleted": False
        }
    )
    
    await db.disconnect()

asyncio.run(main())
```

### With Orchestrator

```python
from orchestrator import AgentOrchestrator
from database.prisma_client_setup import PrismaDatabaseManager
import asyncio

async def main():
    orchestrator = AgentOrchestrator()
    db = PrismaDatabaseManager()
    await db.connect()
    
    # Process message
    response = await orchestrator.process_message(
        thread_id="thread-123",
        message="My name is Sarah",
        author_id="user-456"
    )
    
    # Save to database
    await db.save_conversation_state(response.conversation_state)
    await db.save_message(
        thread_id="thread-123",
        conversation_id=response.conversation_id,
        author_id="user-456",
        author_type="user",
        content="My name is Sarah"
    )
    
    # Continue conversation
    loaded_state = await db.load_conversation_state("thread-123")
    response = await orchestrator.process_message(
        thread_id="thread-123",
        message="555-123-4567",
        author_id="user-456",
        conversation_state=loaded_state
    )
    
    await db.disconnect()

asyncio.run(main())
```

## Switching to PostgreSQL (Production)

### 1. Update schema.prisma

Change the datasource:

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

### 2. Update .env

```env
DATABASE_URL="postgresql://user:password@localhost:5432/catering_db"
```

### 3. Run Migration

```bash
# Create migration
prisma migrate dev --name init

# Or just push schema
prisma db push
```

### 4. Generate Client

```bash
prisma generate
```

That's it! Your code doesn't need to change - Prisma handles the database differences.

## Common Queries

### Find Conversations

```python
# Find by thread ID
conversation = await db.conversationstate.find_first(
    where={
        "threadId": thread_id
    }
)

# Find incomplete conversations
incomplete = await db.conversationstate.find_many(
    where={
        "isCompleted": False
    }
)

# Find by project
project_conversations = await db.conversationstate.find_many(
    where={
        "projectId": project_id
    },
    order={
        "updatedAt": "desc"
    }
)
```

### Find Contracts

```python
# Find by ID
contract = await db.contract.find_unique(
    where={
        "id": contract_id
    }
)

# Find draft contracts
drafts = await db.contract.find_many(
    where={
        "status": "draft"
    }
)

# Find by project
project_contracts = await db.contract.find_many(
    where={
        "projectId": project_id
    },
    order={
        "createdAt": "desc"
    }
)
```

### Complex Queries

```python
# Find conversations with message count
# Note: Prisma Python doesn't support joins yet, so we do this in two queries
conversations = await db.conversationstate.find_many()
for conv in conversations:
    message_count = await db.message.count(
        where={
            "threadId": conv.threadId
        }
    )
    print(f"Conversation {conv.conversationId}: {message_count} messages")

# Find contracts by date range
from datetime import datetime, timedelta

week_ago = (datetime.now() - timedelta(days=7)).isoformat()
recent_contracts = await db.contract.find_many(
    where={
        "createdAt": {
            "gte": week_ago
        }
    }
)
```

## Auto-completion

Prisma Client Python provides excellent autocompletion in supported editors:

- **VSCode** with Pylance
- **PyCharm** 2022.1+
- **Sublime Text** with LSP-Pyright
- **vim/neovim** with coc.nvim

Example:
```python
conversation = await db.conversationstate.find_unique(
    where={
        "|"  # Your editor will suggest: id, conversationId, threadId, etc.
    }
)
```

## Prisma Studio (Database GUI)

Prisma includes a visual database browser:

```bash
prisma studio
```

This opens a web interface where you can:
- View all tables
- Browse records
- Edit data
- Run queries

## Schema Changes

When you modify `schema.prisma`:

### Development (SQLite)

```bash
# Push changes to database
prisma db push

# Generate new client
prisma generate
```

### Production (PostgreSQL)

```bash
# Create migration
prisma migrate dev --name describe_your_change

# Apply migration to production
prisma migrate deploy
```

## Troubleshooting

### "Prisma Client could not be generated"

```bash
# Regenerate client
prisma generate
```

### "Database connection failed"

Check your DATABASE_URL in `.env`:
```bash
# For SQLite
DATABASE_URL="file:./database/catering.db"

# For PostgreSQL
DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

### "Module 'prisma' not found"

```bash
# Reinstall prisma
pip install --upgrade prisma

# Generate client
prisma generate
```

### Schema changes not reflected

```bash
# Push schema changes
prisma db push

# Regenerate client
prisma generate
```

## Performance Tips

1. **Use indexes**: Already defined in schema.prisma for common queries
2. **Batch operations**: Use `create_many()` for bulk inserts
3. **Connection pooling**: Prisma handles this automatically
4. **Pagination**: Use `take` and `skip` for large result sets

```python
# Pagination example
page = 1
page_size = 20

conversations = await db.conversationstate.find_many(
    skip=(page - 1) * page_size,
    take=page_size,
    order={
        "createdAt": "desc"
    }
)
```

## Advantages of Prisma Client Python

✅ **Type Safety**: Fully typed, catches errors at development time  
✅ **Autocompletion**: Excellent IDE support  
✅ **Async/Sync**: Supports both async and sync operations  
✅ **Database Agnostic**: Same code works with SQLite, PostgreSQL, MySQL  
✅ **Migrations**: Built-in migration system  
✅ **Studio**: Visual database browser  
✅ **Clean API**: Intuitive and easy to use  

## Comparison: SQLite3 vs Prisma

| Feature | SQLite3 | Prisma Client Python |
|---------|---------|---------------------|
| Type Safety | ❌ No | ✅ Yes |
| Autocompletion | ❌ No | ✅ Yes |
| Async Support | ⚠️ Manual | ✅ Built-in |
| Migrations | ❌ Manual | ✅ Automatic |
| Database Switch | ❌ Rewrite code | ✅ Change config |
| Visual Browser | ❌ No | ✅ Prisma Studio |
| Learning Curve | Low | Medium |

## Next Steps

1. ✅ Install Prisma Client Python
2. ✅ Generate client with `prisma db push`
3. ✅ Test with `python database/test_prisma.py`
4. 🔄 Use in your application
5. 🔄 Switch to PostgreSQL for production

## Resources

- [Prisma Client Python Docs](https://prisma-client-py.readthedocs.io/)
- [Prisma Schema Reference](https://www.prisma.io/docs/reference/api-reference/prisma-schema-reference)
- [GitHub Repository](https://github.com/RobertCraigie/prisma-client-py)

---

**Prisma Client Python is production-ready and recommended for this project!** 🚀

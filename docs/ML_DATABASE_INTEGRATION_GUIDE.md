# 🚨 ML ENGINEER - DATABASE INTEGRATION GUIDE 🚨

## ⚠️ CRITICAL RULES - READ FIRST ⚠️

### **YOU MUST:**
1. ✅ **USE PRISMA CLIENT ONLY** - No raw SQL queries, no other ORMs
2. ✅ **CONNECT TO LOCAL DATABASE ONLY** - Use the backend's existing connection
3. ✅ **USE THE SAME BACKEND SETUP** - Same database, same Prisma instance, same schema
4. ✅ **NEVER CREATE A SEPARATE DATABASE** - Use `caterDB_prod` database only
5. ✅ **NEVER MODIFY THE SCHEMA DIRECTLY** - All schema changes go through the backend team

### **YOU MUST NOT:**
❌ Create your own database connection
❌ Use raw SQL queries (except through Prisma's `$queryRaw` if absolutely necessary)
❌ Create a separate Prisma schema
❌ Modify the schema without approval
❌ Create your own migrations
❌ Use MongoDB, MySQL, or any other database

---

## 📋 TABLE OF CONTENTS
1. [Database Connection Setup](#1-database-connection-setup)
2. [Prisma Client Usage](#2-prisma-client-usage)
3. [Available Schema & Tables](#3-available-schema--tables)
4. [ML-Specific Tables](#4-ml-specific-tables)
5. [Common Operations](#5-common-operations)
6. [Integration with ML API](#6-integration-with-ml-api)
7. [Testing Your Integration](#7-testing-your-integration)

---

## 1. DATABASE CONNECTION SETUP

### Database Details
```env
Database Type: PostgreSQL
Host: localhost
Port: 5432
Database Name: caterDB_prod
Username: avinash
Password: Avinash@1617
Full URL: postgresql://avinash:Avinash%401617@localhost:5432/caterDB_prod
```

### Option A: Use Backend's Prisma Client (RECOMMENDED ✅)

**This is the BEST approach - your ML API calls the backend, which uses Prisma.**

```python
# In your ML API (TheCateringCompanyAgent/api.py)
# DO NOT CONNECT TO DATABASE DIRECTLY

@app.post("/staffing")
async def predict_staffing(request: dict):
    """
    The backend will call this endpoint and handle database operations.
    You ONLY return the ML predictions/calculations.
    """
    guest_count = request.get("guest_count", 0)
    event_type = request.get("event_type", "general")

    # Your ML logic here
    staffing_requirements = calculate_staffing(guest_count, event_type)

    # Return data - backend saves to database using Prisma
    return {
        "staffing_requirements": staffing_requirements,
        "confidence_score": 0.85
    }
```

**Backend handles database operations:**
```typescript
// backend/src/ml/ml.service.ts
async predictStaffing(data: StaffingInput) {
  // 1. Call your ML API
  const mlResult = await this.mlClient.post('/staffing', data);

  // 2. Save to database using Prisma
  const saved = await this.prisma.project_staff_requirements.createMany({
    data: mlResult.staffing_requirements.map(req => ({
      project_id: data.project_id,
      role: req.role,
      quantity: req.quantity,
      hours_estimated: req.hours_estimated,
      rate_per_hour: req.rate_per_hour,
      total_cost: req.total_cost,
      notes: req.reasoning,
      source: 'ai_suggested', // Enum from schema
      ai_generation_id: savedGeneration.id,
    }))
  });

  return saved;
}
```

### Option B: Direct Prisma Access from Python (ONLY IF ABSOLUTELY NECESSARY)

⚠️ **Use this ONLY if you need to read/write data directly from Python.**

#### Step 1: Install Prisma Client Python
```bash
cd TheCateringCompanyAgent
pip install prisma
```

#### Step 2: Copy Prisma Schema
```bash
# Create prisma directory in your ML project
mkdir -p TheCateringCompanyAgent/prisma

# Copy the schema from backend
cp ../cateringCo/backend/prisma/schema.prisma TheCateringCompanyAgent/prisma/schema.prisma
```

#### Step 3: Set Database URL
```bash
# TheCateringCompanyAgent/.env
DATABASE_URL="postgresql://avinash:Avinash%401617@localhost:5432/caterDB_prod"
```

#### Step 4: Generate Prisma Client
```bash
cd TheCateringCompanyAgent
prisma generate --schema=./prisma/schema.prisma
```

#### Step 5: Use in Python
```python
# TheCateringCompanyAgent/db.py
from prisma import Prisma
from contextlib import asynccontextmanager

prisma = Prisma()

@asynccontextmanager
async def get_db():
    """Database session manager"""
    await prisma.connect()
    try:
        yield prisma
    finally:
        await prisma.disconnect()

# Example usage in api.py
from db import prisma

@app.on_event("startup")
async def startup():
    await prisma.connect()

@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()

@app.post("/staffing")
async def predict_staffing(request: dict):
    project_id = request.get("project_id")
    guest_count = request.get("guest_count", 0)

    # Read project data from database
    project = await prisma.projects.find_unique(
        where={"id": project_id},
        include={
            "order_items": True,
            "project_staff_requirements": True
        }
    )

    # Your ML logic
    staffing = calculate_staffing(guest_count, project.event_date)

    # Save to database
    saved = await prisma.project_staff_requirements.create(
        data={
            "project_id": project_id,
            "role": "server",
            "quantity": 5,
            "hours_estimated": 4.0,
            "rate_per_hour": 25.00,
            "total_cost": 500.00,
            "source": "ai_suggested"
        }
    )

    return {"success": True, "data": saved}
```

---

## 2. PRISMA CLIENT USAGE

### ✅ CORRECT Examples

#### Create Record
```python
# Python
staff = await prisma.project_staff_requirements.create(
    data={
        "project_id": "uuid-here",
        "role": "server",
        "quantity": 5,
        "hours_estimated": 4.0,
        "source": "ai_suggested"
    }
)
```

```typescript
// TypeScript (Backend)
const staff = await prisma.project_staff_requirements.create({
  data: {
    projectId: "uuid-here",
    role: "server",
    quantity: 5,
    hoursEstimated: 4.0,
    source: "ai_suggested"
  }
});
```

#### Read Records
```python
# Find one
project = await prisma.projects.find_unique(
    where={"id": project_id}
)

# Find many
projects = await prisma.projects.find_many(
    where={"status": "active"},
    take=10
)

# With relations
project = await prisma.projects.find_unique(
    where={"id": project_id},
    include={
        "order_items": True,
        "project_staff_requirements": True,
        "project_portion_estimates": True
    }
)
```

#### Update Records
```python
updated = await prisma.project_staff_requirements.update(
    where={"id": staff_id},
    data={"quantity": 6}
)
```

#### Delete Records
```python
deleted = await prisma.project_staff_requirements.delete(
    where={"id": staff_id}
)
```

#### Batch Operations
```python
# Create many
created = await prisma.project_staff_requirements.create_many(
    data=[
        {"project_id": project_id, "role": "server", "quantity": 5},
        {"project_id": project_id, "role": "chef", "quantity": 2}
    ]
)

# Update many
updated = await prisma.project_upsell_items.update_many(
    where={"status": "suggested"},
    data={"status": "presented"}
)
```

### ❌ INCORRECT Examples (DO NOT DO THIS)

```python
# ❌ DO NOT use raw SQL
cursor.execute("INSERT INTO projects ...")

# ❌ DO NOT use SQLAlchemy
session.add(Project(...))

# ❌ DO NOT use psycopg2 directly
conn = psycopg2.connect(...)

# ❌ DO NOT create your own connection
engine = create_engine("postgresql://...")
```

---

## 3. AVAILABLE SCHEMA & TABLES

### Key Tables for ML Operations

#### Projects Table
```prisma
model projects {
  id                       String   @id @default(dbgenerated("gen_random_uuid()"))
  owner_user_id            String
  title                    String
  event_date               DateTime?
  guest_count              Int?
  status                   project_status // draft, active, confirmed, completed
  ai_event_summary         String?
  created_via_ai_intake    Boolean  @default(false)

  // Relations
  order_items                      order_items[]
  project_staff_requirements       project_staff_requirements[]
  project_portion_estimates        project_portion_estimates[]
  project_upsell_items             project_upsell_items[]
  project_pricing                  project_pricing[]
  ai_generations                   ai_generations[]
}
```

#### Menu Items Table
```prisma
model menu_items {
  id           String    @id
  name         String
  description  String?
  unit_cost    Decimal?
  unit_price   Decimal?
  price_type   price_type? // per_person, flat, per_unit, per_hour
  allergens    String[]
  tags         String[]
  is_upsell    Boolean   @default(false)
  active       Boolean   @default(true)
}
```

---

## 4. ML-SPECIFIC TABLES

### AI Generations Table
**Track all AI/ML predictions and their metadata**

```prisma
model ai_generations {
  id                         String           @id
  entity_type                ai_entity_type   // staffing, portions, upsell, pricing, etc.
  entity_id                  String?          // Related entity ID
  project_id                 String?
  triggered_by               String?          // User ID who triggered
  model                      String           // Your ML model name
  prompt_version             String?
  input_summary              Json?            // Input params
  output                     String?          // Model output
  output_tokens              Int?
  input_tokens               Int?
  latency_ms                 Int?
  was_applied                Boolean          @default(false)
  feedback_rating            Int?             // 1-5 star rating
  feedback_notes             String?
  created_at                 DateTime
}
```

**Usage Example:**
```python
# Save ML generation metadata
generation = await prisma.ai_generations.create(
    data={
        "entity_type": "staffing",
        "project_id": project_id,
        "model": "staffing_predictor_v2",
        "prompt_version": "1.0",
        "input_summary": {
            "guest_count": 150,
            "event_type": "wedding"
        },
        "output": json.dumps(staffing_result),
        "latency_ms": 250,
        "was_applied": True
    }
)

# Use generation_id when saving predictions
await prisma.project_staff_requirements.create(
    data={
        "project_id": project_id,
        "role": "server",
        "quantity": 5,
        "source": "ai_suggested",
        "ai_generation_id": generation.id  # Link to AI generation
    }
)
```

### Project Staff Requirements Table
**Store staffing predictions**

```prisma
model project_staff_requirements {
  id               String   @id
  project_id       String
  role             String           // "server", "chef", "bartender"
  quantity         Int
  hours_estimated  Decimal?
  rate_per_hour    Decimal?
  total_cost       Decimal?
  notes            String?
  source           source_type      // manual, ai_suggested
  ai_generation_id String?          // Link to ai_generations
  created_at       DateTime
}
```

### Project Portion Estimates Table
**Store food portion predictions**

```prisma
model project_portion_estimates {
  id               String   @id
  project_id       String
  menu_item_id     String?
  item_name        String
  guest_count      Int
  quantity         Decimal          // Amount needed
  unit             String?          // "lbs", "pieces", "portions"
  waste_factor     Decimal          // 0.10 = 10% waste
  source           source_type
  ai_generation_id String?
  created_at       DateTime
}
```

### Project Upsell Items Table
**Store AI-suggested upsells**

```prisma
model project_upsell_items {
  id                String        @id
  project_id        String
  menu_item_id      String?
  title             String
  description       String?
  estimated_revenue Decimal?
  status            upsell_status  // suggested, presented, accepted, declined
  presented_at      DateTime?
  responded_at      DateTime?
  source            source_type    // ai_suggested, manual
  ai_generation_id  String?
  created_at        DateTime
}
```

---

## 5. COMMON OPERATIONS

### Save Staffing Predictions
```python
async def save_staffing_predictions(project_id: str, staffing_data: list):
    # 1. Create AI generation record
    generation = await prisma.ai_generations.create(
        data={
            "entity_type": "staffing",
            "project_id": project_id,
            "model": "staffing_predictor_v2.1",
            "input_summary": {"guest_count": 150, "event_type": "wedding"},
            "latency_ms": 120,
            "was_applied": True
        }
    )

    # 2. Save staffing requirements
    staff_records = await prisma.project_staff_requirements.create_many(
        data=[
            {
                "project_id": project_id,
                "role": s["role"],
                "quantity": s["quantity"],
                "hours_estimated": s["hours_estimated"],
                "rate_per_hour": s["rate_per_hour"],
                "total_cost": s["total_cost"],
                "notes": s.get("reasoning"),
                "source": "ai_suggested",
                "ai_generation_id": generation.id
            }
            for s in staffing_data
        ]
    )

    return staff_records
```

### Save Portion Estimates
```python
async def save_portion_estimates(project_id: str, portions: list, guest_count: int):
    generation = await prisma.ai_generations.create(
        data={
            "entity_type": "portions",
            "project_id": project_id,
            "model": "portion_estimator_v1",
            "input_summary": {"guest_count": guest_count}
        }
    )

    await prisma.project_portion_estimates.create_many(
        data=[
            {
                "project_id": project_id,
                "item_name": p["item_name"],
                "guest_count": guest_count,
                "quantity": p["quantity"],
                "unit": p["unit"],
                "waste_factor": p.get("waste_factor", 0.10),
                "source": "ai_suggested",
                "ai_generation_id": generation.id
            }
            for p in portions
        ]
    )
```

### Save Upsell Suggestions
```python
async def save_upsell_suggestions(project_id: str, upsells: list):
    generation = await prisma.ai_generations.create(
        data={
            "entity_type": "upsell",
            "project_id": project_id,
            "model": "upsell_recommender_v1"
        }
    )

    await prisma.project_upsell_items.create_many(
        data=[
            {
                "project_id": project_id,
                "title": u["name"],
                "description": u.get("presentation_text"),
                "estimated_revenue": u["estimated_revenue"],
                "status": "suggested",
                "source": "ai_suggested",
                "ai_generation_id": generation.id
            }
            for u in upsells
        ]
    )
```

### Read Project Data for ML Input
```python
async def get_project_context(project_id: str):
    """Get all project data needed for ML predictions"""
    project = await prisma.projects.find_unique(
        where={"id": project_id},
        include={
            "order_items": {
                "include": {
                    "menu_items": True
                }
            },
            "project_staff_requirements": True,
            "project_portion_estimates": True,
            "project_pricing": True
        }
    )

    return {
        "project_id": project.id,
        "event_date": project.event_date,
        "guest_count": project.guest_count,
        "menu_items": [item.item_name_snapshot for item in project.order_items],
        "existing_staff": project.project_staff_requirements,
        "existing_portions": project.project_portion_estimates
    }
```

---

## 6. INTEGRATION WITH ML API

### Complete Example: ML API with Database Integration

```python
# TheCateringCompanyAgent/api.py
from fastapi import FastAPI
from prisma import Prisma
from typing import Dict, List
import json

app = FastAPI()
prisma = Prisma()

@app.on_event("startup")
async def startup():
    await prisma.connect()
    print("✅ Connected to database")

@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()

@app.post("/staffing")
async def predict_staffing(request: Dict):
    """
    Calculate staffing requirements and save to database
    """
    project_id = request.get("project_id")
    guest_count = request.get("guest_count", 0)
    event_type = request.get("event_type", "general")
    service_style = request.get("service_style", "buffet")
    duration = request.get("event_duration_hours", 4)

    # ML calculation
    servers_per_guest = 15 if service_style == "plated" else 20
    servers = max(2, guest_count // servers_per_guest)
    bartenders = max(1, guest_count // 75)
    cooks = max(2, guest_count // 50)

    staffing_requirements = [
        {
            "role": "server",
            "quantity": servers,
            "hours_estimated": duration,
            "rate_per_hour": 25.00,
            "total_cost": servers * duration * 25,
            "reasoning": f"1 server per {servers_per_guest} guests"
        },
        {
            "role": "bartender",
            "quantity": bartenders,
            "hours_estimated": duration,
            "rate_per_hour": 28.00,
            "total_cost": bartenders * duration * 28,
            "reasoning": "1 bartender per 75 guests"
        },
        {
            "role": "chef",
            "quantity": cooks,
            "hours_estimated": duration + 2,
            "rate_per_hour": 35.00,
            "total_cost": cooks * (duration + 2) * 35,
            "reasoning": f"Kitchen staff for {guest_count} guests"
        }
    ]

    # Save to database
    if project_id:
        # 1. Create AI generation record
        generation = await prisma.ai_generations.create(
            data={
                "entity_type": "staffing",
                "project_id": project_id,
                "model": "staffing_predictor_v2",
                "input_summary": {
                    "guest_count": guest_count,
                    "event_type": event_type,
                    "service_style": service_style
                },
                "output": json.dumps(staffing_requirements),
                "latency_ms": 50,
                "was_applied": True
            }
        )

        # 2. Save staff requirements
        await prisma.project_staff_requirements.create_many(
            data=[
                {
                    "project_id": project_id,
                    "role": s["role"],
                    "quantity": s["quantity"],
                    "hours_estimated": s["hours_estimated"],
                    "rate_per_hour": s["rate_per_hour"],
                    "total_cost": s["total_cost"],
                    "notes": s["reasoning"],
                    "source": "ai_suggested",
                    "ai_generation_id": generation.id
                }
                for s in staffing_requirements
            ]
        )

    return {
        "staffing_requirements": staffing_requirements,
        "total_staffing_cost": sum(s["total_cost"] for s in staffing_requirements),
        "confidence_score": 0.85
    }


@app.post("/portions")
async def estimate_portions(request: Dict):
    """
    Estimate food portions and save to database
    """
    project_id = request.get("project_id")
    guest_count = request.get("guest_count", 0)
    menu_items = request.get("menu_items", [])

    portions = []
    for item in menu_items:
        category = item.get("category", "entree")

        if category == "appetizer":
            quantity = guest_count * 3
            unit = "pieces"
        elif category == "entree":
            quantity = guest_count * 1.5
            unit = "portions"
        elif category == "side":
            quantity = guest_count * 0.5
            unit = "lbs"
        else:
            quantity = guest_count
            unit = "portions"

        portions.append({
            "item_name": item.get("name"),
            "quantity": quantity,
            "unit": unit,
            "waste_factor": 0.10
        })

    # Save to database
    if project_id:
        generation = await prisma.ai_generations.create(
            data={
                "entity_type": "portions",
                "project_id": project_id,
                "model": "portion_estimator_v1",
                "input_summary": {"guest_count": guest_count}
            }
        )

        await prisma.project_portion_estimates.create_many(
            data=[
                {
                    "project_id": project_id,
                    "item_name": p["item_name"],
                    "guest_count": guest_count,
                    "quantity": p["quantity"],
                    "unit": p["unit"],
                    "waste_factor": p["waste_factor"],
                    "source": "ai_suggested",
                    "ai_generation_id": generation.id
                }
                for p in portions
            ]
        )

    return {
        "portion_estimates": portions,
        "confidence_score": 0.80
    }
```

---

## 7. TESTING YOUR INTEGRATION

### Test Database Connection
```python
# test_db.py
from prisma import Prisma
import asyncio

async def test_connection():
    prisma = Prisma()
    await prisma.connect()

    # Test read
    projects = await prisma.projects.find_many(take=5)
    print(f"✅ Found {len(projects)} projects")

    # Test create (use a real project_id from your database)
    test_generation = await prisma.ai_generations.create(
        data={
            "entity_type": "staffing",
            "model": "test_model",
            "input_summary": {"test": True}
        }
    )
    print(f"✅ Created test generation: {test_generation.id}")

    # Clean up
    await prisma.ai_generations.delete(where={"id": test_generation.id})
    print("✅ Cleaned up test data")

    await prisma.disconnect()

asyncio.run(test_connection())
```

### Run Test
```bash
cd TheCateringCompanyAgent
python test_db.py
```

### Test Full Flow
```bash
# 1. Start your ML API
python api.py

# 2. In another terminal, test the endpoint
curl -X POST http://localhost:8000/staffing \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "YOUR_REAL_PROJECT_ID_HERE",
    "guest_count": 150,
    "event_type": "wedding",
    "service_style": "plated",
    "event_duration_hours": 4
  }'

# 3. Verify data was saved
# Check database:
psql -h localhost -U avinash -d caterDB_prod
SELECT * FROM project_staff_requirements ORDER BY created_at DESC LIMIT 5;
SELECT * FROM ai_generations ORDER BY created_at DESC LIMIT 5;
```

---

## 📝 CHECKLIST

Before deploying, verify:

- [ ] ✅ Using Prisma Client (Python or TypeScript)
- [ ] ✅ Connected to `caterDB_prod` database on localhost
- [ ] ✅ NOT creating any raw SQL queries
- [ ] ✅ NOT creating a separate database
- [ ] ✅ Saving AI generations to `ai_generations` table
- [ ] ✅ Linking predictions to `ai_generation_id`
- [ ] ✅ Using correct enum values (`ai_suggested`, `staffing`, etc.)
- [ ] ✅ Tested database connection
- [ ] ✅ Tested CRUD operations
- [ ] ✅ Verified data appears in database

---

## 🆘 TROUBLESHOOTING

### "Can't connect to database"
```bash
# Check if PostgreSQL is running
psql -h localhost -U avinash -d caterDB_prod

# Check if credentials are correct in .env
echo $DATABASE_URL

# Test connection manually
python -c "from prisma import Prisma; import asyncio; asyncio.run(Prisma().connect())"
```

### "Prisma client not found"
```bash
# Regenerate Prisma client
prisma generate --schema=./prisma/schema.prisma
```

### "Table doesn't exist"
```bash
# The schema is already migrated on the backend
# DO NOT run migrations from your ML project
# If tables are missing, contact backend team
```

---

## 📞 SUPPORT

**Questions? Issues?**
- Check existing schema: `backend/prisma/schema.prisma`
- Review backend ML service: `backend/src/ml/ml.service.ts`
- Review existing ML integration doc: `ML_INCREMENTAL_UPGRADE.md`
- Contact backend team before making any schema changes

---

## 🎯 SUMMARY

**Remember:**
1. ✅ Use Prisma Client for ALL database operations
2. ✅ Connect to `caterDB_prod` on localhost
3. ✅ Save AI metadata to `ai_generations` table
4. ✅ Link all predictions to `ai_generation_id`
5. ✅ Use the same backend setup - no separate databases!

**Your ML API should:**
- Receive requests from backend
- Perform ML calculations
- Save results to database using Prisma
- Return results to backend

**That's it! Keep it simple and follow the existing patterns.** 🚀

# ML Engineer Onboarding Guide
## FlashBack Catering Platform - Database Setup & Data Access

**Last Updated:** March 9, 2026
**Platform:** NestJS Backend + Next.js Frontend
**Database:** PostgreSQL with Prisma ORM

---

## Overview

This guide will help you set up the development environment, seed the database with test data, and understand the data structure for ML/AI features.

### Your ML/AI Responsibilities

You'll be working on:
1. **AI Conversation State Machine** - Multi-turn intake conversations
2. **Intake Form Parsing** - Extract structured data from free-form client submissions
3. **Smart Suggestions**:
   - Staff requirements calculation
   - Portion size estimation
   - Upsell item recommendations
4. **Contract Generation** - AI-assisted contract clause selection

---

## Quick Start

### 1. Prerequisites

Install the following on your machine:
- **Node.js** v18+ and npm
- **PostgreSQL** v14+
- **Git**

### 2. Clone Repository

```bash
git clone <repository-url>
cd cateringCo
```

### 3. Install Dependencies

```bash
# Backend
cd backend
npm install

# Frontend
cd ../frontend
npm install
```

### 4. Environment Setup

Create `backend/.env` file:

```env
# Database
DATABASE_URL="postgresql://postgres:your_password@localhost:5432/caterDB_prod"

# JWT
JWT_SECRET="your-super-secret-jwt-key-change-this-in-production"

# Redis (for queues)
REDIS_HOST=localhost
REDIS_PORT=6379

# AWS S3 / Cloudflare R2 (for file storage)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=flashback-catering

# Stripe (for payments)
STRIPE_SECRET_KEY=sk_test_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# AI/ML
OPENAI_API_KEY=sk-xxxxx  # For AI features you'll implement
```

### 5. Database Setup

```bash
cd backend

# Create database
psql -U postgres -c "CREATE DATABASE caterDB_prod;"

# Run schema migration
psql -U postgres -d caterDB_prod -f ../sql/schema_final_v3.sql

# Generate Prisma client
npx prisma generate
```

---

## Seeding the Database

### Step 1: Seed Roles (Required First)

```bash
# Verify roles exist
psql -U postgres -d caterDB_prod -c "SELECT * FROM roles;"

# Expected output:
# id          | description                              | domain
# ------------|------------------------------------------|----------
# collaborator| Project Collaborator                     | client
# host        | Event Host - Can create projects         | client
# staff       | FlashBack Labs Staff - Highest authority | platform
```

If roles don't exist, they should be in the schema already. If needed:
```sql
INSERT INTO roles (id, description, domain) VALUES
('staff', 'FlashBack Labs Staff - Highest authority', 'platform'),
('host', 'Event Host - Can create projects', 'client'),
('collaborator', 'Project Collaborator', 'client');
```

### Step 2: Seed Users (100 Test Users)

```bash
cd backend
npm run seed:users
```

**This creates:**
- 20 staff users (emails: `firstname.lastname.N@flashbacklabs.com`)
- 80 host users (emails: `firstname.lastname.N@gmail.com`, etc.)
- All with password: `TestPass123`

**Output:**
```
🌱 Starting user seeding...

Creating 20 staff users...
✓ 20 staff users created

Creating 80 host users...
✓ 80 host users created

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Seeding Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Staff users:  20/20
✅ Host users:   80/80
❌ Errors:       0
📧 Total users:  100/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 3: Seed Menu & Pricing (100+ Menu Items)

```bash
npm run seed:menu
```

**This creates:**
- 19 menu categories (Hors D'oeuvres, Platters, BBQ, Mexican, Italian, etc.)
- 100+ menu items with realistic pricing
- 6 pricing packages (Bronze, Silver, Gold, Platinum, Wedding packages)

**Output:**
```
🍽️  Starting menu seeding...

Creating category: Hors D'oeuvres - Beef...
  ✅ Created 5 items
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Menu Seeding Summary:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Categories created: 19/19
✅ Menu items created: 100+
❌ Errors: 0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 4: Verify Seeding

```sql
-- Check all tables
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM user_roles) as user_roles,
  (SELECT COUNT(*) FROM user_profiles) as user_profiles,
  (SELECT COUNT(*) FROM menu_categories) as categories,
  (SELECT COUNT(*) FROM menu_items) as menu_items,
  (SELECT COUNT(*) FROM pricing_packages) as packages;
```

**Expected:**
```
users | user_roles | user_profiles | categories | menu_items | packages
------|------------|---------------|------------|------------|----------
100   | 100        | 100           | 19         | 100+       | 6
```

---

## Data Structure for ML/AI Features

### 1. Users & Profiles

```sql
-- View user structure
SELECT
  u.id,
  u.email,
  u.primary_phone,
  up.profile_type,
  up.metadata,
  ur.role_id
FROM users u
JOIN user_profiles up ON u.id = up.user_id
JOIN user_roles ur ON u.id = ur.user_id
LIMIT 5;
```

**User Profile Metadata (JSONB):**
```json
{
  "first_name": "John",
  "last_name": "Smith"
}
```

### 2. Menu Items

```sql
-- View menu structure
SELECT
  mc.name as category,
  mi.name as item_name,
  mi.unit_price,
  mi.price_type,
  mi.allergens,
  mi.tags
FROM menu_items mi
JOIN menu_categories mc ON mi.category_id = mc.id
ORDER BY mc.sort_order, mi.name
LIMIT 10;
```

**Price Types:**
- `per_person` - Price per guest
- `flat` - Fixed price
- `per_unit` - Price per item
- `per_hour` - Hourly rate

**Tags:** `vegetarian`, `vegan`, `wedding`, `flowers`, `premium`

### 3. AI-Related Tables (You'll Work With These)

#### a. AI Conversation States

```sql
-- Table structure
\d ai_conversation_states;

-- Key fields:
-- - id: UUID
-- - thread_id: Links to messages thread
-- - project_id: Links to project
-- - current_node: State machine node (start, event_type, guest_count, venue, budget, review, complete)
-- - slots: JSONB - Collected data from conversation
-- - status: enum (active, paused, completed, abandoned)
```

**Slots Example (JSONB):**
```json
{
  "event_type": "wedding",
  "guest_count": 150,
  "event_date": "2026-06-15",
  "venue_preference": "outdoor",
  "budget_range": "5000-7000",
  "dietary_restrictions": ["vegetarian", "gluten-free"],
  "preferences": {
    "cuisine": "italian",
    "service_style": "buffet"
  }
}
```

#### b. Intake Form Submissions

```sql
-- Table structure
\d intake_submissions;

-- Key fields:
-- - id: UUID
-- - template_id: Links to intake_form_templates
-- - submitter_user_id: Who submitted
-- - submission_data: JSONB - Raw form responses
-- - parsed_data: JSONB - AI-extracted structured data
-- - status: enum (submitted, parsing, parsed, error)
-- - confidence_score: NUMERIC - AI confidence (0-100)
```

**Your Job:** Parse `submission_data` → extract structured `parsed_data`

**Example:**
```json
{
  "submission_data": {
    "event_description": "We're planning a wedding reception for about 120 people in June. We want Italian food, maybe a pasta bar, and definitely vegetarian options.",
    "budget": "around 6000 dollars",
    "contact": "Call me at 555-1234"
  },
  "parsed_data": {
    "event_type": "wedding",
    "guest_count_estimate": 120,
    "guest_count_confidence": 0.95,
    "date_estimate": "2026-06",
    "date_confidence": 0.70,
    "cuisine_preferences": ["italian"],
    "service_style_suggestions": ["buffet", "pasta_bar"],
    "dietary_requirements": ["vegetarian"],
    "budget_estimate": 6000,
    "budget_confidence": 0.85,
    "contact_phone": "555-1234",
    "missing_fields": ["exact_date", "venue"]
  }
}
```

#### c. Project Staff Requirements (AI Suggestions)

```sql
-- Table structure
\d project_staff_requirements;

-- Your job: Calculate staff needs based on:
-- - Guest count
-- - Event type
-- - Service style
-- - Duration
-- - Menu complexity
```

**Example Output:**
```json
{
  "servers": { "min": 8, "max": 10, "recommended": 9 },
  "bartenders": { "min": 2, "max": 3, "recommended": 2 },
  "cooks": { "min": 3, "max": 4, "recommended": 3 },
  "reasoning": "For 150 guests with buffet service, recommend 1 server per 16-17 guests, 2 bartenders for bar service, 3 cooks for Italian menu complexity"
}
```

#### d. Project Portion Estimates

```sql
-- Table structure
\d project_portion_estimates;

-- Your job: Estimate quantities based on:
-- - Guest count
-- - Menu items selected
-- - Service style
-- - Event duration
```

#### e. Project Upsell Items

```sql
-- Table structure
\d project_upsell_items;

-- Your job: Suggest relevant upsells based on:
-- - Current menu selection
-- - Event type
-- - Budget tier
-- - Season
```

#### f. AI Generations Audit Log

```sql
-- Table structure
\d ai_generations;

-- Log every AI call:
-- - entity_type: 'contract', 'pricing', 'staffing', 'portions', 'upsells'
-- - model_used: 'gpt-4', 'claude-3', etc.
-- - prompt_tokens, completion_tokens
-- - latency_ms
-- - feedback_rating: User rating of AI output
```

---

## API Endpoints You'll Use

### Authentication
```bash
# Login
POST /api/auth/login
{
  "email": "john.smith.0@flashbacklabs.com",
  "password": "TestPass123"
}

# Returns: { accessToken, refreshToken, user }
```

### Projects
```bash
# Get all projects for user
GET /api/projects
Headers: { Cookie: app_jwt=<token> }

# Get single project
GET /api/projects/:id

# Create project
POST /api/projects
{
  "title": "Smith Wedding",
  "eventDate": "2026-06-15",
  "guestCount": 150
}
```

### Messages (AI Conversation)
```bash
# Get thread messages
GET /api/messages/thread/:threadId

# Send message (user or AI)
POST /api/messages
{
  "threadId": "uuid",
  "projectId": "uuid",
  "content": "What's your guest count?",
  "senderType": "system"  // or "user"
}
```

### Menu
```bash
# Get all menu categories
GET /api/menu/categories

# Get menu items
GET /api/menu/items?category=hors-doeuvres

# Get menu items by tag
GET /api/menu/items?tags=vegetarian
```

---

## Your ML Development Workflow

### 1. Set Up Python Environment (if needed)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install ML libraries
pip install openai langchain pandas numpy scikit-learn
pip install psycopg2-binary  # For direct DB access if needed
```

### 2. Create AI Service Module

You'll create: `backend/src/ai/ai.service.ts`

**Key Methods to Implement:**

```typescript
// 1. Multi-turn conversation
async processConversationTurn(
  conversationId: string,
  userMessage: string
): Promise<{ aiResponse: string; nextNode: string; updatedSlots: any }>;

// 2. Parse intake form
async parseIntakeSubmission(
  submissionId: string
): Promise<{ parsedData: any; confidence: number }>;

// 3. Calculate staff requirements
async calculateStaffing(
  projectId: string
): Promise<StaffRequirements>;

// 4. Estimate portions
async estimatePortions(
  projectId: string,
  menuItems: string[]
): Promise<PortionEstimates>;

// 5. Suggest upsells
async suggestUpsells(
  projectId: string
): Promise<UpsellSuggestion[]>;
```

### 3. Test Your AI Features

```bash
# Start backend
cd backend
npm run start:dev

# In another terminal, test endpoints
curl -X POST http://localhost:3001/api/ai/parse-intake \
  -H "Content-Type: application/json" \
  -d '{"submissionId": "uuid-here"}'
```

---

## Sample Data Access Patterns

### Get Project with Menu Items
```sql
SELECT
  p.id,
  p.title,
  p.event_date,
  p.guest_count,
  json_agg(json_build_object(
    'item_name', mi.name,
    'unit_price', mi.unit_price,
    'quantity', oi.quantity
  )) as ordered_items
FROM projects p
LEFT JOIN order_items oi ON p.id = oi.project_id
LEFT JOIN menu_items mi ON oi.menu_item_id = mi.id
WHERE p.id = 'project-uuid'
GROUP BY p.id;
```

### Get All Vegetarian Menu Items
```sql
SELECT
  mc.name as category,
  mi.name,
  mi.unit_price,
  mi.description
FROM menu_items mi
JOIN menu_categories mc ON mi.category_id = mc.id
WHERE 'vegetarian' = ANY(mi.tags)
ORDER BY mc.sort_order, mi.unit_price;
```

### Get User's Recent Messages
```sql
SELECT
  m.content,
  m.sender_type,
  m.created_at,
  u.email as author_email
FROM messages m
JOIN users u ON m.author_id = u.id
WHERE m.thread_id = 'thread-uuid'
ORDER BY m.created_at ASC;
```

---

## Files to Review

### Critical Files for ML Work

1. **Database Schema:**
   - `sql/schema_final_v3.sql` - Full database structure
   - Tables: `ai_conversation_states`, `ai_generations`, `intake_submissions`, `project_staff_requirements`, `project_portion_estimates`, `project_upsell_items`

2. **Prisma Schema:**
   - `backend/prisma/schema.prisma` - ORM models

3. **Backend Services:**
   - `backend/src/messages/messages.service.ts` - Message handling
   - `backend/src/projects/projects.service.ts` - Project logic

4. **Seed Scripts (for understanding data structure):**
   - `backend/src/scripts/seed-users.ts`
   - `backend/src/scripts/seed-menu.ts`

5. **Documentation:**
   - `DATABASE_SEEDING.md` - Complete seeding guide
   - `MANUAL_SETUP_GUIDE.md` - Setup instructions
   - `TROUBLESHOOTING_GUIDE.md` - Common issues

---

## Environment Variables Needed

Create `backend/.env` with these ML-specific vars:

```env
# OpenAI (or your preferred LLM)
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_MAX_TOKENS=2000

# Vector Database (for RAG if needed)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-qdrant-key

# Or Pinecone
PINECONE_API_KEY=xxxxx
PINECONE_ENVIRONMENT=us-west1-gcp
PINECONE_INDEX=flashback-catering
```

---

## Expected Deliverables

### Phase 1: Intake Form Parsing
- [ ] Parse free-form text submissions
- [ ] Extract: event_type, guest_count, date, budget, dietary requirements
- [ ] Return confidence scores
- [ ] Handle missing/ambiguous data

### Phase 2: Conversation State Machine
- [ ] Multi-turn conversation flow (start → event_type → guest_count → venue → budget → review → complete)
- [ ] Slot filling with validation
- [ ] Context-aware responses
- [ ] Handle user corrections

### Phase 3: Smart Suggestions
- [ ] Staff requirements calculator
- [ ] Portion size estimator
- [ ] Upsell recommender based on menu/event context

### Phase 4: Contract Generation Support
- [ ] Clause selection based on event details
- [ ] Dynamic contract generation
- [ ] Integration with contract templates

---

## Testing Your Work

### 1. Unit Tests

```typescript
// backend/src/ai/ai.service.spec.ts
describe('AiService', () => {
  it('should parse intake form correctly', async () => {
    const result = await aiService.parseIntakeSubmission('submission-id');
    expect(result.parsedData.guest_count).toBeGreaterThan(0);
    expect(result.confidence).toBeGreaterThan(0.7);
  });
});
```

### 2. Integration Tests

```bash
# Test with real seeded data
npm run test:e2e
```

### 3. Manual Testing

```bash
# Start backend
npm run start:dev

# Start frontend
cd ../frontend
npm run dev

# Test conversation at: http://localhost:3000/projects/{id}/conversation
```

---

## Getting Help

- **Database Questions:** Check `DATABASE_SEEDING.md`
- **Setup Issues:** Check `TROUBLESHOOTING_GUIDE.md`
- **API Questions:** Check backend controllers in `backend/src/`
- **Schema Questions:** Review `sql/schema_final_v3.sql`

---

## Quick Command Reference

```bash
# Seed everything
cd backend
npm run seed:users   # 100 users
npm run seed:menu    # Menu items & pricing

# Start services
npm run start:dev    # Backend on :3001
cd ../frontend && npm run dev  # Frontend on :3000

# Database access
psql -U postgres -d caterDB_prod

# Verify data
psql -U postgres -d caterDB_prod -c "
SELECT
  (SELECT COUNT(*) FROM users) as users,
  (SELECT COUNT(*) FROM menu_items) as menu_items,
  (SELECT COUNT(*) FROM projects) as projects;
"
```

---

## Next Steps

1. ✅ Set up local environment
2. ✅ Run database seeding
3. ✅ Review schema and data structure
4. ✅ Create `ai.service.ts` module
5. ✅ Implement Phase 1: Intake Form Parsing
6. ✅ Test with seeded data
7. ✅ Deploy to staging environment

---

**Welcome to the FlashBack Catering Platform! 🎉**

If you have questions, reach out to the team. All seeded data is safe to modify/delete for testing purposes.

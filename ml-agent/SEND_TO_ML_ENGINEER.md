# Files to Send to ML Engineer

## Critical Documentation Files

1. **ML_ENGINEER_ONBOARDING.md** - Complete setup guide
2. **DATABASE_SEEDING.md** - Database seeding instructions
3. **TROUBLESHOOTING_GUIDE.md** - Common issues
4. **MANUAL_SETUP_GUIDE.md** - Manual setup steps

## Code Files

### Database Schema
- `sql/schema_final_v3.sql` - Complete PostgreSQL schema
- `backend/prisma/schema.prisma` - Prisma ORM models

### Seed Scripts (for understanding data structure)
- `backend/src/scripts/seed-users.ts`
- `backend/src/scripts/seed-menu.ts`

### Backend Code Samples
- `backend/src/messages/messages.service.ts`
- `backend/src/projects/projects.service.ts`
- `backend/src/auth/auth.service.ts`
- `backend/package.json`

## Environment Setup

Create `backend/.env`:

```env
DATABASE_URL="postgresql://postgres:password@localhost:5432/caterDB_prod"
JWT_SECRET="your-secret-key"
REDIS_HOST=localhost
REDIS_PORT=6379

# AI/ML
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_MAX_TOKENS=2000
```

## Quick Start Commands

```bash
# 1. Clone and install
cd backend
npm install

# 2. Set up database
psql -U postgres -c "CREATE DATABASE caterDB_prod;"
psql -U postgres -d caterDB_prod -f ../sql/schema_final_v3.sql

# 3. Seed data
npm run seed:users   # Creates 100 test users
npm run seed:menu    # Creates menu items & pricing

# 4. Start development
npm run start:dev    # Backend on :3001
```

## Node.js AI Packages Needed

```bash
cd backend
npm install openai langchain @langchain/openai zod
```

## Python Requirements (Optional)

If using Python for ML work, create `ml-service/requirements.txt`:

```txt
openai==1.12.0
langchain==0.1.9
pandas==2.2.0
numpy==1.26.4
psycopg2-binary==2.9.9
fastapi==0.109.2
python-dotenv==1.0.1
```

## Key Tables for ML Work

- `ai_conversation_states` - Multi-turn conversation tracking
- `ai_generations` - AI audit log
- `intake_submissions` - Form parsing input/output
- `project_staff_requirements` - Staff calculator output
- `project_portion_estimates` - Portion calculator output
- `project_upsell_items` - Upsell suggestions
- `menu_items` - 100+ catering menu items
- `users` - 100 test users (20 staff, 80 hosts)

## ML Features to Implement

### Phase 1: Intake Form Parsing
Parse free-form client submissions → extract structured data with confidence scores

### Phase 2: Conversation State Machine
Multi-turn conversation: start → event_type → guest_count → venue → budget → review → complete

### Phase 3: Smart Suggestions
- Staff requirements calculator
- Portion size estimator
- Upsell recommender

### Phase 4: Contract Generation
AI-assisted clause selection and contract generation

## Test Data Available

After seeding:
- 100 users (password: `TestPass123`)
  - Staff: `firstname.lastname.0-19@flashbacklabs.com`
  - Hosts: `firstname.lastname.0-79@gmail.com`
- 19 menu categories
- 100+ menu items ($1.25 - $275)
- 6 pricing packages

## Sample API Endpoints to Create

```typescript
POST /api/ai/parse-intake          // Parse intake form
POST /api/ai/conversation/turn     // Process conversation turn
POST /api/ai/suggest/staffing      // Calculate staff needs
POST /api/ai/suggest/portions      // Estimate portions
POST /api/ai/suggest/upsells       // Recommend upsells
```

## Documentation Access

All files listed above are in the repository. Send the entire `cateringCo` folder or a ZIP with:
- Root documentation files (*.md)
- `sql/` folder
- `backend/src/` folder
- `backend/prisma/schema.prisma`
- `backend/package.json`

---

**For full details, see ML_ENGINEER_ONBOARDING.md**

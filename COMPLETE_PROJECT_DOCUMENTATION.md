# 🎯 CateringCo Platform - Complete Project Documentation

**Version:** 1.0
**Last Updated:** March 10, 2026
**Status:** (Phase 1 MVP)

---

## 📑 Table of Contents

1. [Executive Summary](#executive-summary)
2. [Project Architecture](#project-architecture)
3. [Tech Stack](#tech-stack)
4. [Data Flow](#data-flow)
5. [User Flows](#user-flows)
6. [Database Schema](#database-schema)
7. [Business Rules](#business-rules)
8. [API Documentation](#api-documentation)
9. [Frontend Architecture](#frontend-architecture)
10. [Backend Architecture](#backend-architecture)
11. [ML Agent System](#ml-agent-system)
12. [Staff Dashboard Features](#staff-dashboard-features)
13. [Authentication & Authorization](#authentication--authorization)
14. [Real-time Communication](#real-time-communication)
15. [Background Workers](#background-workers)
16. [Development Setup](#development-setup)
17. [Deployment](#deployment)
18. [Testing](#testing)

---

### Key Features
- ✅ **AI Lead Intake** - Conversational AI agent with 27-node slot-filling dialogue
- ✅ **Real-time Chat** - Slack-like threaded messaging with WebSocket support
- ✅ **Contract Management** - AI-generated contracts with versioning and e-signatures
- ✅ **Staff Dashboard** - Pricing override, contract approval, menu management, chat monitoring
- ✅ **CRM Pipeline** - Lead management with scoring and risk detection
- ✅ **Payment Integration** - Stripe-gated payment processing with deposit automation
- ✅ **Background Workers** - BullMQ job processing for PDFs, notifications, webhooks
- ✅ **Role-Based Access** - Staff, Host, Collaborator roles with permissions

### System Stats
- **21/21 Tests Passing** (ML Agent)
- **33 Database Tables** (PostgreSQL)
- **8+ REST API Endpoints** (Backend)
- **10+ ML Tools** (Pricing, Staffing, Upsells)
- **100% Type Safety** (TypeScript + Prisma)

---

## 🏗️ Project Architecture

### High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend       │────▶│   ML Agent      │
│   Next.js 16    │     │   NestJS        │     │   Python        │
│   React 19      │     │   Prisma ORM    │     │   LangGraph     │
│   Port: 3000    │     │   Port: 3001    │     │   Port: 8000    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                       │                        │
         │                       ▼                        │
         │              ┌─────────────────┐              │
         │              │   PostgreSQL    │◀─────────────┘
         │              │   Port: 5432    │
         │              └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│   Socket.io     │     │   Background    │
│   Real-time     │     │   Workers       │
│   WebSocket     │     │   BullMQ        │
└─────────────────┘     └─────────────────┘
                                │
                                ▼
                        ┌─────────────────┐
                        │     Redis       │
                        │   Port: 6379    │
                        └─────────────────┘
```

### Service Breakdown

| Service | Technology | Port | Purpose |
|---------|-----------|------|---------|
| **Frontend** | Next.js 16, React 19, Tailwind CSS 4 | 3000 | User interface |
| **Backend** | NestJS, Prisma, PostgreSQL | 3001 | Business logic, API |
| **ML Agent** | Python, LangGraph, OpenAI GPT-4 | 8000 | AI conversation agent |
| **Database** | PostgreSQL 16 | 5432 | Data persistence |
| **Redis** | Redis 7 | 6379 | Queue management, cache |
| **Workers** | Node.js, BullMQ | N/A | Background jobs |

---

## 💻 Tech Stack

### Frontend
- **Framework:** Next.js 16 (App Router)
- **UI Library:** React 19
- **Styling:** Tailwind CSS 4
- **State Management:** Zustand
- **Data Fetching:** TanStack Query (React Query)
- **Real-time:** socket.io-client
- **Form Handling:** React Hook Form
- **Notifications:** Sonner (toast notifications)

### Backend
- **Framework:** NestJS
- **ORM:** Prisma
- **Database:** PostgreSQL 16
- **Authentication:** JWT (HTTP-only cookies)
- **Password Hashing:** argon2
- **Real-time:** socket.io
- **Queue:** BullMQ (Redis-backed)
- **Validation:** class-validator

### ML Agent
- **Language:** Python 3.11+
- **AI Framework:** LangGraph (state machine)
- **LLM:** OpenAI GPT-4 Turbo
- **Conversation:** 27-node slot-filling dialogue
- **Tools:** 8 AI tools (pricing, staffing, upsells, etc.)
- **API:** FastAPI
- **Database:** Prisma Client Python (or direct SQL)

### Background Workers
- **Runtime:** Node.js
- **Queue:** BullMQ
- **Jobs:** PDF generation (Puppeteer), webhooks, notifications, virus scanning, pricing
- **Concurrency:** Multiple workers for each queue

### Infrastructure
- **Docker:** Docker Compose for local development
- **CI/CD:** GitHub Actions
- **File Storage:** Cloudflare R2 (S3-compatible)
- **Email:** SendGrid (or mock in dev)
- **Payments:** Stripe (optional, gated)

---

## 🔄 Data Flow

### 1. Lead Intake Flow (ML Agent)

```
User Message
    │
    ▼
Frontend (Chat UI)
    │
    ▼
Backend API (POST /api/ml/chat)
    │
    ▼
ML Agent (Python/LangGraph)
    │
    ├─▶ Slot Extraction (OpenAI Function Calling)
    ├─▶ Validation (Business Rules)
    ├─▶ State Management (27 Nodes)
    │
    ▼
AI Response Generated
    │
    ▼
Backend Saves to Database
    ├─▶ conversation_states table
    ├─▶ messages table
    ├─▶ ai_generations table (audit)
    │
    ▼
Frontend Receives Response
    │
    ▼
User Sees AI Reply
```

### 2. Contract Generation Flow

```
All Slots Filled (17/17)
    │
    ▼
ML Agent Triggers Contract Generation
    │
    ├─▶ Pricing Calculator Tool
    │   └─▶ Query menu_items, pricing_packages
    │       └─▶ Calculate total with tax, gratuity
    │
    ├─▶ Upsell Suggestions Tool
    │   └─▶ AI generates event-specific upsells
    │
    ├─▶ Staffing Calculator Tool
    │   └─▶ Calculate servers, bartenders based on guest count
    │
    ├─▶ Margin Calculator Tool
    │   └─▶ Calculate profit margins, issue warnings
    │
    └─▶ Risk Detection Tool
        └─▶ Flag missing info, large events, outdoor venues
    │
    ▼
Contract JSON Generated
    │
    ▼
Backend Saves Contract
    ├─▶ contracts table
    ├─▶ contract_clauses table
    │
    ▼
Background Worker Generates PDF
    │
    ▼
Contract Ready for Client Review
```

### 3. Real-time Message Flow

```
User Types Message
    │
    ▼
Frontend (MessageInput Component)
    │
    ├─▶ Sends "typing" indicator via WebSocket
    │   └─▶ socket.emit('message.typing')
    │
    ▼
User Sends Message (Enter key)
    │
    ▼
Frontend API Call
    │
    └─▶ POST /api/threads/{threadId}/messages
    │
    ▼
Backend (MessagesController)
    │
    ├─▶ Extract @mentions
    ├─▶ Save to messages table
    │
    ▼
Backend Emits WebSocket Events
    │
    ├─▶ Emit to thread room: "message.created"
    ├─▶ Emit to project room: "message.created"
    └─▶ Emit to mentioned users: "message.mentioned"
    │
    ▼
All Connected Clients Receive Update
    │
    ▼
Frontend Updates UI (MessageList)
    │
    └─▶ New message appears in chat
```

### 4. Payment Flow (Stripe)

```
Contract Signed
    │
    ▼
Backend Auto-Generates Payment Schedule
    ├─▶ Deposit (50%): Due immediately
    ├─▶ Balance (50%): Due 21 days before event
    │
    ▼
Backend Creates Payment Intent
    │
    └─▶ POST /api/payments/create-intent
        │
        ├─▶ If STRIPE_ENABLED=false: Mock mode
        ├─▶ If STRIPE_ENABLED=true: Stripe API call
        │
        ▼
Frontend Receives Client Secret
    │
    ▼
Stripe Elements UI Shown
    │
    ▼
Client Enters Card Details
    │
    ▼
Stripe Processes Payment
    │
    ▼
Stripe Webhook: payment_intent.succeeded
    │
    ▼
Backend Webhook Handler
    │
    ├─▶ Verify webhook signature
    ├─▶ Save to webhook_events table
    ├─▶ Enqueue background job
    │
    ▼
Background Worker Processes Webhook
    │
    ├─▶ Update payments table (status: completed)
    ├─▶ Create event record
    ├─▶ Send confirmation email
    ├─▶ Emit WebSocket: payment.updated
    │
    ▼
Client Sees Payment Confirmation
```

---

## 👤 User Flows

### Flow 1: New Client Onboarding

1. **Client lands on website** → Clicks "Get Started"
2. **AI agent greeting** → "Hello! I'm thrilled to help you plan your event."
3. **Slot-by-slot collection:**
   - Name → "May I have your first and last name?"
   - Event date → "When is your event?"
   - Service type → "Would you prefer drop-off or on-site service?"
   - Event type → "Is this a wedding, corporate event, birthday, or social gathering?"
   - Venue → "Where will the event take place?"
   - Guest count → "How many guests are you expecting?"
   - Menu selections → AI suggests dishes based on event type
   - Add-ons → Appetizers, desserts, utensils, rentals
   - Special requests → Dietary restrictions, allergies
5. **Contract generation** → AI generates contract with pricing
6. **Client reviews contract** → Can request modifications
7. **Client signs contract** → DocuSign/HelloSign integration
8. **Deposit payment** → Stripe payment intent created
9. **Confirmation email** → Client receives contract + receipt
10. **Project created** → Staff can now manage event

### Flow 2: Staff Managing a Project

1. **Staff logs in** → Dashboard shows all projects
2. **Selects project** → Views project details, contract, messages
3. **Opens chat** → Can message client
4. **Updates project details** → Changes guest count or menu
5. **AI re-calculates pricing** → Backend calls ML agent
6. **Generates new contract version** → Version 2 created
7. **Sends to client** → Client receives updated contract
8. **Client approves** → Contract signed, payment schedule updated

### Flow 3: Client Modifying Event Details

1. **Client in AI chat** → Initial conversation completed
2. **Client wants to change guest count** → Types: `@AI change guest count to 200`
3. **AI detects modification** → Multi-layered disambiguation:
   - Layer 1: Keyword match for "guest count"
   - Layer 2: LLM semantic understanding
   - Layer 3: Combined confidence score
4. **AI updates slot** → `guest_count: 200`
5. **AI confirms change** → "I've updated the guest count to 200."
6. **Pricing recalculated** → Backend triggers pricing recalc job
7. **New pricing shown** → Client sees updated total
8. **Contract regenerated** → New version created
9. **Client approves** → Process continues

### Flow 4: Payment Collection

1. **Contract signed** → Deposit payment schedule created
2. **Client receives email** → "Your deposit of $4,250 is due"
3. **Client clicks payment link** → Opens Stripe-hosted payment page
4. **Client enters card** → Stripe Elements securely handles card data
5. **Payment processed** → Stripe webhook: `payment_intent.succeeded`
6. **Backend updates status** → `payments.status = 'completed'`
7. **Confirmation email sent** → Client + staff notified
8. **30 days before event** → Automated reminder: "Balance due in 30 days"
9. **7 days before event** → Automated reminder: "Balance due in 7 days"
10. **Balance paid** → Event ready to proceed

---

## 🗄️ Database Schema

### Schema Overview

**Total Tables:** 33 tables
**Primary Database:** PostgreSQL 16
**ORM:** Prisma
**Migrations:** Prisma Migrate

### Core Entities

#### 1. Users & Identity (5 tables)

```sql
-- users: Core user accounts
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  primary_phone VARCHAR(50),
  secondary_phone VARCHAR(50),
  status user_status DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- user_profiles: Extended user info
CREATE TABLE user_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  profile_type profile_type NOT NULL, -- 'staff' | 'client'
  metadata JSONB, -- {first_name, last_name, company_name}
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- roles: Role definitions
CREATE TABLE roles (
  id VARCHAR(50) PRIMARY KEY, -- 'staff' | 'host' | 'collaborator'
  description TEXT,
  domain role_domain -- 'platform' | 'client'
);

-- user_roles: User role assignments
CREATE TABLE user_roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role_id VARCHAR(50) REFERENCES roles(id),
  scope role_scope DEFAULT 'global', -- 'global' | 'project'
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  UNIQUE(user_id, role_id, project_id)
);

-- sessions: Active user sessions
CREATE TABLE sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(255) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2. Projects (3 tables)

```sql
-- projects: Catering events
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  status project_status DEFAULT 'draft',
  owner_id UUID REFERENCES users(id),
  signed_contract_id UUID REFERENCES contracts(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- project_collaborators: Team members
CREATE TABLE project_collaborators (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role collaborator_role, -- 'owner' | 'editor' | 'viewer'
  added_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id, user_id)
);

-- crm_pipeline: Lead management
CREATE TABLE crm_pipeline (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  stage pipeline_stage, -- 'inquiry' | 'qualified' | 'proposal_sent' | etc.
  lead_score INTEGER CHECK (lead_score BETWEEN 0 AND 100),
  risk_level risk_level, -- 'low' | 'medium' | 'high'
  notes TEXT,
  moved_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 3. Messaging (3 tables)

```sql
-- threads: Conversation threads
CREATE TABLE threads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  title VARCHAR(255),
  created_by UUID REFERENCES users(id),
  message_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- messages: Slack-like messages
CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
  author_id UUID REFERENCES users(id),
  body TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- message_mentions: @mentions
CREATE TABLE message_mentions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id UUID REFERENCES messages(id) ON DELETE CASCADE,
  mentioned_user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(message_id, mentioned_user_id)
);
```

#### 4. Contracts (3 tables)

```sql
-- contracts: Versioned contracts
CREATE TABLE contracts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  contract_group_id UUID NOT NULL, -- Groups all versions
  version_number INTEGER NOT NULL,
  previous_version_id UUID REFERENCES contracts(id),
  title VARCHAR(255) NOT NULL,
  body JSONB NOT NULL, -- {sections, terms, slots}
  status contract_status DEFAULT 'draft',
  total_amount DECIMAL(12,2),
  pdf_path TEXT,
  docusign_envelope_id VARCHAR(255),
  ai_generated BOOLEAN DEFAULT false,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(contract_group_id, version_number)
);

-- contract_clauses: Reusable clauses
CREATE TABLE contract_clauses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  body TEXT NOT NULL,
  category clause_category, -- 'payment' | 'cancellation' | etc.
  is_required BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- change_orders: Contract modifications
CREATE TABLE change_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contract_id UUID REFERENCES contracts(id) ON DELETE CASCADE,
  title VARCHAR(255),
  description TEXT,
  amount_change DECIMAL(12,2),
  status change_order_status DEFAULT 'pending',
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 5. Menu & Pricing (3 tables)

```sql
-- menu_categories: Menu organization
CREATE TABLE menu_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  sort_order INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- menu_items: Menu catalog
CREATE TABLE menu_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id UUID REFERENCES menu_categories(id),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  unit_price DECIMAL(10,2) NOT NULL,
  price_type price_type, -- 'per_person' | 'per_item' | 'flat'
  allergens TEXT[], -- ['dairy', 'gluten', 'nuts']
  tags TEXT[], -- ['vegetarian', 'premium', 'wedding']
  is_upsell BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- pricing_packages: Event pricing packages
CREATE TABLE pricing_packages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  description TEXT,
  category pricing_category, -- 'wedding' | 'corporate' | 'standard'
  base_price DECIMAL(10,2),
  price_type price_type DEFAULT 'per_person',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 6. Payments (4 tables)

```sql
-- payment_requests: Payment intents
CREATE TABLE payment_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  contract_id UUID REFERENCES contracts(id),
  amount DECIMAL(12,2) NOT NULL,
  currency VARCHAR(3) DEFAULT 'USD',
  status payment_request_status DEFAULT 'pending',
  idempotency_key VARCHAR(255) UNIQUE,
  stripe_payment_intent_id VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- payments: Payment records
CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_request_id UUID REFERENCES payment_requests(id),
  amount DECIMAL(12,2) NOT NULL,
  status payment_status DEFAULT 'pending',
  payment_method_id UUID,
  paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- payment_schedules: Deposit & balance schedule
CREATE TABLE payment_schedules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  contract_id UUID REFERENCES contracts(id),
  sequence_number INTEGER, -- 1 = deposit, 2 = balance
  amount_due DECIMAL(12,2) NOT NULL,
  due_date DATE NOT NULL,
  status schedule_status DEFAULT 'pending',
  payment_id UUID REFERENCES payments(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- refunds: Payment refunds
CREATE TABLE refunds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id UUID REFERENCES payments(id) ON DELETE CASCADE,
  amount DECIMAL(12,2) NOT NULL,
  reason TEXT,
  status refund_status DEFAULT 'pending',
  stripe_refund_id VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 7. AI & ML (4 tables - from ML Agent)

```sql
-- ai_conversation_states: ML Agent conversation state
CREATE TABLE ai_conversation_states (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  thread_id UUID REFERENCES threads(id) ON DELETE CASCADE,
  project_id UUID REFERENCES projects(id),
  current_node VARCHAR(100), -- 'collect_name', 'select_dishes', etc.
  slots JSONB NOT NULL, -- {name, event_date, guest_count, ...}
  modification_history JSONB, -- Array of slot changes
  is_completed BOOLEAN DEFAULT false,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ai_generations: Audit log for AI operations
CREATE TABLE ai_generations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entity_type generation_entity_type, -- 'contract' | 'upsell' | 'staffing'
  project_id UUID REFERENCES projects(id),
  contract_id UUID REFERENCES contracts(id),
  model VARCHAR(100), -- 'gpt-4-turbo', 'upsell_recommender_v1'
  input_summary JSONB,
  output TEXT,
  tokens_used INTEGER,
  latency_ms INTEGER,
  was_applied BOOLEAN DEFAULT false,
  feedback_score INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- project_staff_requirements: Staffing calculations
CREATE TABLE project_staff_requirements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  role VARCHAR(50), -- 'server', 'bartender', 'chef'
  quantity INTEGER NOT NULL,
  hours_estimated DECIMAL(5,2),
  rate_per_hour DECIMAL(10,2),
  total_cost DECIMAL(12,2),
  notes TEXT,
  source staff_source, -- 'ai_suggested' | 'manual'
  ai_generation_id UUID REFERENCES ai_generations(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- project_upsell_items: Upsell suggestions
CREATE TABLE project_upsell_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  title VARCHAR(255),
  description TEXT,
  estimated_revenue DECIMAL(12,2),
  status upsell_status, -- 'suggested' | 'presented' | 'accepted' | 'declined'
  source upsell_source, -- 'ai_suggested' | 'manual'
  ai_generation_id UUID REFERENCES ai_generations(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Key Indexes

```sql
-- Performance indexes
CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_messages_thread ON messages(thread_id);
CREATE INDEX idx_contracts_project ON contracts(project_id);
CREATE INDEX idx_payments_project ON payment_requests(project_id);
CREATE INDEX idx_ai_conversation_thread ON ai_conversation_states(thread_id);
CREATE INDEX idx_ai_generations_project ON ai_generations(project_id);

-- Unique constraints
CREATE UNIQUE INDEX idx_conversation_state_thread ON ai_conversation_states(thread_id);
CREATE UNIQUE INDEX idx_contract_version ON contracts(contract_group_id, version_number);
```

---

## 📏 Business Rules

### Pricing Rules

```javascript
// From config/business_rules.py (ML Agent) + Real Contract Data
const BUSINESS_RULES = {
  // Tax & Fees (From Active Contracts)
  TAX_RATE: 0.094, // 9.4% (standard across all contracts)
  GRATUITY_RATE: 0.20, // 20% service and gratuity charge
  DEPOSIT_PERCENTAGE: 0.50, // 50% deposit due at contract signing
  BALANCE_DUE_DAYS: 21, // Balance due 3 weeks (21 days) before event
  ONSITE_SERVICE_FEE: 0.05, // 5% on full-service events

  // Payment Fees (Actual Contract Pricing)
  PAYMENT_FEES: {
    credit_card: 0.05, // 5% (some contracts 1.5%)
    mastercard: 0.035, // 3.5% (higher rate for MasterCard)
    venmo: 0.02, // 2% fee
    bank_transfer: 0.00, // No fee for checks
  },

  // Per Person Pricing (Real Contract Examples)
  PER_PERSON_RATES: {
    plated_dinner: 42.25, // Buffet dinner example (Contract: Kelly/Aaron)
    cake_cutting: 1.50, // Cake cutting service
    ceremony_setup: 1.25, // Ceremony setup/cleanup
    table_setup: 2.00, // Tables, chairs, linens setup
    preset_tables: 1.75, // Plates, napkins, cutlery preset
    cleanup_reception: 3.25, // Standard cleanup (range: $3.25-$3.75)
    late_night_snack: 7.25, // Example: Funnel cake bar
  },

  // Staffing Ratios
  STAFFING: {
    SERVER_RATIO: 20, // 1 server per 20 guests
    BARTENDER_RATIO: 75, // 1 bartender per 75 guests
    MIN_SERVERS: 2,
    MIN_BARTENDERS: 1,
    EVENT_DURATION_HOURS: 6,
    china_service_staff: 8, // 8 staff for plated china service (150 guests)
  },

  // Staff Hourly Rates (From Active Contracts)
  STAFF_RATES: {
    server_base: 30.00, // Base server rate
    server_china: 35.00, // China serving staff ($350 for 10hrs)
    bartender: 50.00, // Bartender hourly rate
    chef: 85.00, // Chef rate (3 chefs x $85/hr x 5hr = $1275)
    supervisor: 50.00, // Supervisor/additional labor
    plating_coordinator: 850.00, // Flat rate per event
    day_of_coordinator: 1300.00, // 9hrs onsite + 1hr rehearsal
    cleanup: 30.00, // Additional cleanup labor
  },

  // Fixed Fees (From Active Contracts)
  FIXED_FEES: {
    travel_short: 100.00, // Local travel (< 30 miles)
    travel_long: 450.00, // Extended travel (> 50 miles)
    trash_removal: 150.00, // Trash removal fee
    onsite_walkthrough: 150.00, // Walkthrough fee (if not providing setup)
    tasting: 50.00, // Tasting session fee
  },

  // Cost Structure
  COSTS: {
    FOOD_COST_PERCENTAGE: 0.32, // 32% of revenue
    OVERHEAD_PERCENTAGE: 0.18, // 18% of revenue
  },

  // Margin Thresholds
  MARGIN_THRESHOLDS: {
    CRITICAL: 0.20, // <20% = critical
    WARNING: 0.30, // <30% = warning
    EXCELLENT: 0.40, // >40% = excellent
  },

  // Rental Pricing
  RENTALS: {
    table: 15.00, // Per table
    chair: 5.00, // Per chair
    linen: 8.00, // Per table
    TABLE_RATIO: 8, // 1 table per 8 guests
  },

  // Guest Count Validation
  GUEST_COUNT: {
    MIN: 10,
    MAX: 10000,
    GUARANTEE_PERCENTAGE: 0.90, // 90% minimum guarantee
  },

  // Cancellation Policy (Updated from Contract: Carole/Alex)
  CANCELLATION_REFUND: {
    over_12_months: {
      date_freeze: 1000.00,
      rebooking_fee: 500.00,
      refund_percentage: 1.00, // Deposit transferable
    },
    6_to_12_months: {
      date_freeze: 1000.00,
      refund_percentage: 0.30, // 30% of deposit (minus date freeze)
    },
    under_6_months: {
      deposit_forfeited: true,
      refund_percentage: 0.00, // Only amounts above deposit refunded
    },
    under_2_weeks: {
      total_forfeited: true,
      refund_percentage: 0.00, // 100% of contract forfeited
    },
  },
};
```

---

## 📍 Current Project Implementation Status

### ✅ **FULLY IMPLEMENTED & WORKING** (Production Ready)

#### 1. Backend Infrastructure
- ✅ **NestJS Backend** - Running on port 3001
  - Auth module (JWT with HTTP-only cookies)
  - Users module
  - Projects module
  - Messages module (with @mentions support)
  - Contracts module (basic CRUD)
  - Sockets module (WebSocket gateway)
  - Workers producers (BullMQ)
- ✅ **PostgreSQL Database** - 33 tables schema deployed
- ✅ **Prisma ORM** - Full type safety
- ✅ **Database Seeding** - 100 test users, 100+ menu items, 6 pricing packages

#### 2. Frontend (Next.js 16)
- ✅ **Authentication Pages** - Login, Signup
- ✅ **Chat System** - COMPLETE
  - MessageList component
  - MessageInput component with mentions autocomplete
  - ThreadList component
  - ChatSidebar component
  - Real-time WebSocket integration
  - Toast notifications for mentions
- ✅ **CRM Dashboard** - COMPLETE
  - Pipeline view (Kanban board)
  - List view (sortable table)
  - Dashboard stats
  - 3 sample leads with mock data
- ✅ **Project Pages** - Basic structure

#### 3. ML Agent (Python/LangGraph)
- ✅ **Conversation System** - COMPLETE
  - 27-node conversation flow
  - 17-slot data collection
  - @AI modification detection
  - Natural language date parsing
- ✅ **AI Tools** - 8 tools fully implemented
  - Slot extraction
  - Slot validation
  - Modification detection
  - Pricing calculator
  - Upsell suggestions
  - Staffing calculator
  - Margin calculator
  - Risk detector
- ✅ **API Endpoints** - 8 endpoints
  - POST /chat
  - GET /conversation/{thread_id}
  - GET /contract/{contract_id}
  - GET /menu
  - GET /pricing
  - POST /pricing/calculate
  - GET /health
  - GET /version
- ✅ **Testing** - 21/21 tests passing
- ✅ **Database Integration** - Prisma Client Python ready

#### 4. Background Workers
- ✅ **BullMQ Setup** - Redis-backed queues
- ✅ **Worker Processors** - 7 processors scaffolded
  - webhooks
  - payments
  - pdf_generation
  - vector_indexing
  - notifications
  - virus_scan
  - pricing_recalc

#### 5. Infrastructure
- ✅ **Docker Compose** - PostgreSQL + Redis
- ✅ **GitHub Actions CI** - Automated builds
- ✅ **Environment Configuration** - .env setup

---

### 🚧 **PARTIALLY IMPLEMENTED** (In Progress)

#### 1. Contract System
- ✅ Database schema ready
- ✅ Basic CRUD operations
- ⚠️ PDF generation (scaffolded, needs Puppeteer implementation)
- ⚠️ Contract versioning (schema ready, logic needed)
- ❌ E-signature integration (DocuSign/HelloSign)
- ❌ Contract approval workflow (documented, not implemented)

#### 2. Payment System
- ✅ Database schema ready
- ✅ Stripe SDK installed
- ⚠️ Mock payment mode working
- ❌ Real Stripe integration (STRIPE_ENABLED=false)
- ❌ Webhook processing (worker scaffolded)
- ❌ Deposit automation
- ❌ Payment schedules

#### 3. CRM System
- ✅ Frontend UI complete (dashboard, pipeline, list view)
- ✅ Database schema ready (crm_pipeline table)
- ❌ Backend API endpoints (not implemented)
- ❌ Lead scoring logic (documented, not implemented)
- ❌ Drag-and-drop functionality (UI ready, API needed)
- ❌ Lead assignment workflow

---

### ❌ **NOT YET IMPLEMENTED** (Fully Documented)

#### 1. Staff Dashboard Features
All staff dashboard features are **fully documented** but **NOT implemented**:

- ❌ **Custom Pricing Management**
  - API endpoints documented
  - Database schema defined
  - UI mockups provided
  - **Status:** Ready for implementation

- ❌ **Contract Approval Workflow**
  - Complete workflow documented
  - 8 API endpoints specified
  - 2 new database tables defined
  - Review checklist system designed
  - **Status:** Ready for implementation

- ❌ **Menu Management System**
  - CRUD API endpoints documented
  - Database enhancements specified
  - Bulk import/export designed
  - Analytics endpoints defined
  - **Status:** Ready for implementation

- ❌ **Client Chat History & Behavior Monitoring**
  - 7 API endpoints documented
  - 3 new database tables defined
  - Sentiment analysis designed
  - Red flag detection logic specified
  - **Status:** Ready for implementation

- ❌ **Enhanced CRM Dashboard**
  - Lead scoring formula documented
  - Stage transition API specified
  - Analytics endpoints defined
  - **Status:** Backend API needed

#### 2. Advanced Features
- ❌ Attachments system (schema ready, R2/S3 integration needed)
- ❌ Notifications system (email/SMS, currently mock mode)
- ❌ Vector search (Qdrant integration for semantic search)
- ❌ Multi-language support
- ❌ Calendar integration
- ❌ Reporting dashboards

---

### 📊 Implementation Progress Summary

| Component | Schema | Backend API | Frontend UI | Testing | Status |
|-----------|--------|-------------|-------------|---------|--------|
| **Auth System** | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| **Chat System** | ✅ | ✅ | ✅ | ✅ | ✅ Complete |
| **ML Agent** | ✅ | ✅ | N/A | ✅ | ✅ Complete |
| **CRM Dashboard (Frontend)** | ✅ | ❌ | ✅ | ❌ | ⚠️ UI Only |
| **Projects** | ✅ | ⚠️ | ⚠️ | ❌ | ⚠️ Basic |
| **Contracts** | ✅ | ⚠️ | ❌ | ❌ | ⚠️ Schema Only |
| **Payments** | ✅ | ⚠️ | ❌ | ❌ | ⚠️ Mock Mode |
| **Pricing Management** | ✅ | ❌ | ❌ | ❌ | ❌ Docs Only |
| **Contract Approval** | ✅ | ❌ | ❌ | ❌ | ❌ Docs Only |
| **Menu Management** | ✅ | ❌ | ❌ | ❌ | ❌ Docs Only |
| **Chat Monitoring** | ✅ | ❌ | ❌ | ❌ | ❌ Docs Only |
| **Attachments** | ✅ | ❌ | ❌ | ❌ | ❌ Schema Only |
| **Notifications** | ✅ | ⚠️ | ❌ | ❌ | ⚠️ Mock Mode |

**Legend:**
- ✅ **Complete** - Fully implemented and tested
- ⚠️ **Partial** - Some parts implemented
- ❌ **Not Started** - Documented but not implemented

---

### 🎯 Implementation Roadmap

#### **Phase 1: Core Features** (Weeks 1-4)
**Priority: HIGH** - Complete working MVP

1. **Week 1-2: Contract System**
   - ✅ Schema (already done)
   - 🔨 Implement contract approval API endpoints
   - 🔨 Build contract approval dashboard UI
   - 🔨 PDF generation with Puppeteer
   - 🔨 Contract versioning logic

2. **Week 3: CRM Backend**
   - ✅ Schema (already done)
   - ✅ Frontend UI (already done)
   - 🔨 Implement CRM API endpoints
   - 🔨 Lead scoring logic
   - 🔨 Stage transition API

3. **Week 4: Pricing Management**
   - ✅ Schema (already done)
   - 🔨 Implement pricing override API
   - 🔨 Build pricing management UI
   - 🔨 Margin calculation integration

#### **Phase 2: Staff Tools** (Weeks 5-8)
**Priority: MEDIUM** - Staff productivity features

4. **Week 5: Menu Management**
   - ✅ Schema (already done)
   - 🔨 Implement menu CRUD API
   - 🔨 Build menu management UI
   - 🔨 Bulk import/export CSV
   - 🔨 Menu analytics

5. **Week 6-7: Chat Monitoring**
   - ✅ Schema (already done)
   - 🔨 Implement conversation analytics API
   - 🔨 Sentiment analysis integration
   - 🔨 Build chat history dashboard
   - 🔨 Staff notes system
   - 🔨 Red flag detection

6. **Week 8: Integration & Testing**
   - 🔨 End-to-end testing
   - 🔨 Bug fixes
   - 🔨 Performance optimization

#### **Phase 3: Advanced Features** (Weeks 9-12)
**Priority: LOW** - Nice-to-have enhancements

7. **Week 9: Payments**
   - ✅ Schema (already done)
   - 🔨 Enable real Stripe integration
   - 🔨 Deposit automation
   - 🔨 Payment reminder system

8. **Week 10: Attachments & Notifications**
   - 🔨 R2/S3 file upload
   - 🔨 Virus scanning integration
   - 🔨 Email/SMS notifications

9. **Week 11-12: Polish**
   - 🔨 Advanced analytics
   - 🔨 Reporting dashboards
   - 🔨 Performance optimization
   - 🔨 Documentation updates

---

### 🛠️ What's Ready to Build Right Now

#### **Immediate Next Steps** (Can start today):

1. **Contract Approval System**
   - 📄 Docs: Complete
   - 🗄️ Schema: Complete
   - 🔌 API Spec: Complete
   - 🎨 UI Mockups: Complete

2. **CRM Backend API**
   - 📄 Docs: Complete
   - 🗄️ Schema: Complete (crm_pipeline table exists)
   - 🎨 UI: Complete (dashboard already built)
 
3. **Pricing Management**
   - 📄 Docs: Complete
   - 🗄️ Schema: Complete
   - 🔌 API Spec: Complete


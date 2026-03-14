# ML Project Integration Guide
## Connecting Separate ML Agent Project with Main CateringCo Platform

**Architecture:** Two separate projects sharing one database
- **Main Project (This):** Frontend + Backend + Database
- **ML Project (Separate):** AI Agent Integration + Database Access

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT (Browser)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Next.js Frontend (Port 3000)                    │
│              Location: cateringCo/frontend/                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           NestJS Backend (Port 3001)                         │
│           Location: cateringCo/backend/                      │
│                                                              │
│   ┌─────────────────────────────────┐                       │
│   │  ML Service Client              │◄─────┐                │
│   │  (Calls ML Project APIs)        │      │                │
│   └─────────────────────────────────┘      │                │
└──────────────────┬────────────────────────┬─────────────────┘
                   │                        │
                   │                        │ HTTP Calls
                   │                        │
                   │                        ▼
                   │            ┌─────────────────────────────┐
                   │            │  ML Project (Port 8000)     │
                   │            │  Location: ml-agent/        │
                   │            │                             │
                   │            │  ┌──────────────────────┐   │
                   │            │  │ AI Agent Service     │   │
                   │            │  │ - Conversation       │   │
                   │            │  │ - Intake Parsing     │   │
                   │            │  │ - Contract Gen       │   │
                   │            │  │ - Suggestions        │   │
                   │            │  └──────────────────────┘   │
                   │            │                             │
                   │            └──────────────┬──────────────┘
                   │                           │
                   ▼                           ▼
┌──────────────────────────────────────────────────────────────┐
│              PostgreSQL Database (Port 5432)                  │
│              Database: caterDB_prod                           │
│                                                               │
│  Tables:                                                      │
│  - users, projects, messages (Main Backend)                  │
│  - ai_conversation_states (ML Project)                       │
│  - ai_generations (ML Project)                               │
│  - intake_submissions (ML Project)                           │
│  - menu_items, pricing_packages (Shared)                     │
└───────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
flashback/
├── cateringCo/                    # Main Project (THIS)
│   ├── frontend/                  # Next.js frontend
│   ├── backend/                   # NestJS backend
│   ├── sql/                       # Database schemas
│   └── *.md                       # Documentation
│
└── ml-agent/                      # ML Project (SEPARATE)
    ├── src/
    │   ├── agents/                # AI agent implementations
    │   ├── api/                   # FastAPI/Flask endpoints
    │   ├── models/                # ML model wrappers
    │   ├── services/              # Business logic
    │   └── utils/                 # Helpers
    ├── tests/
    ├── requirements.txt           # Python dependencies
    ├── .env                       # ML project environment
    └── README.md
```

---

## Setup Instructions

### Step 1: Create ML Project Directory

```bash
# Navigate to flashback folder (parent of cateringCo)
cd c:/Users/avina/projects/flashback

# Create ML project
mkdir ml-agent
cd ml-agent

# Initialize Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Create project structure
mkdir -p src/{agents,api,models,services,utils}
mkdir tests
```

### Step 2: ML Project Configuration

Create `ml-agent/.env`:

```env
# Database Connection (SAME as main project)
DATABASE_URL=postgresql://postgres:your_password@localhost:5432/caterDB_prod
DB_HOST=localhost
DB_PORT=5432
DB_NAME=caterDB_prod
DB_USER=postgres
DB_PASSWORD=your_password

# API Configuration
ML_API_HOST=0.0.0.0
ML_API_PORT=8000
ML_API_DEBUG=true

# API Authentication
ML_API_KEY=your-ml-api-secret-key-change-this
BACKEND_API_KEY=backend-to-ml-shared-secret

# OpenAI / LLM
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_MAX_TOKENS=2000

# Vector Database (if using)
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/ml-agent.log

# CORS (for development)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
```

### Step 3: Install ML Project Dependencies

Create `ml-agent/requirements.txt`:

```txt
# Web Framework
fastapi==0.109.2
uvicorn[standard]==0.27.1
pydantic==2.6.1
pydantic-settings==2.2.1

# Database
psycopg2-binary==2.9.9
sqlalchemy==2.0.27

# LLM & AI
openai==1.12.0
langchain==0.1.9
langchain-openai==0.0.5
tiktoken==0.6.0

# Vector DB (optional)
qdrant-client==1.7.3

# ML/Data
numpy==1.26.4
pandas==2.2.0

# Utils
python-dotenv==1.0.1
httpx==0.27.0
python-multipart==0.0.9

# Testing
pytest==8.0.2
pytest-asyncio==0.23.5
```

Install:
```bash
pip install -r requirements.txt
```

### Step 4: Create ML API Server

Create `ml-agent/src/api/main.py`:

```python
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="FlashBack Catering ML API",
    version="1.0.0",
    description="AI Agent Integration for CateringCo Platform"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
async def verify_api_key(x_api_key: str = Header(...)):
    expected_key = os.getenv("BACKEND_API_KEY")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# Health Check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml-agent"}


# ==================== AI ENDPOINTS ====================

# 1. Conversation Turn Processing
class ConversationTurnRequest(BaseModel):
    conversation_id: str
    user_message: str
    project_id: Optional[str] = None

class ConversationTurnResponse(BaseModel):
    ai_response: str
    next_node: str
    updated_slots: Dict[str, Any]
    confidence: float
    metadata: Dict[str, Any]

@app.post("/api/conversation/turn", response_model=ConversationTurnResponse)
async def process_conversation_turn(
    request: ConversationTurnRequest,
    api_key: str = Depends(verify_api_key)
):
    # TODO: Implement conversation state machine
    # Import your agent logic here
    from ..agents.conversation_agent import ConversationAgent

    agent = ConversationAgent()
    result = await agent.process_turn(
        conversation_id=request.conversation_id,
        user_message=request.user_message,
        project_id=request.project_id
    )

    return result


# 2. Intake Form Parsing
class IntakeParsingRequest(BaseModel):
    submission_id: str
    submission_data: Dict[str, Any]

class IntakeParsingResponse(BaseModel):
    parsed_data: Dict[str, Any]
    confidence_score: float
    field_confidence: Dict[str, float]
    missing_fields: List[str]
    metadata: Dict[str, Any]

@app.post("/api/intake/parse", response_model=IntakeParsingResponse)
async def parse_intake_form(
    request: IntakeParsingRequest,
    api_key: str = Depends(verify_api_key)
):
    # TODO: Implement intake parsing
    from ..agents.intake_parser import IntakeParser

    parser = IntakeParser()
    result = await parser.parse(request.submission_data)

    return result


# 3. Staff Requirements Prediction
class StaffingRequest(BaseModel):
    project_id: str
    guest_count: int
    event_type: str
    service_style: str
    event_duration_hours: float
    menu_complexity: Optional[str] = "moderate"

class StaffingResponse(BaseModel):
    staffing_requirements: List[Dict[str, Any]]
    total_staffing_cost: float
    confidence_score: float
    reasoning: str
    metadata: Dict[str, Any]

@app.post("/api/staffing/predict", response_model=StaffingResponse)
async def predict_staffing(
    request: StaffingRequest,
    api_key: str = Depends(verify_api_key)
):
    # TODO: Implement staffing calculator
    from ..services.staffing_calculator import StaffingCalculator

    calculator = StaffingCalculator()
    result = await calculator.calculate(
        guest_count=request.guest_count,
        event_type=request.event_type,
        service_style=request.service_style,
        duration=request.event_duration_hours
    )

    return result


# 4. Portion Estimation
class PortionRequest(BaseModel):
    project_id: str
    guest_count: int
    menu_items: List[Dict[str, Any]]
    event_type: str

class PortionResponse(BaseModel):
    portion_estimates: List[Dict[str, Any]]
    confidence_score: float
    metadata: Dict[str, Any]

@app.post("/api/portions/estimate", response_model=PortionResponse)
async def estimate_portions(
    request: PortionRequest,
    api_key: str = Depends(verify_api_key)
):
    # TODO: Implement portion estimator
    from ..services.portion_estimator import PortionEstimator

    estimator = PortionEstimator()
    result = await estimator.estimate(
        guest_count=request.guest_count,
        menu_items=request.menu_items,
        event_type=request.event_type
    )

    return result


# 5. Upsell Suggestions
class UpsellRequest(BaseModel):
    project_id: str
    current_menu_items: List[str]
    event_type: str
    budget: float

class UpsellResponse(BaseModel):
    suggestions: List[Dict[str, Any]]
    total_potential_revenue: float
    metadata: Dict[str, Any]

@app.post("/api/upsells/suggest", response_model=UpsellResponse)
async def suggest_upsells(
    request: UpsellRequest,
    api_key: str = Depends(verify_api_key)
):
    # TODO: Implement upsell suggester
    from ..services.upsell_suggester import UpsellSuggester

    suggester = UpsellSuggester()
    result = await suggester.suggest(
        project_id=request.project_id,
        current_items=request.current_menu_items,
        event_type=request.event_type,
        budget=request.budget
    )

    return result


# 6. Contract Generation
class ContractGenerationRequest(BaseModel):
    project_id: str
    event_details: Dict[str, Any]
    menu_items: List[Dict[str, Any]]
    pricing: Dict[str, Any]
    client_info: Dict[str, Any]

class ContractGenerationResponse(BaseModel):
    contract: Dict[str, Any]
    confidence_score: float
    warnings: List[str]
    metadata: Dict[str, Any]

@app.post("/api/contracts/generate", response_model=ContractGenerationResponse)
async def generate_contract(
    request: ContractGenerationRequest,
    api_key: str = Depends(verify_api_key)
):
    # TODO: Implement contract generator
    from ..agents.contract_generator import ContractGenerator

    generator = ContractGenerator()
    result = await generator.generate(
        project_id=request.project_id,
        event_details=request.event_details,
        menu_items=request.menu_items,
        pricing=request.pricing,
        client_info=request.client_info
    )

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("ML_API_HOST", "0.0.0.0"),
        port=int(os.getenv("ML_API_PORT", 8000)),
        reload=os.getenv("ML_API_DEBUG", "false").lower() == "true"
    )
```

### Step 5: Database Access in ML Project

Create `ml-agent/src/utils/database.py`:

```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db():
    """Database session context manager"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


async def get_conversation_state(conversation_id: str):
    """Get AI conversation state from database"""
    with get_db() as db:
        query = text("""
            SELECT id, thread_id, project_id, current_node, slots, status
            FROM ai_conversation_states
            WHERE id = :conversation_id
        """)
        result = db.execute(query, {"conversation_id": conversation_id})
        return result.fetchone()


async def update_conversation_state(conversation_id: str, node: str, slots: dict):
    """Update AI conversation state"""
    with get_db() as db:
        query = text("""
            UPDATE ai_conversation_states
            SET current_node = :node,
                slots = :slots,
                updated_at = NOW()
            WHERE id = :conversation_id
        """)
        db.execute(query, {
            "conversation_id": conversation_id,
            "node": node,
            "slots": slots
        })


async def log_ai_generation(entity_type: str, entity_id: str, model: str,
                           prompt_tokens: int, completion_tokens: int,
                           latency_ms: int):
    """Log AI generation to database"""
    with get_db() as db:
        query = text("""
            INSERT INTO ai_generations
            (entity_type, entity_id, model_used, prompt_tokens,
             completion_tokens, latency_ms)
            VALUES (:entity_type, :entity_id, :model, :prompt_tokens,
                    :completion_tokens, :latency_ms)
        """)
        db.execute(query, {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "latency_ms": latency_ms
        })
```

---

## Main Backend Integration

### Step 6: Add ML Service Client to Main Backend

Create `backend/src/ml/ml.service.ts`:

```typescript
import { Injectable, HttpException, HttpStatus } from '@nestjs/common';
import axios, { AxiosInstance } from 'axios';

@Injectable()
export class MlService {
  private mlClient: AxiosInstance;

  constructor() {
    this.mlClient = axios.create({
      baseURL: process.env.ML_API_URL || 'http://localhost:8000',
      timeout: 30000,
      headers: {
        'X-API-Key': process.env.ML_API_KEY,
        'Content-Type': 'application/json',
      },
    });
  }

  // 1. Process conversation turn
  async processConversationTurn(
    conversationId: string,
    userMessage: string,
    projectId?: string,
  ) {
    try {
      const response = await this.mlClient.post('/api/conversation/turn', {
        conversation_id: conversationId,
        user_message: userMessage,
        project_id: projectId,
      });
      return response.data;
    } catch (error) {
      throw new HttpException(
        'ML service error: ' + error.message,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // 2. Parse intake form
  async parseIntakeForm(submissionId: string, submissionData: any) {
    try {
      const response = await this.mlClient.post('/api/intake/parse', {
        submission_id: submissionId,
        submission_data: submissionData,
      });
      return response.data;
    } catch (error) {
      throw new HttpException(
        'ML service error: ' + error.message,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // 3. Predict staffing requirements
  async predictStaffing(projectData: {
    project_id: string;
    guest_count: number;
    event_type: string;
    service_style: string;
    event_duration_hours: number;
  }) {
    try {
      const response = await this.mlClient.post('/api/staffing/predict', projectData);
      return response.data;
    } catch (error) {
      throw new HttpException(
        'ML service error: ' + error.message,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // 4. Estimate portions
  async estimatePortions(projectData: {
    project_id: string;
    guest_count: number;
    menu_items: any[];
    event_type: string;
  }) {
    try {
      const response = await this.mlClient.post('/api/portions/estimate', projectData);
      return response.data;
    } catch (error) {
      throw new HttpException(
        'ML service error: ' + error.message,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // 5. Suggest upsells
  async suggestUpsells(projectData: {
    project_id: string;
    current_menu_items: string[];
    event_type: string;
    budget: number;
  }) {
    try {
      const response = await this.mlClient.post('/api/upsells/suggest', projectData);
      return response.data;
    } catch (error) {
      throw new HttpException(
        'ML service error: ' + error.message,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // 6. Generate contract
  async generateContract(contractData: {
    project_id: string;
    event_details: any;
    menu_items: any[];
    pricing: any;
    client_info: any;
  }) {
    try {
      const response = await this.mlClient.post('/api/contracts/generate', contractData);
      return response.data;
    } catch (error) {
      throw new HttpException(
        'ML service error: ' + error.message,
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  // Health check
  async healthCheck() {
    try {
      const response = await this.mlClient.get('/health');
      return response.data;
    } catch (error) {
      return { status: 'unhealthy', error: error.message };
    }
  }
}
```

Create `backend/src/ml/ml.module.ts`:

```typescript
import { Module } from '@nestjs/common';
import { MlService } from './ml.service';

@Module({
  providers: [MlService],
  exports: [MlService],
})
export class MlModule {}
```

### Step 7: Update Main Backend Environment

Add to `backend/.env`:

```env
# ML Service Connection
ML_API_URL=http://localhost:8000
ML_API_KEY=backend-to-ml-shared-secret
```

### Step 8: Use ML Service in Controllers

Example: `backend/src/messages/messages.controller.ts`:

```typescript
import { Controller, Post, Body, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { MlService } from '../ml/ml.service';

@Controller('api/messages')
@UseGuards(JwtAuthGuard)
export class MessagesController {
  constructor(
    private readonly mlService: MlService,
  ) {}

  @Post('ai-response')
  async getAiResponse(
    @Body() dto: { conversationId: string; userMessage: string; projectId?: string },
  ) {
    // Call ML service to get AI response
    const aiResponse = await this.mlService.processConversationTurn(
      dto.conversationId,
      dto.userMessage,
      dto.projectId,
    );

    return aiResponse;
  }
}
```

---

## Running Both Projects

### Terminal 1: Database
```bash
# Ensure PostgreSQL is running
psql -U postgres -c "SELECT version();"
```

### Terminal 2: ML Project
```bash
cd c:/Users/avina/projects/flashback/ml-agent
source venv/bin/activate  # Windows: venv\Scripts\activate
python src/api/main.py

# Or using uvicorn directly:
uvicorn src.api.main:app --reload --port 8000
```

### Terminal 3: Main Backend
```bash
cd c:/Users/avina/projects/flashback/cateringCo/backend
npm run start:dev

# Backend runs on :3001
```

### Terminal 4: Frontend
```bash
cd c:/Users/avina/projects/flashback/cateringCo/frontend
npm run dev

# Frontend runs on :3000
```

---

## Testing the Integration

### 1. Test ML API Health

```bash
curl http://localhost:8000/health
```

Expected:
```json
{
  "status": "healthy",
  "service": "ml-agent"
}
```

### 2. Test from Backend

```bash
curl -X GET http://localhost:3001/api/ml/health \
  -H "Cookie: app_jwt=<your-jwt-token>"
```

### 3. Test Full Flow

```bash
# Login to get token
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.smith.0@flashbacklabs.com",
    "password": "TestPass123"
  }'

# Use AI conversation
curl -X POST http://localhost:3001/api/messages/ai-response \
  -H "Content-Type: application/json" \
  -H "Cookie: app_jwt=<token>" \
  -d '{
    "conversationId": "uuid",
    "userMessage": "I need catering for 150 guests",
    "projectId": "uuid"
  }'
```

---

## Deployment

### Development
- Main Backend: `http://localhost:3001`
- ML API: `http://localhost:8000`
- Frontend: `http://localhost:3000`

### Production

**Option 1: Same Server**
```
nginx reverse proxy:
  /           → Frontend (port 3000)
  /api/*      → Backend (port 3001)
  /ml/*       → ML API (port 8000)
```

**Option 2: Separate Servers**
```
Frontend:  https://catering.flashbacklabs.com
Backend:   https://api.catering.flashbacklabs.com
ML API:    https://ml.catering.flashbacklabs.com (private network)
```

---

## Environment Variables Summary

### ML Project (.env)
```env
DATABASE_URL=postgresql://user:pass@host:5432/caterDB_prod
ML_API_HOST=0.0.0.0
ML_API_PORT=8000
BACKEND_API_KEY=shared-secret
OPENAI_API_KEY=sk-xxxxx
```

### Main Backend (.env)
```env
DATABASE_URL=postgresql://user:pass@host:5432/caterDB_prod
ML_API_URL=http://localhost:8000
ML_API_KEY=shared-secret
JWT_SECRET=your-jwt-secret
```

---

## Database Tables Ownership

**Main Backend writes to:**
- users, user_profiles, user_roles
- projects, venues, events
- messages, threads
- menu_items, menu_categories
- orders, order_items
- contracts (initial creation)

**ML Project writes to:**
- ai_conversation_states
- ai_generations
- intake_submissions (parsed_data field)
- project_staff_requirements
- project_portion_estimates
- project_upsell_items
- contracts (AI-generated sections)

**Both read from:**
- menu_items, menu_categories
- projects, events
- users, user_profiles
- messages, threads

---

## Security Checklist

- [ ] Use HTTPS in production
- [ ] API key authentication between services
- [ ] Rate limiting on ML endpoints
- [ ] Input validation on all ML endpoints
- [ ] Database connection pooling
- [ ] Error handling without exposing internals
- [ ] Logging of all ML requests
- [ ] CORS configured properly
- [ ] Environment variables secured

---

## Next Steps

1. ✅ Create ML project structure
2. ✅ Set up FastAPI server
3. ✅ Configure database access
4. ✅ Create ML service client in backend
5. ✅ Implement first AI endpoint (conversation)
6. ✅ Test integration
7. ✅ Deploy both services
8. ✅ Monitor and optimize

---

**Ready to integrate! 🚀**

The ML project can now access the same database and be called from the main backend via HTTP APIs.

# Quick ML Project Setup Script

This script automates the setup of the separate ML agent project.

---

## One-Command Setup

Run this from the `flashback` directory (parent of `cateringCo`):

```bash
# Navigate to parent directory
cd c:/Users/avina/projects/flashback

# Create ML project structure
mkdir -p ml-agent/src/{agents,api,models,services,utils} ml-agent/tests ml-agent/logs

# Create Python virtual environment
cd ml-agent
python -m venv venv
```

**Activate virtual environment:**
```bash
# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

**Install dependencies:**
```bash
# Create requirements.txt (copy from ML_PROJECT_INTEGRATION.md)
pip install fastapi uvicorn[standard] pydantic pydantic-settings
pip install psycopg2-binary sqlalchemy
pip install openai langchain langchain-openai tiktoken
pip install numpy pandas python-dotenv httpx python-multipart
pip install pytest pytest-asyncio
```

**Create .env file:**
```bash
cat > .env << 'EOF'
# Database (SAME as main project)
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

# Authentication
ML_API_KEY=your-ml-api-secret-key
BACKEND_API_KEY=backend-to-ml-shared-secret

# OpenAI
OPENAI_API_KEY=sk-xxxxx
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_MAX_TOKENS=2000

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/ml-agent.log

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
EOF
```

**Create main API file:**
```bash
# Copy the FastAPI code from ML_PROJECT_INTEGRATION.md
# to src/api/main.py

# Quick test:
python src/api/main.py
```

---

## Update Main Backend

**Add to `backend/.env`:**
```env
ML_API_URL=http://localhost:8000
ML_API_KEY=backend-to-ml-shared-secret
```

**Create ML service:**
```bash
cd ../cateringCo/backend
mkdir -p src/ml
# Copy ml.service.ts and ml.module.ts from integration doc
```

**Import ML module in app.module.ts:**
```typescript
import { MlModule } from './ml/ml.module';

@Module({
  imports: [
    // ... existing imports
    MlModule,
  ],
})
export class AppModule {}
```

---

## Test the Setup

### Terminal 1: Start ML API
```bash
cd c:/Users/avina/projects/flashback/ml-agent
venv\Scripts\activate
python src/api/main.py

# Should see: Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2: Test ML API
```bash
# Health check
curl http://localhost:8000/health

# Expected: {"status":"healthy","service":"ml-agent"}
```

### Terminal 3: Start Main Backend
```bash
cd c:/Users/avina/projects/flashback/cateringCo/backend
npm run start:dev

# Should connect and run on :3001
```

### Terminal 4: Test Integration
```bash
# Test backend → ML communication
curl http://localhost:3001/api/ml/health
```

---

## Project Structure After Setup

```
flashback/
├── cateringCo/              # Main project
│   ├── frontend/            # Next.js (port 3000)
│   ├── backend/             # NestJS (port 3001)
│   │   └── src/ml/          # ← ML service client (NEW)
│   └── sql/
│
└── ml-agent/                # ← ML project (NEW)
    ├── venv/                # Python virtual env
    ├── src/
    │   ├── api/             # FastAPI endpoints (port 8000)
    │   ├── agents/          # AI agent logic
    │   ├── services/        # Business logic
    │   └── utils/           # DB helpers
    ├── tests/
    ├── logs/
    ├── .env                 # ML config
    └── requirements.txt
```

---

## Quick Reference

### Start All Services

```bash
# Terminal 1: ML API
cd ml-agent && venv\Scripts\activate && python src/api/main.py

# Terminal 2: Backend
cd cateringCo/backend && npm run start:dev

# Terminal 3: Frontend
cd cateringCo/frontend && npm run dev
```

### Check Services

```bash
# Database
psql -U postgres -d caterDB_prod -c "SELECT COUNT(*) FROM users;"

# ML API
curl http://localhost:8000/health

# Backend
curl http://localhost:3001/api/health  # (if you have this endpoint)

# Frontend
open http://localhost:3000
```

---

## Common Issues

### Issue: ML API won't start
**Solution:** Check Python version (need 3.8+) and activate venv

### Issue: Database connection refused
**Solution:** Ensure PostgreSQL is running and DATABASE_URL is correct

### Issue: Backend can't reach ML API
**Solution:**
1. Check ML_API_URL in backend/.env
2. Verify ML API is running on port 8000
3. Check firewall settings

### Issue: API key authentication fails
**Solution:** Ensure BACKEND_API_KEY matches in both .env files

---

## Next Steps

1. ✅ Set up ML project structure
2. ✅ Install Python dependencies
3. ✅ Create FastAPI endpoints
4. ✅ Configure database access
5. ✅ Add ML service to backend
6. ✅ Test integration
7. → Implement first AI agent (conversation)
8. → Test with frontend
9. → Deploy to production

---

**Setup complete! Both projects share the same database and communicate via HTTP APIs.** 🎉

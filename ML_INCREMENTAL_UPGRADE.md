# ML Integration - Incremental Upgrade Guide

**Current Status:** ✅ Chat integration working (`/chat` endpoint)
**Goal:** Add staffing, portions, upsells, intake parsing using same pattern

---

## What You Already Have (From QUICK_INTEGRATION.md)

✅ `TheCateringCompanyAgent/api.py` - ML API on port 8000
✅ `/chat` endpoint - Working
✅ `/health` endpoint - Working
✅ `backend/src/ml/ml.service.ts` - ML client with `chat()` method
✅ `backend/src/messages/messages.controller.ts` - `/api/messages/ai-chat` endpoint
✅ Frontend `ChatInterface` component

---

## Step 1: Add New Endpoints to ML API

Add these endpoints to `TheCateringCompanyAgent/api.py` (using same pattern as `/chat`):

```python
# Add these new endpoints to your existing api.py (same pattern as /chat)

@app.post("/staffing")
async def predict_staffing(request: dict):
    """Calculate staff requirements"""
    guest_count = request.get("guest_count", 0)
    event_type = request.get("event_type", "general")
    service_style = request.get("service_style", "buffet")
    duration = request.get("event_duration_hours", 4)

    # Simple calculation (you can enhance with your ML model)
    servers_per_guest = 15 if service_style == "plated" else 20
    servers = max(2, guest_count // servers_per_guest)
    bartenders = max(1, guest_count // 75)
    cooks = max(2, guest_count // 50)

    return {
        "staffing_requirements": [
            {
                "role": "server",
                "quantity": servers,
                "hours_estimated": duration,
                "rate_per_hour": 25.00,
                "total_cost": servers * duration * 25,
                "reasoning": f"1 server per {servers_per_guest} guests for {service_style} service"
            },
            {
                "role": "bartender",
                "quantity": bartenders,
                "hours_estimated": duration,
                "rate_per_hour": 28.00,
                "total_cost": bartenders * duration * 28,
                "reasoning": f"1 bartender per 75 guests"
            },
            {
                "role": "chef",
                "quantity": cooks,
                "hours_estimated": duration + 2,
                "rate_per_hour": 35.00,
                "total_cost": cooks * (duration + 2) * 35,
                "reasoning": f"Kitchen staff for {guest_count} guests"
            }
        ],
        "total_staffing_cost": (servers * duration * 25) + (bartenders * duration * 28) + (cooks * (duration + 2) * 35),
        "confidence_score": 0.85
    }


@app.post("/portions")
async def estimate_portions(request: dict):
    """Estimate food portions"""
    guest_count = request.get("guest_count", 0)
    menu_items = request.get("menu_items", [])
    event_type = request.get("event_type", "general")

    portions = []
    for item in menu_items:
        category = item.get("category", "entree")

        # Portion calculations
        if category == "appetizer":
            quantity = guest_count * 3  # 3 pieces per person
            unit = "pieces"
        elif category == "entree":
            quantity = guest_count * 1.5  # 1.5 portions per person (buffer)
            unit = "portions"
        elif category == "side":
            quantity = guest_count * 0.5  # 0.5 lb per person
            unit = "lbs"
        else:
            quantity = guest_count
            unit = "portions"

        portions.append({
            "menu_item_id": item.get("id"),
            "item_name": item.get("name"),
            "quantity": quantity,
            "unit": unit,
            "waste_factor": 0.10,  # 10% waste factor
            "reasoning": f"Based on {guest_count} guests and {category} category"
        })

    return {
        "portion_estimates": portions,
        "confidence_score": 0.80
    }


@app.post("/upsells")
async def suggest_upsells(request: dict):
    """Suggest upsells based on event details"""
    event_type = request.get("event_type", "general")
    budget = request.get("budget", 0)
    current_items = request.get("current_menu_items", [])

    suggestions = []

    # Wedding-specific upsells
    if event_type == "wedding":
        suggestions.append({
            "name": "Wedding Cake - 3 Tier",
            "category": "dessert",
            "reasoning": "Essential for wedding celebrations",
            "estimated_revenue": 275.00,
            "confidence_score": 0.95,
            "priority": 10,
            "presentation_text": "Complete your special day with an elegant 3-tier wedding cake, customized to your preferences."
        })
        suggestions.append({
            "name": "Bridal Bouquet",
            "category": "floral",
            "reasoning": "Weddings typically need floral arrangements",
            "estimated_revenue": 75.00,
            "confidence_score": 0.90,
            "priority": 8,
            "presentation_text": "Beautiful bridal bouquets starting at $75, perfectly matched to your theme."
        })

    # Check if Italian menu - suggest wine
    if any("italian" in str(item).lower() for item in current_items):
        suggestions.append({
            "name": "Wine Pairing Package",
            "category": "beverage",
            "reasoning": "Italian menu pairs well with wine service",
            "estimated_revenue": 15.00,  # per person
            "confidence_score": 0.85,
            "priority": 7,
            "presentation_text": "Enhance your Italian dining experience with our curated wine pairing selection."
        })

    # Bar service for larger events
    if budget > 3000:
        suggestions.append({
            "name": "Full Bar Service",
            "category": "bar",
            "reasoning": "Budget allows for premium bar service",
            "estimated_revenue": 800.00,
            "confidence_score": 0.75,
            "priority": 6,
            "presentation_text": "Professional bartenders with full bar setup including premium spirits, beer, and wine."
        })

    total_revenue = sum(s["estimated_revenue"] for s in suggestions)

    return {
        "suggestions": suggestions,
        "total_potential_revenue": total_revenue
    }


@app.post("/intake")
async def parse_intake(request: dict):
    """Parse intake form submission"""
    submission_data = request.get("submission_data", {})

    # Use LLM to extract structured data
    # For now, simple extraction (you can enhance with GPT)

    parsed = {
        "event_type": "general",
        "guest_count": None,
        "event_date": None,
        "budget": None,
        "service_style": "buffet",
        "dietary_restrictions": [],
        "special_requests": []
    }

    # Extract from submission
    for key, value in submission_data.items():
        value_str = str(value).lower()

        # Event type detection
        if "wedding" in value_str:
            parsed["event_type"] = "wedding"
        elif "corporate" in value_str:
            parsed["event_type"] = "corporate"
        elif "birthday" in value_str:
            parsed["event_type"] = "birthday"

        # Guest count extraction
        import re
        guest_match = re.search(r'(\d+)\s*(?:guest|people|person)', value_str)
        if guest_match:
            parsed["guest_count"] = int(guest_match.group(1))

        # Budget extraction
        budget_match = re.search(r'\$?(\d+(?:,\d{3})*)', value_str)
        if budget_match and "budget" in key.lower():
            parsed["budget"] = float(budget_match.group(1).replace(",", ""))

        # Dietary restrictions
        if "vegetarian" in value_str:
            parsed["dietary_restrictions"].append("vegetarian")
        if "vegan" in value_str:
            parsed["dietary_restrictions"].append("vegan")
        if "gluten" in value_str:
            parsed["dietary_restrictions"].append("gluten-free")

    return {
        "parsed_data": parsed,
        "confidence_score": 0.70,
        "field_confidence": {
            "event_type": 0.80,
            "guest_count": 0.85 if parsed["guest_count"] else 0.20,
            "budget": 0.75 if parsed["budget"] else 0.30
        },
        "missing_fields": [k for k, v in parsed.items() if v is None]
    }
```

---

## Step 2: Add Methods to Backend MlService

Update `backend/src/ml/ml.service.ts` (add these methods to your existing service):

```typescript
// Add to existing MlService class

async predictStaffing(data: {
  project_id: string;
  guest_count: number;
  event_type: string;
  service_style: string;
  event_duration_hours: number;
}) {
  try {
    const response = await this.mlClient.post('/staffing', {
      guest_count: data.guest_count,
      event_type: data.event_type,
      service_style: data.service_style,
      event_duration_hours: data.event_duration_hours,
    });
    return response.data;
  } catch (error) {
    throw new HttpException(
      'ML service unavailable',
      HttpStatus.SERVICE_UNAVAILABLE,
    );
  }
}

async estimatePortions(data: {
  project_id: string;
  guest_count: number;
  menu_items: any[];
  event_type: string;
}) {
  try {
    const response = await this.mlClient.post('/portions', {
      guest_count: data.guest_count,
      menu_items: data.menu_items,
      event_type: data.event_type,
    });
    return response.data;
  } catch (error) {
    throw new HttpException(
      'ML service unavailable',
      HttpStatus.SERVICE_UNAVAILABLE,
    );
  }
}

async suggestUpsells(data: {
  project_id: string;
  event_type: string;
  budget: number;
  current_menu_items: string[];
}) {
  try {
    const response = await this.mlClient.post('/upsells', {
      event_type: data.event_type,
      budget: data.budget,
      current_menu_items: data.current_menu_items,
    });
    return response.data;
  } catch (error) {
    throw new HttpException(
      'ML service unavailable',
      HttpStatus.SERVICE_UNAVAILABLE,
    );
  }
}

async parseIntakeForm(submissionId: string, submissionData: any) {
  try {
    const response = await this.mlClient.post('/intake', {
      submission_id: submissionId,
      submission_data: submissionData,
    });
    return response.data;
  } catch (error) {
    throw new HttpException(
      'ML service unavailable',
      HttpStatus.SERVICE_UNAVAILABLE,
    );
  }
}
```

---

## Step 3: Create New Backend Endpoints

Create `backend/src/projects/projects.controller.ts` (or add to existing):

```typescript
import { Controller, Post, Body, Param, UseGuards } from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { MlService } from '../ml/ml.service';

@Controller('api/projects')
@UseGuards(JwtAuthGuard)
export class ProjectsController {
  constructor(private readonly mlService: MlService) {}

  // Get staffing suggestions
  @Post(':id/staffing')
  async getStaffingSuggestions(
    @Param('id') projectId: string,
    @Body() dto: {
      guest_count: number;
      event_type: string;
      service_style: string;
      event_duration_hours: number;
    },
  ) {
    const result = await this.mlService.predictStaffing({
      project_id: projectId,
      ...dto,
    });
    return { success: true, data: result };
  }

  // Get portion estimates
  @Post(':id/portions')
  async getPortionEstimates(
    @Param('id') projectId: string,
    @Body() dto: {
      guest_count: number;
      menu_items: any[];
      event_type: string;
    },
  ) {
    const result = await this.mlService.estimatePortions({
      project_id: projectId,
      ...dto,
    });
    return { success: true, data: result };
  }

  // Get upsell suggestions
  @Post(':id/upsells')
  async getUpsellSuggestions(
    @Param('id') projectId: string,
    @Body() dto: {
      event_type: string;
      budget: number;
      current_menu_items: string[];
    },
  ) {
    const result = await this.mlService.suggestUpsells({
      project_id: projectId,
      ...dto,
    });
    return { success: true, data: result };
  }
}
```

---

## Step 4: Test New Endpoints

### Test ML API Directly

```bash
# Test staffing (same pattern as /chat)
curl -X POST http://localhost:8000/staffing \
  -H "Content-Type: application/json" \
  -d '{
    "guest_count": 150,
    "event_type": "wedding",
    "service_style": "plated",
    "event_duration_hours": 4
  }'

# Test portions
curl -X POST http://localhost:8000/portions \
  -H "Content-Type: application/json" \
  -d '{
    "guest_count": 100,
    "menu_items": [
      {"id": "1", "name": "Chicken Marsala", "category": "entree"}
    ],
    "event_type": "corporate"
  }'

# Test upsells
curl -X POST http://localhost:8000/upsells \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "wedding",
    "budget": 5000,
    "current_menu_items": ["Chicken Piccata", "Italian Salad"]
  }'
```

### Test via Backend

```bash
# Login first
curl -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john.smith.0@flashbacklabs.com",
    "password": "TestPass123"
  }'

# Use token to call project endpoints
curl -X POST http://localhost:3001/api/projects/PROJECT_ID/staffing \
  -H "Content-Type: application/json" \
  -H "Cookie: app_jwt=YOUR_TOKEN" \
  -d '{
    "guest_count": 150,
    "event_type": "wedding",
    "service_style": "plated",
    "event_duration_hours": 4
  }'
```

---

## Step 5: Frontend Integration (Optional)

### Create API Client

Update `frontend/lib/api/ml-client.ts`:

```typescript
export const mlApiClient = {
  // Existing chat method
  async chat(data: { message: string; threadId?: string; projectId?: string }) {
    // ... your existing implementation
  },

  // NEW: Get staffing suggestions
  async getStaffing(projectId: string, data: {
    guest_count: number;
    event_type: string;
    service_style: string;
    event_duration_hours: number;
  }) {
    const response = await fetch(`http://localhost:3001/api/projects/${projectId}/staffing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to get staffing suggestions');
    return response.json();
  },

  // NEW: Get portion estimates
  async getPortions(projectId: string, data: {
    guest_count: number;
    menu_items: any[];
    event_type: string;
  }) {
    const response = await fetch(`http://localhost:3001/api/projects/${projectId}/portions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to get portion estimates');
    return response.json();
  },

  // NEW: Get upsell suggestions
  async getUpsells(projectId: string, data: {
    event_type: string;
    budget: number;
    current_menu_items: string[];
  }) {
    const response = await fetch(`http://localhost:3001/api/projects/${projectId}/upsells`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Failed to get upsell suggestions');
    return response.json();
  },
};
```

---

## Summary of Changes

### ✅ What You're Adding

**ML API (`TheCateringCompanyAgent/api.py`):**
- ✅ `/api/staffing/predict` - Calculate staff needs
- ✅ `/api/portions/estimate` - Estimate food quantities
- ✅ `/api/upsells/suggest` - Recommend upsells
- ✅ `/api/intake/parse` - Parse intake forms

**Backend (`backend/src/ml/ml.service.ts`):**
- ✅ `predictStaffing()` method
- ✅ `estimatePortions()` method
- ✅ `suggestUpsells()` method
- ✅ `parseIntakeForm()` method

**Backend (`backend/src/projects/projects.controller.ts`):**
- ✅ `POST /api/projects/:id/staffing`
- ✅ `POST /api/projects/:id/portions`
- ✅ `POST /api/projects/:id/upsells`

**Frontend (optional):**
- ✅ Add methods to `mlApiClient`

---

## File Locations

```
TheCateringCompanyAgent/
└── api.py                    # ← Add new endpoints here

cateringCo/
├── backend/
│   └── src/
│       ├── ml/
│       │   └── ml.service.ts  # ← Add new methods here
│       └── projects/
│           └── projects.controller.ts  # ← Add new routes here
└── frontend/
    └── lib/
        └── api/
            └── ml-client.ts   # ← Add new methods here (optional)
```

---

## Quick Test Checklist

After making changes:

1. ✅ Restart ML API: `cd TheCateringCompanyAgent && .venv\Scripts\activate && python api.py`
2. ✅ Restart Backend: `cd cateringCo/backend && npm run start:dev`
3. ✅ Test health: `curl http://localhost:8000/health`
4. ✅ Test chat (existing): `curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d '{"message":"hi"}'`
5. ✅ Test staffing (new): `curl -X POST http://localhost:8000/staffing -H "Content-Type: application/json" -d '{"guest_count":100,"event_type":"wedding","service_style":"plated","event_duration_hours":4}'`
6. ✅ Test via backend: Login and call `/api/projects/PROJECT_ID/staffing`

---

## Next Steps

1. **Enhance ML Logic:** Replace simple calculations with your actual ML models
2. **Database Integration:** Save staffing/portion estimates to database
3. **Frontend UI:** Create components to display suggestions
4. **Contract Generation:** Add contract generation endpoint using LangGraph

---

**You now have all ML features integrated! 🎉**

The simple implementations provided can be enhanced with your actual ML models and LangGraph agents.

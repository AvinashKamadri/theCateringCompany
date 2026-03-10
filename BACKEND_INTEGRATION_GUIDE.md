# Backend Integration Guide - ML API

## Overview

The ML API provides **calculation-only endpoints**. The backend is responsible for:
1. Calling ML endpoints with event data
2. Receiving ML predictions/calculations
3. Saving results to PostgreSQL using Prisma (TypeScript)
4. Linking results to AI generations for tracking

## Architecture

```
Frontend → Backend (TypeScript) → ML API (Python) → ML Models
              ↓ (saves results)
           PostgreSQL (Prisma)
```

## ML API Base URL

```
Development: http://localhost:8000
Production: <your-ml-api-url>
```

## Available Endpoints

### 1. Staffing Predictions

**Endpoint:** `POST /ml/staffing`

**Request:**
```json
{
  "project_id": "uuid-optional",
  "guest_count": 150,
  "service_type": "on-site",
  "event_type": "Wedding",
  "event_duration_hours": 4.0
}
```

**Response:**
```json
{
  "recommended_staff": {
    "server": 5,
    "bartender": 2,
    "chef": 2,
    "cleanup": 2
  },
  "total_labor_hours": 44.0,
  "estimated_labor_cost": 1320.00,
  "reasoning": "1 server per 30 guests for plated service, 1 bartender per 75 guests",
  "confidence_score": 0.85
}
```

**Backend saves to:**
- `project_staff_requirements` table
- `ai_generations` table (entity_type: "staffing")

---

### 2. Pricing Calculations

**Endpoint:** `POST /ml/pricing`

**Request:**
```json
{
  "project_id": "uuid-optional",
  "event_type": "Wedding",
  "service_type": "on-site",
  "guest_count": 150,
  "menu_selections": ["Chicken Alfredo", "Caesar Salad"]
}
```

**Response:**
```json
{
  "base_price": 500.00,
  "per_person_price": 45.00,
  "estimated_total": 7250.00,
  "currency": "USD",
  "package_name": "Wedding Premium Package",
  "breakdown": {
    "food_cost": 5500.00,
    "labor_cost": 1200.00,
    "overhead": 550.00
  }
}
```

**Backend saves to:**
- `project_pricing` table
- `ai_generations` table (entity_type: "pricing")

---

### 3. Upsell Suggestions

**Endpoint:** `POST /ml/upsells`

**Request:**
```json
{
  "project_id": "uuid-optional",
  "event_type": "Wedding",
  "guest_count": 150,
  "current_selections": {
    "menu": ["Chicken Alfredo"],
    "service_type": "on-site"
  }
}
```

**Response:**
```json
{
  "upsells": [
    {
      "category": "Bar Service",
      "name": "Premium Open Bar Package",
      "price": 6750.00,
      "reasoning": "Weddings typically include bar service. Premium package includes top-shelf liquor and signature cocktails.",
      "priority": "high"
    },
    {
      "category": "Staffing",
      "name": "Additional Service Staff",
      "price": 800.00,
      "reasoning": "Extra servers ensure seamless service during cocktail hour and reception.",
      "priority": "medium"
    }
  ],
  "total_potential_revenue": 7550.00
}
```

**Backend saves to:**
- `project_upsell_items` table (status: "suggested")
- `ai_generations` table (entity_type: "upsell")

---

### 4. Portion Estimates

**Endpoint:** `POST /ml/portions`

**Request:**
```json
{
  "project_id": "uuid-optional",
  "guest_count": 150,
  "menu_items": [
    {"name": "Chicken Alfredo", "category": "entree"},
    {"name": "Caesar Salad", "category": "side"},
    {"name": "Garlic Bread", "category": "appetizer"}
  ]
}
```

**Response:**
```json
{
  "portion_estimates": [
    {
      "item_name": "Chicken Alfredo",
      "quantity": 225.0,
      "unit": "portions",
      "waste_factor": 0.10
    },
    {
      "item_name": "Caesar Salad",
      "quantity": 75.0,
      "unit": "lbs",
      "waste_factor": 0.10
    },
    {
      "item_name": "Garlic Bread",
      "quantity": 450.0,
      "unit": "pieces",
      "waste_factor": 0.10
    }
  ],
  "confidence_score": 0.80
}
```

**Backend saves to:**
- `project_portion_estimates` table
- `ai_generations` table (entity_type: "portions")

---

## Backend Implementation (TypeScript/NestJS)

### 1. Create ML Service

**File:** `backend/src/ml/ml.service.ts`

```typescript
import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { HttpService } from '@nestjs/axios';
import { firstValueFrom } from 'rxjs';

@Injectable()
export class MlService {
  private readonly mlApiUrl = process.env.ML_API_URL || 'http://localhost:8000';

  constructor(
    private prisma: PrismaService,
    private httpService: HttpService,
  ) {}

  /**
   * Call ML API for staffing predictions and save to database
   */
  async predictStaffing(projectId: string, data: {
    guest_count: number;
    service_type: string;
    event_type: string;
    event_duration_hours?: number;
  }) {
    // 1. Call ML API
    const response = await firstValueFrom(
      this.httpService.post(`${this.mlApiUrl}/ml/staffing`, {
        project_id: projectId,
        ...data,
      })
    );

    const mlResult = response.data;

    // 2. Save AI generation record
    const generation = await this.prisma.ai_generations.create({
      data: {
        entity_type: 'staffing',
        project_id: projectId,
        model: 'staffing_predictor_v2',
        input_summary: {
          guest_count: data.guest_count,
          service_type: data.service_type,
          event_type: data.event_type,
        },
        output: JSON.stringify(mlResult),
        latency_ms: 0, // Can track this if needed
        was_applied: false,
      },
    });

    // 3. Save staff requirements to database
    const staffRecords = [];
    for (const [role, quantity] of Object.entries(mlResult.recommended_staff)) {
      // Calculate individual costs based on role
      const ratePerHour = this.getStaffRate(role);
      const hours = data.event_duration_hours || 4.0;

      staffRecords.push({
        project_id: projectId,
        role: role,
        quantity: quantity as number,
        hours_estimated: hours,
        rate_per_hour: ratePerHour,
        total_cost: (quantity as number) * hours * ratePerHour,
        notes: mlResult.reasoning,
        source: 'ai_suggested', // Enum from schema
        ai_generation_id: generation.id,
      });
    }

    await this.prisma.project_staff_requirements.createMany({
      data: staffRecords,
    });

    return {
      generation_id: generation.id,
      staff_requirements: staffRecords,
      total_cost: mlResult.estimated_labor_cost,
      confidence_score: mlResult.confidence_score,
    };
  }

  /**
   * Call ML API for upsell suggestions and save to database
   */
  async generateUpsells(projectId: string, data: {
    event_type: string;
    guest_count: number;
    current_selections: any;
  }) {
    // 1. Call ML API
    const response = await firstValueFrom(
      this.httpService.post(`${this.mlApiUrl}/ml/upsells`, {
        project_id: projectId,
        ...data,
      })
    );

    const mlResult = response.data;

    // 2. Save AI generation record
    const generation = await this.prisma.ai_generations.create({
      data: {
        entity_type: 'upsell',
        project_id: projectId,
        model: 'upsell_recommender_v1',
        input_summary: {
          event_type: data.event_type,
          guest_count: data.guest_count,
        },
        output: JSON.stringify(mlResult),
        was_applied: false,
      },
    });

    // 3. Save upsell items to database
    const upsellRecords = mlResult.upsells.map(upsell => ({
      project_id: projectId,
      title: upsell.name,
      description: upsell.reasoning,
      estimated_revenue: upsell.price,
      status: 'suggested', // Enum: suggested, presented, accepted, declined
      source: 'ai_suggested',
      ai_generation_id: generation.id,
    }));

    await this.prisma.project_upsell_items.createMany({
      data: upsellRecords,
    });

    return {
      generation_id: generation.id,
      upsells: upsellRecords,
      total_potential_revenue: mlResult.total_potential_revenue,
    };
  }

  /**
   * Call ML API for portion estimates and save to database
   */
  async estimatePortions(projectId: string, data: {
    guest_count: number;
    menu_items: Array<{ name: string; category: string }>;
  }) {
    // 1. Call ML API
    const response = await firstValueFrom(
      this.httpService.post(`${this.mlApiUrl}/ml/portions`, {
        project_id: projectId,
        ...data,
      })
    );

    const mlResult = response.data;

    // 2. Save AI generation record
    const generation = await this.prisma.ai_generations.create({
      data: {
        entity_type: 'portions',
        project_id: projectId,
        model: 'portion_estimator_v1',
        input_summary: { guest_count: data.guest_count },
        was_applied: false,
      },
    });

    // 3. Save portion estimates to database
    const portionRecords = mlResult.portion_estimates.map(portion => ({
      project_id: projectId,
      item_name: portion.item_name,
      guest_count: data.guest_count,
      quantity: portion.quantity,
      unit: portion.unit,
      waste_factor: portion.waste_factor,
      source: 'ai_suggested',
      ai_generation_id: generation.id,
    }));

    await this.prisma.project_portion_estimates.createMany({
      data: portionRecords,
    });

    return {
      generation_id: generation.id,
      portions: portionRecords,
    };
  }

  /**
   * Helper: Get staff hourly rate by role
   */
  private getStaffRate(role: string): number {
    const rates = {
      server: 25.00,
      bartender: 28.00,
      chef: 35.00,
      cleanup: 20.00,
    };
    return rates[role.toLowerCase()] || 25.00;
  }
}
```

### 2. Create ML Controller

**File:** `backend/src/ml/ml.controller.ts`

```typescript
import { Controller, Post, Body, Param } from '@nestjs/common';
import { MlService } from './ml.service';

@Controller('ml')
export class MlController {
  constructor(private mlService: MlService) {}

  @Post('staffing/:projectId')
  async predictStaffing(
    @Param('projectId') projectId: string,
    @Body() data: any,
  ) {
    return this.mlService.predictStaffing(projectId, data);
  }

  @Post('upsells/:projectId')
  async generateUpsells(
    @Param('projectId') projectId: string,
    @Body() data: any,
  ) {
    return this.mlService.generateUpsells(projectId, data);
  }

  @Post('portions/:projectId')
  async estimatePortions(
    @Param('projectId') projectId: string,
    @Body() data: any,
  ) {
    return this.mlService.estimatePortions(projectId, data);
  }
}
```

### 3. Register Module

**File:** `backend/src/ml/ml.module.ts`

```typescript
import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { MlService } from './ml.service';
import { MlController } from './ml.controller';

@Module({
  imports: [HttpModule],
  controllers: [MlController],
  providers: [MlService],
  exports: [MlService],
})
export class MlModule {}
```

---

## Testing the Integration

### 1. Start ML API

```bash
cd TheCateringCompanyAgent
python api.py
# or
uvicorn api:app --reload --port 8000
```

### 2. Test ML Endpoint Directly

```bash
curl -X POST http://localhost:8000/ml/staffing \
  -H "Content-Type: application/json" \
  -d '{
    "guest_count": 150,
    "service_type": "on-site",
    "event_type": "Wedding",
    "event_duration_hours": 4.0
  }'
```

### 3. Test via Backend

```bash
curl -X POST http://localhost:3000/ml/staffing/PROJECT_ID_HERE \
  -H "Content-Type: application/json" \
  -d '{
    "guest_count": 150,
    "service_type": "on-site",
    "event_type": "Wedding",
    "event_duration_hours": 4.0
  }'
```

### 4. Verify Database

```sql
-- Check AI generations
SELECT * FROM ai_generations ORDER BY created_at DESC LIMIT 5;

-- Check staff requirements
SELECT * FROM project_staff_requirements ORDER BY created_at DESC LIMIT 5;

-- Check upsells
SELECT * FROM project_upsell_items ORDER BY created_at DESC LIMIT 5;
```

---

## Environment Variables

### ML API (.env)
```env
# No DATABASE_URL needed - backend handles database
OPENAI_API_KEY=your-key-here
ML_API_PORT=8000
```

### Backend (.env)
```env
DATABASE_URL="postgresql://avinash:Avinash@1617@localhost:5432/caterDB_prod"
ML_API_URL="http://localhost:8000"
```

---

## Error Handling

The ML API returns standard HTTP errors:

- `200` - Success
- `400` - Bad request (invalid input)
- `500` - Internal server error (ML calculation failed)

The backend should:
1. Catch ML API errors
2. Log failures
3. Return appropriate errors to frontend
4. NOT save incomplete/failed predictions to database

---

## Deployment

### Development
- ML API: `http://localhost:8000`
- Backend: `http://localhost:3000`

### Production
- ML API: Deploy to Render/Railway/Cloud Run
- Update `ML_API_URL` in backend `.env`
- Ensure ML API is accessible from backend (firewall rules)

---

## Summary

✅ **ML API Responsibilities:**
- Perform calculations/predictions
- Return JSON responses
- NO database access

✅ **Backend Responsibilities:**
- Call ML API endpoints
- Save results to PostgreSQL using Prisma
- Track AI generations
- Handle errors and retries

This separation keeps your ML code focused on machine learning, while the backend handles data persistence and business logic.

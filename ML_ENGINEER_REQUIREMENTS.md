# ML Engineer Integration Requirements - CateringCo Platform

## Overview
We need AI/ML models integrated into the CateringCo platform for automated contract generation, intelligent upsells, event summarization, and data validation.

---

## 1. Contract Generator Model

### Input Schema
```json
{
  "event_details": {
    "event_type": "string",          // e.g., "wedding", "corporate", "birthday"
    "event_date": "ISO8601 date",
    "event_end_date": "ISO8601 date (optional)",
    "guest_count": "integer",
    "venue_id": "uuid (optional)",
    "venue_name": "string (optional)",
    "service_style": "string",       // "buffet", "plated", "stations", etc.
    "budget": "number (optional)",
    "special_requests": "string (optional)"
  },
  "menu_items": [
    {
      "id": "uuid",
      "name": "string",
      "quantity": "integer",
      "price": "number"
    }
  ],
  "pricing": {
    "subtotal": "number",
    "tax": "number",
    "service_charge": "number",
    "total": "number"
  },
  "client_info": {
    "name": "string",
    "email": "string",
    "phone": "string",
    "company": "string (optional)"
  }
}
```

### Expected Output
```json
{
  "contract": {
    "title": "string",               // e.g., "Catering Agreement - Smith Wedding"
    "body": {
      "sections": [
        {
          "heading": "string",
          "content": "string",       // Generated contract text
          "clauses": ["string"]      // Individual clause paragraphs
        }
      ]
    },
    "total_amount": "number",
    "confidence_score": "number",    // 0-1 confidence in generation
    "warnings": ["string"],          // Any issues detected
    "suggested_clauses": [           // Additional recommended clauses
      {
        "title": "string",
        "reason": "string",          // Why this clause is suggested
        "content": "string"
      }
    ]
  },
  "ai_generation_metadata": {
    "model": "string",               // Model name/version
    "prompt_version": "string",
    "input_tokens": "integer",
    "output_tokens": "integer",
    "latency_ms": "integer"
  }
}
```

### API Endpoint Expected
- **POST** `/ml/contracts/generate`
- **Headers**: `Authorization: Bearer <api_key>`
- **Content-Type**: `application/json`
- **Timeout**: Max 30 seconds
- **Rate Limit**: 100 requests/hour per project

---

## 2. Upsell Suggestion Model

### Input Schema
```json
{
  "event_details": {
    "event_type": "string",
    "guest_count": "integer",
    "service_style": "string",
    "current_menu_items": ["string"], // Names of selected items
    "total_budget": "number",
    "venue_type": "string (optional)"
  },
  "project_context": {
    "season": "string",              // "spring", "summer", "fall", "winter"
    "day_of_week": "string",
    "time_of_day": "string"          // "morning", "afternoon", "evening"
  },
  "available_upsells": [             // Our catalog of upsell options
    {
      "id": "uuid",
      "category": "string",          // "bar", "staffing", "rentals", "upgrades"
      "name": "string",
      "description": "string",
      "estimated_revenue": "number"
    }
  ]
}
```

### Expected Output
```json
{
  "suggestions": [
    {
      "upsell_id": "uuid",
      "name": "string",
      "category": "string",
      "reasoning": "string",           // Why this upsell makes sense
      "estimated_revenue": "number",
      "confidence_score": "number",    // 0-1 likelihood of acceptance
      "priority": "integer",           // 1-10, higher = more important
      "presentation_text": "string"    // Pre-written pitch for sales team
    }
  ],
  "total_potential_revenue": "number",
  "ai_generation_metadata": {
    "model": "string",
    "latency_ms": "integer"
  }
}
```

### API Endpoint Expected
- **POST** `/ml/upsells/suggest`
- **Response Time**: Max 10 seconds

---

## 3. Event Notes Summarization Model

### Input Schema
```json
{
  "messages": [
    {
      "id": "uuid",
      "content": "string",
      "author": "string",              // "client", "staff", "ai"
      "timestamp": "ISO8601 datetime"
    }
  ],
  "thread_subject": "string (optional)",
  "project_id": "uuid"
}
```

### Expected Output
```json
{
  "summary": {
    "brief": "string",                 // 1-2 sentence summary
    "key_points": ["string"],          // Bullet points of main topics
    "action_items": [
      {
        "task": "string",
        "assigned_to": "string (optional)",
        "priority": "low|medium|high",
        "due_date": "ISO8601 date (optional)"
      }
    ],
    "decisions_made": ["string"],      // Important decisions from conversation
    "open_questions": ["string"],      // Unresolved questions
    "client_preferences": {            // Extracted preferences
      "dietary_restrictions": ["string"],
      "style_preferences": ["string"],
      "budget_concerns": ["string"],
      "other": ["string"]
    }
  },
  "confidence_score": "number",
  "ai_generation_metadata": {
    "model": "string",
    "input_tokens": "integer",
    "output_tokens": "integer"
  }
}
```

### API Endpoint Expected
- **POST** `/ml/summaries/generate`
- **Max Messages**: 500 per request

---

## 4. Contract Validation / Missing Info Detection

### Input Schema
```json
{
  "contract": {
    "title": "string",
    "body": "object",                  // Contract JSON structure
    "total_amount": "number"
  },
  "event_details": {
    "event_type": "string",
    "event_date": "ISO8601 date",
    "guest_count": "integer",
    "venue_id": "uuid (optional)"
  },
  "menu_items": ["object"],
  "signatures": ["object"]             // Existing signatures
}
```

### Expected Output
```json
{
  "validation": {
    "is_complete": "boolean",
    "completeness_score": "number",    // 0-1, how complete the contract is
    "missing_fields": [
      {
        "field": "string",             // e.g., "venue_address"
        "category": "string",          // "required" | "recommended" | "optional"
        "impact": "string",            // Why this matters
        "suggestion": "string"         // How to fix it
      }
    ],
    "risk_flags": [
      {
        "type": "string",              // "legal", "financial", "operational"
        "severity": "low|medium|high",
        "description": "string",
        "recommendation": "string"
      }
    ],
    "recommended_clauses": [           // Additional clauses to add
      {
        "clause_name": "string",
        "reason": "string",
        "template_id": "uuid (optional)"
      }
    ]
  },
  "ai_generation_metadata": {
    "model": "string",
    "latency_ms": "integer"
  }
}
```

### API Endpoint Expected
- **POST** `/ml/contracts/validate`

---

## 5. Intake Form Parsing (AI-Enhanced)

### Input Schema
```json
{
  "form_submission": {
    "submission_id": "uuid",
    "form_template_id": "uuid",
    "raw_answers": {                   // Key-value pairs from form
      "field_key": "user_answer_string"
    },
    "submitted_at": "ISO8601 datetime"
  },
  "form_template": {
    "fields": [
      {
        "key": "string",
        "label": "string",
        "type": "string",              // "text", "textarea", "number", "date"
        "ai_mapping": "string (optional)" // What this field maps to in our system
      }
    ]
  }
}
```

### Expected Output
```json
{
  "parsed_output": {
    "event_type": "string",
    "event_date": "ISO8601 date",
    "guest_count": "integer",
    "budget": "number",
    "service_style": "string",
    "dietary_restrictions": ["string"],
    "special_requests": ["string"],
    "extracted_preferences": {
      "venue_preferences": "string",
      "menu_preferences": ["string"],
      "timeline_constraints": "string"
    }
  },
  "confidence_score": "number",        // 0-1 overall parsing confidence
  "field_confidence": {                // Per-field confidence
    "event_type": "number",
    "event_date": "number",
    // ... for each field
  },
  "missing_fields": ["string"],        // Required fields not found
  "ambiguities": [
    {
      "field": "string",
      "issue": "string",
      "suggestions": ["string"]
    }
  ],
  "upsell_triggers": [                 // Detected upsell opportunities
    {
      "category": "string",
      "reason": "string",
      "confidence": "number"
    }
  ],
  "ai_generation_metadata": {
    "model": "string",
    "input_tokens": "integer",
    "output_tokens": "integer"
  }
}
```

### API Endpoint Expected
- **POST** `/ml/intake/parse`

---

## 6. Staffing Requirements Prediction

### Input Schema
```json
{
  "event_details": {
    "event_type": "string",
    "guest_count": "integer",
    "service_style": "string",
    "event_duration_hours": "number",
    "venue_layout": "string (optional)"
  },
  "menu_items": [
    {
      "name": "string",
      "quantity": "integer",
      "complexity": "string"          // "simple", "moderate", "complex"
    }
  ]
}
```

### Expected Output
```json
{
  "staffing_requirements": [
    {
      "role": "string",                // "chef", "server", "bartender", etc.
      "quantity": "integer",
      "hours_estimated": "number",
      "rate_per_hour": "number",
      "total_cost": "number",
      "reasoning": "string"
    }
  ],
  "total_staffing_cost": "number",
  "confidence_score": "number",
  "ai_generation_metadata": {
    "model": "string"
  }
}
```

### API Endpoint Expected
- **POST** `/ml/staffing/predict`

---

## 7. Portion Size Estimation

### Input Schema
```json
{
  "menu_items": [
    {
      "id": "uuid",
      "name": "string",
      "category": "string",            // "appetizer", "entree", "dessert"
      "serving_style": "string"        // "buffet", "plated", "family_style"
    }
  ],
  "guest_count": "integer",
  "event_type": "string",
  "event_duration_hours": "number"
}
```

### Expected Output
```json
{
  "portion_estimates": [
    {
      "menu_item_id": "uuid",
      "item_name": "string",
      "quantity": "number",
      "unit": "string",                // "lbs", "portions", "trays", "gallons"
      "waste_factor": "number",        // 0.05-0.20 typical
      "reasoning": "string"
    }
  ],
  "confidence_score": "number",
  "ai_generation_metadata": {
    "model": "string"
  }
}
```

### API Endpoint Expected
- **POST** `/ml/portions/estimate`

---

## Integration Requirements

### Authentication
- **Method**: API Key authentication
- **Header**: `X-API-Key: <your_key>` or `Authorization: Bearer <token>`
- We'll provide the key after your models are deployed

### Response Format
- **Content-Type**: `application/json`
- **Status Codes**:
  - `200 OK` - Success
  - `400 Bad Request` - Invalid input
  - `422 Unprocessable Entity` - Validation error
  - `429 Too Many Requests` - Rate limit exceeded
  - `500 Internal Server Error` - Model error
  - `503 Service Unavailable` - Model not ready

### Error Response Format
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": "object (optional)"
  }
}
```

### Performance Requirements
- **Contract Generation**: < 30s
- **Upsell Suggestions**: < 10s
- **Event Summarization**: < 15s
- **Contract Validation**: < 10s
- **Intake Parsing**: < 5s
- **Staffing Prediction**: < 5s
- **Portion Estimation**: < 5s

### Monitoring & Logging
Please log:
- Request ID (we'll send as `X-Request-ID` header)
- Model version used
- Latency (ms)
- Input/output token counts
- Confidence scores
- Any errors or warnings

### Deployment
- **Environment**: Cloud-hosted API (AWS/GCP/Azure)
- **Availability**: 99.5% uptime SLA
- **Scaling**: Auto-scale to handle 1000 concurrent requests
- **Endpoints**: Provide both staging and production URLs

---

## Testing Data

We'll provide you with:
1. **Sample event data** (100 realistic events)
2. **Sample conversations** (50 message threads)
3. **Sample contracts** (20 examples of good/bad contracts)
4. **Sample intake forms** (30 filled forms)

Request access to our test database once your models are ready.

---

## Timeline

| Milestone | Expected Delivery |
|-----------|------------------|
| Contract Generator MVP | Week 3 |
| Upsell Suggestions | Week 4 |
| Event Summarization | Week 5 |
| Contract Validation | Week 6 |
| Intake Parsing | Week 7 |
| Staffing + Portions | Week 8 |

---

## Questions for ML Engineer

1. **Model Framework**: What framework are you using? (TensorFlow, PyTorch, Hugging Face, OpenAI API, etc.)
2. **Hosting**: Where will models be deployed? (Your infrastructure or ours?)
3. **Fine-tuning**: Do you need access to our production data for fine-tuning?
4. **Versioning**: How will you version your models? Can we A/B test?
5. **Cost**: What's the cost per API call? (tokens, compute time, etc.)
6. **Rate Limits**: What rate limits should we expect?
7. **Latency**: Can you meet the performance requirements above?
8. **Fallback**: What happens if a model fails? Should we have a fallback?

---

## Contact

**Backend Team**: [Your email]
**Project Manager**: [PM email]
**Slack Channel**: #ml-integration

Please review this document and confirm:
- [ ] All input/output schemas are clear
- [ ] Performance requirements are feasible
- [ ] Timeline is realistic
- [ ] You have all necessary context

We'll schedule a kick-off meeting once you've reviewed.

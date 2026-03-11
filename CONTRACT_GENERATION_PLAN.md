# Contract Generation Enhancement Plan

## Current State ✅
- ML Agent collects: name, phone, event_date, event_type, venue, guest_count, service_type, special_requests
- Basic contract summary generated with LLM
- Backend creates contract record in database
- PDF generation queued (BullMQ)

## Missing Features (From Sample Contract) 🎯

### 1. **Menu Selection & Pricing**
**Status**: Partially implemented
- ✅ Pricing calculator exists (`ml-agent/tools/pricing.py`)
- ✅ Menu database seeded
- ❌ ML Agent doesn't collect menu selections during conversation
- ❌ Contract doesn't include itemized menu with per-person pricing

**Need**:
- Add menu selection nodes to ML conversation graph
- Collect: appetizers, main dishes, desserts, beverages, utensils
- Use pricing calculator to generate line-item breakdown

### 2. **Package Selection**
**Status**: Partially implemented
- ✅ Pricing packages exist in database (Wedding Deluxe, Standard, etc.)
- ❌ ML Agent doesn't ask about packages
- ❌ Contract doesn't show package details

**Need**:
- Add package selection to conversation flow
- Match package based on event_type and guest_count
- Include package details in contract

### 3. **Billing Calculations**
**Status**: Implemented in pricing.py, not in contract
- ✅ Pricing calculator computes:
  - Menu subtotal
  - Tax (9.4% configurable)
  - Service & Gratuity (20% configurable)
  - Deposit (50%)
  - Balance due
- ❌ These details not included in contract body

**Need**:
- Include full billing breakdown in contract
- Show deposit schedule
- Show payment terms

### 4. **Dietary & Special Instructions**
**Status**: Collected but not formatted
- ✅ ML Agent collects special_requests
- ❌ Not prominently displayed in contract
- ❌ Dietary requirements (halal, vegan, gluten-free, etc.) not specifically highlighted

**Need**:
- Add dedicated dietary restrictions section to contract
- Format special instructions clearly
- Add allergen warnings if needed

### 5. **Policies Section**
**Status**: Missing
- ❌ Cancellation policy
- ❌ Guest count policy
- ❌ Food escalation clause
- ❌ Payment method fees
- ❌ Additional labor charges

**Need**:
- Add business policies to contract template
- Make configurable via business_rules config

### 6. **Contract Metadata**
**Status**: Partially implemented
- ✅ Contract ID exists
- ❌ Not formatted as "CC-YYYYMMDD-XXXX"
- ❌ Date issued not prominently displayed
- ❌ No contract number prefix

**Need**:
- Generate formatted contract numbers
- Add issue date to contract

### 7. **PDF Formatting**
**Status**: Basic implementation
- ✅ PDF generation worker exists
- ❌ PDF uses basic template
- ❌ Doesn't match sample contract format

**Need**:
- Create professional PDF template
- Include company branding
- Match sample contract layout

## Implementation Steps

### Phase 1: Enhance ML Agent Contract Generation (HIGH PRIORITY)

#### Step 1.1: Update Contract Generator Node
**File**: `ml-agent/agent/nodes/generate_contract.py`

```python
# Instead of just generating summary text, call pricing calculator:
from tools.pricing import calculate_event_pricing

pricing_data = await calculate_event_pricing(
    guest_count=guest_count,
    event_type=event_type,
    service_type=service_type,
    selected_dishes=menu_items,
    appetizers=appetizers,
    desserts=desserts,
    # ... etc
)

# Create detailed contract_data with all pricing
state["contract_data"] = {
    "contract_id": f"CC-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
    "issue_date": datetime.now().isoformat(),
    "client_name": name,
    "client_phone": phone,
    "client_email": email,
    "event_type": event_type,
    "event_date": event_date,
    "venue": venue,
    "guest_count": guest_count,
    "service_type": service_type,

    # ADD PRICING DETAILS
    "package": pricing_data.get("package"),
    "menu_items": pricing_data["line_items"],
    "menu_subtotal": pricing_data["menu_total"],
    "service_charge": pricing_data["service_surcharge"],
    "tax_amount": pricing_data["tax"],
    "tax_rate": pricing_data["tax_rate"],
    "gratuity_amount": pricing_data["gratuity"],
    "gratuity_rate": pricing_data["gratuity_rate"],
    "grand_total": pricing_data["grand_total"],
    "deposit_amount": pricing_data["deposit"],
    "balance_due": pricing_data["balance"],

    # ADD POLICIES
    "dietary_restrictions": dietary_restrictions,
    "special_requests": special_requests,
    "policies": {
        "cancellation": "...",
        "guest_count": "...",
        "payment_terms": "..."
    },

    "status": "pending_staff_approval",
}
```

#### Step 1.2: Add Menu Collection Nodes
**New Files**:
- `ml-agent/agent/nodes/collect_menu_items.py`
- `ml-agent/agent/nodes/collect_appetizers.py`
- `ml-agent/agent/nodes/collect_desserts.py`

Add to conversation graph before final/contract generation.

#### Step 1.3: Update Slots
**File**: `ml-agent/agent/state.py`

Add new slots for:
- `menu_items` (main dishes)
- `appetizers`
- `desserts`
- `beverages`
- `dietary_restrictions` (specific list)
- `package_preference`

### Phase 2: Update Backend Contract Storage

#### Step 2.1: Enhance Contract Body Schema
**File**: `backend/src/projects/projects.service.ts`

When creating contract, ensure `body` field includes:
```typescript
body: {
  // Existing
  client_info: {...},
  event_details: {...},

  // ADD THESE
  package: pricing_data.package,
  menu: {
    items: pricing_data.menu_items,
    dietary_restrictions: [...],
  },
  billing: {
    menu_subtotal: pricing_data.menu_total,
    service_charge: pricing_data.service_charge,
    subtotal: pricing_data.subtotal_before_fees,
    tax: { amount: ..., rate: ... },
    gratuity: { amount: ..., rate: ... },
    grand_total: pricing_data.grand_total,
    deposit: { amount: ..., percentage: 0.5, due: "at signing" },
    balance: { amount: ..., due: "21 days prior to event" },
  },
  policies: {
    cancellation: {...},
    guest_count: {...},
    payment: {...},
  },
}
```

### Phase 3: Enhance PDF Generation

#### Step 3.1: Create Professional PDF Template
**File**: `workers/src/processors/pdf-generator.processor.ts`

Update PDF generation to include:
- Company header with logo
- Contract metadata (number, date)
- Client & event details section
- Package information
- Itemized menu with pricing
- Billing summary table
- Policies section
- Signature lines
- Footer with contact info

Use PDF library features for:
- Tables for menu items
- Bold/italic formatting
- Section headers
- Page breaks if needed

### Phase 4: Testing

1. **Start ML Agent**: `cd ml-agent && python api.py`
2. **Test Conversation**: Chat through complete flow
3. **Verify Contract**: Check database has full details
4. **Verify PDF**: Open generated PDF and compare to sample

## Files to Modify

### ML Agent
- [ ] `ml-agent/agent/nodes/generate_contract.py` - Use pricing calculator
- [ ] `ml-agent/agent/state.py` - Add menu/package slots
- [ ] `ml-agent/agent/graph.py` - Add menu collection nodes
- [ ] `ml-agent/agent/nodes/collect_menu_items.py` - NEW
- [ ] `ml-agent/orchestrator.py` - Ensure contract_data passed through

### Backend
- [ ] `backend/src/projects/projects.service.ts` - Enhanced contract body
- [ ] `backend/prisma/schema.prisma` - Verify JSON schema allows nested data
- [ ] `workers/src/processors/pdf-generator.processor.ts` - Professional PDF template

### Frontend
- [ ] `frontend/app/chat/page.tsx` - Pass additional fields to backend
- [ ] `frontend/types/chat-ai.types.ts` - Update ContractData type

## Priority Order

1. **HIGH**: Update `generate_contract.py` to use pricing calculator
2. **HIGH**: Test contract generation with pricing data
3. **MEDIUM**: Add menu selection to conversation flow
4. **MEDIUM**: Update PDF template
5. **LOW**: Polish UI for contract display

## Success Criteria

✅ ML Agent generates contract with itemized menu and pricing
✅ Backend stores complete contract details in database
✅ PDF matches sample contract format
✅ Staff can review and approve contracts
✅ Contract sent to SignWell with all details

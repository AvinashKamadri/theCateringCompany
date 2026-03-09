# Payment Collection & Stripe Integration - Roadmap

## Overview
Implement comprehensive payment collection system with Stripe integration for deposits, installments, and final payments for catering events.

---

## Current State

### Existing Implementation
- ✅ Stripe SDK installed (`stripe@^16.0.0` in backend)
- ✅ Basic payment schema in database:
  - `payments` table (id, project_id, payment_method_id, amount, status, etc.)
  - `payment_methods` table (card/bank info)
  - `payment_schedules` table (installment plans)
  - `refunds` table
- ✅ PaymentsModule scaffolded (`backend/src/payments/`)
- ✅ Environment variables configured:
  - `STRIPE_ENABLED=false` (currently using mock)
  - `STRIPE_SECRET_KEY=sk_test_...`
  - `STRIPE_WEBHOOK_SECRET=whsec_...`

### Gaps to Address
- ❌ No Stripe API integration (currently mock provider)
- ❌ No payment intent creation flow
- ❌ No webhook handler for payment events
- ❌ No frontend payment UI components
- ❌ No payment schedule automation
- ❌ No deposit collection workflow

---

## Phase 1: Stripe Core Integration (Week 1-2)

### Backend Tasks

#### 1.1 Stripe Service Implementation
**File**: `backend/src/payments/stripe.service.ts`

```typescript
import Stripe from 'stripe';

@Injectable()
export class StripeService {
  private stripe: Stripe;

  constructor() {
    this.stripe = new Stripe(process.env.STRIPE_SECRET_KEY, {
      apiVersion: '2024-11-20.acacia',
    });
  }

  // Create payment intent
  async createPaymentIntent(amount: number, projectId: string, metadata: any) {
    return this.stripe.paymentIntents.create({
      amount: Math.round(amount * 100), // Convert to cents
      currency: 'usd',
      metadata: { projectId, ...metadata },
      automatic_payment_methods: { enabled: true },
    });
  }

  // Create customer
  async createCustomer(email: string, name: string, metadata: any) {
    return this.stripe.customers.create({ email, name, metadata });
  }

  // Attach payment method to customer
  async attachPaymentMethod(paymentMethodId: string, customerId: string) {
    return this.stripe.paymentMethods.attach(paymentMethodId, {
      customer: customerId,
    });
  }

  // Create refund
  async createRefund(paymentIntentId: string, amount?: number) {
    return this.stripe.refunds.create({
      payment_intent: paymentIntentId,
      amount: amount ? Math.round(amount * 100) : undefined,
    });
  }

  // Get payment intent
  async getPaymentIntent(id: string) {
    return this.stripe.paymentIntents.retrieve(id);
  }
}
```

#### 1.2 Payment Controller Endpoints
**File**: `backend/src/payments/payments.controller.ts`

```typescript
@Controller('payments')
@UseGuards(AuthGuard('jwt'))
export class PaymentsController {
  // POST /payments/intents - Create payment intent
  @Post('intents')
  async createIntent(@Body() dto: CreatePaymentIntentDto) {
    // 1. Validate project exists and user has access
    // 2. Create Stripe payment intent
    // 3. Save to payments table
    // 4. Return client secret for frontend
  }

  // POST /payments/confirm - Confirm payment (after Stripe Elements)
  @Post('confirm')
  async confirmPayment(@Body() dto: ConfirmPaymentDto) {
    // 1. Verify payment intent status from Stripe
    // 2. Update payment record in database
    // 3. Emit socket event for real-time update
    // 4. Enqueue notification job
  }

  // POST /payments/refund - Issue refund
  @Post('refund')
  async refundPayment(@Body() dto: RefundPaymentDto) {
    // 1. Validate payment exists
    // 2. Create refund in Stripe
    // 3. Update database with refund record
    // 4. Notify client
  }

  // GET /projects/:id/payments - Get project payments
  @Get('projects/:id/payments')
  async getProjectPayments(@Param('id') projectId: string) {
    // Return all payments for project with status
  }
}
```

#### 1.3 Webhook Handler
**File**: `backend/src/payments/webhooks.controller.ts`

```typescript
@Controller('webhooks')
export class WebhooksController {
  @Post('stripe')
  async handleStripeWebhook(@Req() req: Request) {
    const sig = req.headers['stripe-signature'];
    const event = this.stripe.webhooks.constructEvent(
      req.body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET
    );

    switch (event.type) {
      case 'payment_intent.succeeded':
        await this.handlePaymentSuccess(event.data.object);
        break;
      case 'payment_intent.payment_failed':
        await this.handlePaymentFailed(event.data.object);
        break;
      case 'charge.refunded':
        await this.handleRefund(event.data.object);
        break;
    }

    return { received: true };
  }
}
```

### Frontend Tasks

#### 1.4 Payment UI Components
**Files**:
- `frontend/components/payments/payment-form.tsx` - Stripe Elements wrapper
- `frontend/components/payments/payment-method-selector.tsx` - Saved cards
- `frontend/components/payments/payment-status.tsx` - Status badges

#### 1.5 Install Dependencies
```bash
npm install @stripe/stripe-js @stripe/react-stripe-js
```

#### 1.6 Stripe Provider Setup
**File**: `frontend/app/(dashboard)/layout.tsx`

```typescript
import { loadStripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY);

<Elements stripe={stripePromise}>
  {children}
</Elements>
```

### Deliverables
- ✅ Stripe API integrated in backend
- ✅ Payment intent creation working
- ✅ Webhook handler processing events
- ✅ Frontend can collect payment via Stripe Elements
- ✅ Payments stored in database with proper status tracking

---

## Phase 2: Deposit Automation (Week 3-4)

### Features

#### 2.1 Deposit Calculation
**Logic**:
- Calculate deposit amount based on project pricing
- Options:
  - Fixed percentage (e.g., 30% deposit)
  - Fixed amount (e.g., $500 deposit)
  - Tiered by total (e.g., <$5K = 50%, >$5K = 30%)

**File**: `backend/src/payments/deposit-calculator.service.ts`

```typescript
@Injectable()
export class DepositCalculatorService {
  calculateDeposit(totalAmount: number, eventType: string): number {
    // Wedding/corporate: 30% deposit
    if (['wedding', 'corporate'].includes(eventType)) {
      return Math.round(totalAmount * 0.30);
    }
    // Smaller events: 50% deposit
    return Math.round(totalAmount * 0.50);
  }
}
```

#### 2.2 Payment Schedule Generation
**File**: `backend/src/payments/payment-schedule.service.ts`

```typescript
interface PaymentScheduleItem {
  due_date: Date;
  amount: number;
  description: string;
  is_paid: boolean;
}

@Injectable()
export class PaymentScheduleService {
  async generateSchedule(projectId: string): Promise<PaymentScheduleItem[]> {
    const project = await this.getProject(projectId);
    const total = project.total_price;
    const eventDate = new Date(project.event_date);

    const schedule = [
      {
        due_date: new Date(), // Immediate
        amount: this.depositCalc.calculateDeposit(total, project.event_type),
        description: 'Initial Deposit',
        is_paid: false,
      },
      {
        due_date: new Date(eventDate.getTime() - 30 * 24 * 60 * 60 * 1000), // 30 days before
        amount: total * 0.40,
        description: 'Second Payment',
        is_paid: false,
      },
      {
        due_date: new Date(eventDate.getTime() - 7 * 24 * 60 * 60 * 1000), // 7 days before
        amount: total * 0.30,
        description: 'Final Payment',
        is_paid: false,
      },
    ];

    // Save to payment_schedules table
    return this.saveSchedule(projectId, schedule);
  }
}
```

#### 2.3 Automatic Payment Reminders
**Queue**: Use BullMQ `payments` queue

```typescript
// Enqueue reminder jobs when schedule is created
@Processor('payments')
export class PaymentsProcessor {
  @Process('send_payment_reminder')
  async sendReminder(job: Job) {
    const { projectId, scheduleItemId } = job.data;

    // 1. Get project and client info
    // 2. Check if payment is still pending
    // 3. Send email reminder via notifications queue
    // 4. Create in-app notification
  }
}
```

### Frontend Tasks

#### 2.4 Payment Schedule UI
**File**: `frontend/app/(dashboard)/projects/[id]/payments/page.tsx`

Features:
- Display payment schedule timeline
- Show paid/pending status for each installment
- "Pay Now" button for pending payments
- Payment history table

#### 2.5 Deposit Collection Flow
**Flow**:
1. Contract signed → Trigger deposit request
2. Email sent to client with payment link
3. Client clicks link → Redirected to payment page
4. Payment collected via Stripe
5. Confirmation email sent
6. Project status updated to "deposit_paid"

### Deliverables
- ✅ Deposit calculation logic implemented
- ✅ Payment schedules auto-generated on contract signing
- ✅ Payment reminders sent automatically
- ✅ Clients can pay deposits online
- ✅ Frontend displays payment schedule

---

## Phase 3: Advanced Features (Week 5-6)

### 3.1 Recurring Billing (Optional)
For venue rentals or subscription-based services

**Implementation**:
- Use Stripe Subscriptions API
- Link to `payment_schedules` table
- Auto-charge on due dates

### 3.2 Payment Plans
Allow clients to customize payment schedule

**Features**:
- Drag-and-drop schedule editor
- Custom installment amounts
- Approval workflow

### 3.3 Multi-Currency Support
For international clients

**Implementation**:
- Detect client location
- Offer currency selection
- Use Stripe multi-currency

### 3.4 Invoice Generation
PDF invoices for each payment

**Implementation**:
- Use `pdf_generation` queue
- Template with line items
- Auto-email after payment

### 3.5 Payment Analytics
Dashboard with metrics

**Metrics**:
- Total revenue (by period)
- Deposit collection rate
- Outstanding balances
- Payment method breakdown

---

## Database Schema Updates

### No changes needed - schema already supports:
- ✅ `payments` table with Stripe IDs
- ✅ `payment_methods` table
- ✅ `payment_schedules` table
- ✅ `refunds` table
- ✅ Foreign keys to projects

---

## Configuration

### Environment Variables

```bash
# .env
STRIPE_ENABLED=true
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Deposit settings
DEPOSIT_PERCENTAGE_DEFAULT=0.30
DEPOSIT_MIN_AMOUNT=500
```

---

## Testing Strategy

### Unit Tests
- Deposit calculation logic
- Payment schedule generation
- Refund calculations

### Integration Tests
- Stripe API calls (use test mode)
- Webhook handling
- Database updates

### E2E Tests
1. Client receives contract → Signs → Deposit payment requested
2. Client pays deposit via Stripe → Webhook updates database
3. Payment schedule displayed in dashboard
4. Client pays remaining installments
5. Invoice generated and emailed

---

## Security Considerations

1. **Never store card details** - Use Stripe tokens
2. **Verify webhook signatures** - Prevent spoofing
3. **HTTPS only** for payment pages
4. **PCI compliance** - Stripe handles card processing
5. **Authorization checks** - Only project collaborators can view payments
6. **Audit logging** - Log all payment actions

---

## Success Criteria

- ✅ Clients can pay deposits online via credit card
- ✅ Payment schedules auto-generated after contract signing
- ✅ Automated reminders sent before due dates
- ✅ Webhook updates payment status in real-time
- ✅ Refunds processed within 24 hours
- ✅ Payment dashboard shows all transactions
- ✅ 99.9% uptime for payment processing
- ✅ <5 second payment intent creation
- ✅ Stripe test mode passes all scenarios

---

## Future Enhancements

- ACH/bank transfer support
- Split payments (multiple payers)
- Tip/gratuity collection
- Late payment fees
- Payment disputes resolution UI
- QuickBooks/Xero integration

---

## Resources

- [Stripe Payment Intents API](https://stripe.com/docs/payments/payment-intents)
- [Stripe Webhooks](https://stripe.com/docs/webhooks)
- [Stripe Elements (React)](https://stripe.com/docs/stripe-js/react)
- [PCI Compliance](https://stripe.com/docs/security/guide)

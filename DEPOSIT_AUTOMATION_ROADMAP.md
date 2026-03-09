# Deposit + Balance Automation - Roadmap

## Overview
Automate the entire deposit collection and balance payment workflow from contract signing through final payment, with intelligent triggers, reminders, and reconciliation.

---

## Goals

1. **Eliminate manual payment tracking** - Automate from contract signature to final payment
2. **Improve cash flow** - Collect deposits immediately after contract signing
3. **Reduce no-shows** - Require deposit to confirm booking
4. **Automated reminders** - Send payment reminders at key milestones
5. **Client convenience** - One-click payment links via email/SMS

---

## Workflow Overview

```
Contract Signed
    ↓
[Auto] Generate Payment Schedule
    ↓
[Auto] Send Deposit Request Email
    ↓
Client Pays Deposit (Stripe)
    ↓
[Auto] Webhook Updates Status
    ↓
[Auto] Confirmation Email Sent
    ↓
[Auto] Schedule Balance Reminders (30d, 7d, 1d before event)
    ↓
Client Pays Balance Installments
    ↓
[Auto] Final Payment Reminder (if unpaid)
    ↓
Event Date Reached
    ↓
[Auto] Mark Project as "Payment Complete" or "Overdue"
```

---

## Phase 1: Contract → Deposit Trigger (Week 1)

### 1.1 Contract Signature Webhook

**Trigger**: When contract status changes to `signed`

**File**: `backend/src/contracts/contracts.service.ts`

```typescript
async signContract(contractId: string, signatureData: any) {
  // 1. Update contract status to 'signed'
  const contract = await this.prisma.contracts.update({
    where: { id: contractId },
    data: { status: 'signed', signed_at: new Date() },
  });

  // 2. Trigger deposit automation
  await this.eventEmitter.emit('contract.signed', {
    contractId: contract.id,
    projectId: contract.project_id,
    total_amount: contract.total_amount,
  });

  return contract;
}
```

### 1.2 Deposit Automation Listener

**File**: `backend/src/payments/deposit-automation.service.ts`

```typescript
@Injectable()
export class DepositAutomationService {
  @OnEvent('contract.signed')
  async handleContractSigned(event: ContractSignedEvent) {
    // 1. Calculate deposit amount
    const depositAmount = await this.calculateDeposit(event.projectId);

    // 2. Generate full payment schedule
    const schedule = await this.paymentScheduleService.generateSchedule(
      event.projectId,
      event.total_amount,
      depositAmount
    );

    // 3. Create payment intent for deposit
    const paymentIntent = await this.stripeService.createPaymentIntent(
      depositAmount,
      event.projectId,
      { type: 'deposit', scheduleId: schedule[0].id }
    );

    // 4. Send deposit request email to client
    await this.notificationQueue.add('send_email', {
      to: event.clientEmail,
      template: 'deposit_request',
      data: {
        projectName: event.projectName,
        depositAmount,
        paymentLink: `${FRONTEND_URL}/payments/${paymentIntent.id}`,
        dueDate: 'Immediately',
      },
    });

    // 5. Schedule future payment reminders
    await this.schedulePaymentReminders(schedule);
  }

  private async calculateDeposit(projectId: string): Promise<number> {
    const project = await this.prisma.projects.findUnique({
      where: { id: projectId },
      include: { project_pricing: true },
    });

    const total = project.project_pricing?.total_price || 0;
    const eventType = project.event_type;

    // Business logic for deposit percentage
    const depositPercentage =
      eventType === 'wedding' || eventType === 'corporate' ? 0.30 : 0.50;

    const depositAmount = Math.max(
      total * depositPercentage,
      parseInt(process.env.DEPOSIT_MIN_AMOUNT || '500')
    );

    return depositAmount;
  }

  private async schedulePaymentReminders(schedule: PaymentScheduleItem[]) {
    for (const item of schedule) {
      if (item.description === 'Initial Deposit') continue; // Already sent

      const reminderDate = new Date(item.due_date);
      reminderDate.setDate(reminderDate.getDate() - 3); // 3 days before

      await this.paymentQueue.add(
        'send_payment_reminder',
        { scheduleItemId: item.id },
        { delay: reminderDate.getTime() - Date.now() }
      );
    }
  }
}
```

---

## Phase 2: Payment Collection Flow (Week 2)

### 2.1 Payment Link Page

**File**: `frontend/app/payments/[intentId]/page.tsx`

**Features**:
- Public page (no auth required)
- Display project details, amount due
- Stripe Elements for card input
- "Pay Now" button
- Payment success/failure handling

```typescript
'use client';

import { useEffect, useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';

export default function PaymentPage({ params }: { params: { intentId: string } }) {
  const [clientSecret, setClientSecret] = useState('');
  const [paymentInfo, setPaymentInfo] = useState<any>(null);

  useEffect(() => {
    // Fetch payment intent from backend
    fetch(`/api/payments/intents/${params.intentId}`)
      .then((res) => res.json())
      .then((data) => {
        setClientSecret(data.clientSecret);
        setPaymentInfo(data.paymentInfo);
      });
  }, [params.intentId]);

  if (!clientSecret) return <div>Loading...</div>;

  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <PaymentForm paymentInfo={paymentInfo} />
    </Elements>
  );
}

function PaymentForm({ paymentInfo }: any) {
  const stripe = useStripe();
  const elements = useElements();
  const [isProcessing, setIsProcessing] = useState(false);
  const [message, setMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stripe || !elements) return;

    setIsProcessing(true);

    const { error } = await stripe.confirmPayment({
      elements,
      confirmParams: {
        return_url: `${window.location.origin}/payment-success`,
      },
    });

    if (error) {
      setMessage(error.message || 'Payment failed');
    }

    setIsProcessing(false);
  };

  return (
    <form onSubmit={handleSubmit}>
      <h1>Complete Your Payment</h1>
      <p>Amount: ${paymentInfo.amount}</p>
      <p>For: {paymentInfo.projectName}</p>

      <PaymentElement />

      <button disabled={isProcessing || !stripe}>
        {isProcessing ? 'Processing...' : `Pay $${paymentInfo.amount}`}
      </button>

      {message && <div>{message}</div>}
    </form>
  );
}
```

### 2.2 Webhook Payment Confirmation

**File**: `backend/src/payments/webhooks.controller.ts`

```typescript
@Post('stripe')
async handleStripeWebhook(@Req() req: Request) {
  const event = this.constructWebhookEvent(req);

  switch (event.type) {
    case 'payment_intent.succeeded':
      await this.handlePaymentSuccess(event.data.object);
      break;
  }

  return { received: true };
}

private async handlePaymentSuccess(paymentIntent: Stripe.PaymentIntent) {
  const { projectId, type, scheduleId } = paymentIntent.metadata;

  // 1. Update payment record
  await this.prisma.payments.update({
    where: { stripe_payment_intent_id: paymentIntent.id },
    data: {
      status: 'completed',
      paid_at: new Date(),
    },
  });

  // 2. Update payment schedule item
  await this.prisma.payment_schedules.update({
    where: { id: scheduleId },
    data: { is_paid: true, paid_at: new Date() },
  });

  // 3. Check if deposit - update project status
  if (type === 'deposit') {
    await this.prisma.projects.update({
      where: { id: projectId },
      data: { deposit_paid: true, deposit_paid_at: new Date() },
    });
  }

  // 4. Send confirmation email
  await this.notificationQueue.add('send_email', {
    template: 'payment_confirmation',
    data: {
      amount: paymentIntent.amount / 100,
      type,
    },
  });

  // 5. Emit socket event for real-time update
  this.socketsGateway.emitToRoom(`project:${projectId}`, 'payment.completed', {
    paymentId: paymentIntent.id,
    amount: paymentIntent.amount / 100,
  });

  // 6. Check if all payments complete
  await this.checkPaymentCompletion(projectId);
}

private async checkPaymentCompletion(projectId: string) {
  const schedule = await this.prisma.payment_schedules.findMany({
    where: { project_id: projectId },
  });

  const allPaid = schedule.every((item) => item.is_paid);

  if (allPaid) {
    await this.prisma.projects.update({
      where: { id: projectId },
      data: { payment_status: 'fully_paid' },
    });

    // Send "All Paid" confirmation
    await this.notificationQueue.add('send_email', {
      template: 'payment_complete',
      data: { projectId },
    });
  }
}
```

---

## Phase 3: Balance Payment Reminders (Week 3)

### 3.1 Automated Reminder Schedule

**Triggers**:
- 30 days before event → "Second payment due soon"
- 7 days before event → "Final payment due"
- 1 day before event → "Last chance - payment overdue"
- Event date → "Payment overdue - contact support"

**File**: `backend/src/workers/payments/payments.processor.ts`

```typescript
@Processor('payments')
export class PaymentsProcessor {
  @Process('send_payment_reminder')
  async handlePaymentReminder(job: Job) {
    const { scheduleItemId } = job.data;

    const scheduleItem = await this.prisma.payment_schedules.findUnique({
      where: { id: scheduleItemId },
      include: { projects: true },
    });

    // Skip if already paid
    if (scheduleItem.is_paid) return;

    const daysUntilDue = Math.ceil(
      (new Date(scheduleItem.due_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
    );

    // Determine urgency
    let template = 'payment_reminder';
    if (daysUntilDue <= 0) {
      template = 'payment_overdue';
    } else if (daysUntilDue <= 1) {
      template = 'payment_urgent';
    }

    // Send email reminder
    await this.notificationQueue.add('send_email', {
      template,
      data: {
        amount: scheduleItem.amount,
        dueDate: scheduleItem.due_date,
        paymentLink: `${FRONTEND_URL}/payments/${scheduleItem.stripe_payment_intent_id}`,
        daysUntilDue,
      },
    });

    // Send SMS if urgent
    if (daysUntilDue <= 3) {
      await this.notificationQueue.add('send_sms', {
        message: `Payment of $${scheduleItem.amount} due in ${daysUntilDue} days. Pay now: [link]`,
      });
    }

    // Create in-app notification
    await this.prisma.notifications.create({
      data: {
        recipient_id: scheduleItem.projects.created_by,
        type: 'payment_reminder',
        title: 'Payment Due',
        message: `Payment of $${scheduleItem.amount} due ${scheduleItem.due_date}`,
      },
    });
  }
}
```

### 3.2 Escalation for Overdue Payments

**File**: `backend/src/payments/overdue-handler.service.ts`

```typescript
@Injectable()
export class OverduePaymentService {
  @Cron('0 9 * * *') // Daily at 9 AM
  async checkOverduePayments() {
    const overdueItems = await this.prisma.payment_schedules.findMany({
      where: {
        is_paid: false,
        due_date: { lt: new Date() },
      },
      include: { projects: true },
    });

    for (const item of overdueItems) {
      const daysOverdue = Math.floor(
        (Date.now() - new Date(item.due_date).getTime()) / (1000 * 60 * 60 * 24)
      );

      // Escalation levels
      if (daysOverdue === 1) {
        await this.sendOverdueNotice(item, 'gentle');
      } else if (daysOverdue === 3) {
        await this.sendOverdueNotice(item, 'firm');
      } else if (daysOverdue === 7) {
        await this.sendOverdueNotice(item, 'final');
        // Flag project as high-risk
        await this.flagProjectRisk(item.project_id, 'payment_overdue');
      } else if (daysOverdue >= 14) {
        // Auto-cancel or lock project
        await this.lockProject(item.project_id);
      }
    }
  }

  private async flagProjectRisk(projectId: string, reason: string) {
    await this.prisma.client_risk_flags.create({
      data: {
        project_id: projectId,
        flag_type: 'payment',
        severity: 'high',
        description: reason,
        flagged_by: 'system',
      },
    });
  }
}
```

---

## Phase 4: Balance Reconciliation (Week 4)

### 4.1 Payment Dashboard

**File**: `frontend/app/(dashboard)/projects/[id]/payments/page.tsx`

**Features**:
- Payment schedule timeline
- Paid vs outstanding amounts
- Download receipt/invoice
- "Send Reminder" manual button
- Refund option

### 4.2 Admin Payment Overview

**File**: `frontend/app/(dashboard)/admin/payments/page.tsx`

**Features**:
- All projects payment status
- Overdue payments highlighted
- Total outstanding balance
- Export to CSV
- Bulk reminder sending

---

## Configuration

### Environment Variables

```bash
# Deposit settings
DEPOSIT_PERCENTAGE_WEDDING=0.30
DEPOSIT_PERCENTAGE_CORPORATE=0.30
DEPOSIT_PERCENTAGE_OTHER=0.50
DEPOSIT_MIN_AMOUNT=500

# Payment schedule
BALANCE_PAYMENT_1_DAYS_BEFORE=30  # 30 days before event
BALANCE_PAYMENT_2_DAYS_BEFORE=7   # 7 days before event

# Reminder settings
PAYMENT_REMINDER_DAYS_BEFORE=3
PAYMENT_OVERDUE_ESCALATION_DAYS=7
PAYMENT_AUTO_CANCEL_DAYS=14

# Email templates
DEPOSIT_REQUEST_TEMPLATE=deposit_request
PAYMENT_REMINDER_TEMPLATE=payment_reminder
PAYMENT_CONFIRMATION_TEMPLATE=payment_confirmation
PAYMENT_OVERDUE_TEMPLATE=payment_overdue
```

---

## Email Templates

### Deposit Request Email
**Subject**: 🎉 Your Catering Contract is Ready - Deposit Required

**Body**:
```
Hi {client_name},

Great news! Your catering contract for {event_type} on {event_date} has been signed.

To confirm your booking, please pay the deposit of ${deposit_amount} by clicking below:

[Pay Deposit Now]

Your payment schedule:
- Deposit: ${deposit_amount} (Due immediately)
- Second Payment: ${second_payment} (Due {due_date_2})
- Final Payment: ${final_payment} (Due {due_date_3})

Questions? Reply to this email or call us at {phone}.

Thanks!
{company_name}
```

### Payment Reminder Email
**Subject**: Upcoming Payment Due for {event_type} on {event_date}

**Body**:
```
Hi {client_name},

Just a friendly reminder that your next payment of ${amount} is due on {due_date}.

[Pay Now]

Remaining balance: ${remaining_balance}

Thanks!
```

---

## Success Metrics

- ✅ 95% of deposits collected within 24 hours of contract signing
- ✅ 90% of balance payments on time
- ✅ <5% overdue payment rate
- ✅ 100% automated reminder delivery
- ✅ <2 hours average payment confirmation time
- ✅ Zero manual payment tracking required

---

## Future Enhancements

1. **Payment Plan Negotiation** - Allow clients to request custom schedules
2. **Auto-Applied Credits** - Apply refunds/credits automatically
3. **Loyalty Discounts** - Auto-apply discounts for repeat clients
4. **Early Payment Incentives** - Offer 5% discount for paying in full upfront
5. **Flexible Deposit Options** - Let clients choose deposit percentage
6. **Payment Insurance** - Offer cancellation insurance at checkout
7. **Partial Refund Automation** - Auto-calculate refunds based on cancellation date

---

## Testing Checklist

- [ ] Contract signed → Deposit email sent within 1 minute
- [ ] Deposit payment → Webhook updates status immediately
- [ ] Payment schedule → Reminders sent at correct intervals
- [ ] Overdue payment → Escalation emails sent
- [ ] Full payment → "All Paid" confirmation sent
- [ ] Refund request → Processed within 24 hours
- [ ] Client can view payment history in dashboard
- [ ] Admin can manually send reminders
- [ ] Analytics dashboard shows correct metrics

---

## Integration Points

### Triggers
1. **Contract Signed** → Generate payment schedule + send deposit request
2. **Payment Received** → Update schedule + send confirmation
3. **Payment Overdue** → Send reminder + flag risk
4. **All Paid** → Update project status + send completion email

### Dependencies
- Stripe API (payment processing)
- BullMQ (reminder scheduling)
- Notifications queue (email/SMS)
- Socket.io (real-time updates)
- PDF generation (receipts/invoices)

---

This roadmap provides a complete automated deposit and balance payment system that eliminates manual tracking and improves cash flow.

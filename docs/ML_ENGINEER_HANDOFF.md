# ML Engineer Handoff — Conversation Summaries + Reminder Content

This doc describes the two async jobs the backend now **enqueues but does not consume**. You own the worker side (TheCateringCompanyAgent service).

---

## 1. `project_summary_generation`

### When it fires
Every time a contract is created for a project — both via the AI intake flow (`ProjectsService.createFromAiIntake`) and the manual `POST /api/projects/:projectId/contracts` endpoint.

Enqueued in [backend/src/contracts/contracts.service.ts](../backend/src/contracts/contracts.service.ts) via:

```ts
await this.jobQueue.send('project_summary_generation', {
  projectId: string,
  contractId: string,
});
```

Queue backend is **pg-boss** (connection string = `DATABASE_URL`). Jobs land in the `pgboss.job` table with `name = 'project_summary_generation'`.

### What the worker must do

1. Pull the full conversation for the project:
   ```sql
   SELECT m.role, m.content, m.created_at
   FROM messages m
   JOIN threads t ON t.id = m.thread_id
   WHERE t.project_id = $projectId
   ORDER BY m.created_at ASC;
   ```
2. Pull structured slots:
   ```sql
   SELECT slots, filled_slots
   FROM ai_conversation_states
   WHERE project_id = $projectId
   ORDER BY updated_at DESC
   LIMIT 1;
   ```
3. Summarize via LLM. Target output: **3–6 sentences** describing what the client wants, key constraints (guest count, dietary, venue), open questions, and the outcome (which contract version this summary belongs to).
4. Write back to Postgres:
   ```sql
   UPDATE projects
   SET conversation_summary = $summary, updated_at = now()
   WHERE id = $projectId;

   INSERT INTO project_summaries (project_id, contract_id, summary)
   VALUES ($projectId, $contractId, $summary);
   ```

### Schema reference

```prisma
model projects {
  conversation_summary String?   // latest summary, mutable
  project_summaries    project_summaries[]
}

model project_summaries {
  id            String   @id @default(dbgenerated("gen_random_uuid()")) @db.Uuid
  project_id    String   @db.Uuid
  contract_id   String?  @db.Uuid
  summary       String
  generated_at  DateTime @default(now())
}
```

### Suggested prompt skeleton

```
System: You are summarizing a catering planning conversation at the point a contract was generated. Produce a neutral, factual recap for internal staff review.

Input:
- slots (structured event details): {{slots json}}
- transcript (chronological): {{messages}}

Output: 3–6 sentences covering (1) event type + date + guest count, (2) menu direction + any dietary constraints, (3) venue / service style, (4) notable client preferences or unresolved asks.
```

### Failure handling
pg-boss retries 5x with backoff. If the LLM is unreachable, fail the job (throw) — pg-boss will reschedule. Don't write a partial summary. If after retries it still fails, log to the existing worker observability stack; the contract flow does **not** block on summary completion.

---

## 2. `email_notification`

### When it fires
Every time the backend's `PaymentRemindersService` finds an item that needs a reminder (daily cron `0 9 * * *`, plus the staff-only manual trigger `POST /api/payments/reminders/run`).

Enqueued per recipient in [backend/src/payments/payment-reminders.service.ts](../backend/src/payments/payment-reminders.service.ts):

```ts
await this.jobQueue.send('email_notification', {
  recipient_user_id: string,
  template_key: 'payment_reminder_upcoming' | 'payment_reminder_overdue',
  payload: {
    project_id: string,
    project_title: string,
    schedule_item_id: string,
    amount: number,
    due_date: Date,
    label: string | null,
  },
});
```

An in-app notification row is also written directly to the `notifications` table — you only handle the **email channel**.

### What the worker must do

1. Resolve `recipient_user_id` → email address (read `users.email`).
2. Load the template from `notification_templates` by `template_key` (subject + body with `{{variables}}`).
3. Render the template with `payload` + project/user context.
4. Send via SendGrid / SES / whatever provider is configured for this env.
5. On success, update the matching `notifications` row (same `template_key`, same recipient, `status='pending'`, most recent) to `status='sent'`, `sent_at=now()`.
6. On failure, increment `attempt_count` and `last_attempt_at`; let pg-boss retry.

### Template keys to add (if not present)
- `payment_reminder_upcoming` — "Payment of $X for {{project_title}} is due on {{due_date}}."
- `payment_reminder_overdue` — "Your payment of $X for {{project_title}} was due {{due_date}} and is now overdue."

### Dedup contract
The backend already guards against duplicate reminders:
- `payment_schedule_items.last_reminder_sent_at` — backend won't re-enqueue within 24h
- `payment_schedule_items.overdue_notified_at` — overdue is a one-shot

So the worker can treat every job as "send it"; no dedup on your side.

---

## Environment
- `DATABASE_URL` — same Postgres as backend (pg-boss shares the DB)
- `PAYMENT_REMINDER_DAYS` — set on the backend, not the worker (default 7)
- LLM creds — your existing agent-service env

## Local testing checklist
- [ ] Create a contract via the UI → see a new row in pgboss.job with `name='project_summary_generation'`
- [ ] Worker picks it up, writes `projects.conversation_summary` + a `project_summaries` row
- [ ] Backdate a `payment_schedule_items.due_date` to tomorrow, call `POST /api/payments/reminders/run` as a `@catering-company.com` user → worker receives `email_notification` job and sends the email
- [ ] `notifications` row flips from `pending` → `sent`

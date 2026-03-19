

import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import type { WebhookJobData } from '../types/jobs';

export async function processWebhook(job: { id: string; data: WebhookJobData }): Promise<void> {
  const { webhookEventId, userId, projectId } = job.data;
  const log = createJobLogger('webhooks', job.id!, userId, projectId);

  log.info({ webhookEventId }, 'Processing webhook event');

  const webhookEvent = await prisma.webhook_events.findUnique({
    where: { id: webhookEventId },
  });

  if (!webhookEvent) {
    log.warn({ webhookEventId }, 'Webhook event not found, skipping');
    return;
  }

  // Idempotency check
  if (webhookEvent.status === 'processed') {
    log.info({ webhookEventId }, 'Webhook event already processed, skipping');
    return;
  }

  const eventType = webhookEvent.event_type;
  const payload = webhookEvent.payload as Record<string, unknown> | null;

  log.info({ eventType, provider: webhookEvent.provider }, 'Handling webhook event type');

  // Route based on event_type and update domain tables
  switch (eventType) {
    case 'payment_intent.succeeded': {
      const paymentIntentId = (payload as Record<string, unknown>)?.payment_intent_id as string | undefined;
      if (paymentIntentId) {
        const payment = await prisma.payments.findFirst({
          where: { gateway_payment_intent_id: paymentIntentId },
        });

        if (payment && payment.status !== 'paid') {
          await prisma.payments.update({
            where: { id: payment.id },
            data: { status: 'paid', paid_at: new Date() },
          });
          log.info({ paymentId: payment.id }, 'Payment marked as paid via webhook');
        }
      }
      break;
    }

    case 'payment_intent.payment_failed': {
      const paymentIntentId = (payload as Record<string, unknown>)?.payment_intent_id as string | undefined;
      if (paymentIntentId) {
        const payment = await prisma.payments.findFirst({
          where: { gateway_payment_intent_id: paymentIntentId },
        });

        if (payment && payment.status !== 'failed') {
          await prisma.payments.update({
            where: { id: payment.id },
            data: { status: 'failed' },
          });
          log.info({ paymentId: payment.id }, 'Payment marked as failed via webhook');
        }
      }
      break;
    }

    default:
      log.info({ eventType }, 'Unhandled webhook event type, marking as processed');
      break;
  }

  // Mark webhook event as processed
  await prisma.webhook_events.update({
    where: { id: webhookEventId },
    data: {
      status: 'processed',
      processed_at: new Date(),
      attempt_count: { increment: 1 },
      last_attempt_at: new Date(),
    },
  });

  // Create events row for audit trail
  await prisma.events.create({
    data: {
      event_type: `webhook.${eventType || 'unknown'}`,
      project_id: projectId || null,
      actor_id: userId || null,
      payload: {
        webhookEventId,
        provider: webhookEvent.provider,
        externalEventId: webhookEvent.external_event_id,
      },
    },
  });

  log.info({ webhookEventId }, 'Webhook event processed successfully');
}

import { Job, Queue } from 'bullmq';
import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import { createRedisConnection } from '../lib/redis';
import type { PaymentJobData, NotificationJobData } from '../types/jobs';
import { randomUUID } from 'crypto';

const STRIPE_ENABLED = process.env.STRIPE_ENABLED === 'true';

let notificationQueue: Queue<NotificationJobData> | null = null;

function getNotificationQueue(): Queue<NotificationJobData> {
  if (!notificationQueue) {
    notificationQueue = new Queue<NotificationJobData>('notifications', {
      connection: createRedisConnection(),
    });
  }
  return notificationQueue;
}

export async function processPayment(job: Job<PaymentJobData>): Promise<void> {
  const { paymentId, paymentIntentId, userId, projectId } = job.data;
  const log = createJobLogger('payments', job.id!, userId, projectId);

  log.info({ paymentId, paymentIntentId }, 'Processing payment');

  const payment = await prisma.payments.findUnique({
    where: { id: paymentId },
  });

  if (!payment) {
    log.warn({ paymentId }, 'Payment not found, skipping');
    return;
  }

  // Idempotency check
  if (payment.status === 'paid') {
    log.info({ paymentId }, 'Payment already marked as paid, skipping');
    return;
  }

  // If Stripe is enabled and we have a payment intent, verify with Stripe
  if (STRIPE_ENABLED && paymentIntentId) {
    log.info({ paymentIntentId }, 'STRIPE_ENABLED=true, would verify payment intent with Stripe');
    // TODO: Integrate with Stripe SDK to verify payment intent status
    // const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);
    // const intent = await stripe.paymentIntents.retrieve(paymentIntentId);
    // if (intent.status !== 'succeeded') { throw new Error('Payment intent not succeeded'); }
  }

  // Update payment status
  await prisma.payments.update({
    where: { id: paymentId },
    data: {
      status: 'paid',
      paid_at: new Date(),
    },
  });

  log.info({ paymentId }, 'Payment marked as paid');

  // Create events row for audit trail
  const event = await prisma.events.create({
    data: {
      event_type: 'payment.paid',
      project_id: payment.project_id || null,
      actor_id: userId || null,
      payload: {
        paymentId,
        amount: payment.amount.toString(),
        currency: payment.currency,
      },
    },
  });

  // Enqueue notification job
  if (userId) {
    const notification = await prisma.notifications.create({
      data: {
        event_id: event.id,
        recipient_user_id: userId,
        channel: 'in_app',
        payload: {
          title: 'Payment Received',
          message: `Payment of ${payment.amount} ${payment.currency} has been received.`,
        },
      },
    });

    const notifJobData: NotificationJobData = {
      jobId: randomUUID(),
      userId,
      projectId: payment.project_id || undefined,
      notificationId: notification.id,
      channel: 'in_app',
    };

    await getNotificationQueue().add('send-notification', notifJobData, {
      attempts: 5,
      backoff: { type: 'exponential', delay: 2000 },
    });

    log.info({ notificationId: notification.id }, 'Notification job enqueued');
  }

  log.info({ paymentId }, 'Payment processing completed');
}

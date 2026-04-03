// eslint-disable-next-line @typescript-eslint/no-var-requires, @typescript-eslint/no-require-imports
const PgBossModule = require('pg-boss');
const PgBoss = PgBossModule.PgBoss ?? PgBossModule.default ?? PgBossModule;
import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import type { PaymentJobData, NotificationJobData } from '../types/jobs';
import { randomUUID } from 'crypto';

const STRIPE_ENABLED = process.env.STRIPE_ENABLED === 'true';

// Shared pg-boss instance for enqueuing notification sub-jobs from within this processor.
let boss: any = null;

async function getBoss(): Promise<any> {
  if (!boss) {
    boss = new PgBoss({ connectionString: process.env.DATABASE_URL! });
    await boss.start();
  }
  return boss;
}

export async function processPayment(job: { id: string; data: PaymentJobData }): Promise<void> {
  const { paymentId, paymentIntentId, userId, projectId } = job.data;
  const log = createJobLogger('payments', job.id!, userId, projectId);

  log.info({ paymentId, paymentIntentId }, 'Processing payment');

  const payment = await prisma.payments.findUnique({ where: { id: paymentId } });

  if (!payment) {
    log.warn({ paymentId }, 'Payment not found, skipping');
    return;
  }

  if (payment.status === 'paid') {
    log.info({ paymentId }, 'Payment already marked as paid, skipping');
    return;
  }

  if (STRIPE_ENABLED && paymentIntentId) {
    log.info({ paymentIntentId }, 'STRIPE_ENABLED=true, would verify payment intent with Stripe');
  }

  await prisma.payments.update({
    where: { id: paymentId },
    data: { status: 'paid', paid_at: new Date() },
  });

  log.info({ paymentId }, 'Payment marked as paid');

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

    const b = await getBoss();
    await b.send('notifications', notifJobData);
    log.info({ notificationId: notification.id }, 'Notification job enqueued');
  }

  log.info({ paymentId }, 'Payment processing completed');
}

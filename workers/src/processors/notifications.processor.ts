

import prisma from '../lib/prisma';
import { createJobLogger } from '../lib/logger';
import type { NotificationJobData } from '../types/jobs';

const NOTIFICATION_MOCK = process.env.NOTIFICATION_MOCK !== 'false'; // Default to true

export async function processNotification(job: { id: string; data: NotificationJobData }): Promise<void> {
  const { notificationId, channel, userId, projectId } = job.data;
  const log = createJobLogger('notifications', job.id!, userId, projectId);

  log.info({ notificationId, channel }, 'Processing notification');

  const notification = await prisma.notifications.findUnique({
    where: { id: notificationId },
  });

  if (!notification) {
    log.warn({ notificationId }, 'Notification not found, skipping');
    return;
  }

  // Idempotency check
  if (notification.status === 'sent') {
    log.info({ notificationId }, 'Notification already sent, skipping');
    return;
  }

  // Update attempt count
  await prisma.notifications.update({
    where: { id: notificationId },
    data: {
      attempt_count: { increment: 1 },
      last_attempt_at: new Date(),
    },
  });

  if (NOTIFICATION_MOCK) {
    log.info(
      { notificationId, channel, payload: notification.payload },
      'NOTIFICATION_MOCK=true, logging notification instead of sending',
    );
  } else {
    // TODO: Implement actual delivery based on channel
    switch (channel) {
      case 'email': {
        log.info({ notificationId }, 'Would send email via SendGrid');
        // const sgMail = require('@sendgrid/mail');
        // sgMail.setApiKey(process.env.SENDGRID_API_KEY);
        // await sgMail.send({ to, from, subject, html });
        break;
      }

      case 'sms': {
        log.info({ notificationId }, 'Would send SMS via Twilio');
        // const twilio = require('twilio')(process.env.TWILIO_SID, process.env.TWILIO_TOKEN);
        // await twilio.messages.create({ to, from: process.env.TWILIO_FROM, body });
        break;
      }

      case 'in_app': {
        log.info({ notificationId }, 'In-app notification stored, no external delivery needed');
        break;
      }

      default:
        log.warn({ notificationId, channel }, 'Unknown notification channel');
        break;
    }
  }

  // Mark notification as sent
  await prisma.notifications.update({
    where: { id: notificationId },
    data: {
      status: 'sent',
      sent_at: new Date(),
    },
  });

  log.info({ notificationId, channel }, 'Notification processed successfully');
}

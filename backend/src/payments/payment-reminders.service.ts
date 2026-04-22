import { Injectable, Logger, OnModuleInit } from '@nestjs/common';

import { PrismaService } from '../prisma.service';

import { JobQueueService } from '../job_queue/job-queue.service';



const REMINDER_WINDOW_DAYS = Number(process.env.PAYMENT_REMINDER_DAYS || 7);

const QUEUE = 'payment_reminders_daily';

const CRON = '0 9 * * *'; // 09:00 UTC daily



@Injectable()

export class PaymentRemindersService implements OnModuleInit {

  private readonly logger = new Logger(PaymentRemindersService.name);



  constructor(

    private readonly prisma: PrismaService,

    private readonly jobQueue: JobQueueService,

  ) {}



  async onModuleInit() {

    try {

      // Register worker — runs scanAndNotify() whenever the scheduled job fires.

      // eslint-disable-next-line @typescript-eslint/no-explicit-any

      const boss = (this.jobQueue as any).boss;

      if (!boss) return;

      await boss.createQueue(QUEUE).catch(() => {
        // pg-boss v12 requires queues to exist before workers subscribe/schedule.
      });

      await boss.work(QUEUE, async () => {

        await this.scanAndNotify();

      });

      await boss.schedule(QUEUE, CRON);

      this.logger.log(`Scheduled daily payment reminders (cron=${CRON}, window=${REMINDER_WINDOW_DAYS}d)`);

    } catch (err) {

      this.logger.error('Failed to register payment reminder schedule', err as Error);

    }

  }



  /**

   * Scans payment_schedule_items for:

   *  - upcoming: due within [now, now+N days], status=pending, not yet reminded in last 24h

   *  - overdue: due_date < now, status=pending, not yet notified as overdue

   * Sends notifications to project owner + assigned CRM staff.

   */

  async scanAndNotify() {

    const now = new Date();

    const windowEnd = new Date(now.getTime() + REMINDER_WINDOW_DAYS * 24 * 60 * 60 * 1000);

    const twentyFourHoursAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);



    // Upcoming

    const upcoming = await this.prisma.payment_schedule_items.findMany({

      where: {

        status: 'pending',

        due_date: { gte: now, lte: windowEnd },

        OR: [

          { last_reminder_sent_at: null },

          { last_reminder_sent_at: { lt: twentyFourHoursAgo } },

        ],

      },

      include: {

        payment_schedules: {

          include: {

            projects: {

              select: {

                id: true,

                title: true,

                owner_user_id: true,

                crm_pipeline: { select: { assigned_staff_user_id: true } },

              },

            },

          },

        },

      },

    });



    // Overdue

    const overdue = await this.prisma.payment_schedule_items.findMany({

      where: {

        status: 'pending',

        due_date: { lt: now },

        overdue_notified_at: null,

      },

      include: {

        payment_schedules: {

          include: {

            projects: {

              select: {

                id: true,

                title: true,

                owner_user_id: true,

                crm_pipeline: { select: { assigned_staff_user_id: true } },

              },

            },

          },

        },

      },

    });



    for (const item of upcoming) {

      await this.notifyItem(item, 'payment_reminder_upcoming');

      await this.prisma.payment_schedule_items.update({

        where: { id: item.id },

        data: { last_reminder_sent_at: now },

      });

    }



    for (const item of overdue) {

      await this.notifyItem(item, 'payment_reminder_overdue');

      await this.prisma.payment_schedule_items.update({

        where: { id: item.id },

        data: { overdue_notified_at: now },

      });

    }



    const result = { upcoming: upcoming.length, overdue: overdue.length };

    this.logger.log(`Payment reminders fired: ${JSON.stringify(result)}`);

    return result;

  }



  // eslint-disable-next-line @typescript-eslint/no-explicit-any

  private async notifyItem(item: any, templateKey: string) {

    const project = item.payment_schedules?.projects;

    if (!project) return;



    const recipients = new Set<string>();

    if (project.owner_user_id) recipients.add(project.owner_user_id);

    const staffId = project.crm_pipeline?.assigned_staff_user_id;

    if (staffId) recipients.add(staffId);



    const payload = {

      project_id: project.id,

      project_title: project.title,

      schedule_item_id: item.id,

      amount: Number(item.amount),

      due_date: item.due_date,

      label: item.label,

    };



    for (const recipientId of recipients) {

      // in-app notification row

      const inAppNotification = await this.prisma.notifications.create({

        data: {

          recipient_user_id: recipientId,

          channel: 'in_app',

          template_key: templateKey,

          payload,

          status: 'pending',

        },

      });

      try {

        await this.jobQueue.send('notifications', {

          notificationId: inAppNotification.id,

          channel: 'in_app',

          userId: recipientId,

          projectId: project.id,

        });

      } catch (err) {

        this.logger.warn(`Failed to enqueue in-app notification for ${recipientId}: ${(err as Error).message}`);

      }

      // email notification row + queue handoff

      const emailNotification = await this.prisma.notifications.create({

        data: {

          recipient_user_id: recipientId,

          channel: 'email',

          template_key: templateKey,

          payload,

          status: 'pending',

        },

      });

      try {

        await this.jobQueue.send('notifications', {

          notificationId: emailNotification.id,

          channel: 'email',

          userId: recipientId,

          projectId: project.id,

        });

      } catch (err) {

        this.logger.warn(`Failed to enqueue email notification for ${recipientId}: ${(err as Error).message}`);

      }

    }

  }

}


import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma.service';

@Injectable()
export class NotificationsService {
  private readonly logger = new Logger(NotificationsService.name);

  constructor(private readonly prisma: PrismaService) {}

  async listForUser(recipientUserId: string) {
    return this.prisma.notifications.findMany({
      where: { recipient_user_id: recipientUserId },
      orderBy: { created_at: 'desc' },
    });
  }

  async acknowledge(notificationId: string, recipientUserId: string) {
    const notification = await this.prisma.notifications.findFirst({
      where: {
        id: notificationId,
        recipient_user_id: recipientUserId,
      },
    });

    if (!notification) {
      throw new NotFoundException('Notification not found');
    }

    return this.prisma.notifications.update({
      where: { id: notificationId },
      data: { is_read: true },
    });
  }
}

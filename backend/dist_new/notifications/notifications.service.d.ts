import { PrismaService } from '../prisma.service';
export declare class NotificationsService {
    private readonly prisma;
    private readonly logger;
    constructor(prisma: PrismaService);
    listForUser(recipientUserId: string): Promise<{
        id: string;
        status: string;
        created_at: Date;
        sent_at: Date | null;
        payload: import("@prisma/client/runtime/library").JsonValue | null;
        attempt_count: number;
        last_attempt_at: Date | null;
        event_id: string | null;
        recipient_user_id: string | null;
        channel: import(".prisma/client").$Enums.notification_channel;
        template_key: string | null;
        is_read: boolean;
    }[]>;
    acknowledge(notificationId: string, recipientUserId: string): Promise<{
        id: string;
        status: string;
        created_at: Date;
        sent_at: Date | null;
        payload: import("@prisma/client/runtime/library").JsonValue | null;
        attempt_count: number;
        last_attempt_at: Date | null;
        event_id: string | null;
        recipient_user_id: string | null;
        channel: import(".prisma/client").$Enums.notification_channel;
        template_key: string | null;
        is_read: boolean;
    }>;
}

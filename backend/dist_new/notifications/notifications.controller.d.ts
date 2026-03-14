import { NotificationsService } from './notifications.service';
import { JwtPayload } from '../common/interfaces/jwt-payload.interface';
export declare class NotificationsController {
    private readonly notificationsService;
    constructor(notificationsService: NotificationsService);
    list(user: JwtPayload): Promise<{
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
    acknowledge(id: string, user: JwtPayload): Promise<{
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

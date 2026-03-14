import { Queue } from 'bullmq';
import { MessagesService } from './messages.service';
import { SocketsGateway } from '../sockets/sockets.gateway';
export declare class MessagesController {
    private readonly messagesService;
    private readonly socketsGateway;
    private readonly vectorQueue;
    private readonly logger;
    constructor(messagesService: MessagesService, socketsGateway: SocketsGateway, vectorQueue: Queue);
    listThreads(projectId: string): Promise<{
        threads: {
            id: string;
            created_at: Date;
            project_id: string;
            created_by: string | null;
            subject: string | null;
            is_resolved: boolean;
            message_count: number;
            last_activity_at: Date | null;
        }[];
    }>;
    getThread(threadId: string, page?: string, limit?: string): Promise<{
        thread: {
            id: string;
            created_at: Date;
            project_id: string;
            created_by: string | null;
            subject: string | null;
            is_resolved: boolean;
            message_count: number;
            last_activity_at: Date | null;
        };
        messages: {
            mentioned_user_ids: string[];
            message_mentions: undefined;
            attachments: import("@prisma/client/runtime/library").JsonValue | null;
            id: string;
            created_at: Date;
            project_id: string;
            ai_conversation_state_id: string | null;
            thread_id: string;
            parent_message_id: string | null;
            author_id: string | null;
            sender_type: string | null;
            content: string;
            qdrant_vector_id: string | null;
            vector_indexed_at: Date | null;
            vector_status: string;
            is_deleted: boolean;
            last_edited_at: Date | null;
        }[];
        pagination: {
            page: number;
            limit: number;
            totalMessages: number;
            totalPages: number;
        };
    }>;
    createThread(projectId: string, user: {
        userId: string;
    }, body: {
        subject?: string;
    }): Promise<{
        thread: {
            id: string;
            created_at: Date;
            project_id: string;
            created_by: string | null;
            subject: string | null;
            is_resolved: boolean;
            message_count: number;
            last_activity_at: Date | null;
        };
    }>;
    getProjectCollaborators(projectId: string): Promise<{
        collaborators: {
            id: string;
            email: string;
            role: string | null;
        }[];
    }>;
    createMessage(threadId: string, user: {
        userId: string;
    }, body: {
        content: string;
        parentMessageId?: string;
        mentionedUserIds?: string[];
    }): Promise<{
        message: {
            attachments: import("@prisma/client/runtime/library").JsonValue | null;
            id: string;
            created_at: Date;
            project_id: string;
            ai_conversation_state_id: string | null;
            thread_id: string;
            parent_message_id: string | null;
            author_id: string | null;
            sender_type: string | null;
            content: string;
            qdrant_vector_id: string | null;
            vector_indexed_at: Date | null;
            vector_status: string;
            is_deleted: boolean;
            last_edited_at: Date | null;
        };
    }>;
}

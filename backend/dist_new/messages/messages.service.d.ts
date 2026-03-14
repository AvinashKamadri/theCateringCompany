import { PrismaService } from '../prisma.service';
interface CreateThreadDto {
    subject?: string;
}
interface CreateMessageDto {
    content: string;
    parentMessageId?: string;
    mentionedUserIds?: string[];
}
export declare class MessagesService {
    private readonly prisma;
    constructor(prisma: PrismaService);
    listThreads(projectId: string): Promise<{
        id: string;
        created_at: Date;
        project_id: string;
        created_by: string | null;
        subject: string | null;
        is_resolved: boolean;
        message_count: number;
        last_activity_at: Date | null;
    }[]>;
    getThread(threadId: string, page: number, limit: number): Promise<{
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
    createThread(userId: string, projectId: string, dto: CreateThreadDto): Promise<{
        id: string;
        created_at: Date;
        project_id: string;
        created_by: string | null;
        subject: string | null;
        is_resolved: boolean;
        message_count: number;
        last_activity_at: Date | null;
    }>;
    createMessage(userId: string, threadId: string, dto: CreateMessageDto): Promise<{
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
        projectId: string;
        mentionedUserIds: string[];
    }>;
    private extractMentions;
    getProjectCollaborators(projectId: string): Promise<{
        id: string;
        email: string;
        role: string | null;
    }[]>;
}
export {};

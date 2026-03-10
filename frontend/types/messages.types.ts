export interface Thread {
  id: string;
  project_id: string;
  subject: string | null;
  created_by: string;
  created_at: string;
  last_activity_at: string;
  message_count: number;
}

export interface Message {
  id: string;
  thread_id: string;
  project_id: string;
  author_id: string;
  sender_type: 'user' | 'ai' | 'system';
  content: string;
  parent_message_id: string | null;
  mentioned_user_ids: string[];
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

export interface Collaborator {
  id: string;
  email: string;
  role: string;
}

export interface CreateThreadDto {
  subject?: string;
}

export interface CreateMessageDto {
  content: string;
  parentMessageId?: string;
  mentionedUserIds?: string[];
}

export interface GetThreadResponse {
  thread: Thread;
  messages: Message[];
  pagination: {
    page: number;
    limit: number;
    totalMessages: number;
    totalPages: number;
  };
}

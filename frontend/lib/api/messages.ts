import { apiClient } from './client';
import type {
  Thread,
  Message,
  Collaborator,
  CreateThreadDto,
  CreateMessageDto,
  GetThreadResponse,
} from '@/types/messages.types';

export const messagesApi = {
  // Get threads for a project
  getThreads: async (projectId: string): Promise<{ threads: Thread[] }> => {
    return apiClient.get(`/projects/${projectId}/threads`);
  },

  // Get a single thread with messages
  getThread: async (threadId: string, page = 1, limit = 50): Promise<GetThreadResponse> => {
    return apiClient.get(`/threads/${threadId}`, {
      params: { page, limit },
    });
  },

  // Create a new thread
  createThread: async (projectId: string, dto: CreateThreadDto): Promise<{ thread: Thread }> => {
    return apiClient.post(`/projects/${projectId}/threads`, dto);
  },

  // Create a message in a thread
  createMessage: async (threadId: string, dto: CreateMessageDto): Promise<{ message: Message }> => {
    return apiClient.post(`/threads/${threadId}/messages`, dto);
  },

  // Get project collaborators for mentions
  getCollaborators: async (projectId: string): Promise<{ collaborators: Collaborator[] }> => {
    return apiClient.get(`/projects/${projectId}/collaborators`);
  },
};

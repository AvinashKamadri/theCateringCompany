/**
 * Chat AI API Service
 * Integrates with ML Chat API for conversational event intake
 * Based on: CHAT_API_INTEGRATION_GUIDE.md
 */

import axios, { AxiosError } from 'axios';
import type { ChatRequest, ChatResponse, ConversationState } from '@/types/chat-ai.types';

const ML_API_BASE_URL = process.env.NEXT_PUBLIC_ML_API_URL || 'http://localhost:8000';

/**
 * Axios instance for ML Chat API
 */
export const chatAiClient = axios.create({
  baseURL: ML_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 90000, // 90 second timeout for AI responses (contract generation can take time)
});

// Response interceptor for error handling
chatAiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    // Only log non-network errors (network errors just mean the ML agent is offline)
    if (error.response) {
      console.error('Chat AI API error:', error.response.data);
    }
    return Promise.reject(error.response?.data || error);
  }
);

export interface SendMessageOptions {
  message: string;
  threadId?: string;
  authorId?: string;
  projectId?: string;
  userId?: string;
}

export const chatAiApi = {
  /**
   * Send a message to the AI chat agent
   * @param options Message options
   * @returns AI response with conversation state
   */
  sendMessage: async (options: SendMessageOptions): Promise<ChatResponse> => {
    const request: ChatRequest = {
      message: options.message,
      thread_id: options.threadId,
      author_id: options.authorId,
      project_id: options.projectId,
      user_id: options.userId,
    };

    try {
      const response = await chatAiClient.post<ChatResponse>('/chat', request);
      return response as unknown as ChatResponse;
    } catch (error) {
      throw new Error('Failed to send message to AI agent');
    }
  },

  /**
   * Send message with retry logic for network failures
   * @param options Message options
   * @param maxRetries Maximum number of retries
   * @returns AI response
   */
  sendMessageWithRetry: async (
    options: SendMessageOptions,
    maxRetries = 3
  ): Promise<ChatResponse> => {
    let lastError: any;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        return await chatAiApi.sendMessage(options);
      } catch (error: any) {
        lastError = error;

        // Don't retry validation errors (4xx)
        if (error.response?.status >= 400 && error.response?.status < 500) {
          throw error;
        }

        // Exponential backoff for server errors (5xx)
        if (attempt < maxRetries - 1) {
          const delay = Math.pow(2, attempt) * 1000;
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError;
  },

  /**
   * Check if ML API is healthy
   * @returns True if API is responding
   */
  checkHealth: async (): Promise<boolean> => {
    try {
      const response = await chatAiClient.get('/health');
      return (response as any).status === 'ok';
    } catch (error) {
      return false;
    }
  },

  /**
   * Start a new conversation
   * @param initialMessage First message to the AI
   * @param projectId Optional project ID
   * @returns AI response with new thread_id
   */
  startConversation: async (
    initialMessage: string,
    projectId?: string
  ): Promise<ChatResponse> => {
    return chatAiApi.sendMessage({
      message: initialMessage,
      projectId,
    });
  },

  /**
   * Continue an existing conversation
   */
  continueConversation: async (
    threadId: string,
    message: string
  ): Promise<ChatResponse> => {
    return chatAiApi.sendMessage({ threadId, message });
  },

  /**
   * Fetch full conversation state including all filled slot values.
   * Used after is_complete=true to get rich slot data from the Desktop agent.
   */
  getConversation: async (threadId: string): Promise<ConversationState> => {
    try {
      const response = await chatAiClient.get<ConversationState>(`/conversation/${threadId}`);
      return response as unknown as ConversationState;
    } catch (error) {
      throw new Error('Failed to fetch conversation state');
    }
  },
};

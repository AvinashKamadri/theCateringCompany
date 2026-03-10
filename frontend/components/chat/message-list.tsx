"use client";

import { useEffect, useRef } from 'react';
import type { Message } from '@/types/messages.types';
import { useAuthStore } from '@/lib/store/auth-store';
import { cn } from '@/lib/utils';

interface MessageListProps {
  messages: Message[];
  isLoading?: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const currentUser = useAuthStore((state) => state.user);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
          <p className="mt-2 text-sm text-gray-500">Loading messages...</p>
        </div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-500">No messages yet. Start the conversation!</p>
        </div>
      </div>
    );
  }

  const renderMessageContent = (content: string) => {
    // Replace @[userId:displayName] with styled mentions
    return content.replace(/@\[([a-f0-9-]+):([^\]]+)\]/g, (match, userId, displayName) => {
      return `<span class="bg-blue-100 text-blue-700 px-1 rounded font-medium">@${displayName}</span>`;
    });
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => {
        const isOwnMessage = message.author_id === currentUser?.id;
        const isAI = message.sender_type === 'ai';
        const isSystem = message.sender_type === 'system';

        return (
          <div
            key={message.id}
            className={cn(
              'flex',
              isOwnMessage && !isAI && !isSystem ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={cn(
                'max-w-[70%] rounded-lg px-4 py-2',
                isSystem
                  ? 'bg-gray-100 text-gray-600 text-sm italic'
                  : isAI
                    ? 'bg-purple-100 text-purple-900'
                    : isOwnMessage
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-900'
              )}
            >
              {isAI && (
                <div className="flex items-center gap-2 mb-1">
                  <div className="w-6 h-6 rounded-full bg-purple-600 flex items-center justify-center text-white text-xs font-bold">
                    AI
                  </div>
                  <span className="text-xs font-medium">AI Assistant</span>
                </div>
              )}
              <div
                dangerouslySetInnerHTML={{
                  __html: renderMessageContent(message.content),
                }}
              />
              <div
                className={cn(
                  'text-xs mt-1',
                  isOwnMessage && !isAI && !isSystem ? 'text-blue-100' : 'text-gray-500'
                )}
              >
                {new Date(message.created_at).toLocaleTimeString('en-US', {
                  hour: 'numeric',
                  minute: '2-digit',
                })}
              </div>
            </div>
          </div>
        );
      })}
      <div ref={messagesEndRef} />
    </div>
  );
}

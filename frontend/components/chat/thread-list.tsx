"use client";

import { MessageCircle, Plus } from 'lucide-react';
import type { Thread } from '@/types/messages.types';
import { cn } from '@/lib/utils';

interface ThreadListProps {
  threads: Thread[];
  activeThreadId?: string;
  onSelectThread: (threadId: string) => void;
  onCreateThread: () => void;
  isLoading?: boolean;
}

export function ThreadList({
  threads,
  activeThreadId,
  onSelectThread,
  onCreateThread,
  isLoading,
}: ThreadListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="inline-block h-6 w-6 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Conversations</h2>
        <button
          onClick={onCreateThread}
          className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
        >
          <Plus className="h-4 w-4" />
          New
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {threads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <MessageCircle className="h-12 w-12 text-gray-400 mb-3" />
            <p className="text-sm text-gray-500">No conversations yet</p>
            <p className="text-xs text-gray-400 mt-1">Create a new conversation to get started</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {threads.map((thread) => {
              const isActive = thread.id === activeThreadId;
              const lastActivity = new Date(thread.last_activity_at);
              const now = new Date();
              const diffMs = now.getTime() - lastActivity.getTime();
              const diffMins = Math.floor(diffMs / 60000);
              const diffHours = Math.floor(diffMs / 3600000);
              const diffDays = Math.floor(diffMs / 86400000);

              let timeAgo = '';
              if (diffMins < 1) {
                timeAgo = 'Just now';
              } else if (diffMins < 60) {
                timeAgo = `${diffMins}m ago`;
              } else if (diffHours < 24) {
                timeAgo = `${diffHours}h ago`;
              } else {
                timeAgo = `${diffDays}d ago`;
              }

              return (
                <button
                  key={thread.id}
                  onClick={() => onSelectThread(thread.id)}
                  className={cn(
                    'w-full px-4 py-3 text-left hover:bg-gray-50 transition',
                    isActive && 'bg-blue-50 border-l-4 border-blue-600'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-gray-900 truncate">
                        {thread.subject || 'Untitled Conversation'}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-500">{timeAgo}</span>
                        <span className="text-xs text-gray-400">•</span>
                        <span className="text-xs text-gray-500">
                          {thread.message_count} {thread.message_count === 1 ? 'message' : 'messages'}
                        </span>
                      </div>
                    </div>
                    <MessageCircle
                      className={cn('h-5 w-5 flex-shrink-0', isActive ? 'text-blue-600' : 'text-gray-400')}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

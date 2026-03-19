"use client";

import { useState } from 'react';
import { MessageCircle, Plus, Loader2, Check, X } from 'lucide-react';
import type { Thread } from '@/types/messages.types';
import { cn } from '@/lib/utils';

interface ThreadListProps {
  threads: Thread[];
  activeThreadId?: string;
  onSelectThread: (threadId: string) => void;
  onCreateThread: (subject?: string) => void;
  isLoading?: boolean;
}

export function ThreadList({
  threads,
  activeThreadId,
  onSelectThread,
  onCreateThread,
  isLoading,
}: ThreadListProps) {
  const [creating, setCreating] = useState(false);
  const [subject, setSubject] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreateThread(subject.trim() || undefined);
    setSubject('');
    setCreating(false);
  };

  const handleCancel = () => {
    setSubject('');
    setCreating(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-4 w-4 animate-spin text-neutral-300" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-neutral-900">Conversations</h2>
        {!creating && (
          <button
            onClick={() => setCreating(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 bg-black text-white rounded-lg hover:bg-neutral-800 transition-colors text-xs font-medium"
          >
            <Plus className="h-3.5 w-3.5" />
            New
          </button>
        )}
      </div>

      {/* Inline new thread form */}
      {creating && (
        <form onSubmit={handleSubmit} className="px-3 py-2.5 border-b border-neutral-200 flex items-center gap-2">
          <input
            autoFocus
            type="text"
            placeholder="Subject (optional)"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="flex-1 text-sm px-2.5 py-1.5 border border-neutral-200 rounded-lg outline-none focus:ring-1 focus:ring-neutral-900"
          />
          <button type="submit" className="p-1.5 text-neutral-900 hover:bg-neutral-100 rounded-md transition-colors">
            <Check className="h-3.5 w-3.5" />
          </button>
          <button type="button" onClick={handleCancel} className="p-1.5 text-neutral-400 hover:bg-neutral-100 rounded-md transition-colors">
            <X className="h-3.5 w-3.5" />
          </button>
        </form>
      )}

      <div className="flex-1 overflow-y-auto">
        {threads.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
            <div className="p-3 bg-neutral-100 rounded-full mb-3">
              <MessageCircle className="h-5 w-5 text-neutral-300" />
            </div>
            <p className="text-sm font-medium text-neutral-900">No conversations yet</p>
            <p className="text-xs text-neutral-400 mt-0.5">Create a new conversation to get started</p>
          </div>
        ) : (
          <div className="divide-y divide-neutral-100">
            {threads.map((thread) => {
              const isActive = thread.id === activeThreadId;
              const lastActivity = new Date(thread.last_activity_at);
              const now = new Date();
              const diffMs = now.getTime() - lastActivity.getTime();
              const diffMins = Math.floor(diffMs / 60000);
              const diffHours = Math.floor(diffMs / 3600000);
              const diffDays = Math.floor(diffMs / 86400000);

              const timeAgo =
                diffMins < 1 ? 'Just now' :
                diffMins < 60 ? `${diffMins}m ago` :
                diffHours < 24 ? `${diffHours}h ago` :
                `${diffDays}d ago`;

              return (
                <button
                  key={thread.id}
                  onClick={() => onSelectThread(thread.id)}
                  className={cn(
                    'w-full px-4 py-3 text-left transition-colors',
                    isActive
                      ? 'bg-neutral-900 text-white'
                      : 'hover:bg-neutral-50'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className={cn('text-sm font-medium truncate', isActive ? 'text-white' : 'text-neutral-900')}>
                        {thread.subject || 'General'}
                      </p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className={cn('text-xs', isActive ? 'text-neutral-400' : 'text-neutral-400')}>{timeAgo}</span>
                        <span className={cn('text-xs', isActive ? 'text-neutral-500' : 'text-neutral-300')}>·</span>
                        <span className={cn('text-xs', isActive ? 'text-neutral-400' : 'text-neutral-400')}>
                          {thread.message_count} {thread.message_count === 1 ? 'msg' : 'msgs'}
                        </span>
                      </div>
                    </div>
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

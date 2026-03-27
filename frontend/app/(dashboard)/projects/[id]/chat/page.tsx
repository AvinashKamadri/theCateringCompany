"use client";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { useSocket } from '@/hooks/use-socket';
import { messagesApi } from '@/lib/api/messages';
import { MessageList } from '@/components/chat/message-list';
import { MessageInput } from '@/components/chat/message-input';
import { ThreadList } from '@/components/chat/thread-list';
import type { Thread, Message, Collaborator } from '@/types/messages.types';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

export default function ProjectChatPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.id as string;

  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  const { socket, isConnected, joinThread, leaveThread, sendTyping } = useSocket({});

  // Load threads on mount
  useEffect(() => {
    if (!projectId) return;
    const load = async () => {
      try {
        setIsLoadingThreads(true);
        const data = await messagesApi.getThreads(projectId);
        setThreads(data.threads);
        if (data.threads.length > 0 && !activeThreadId) {
          setActiveThreadId(data.threads[0].id);
        }
      } catch {
        toast.error('Failed to load conversations');
      } finally {
        setIsLoadingThreads(false);
      }
    };
    load();
  }, [projectId]);

  // Poll thread list every 10 s — catches new threads from collaborators
  useEffect(() => {
    if (!projectId) return;
    const interval = setInterval(async () => {
      try {
        const data = await messagesApi.getThreads(projectId);
        setThreads(data.threads);
      } catch { /* silent */ }
    }, 10_000);
    return () => clearInterval(interval);
  }, [projectId]);

  // Load collaborators
  useEffect(() => {
    if (!projectId) return;
    messagesApi.getCollaborators(projectId)
      .then((data) => setCollaborators(data.collaborators))
      .catch(() => {});
  }, [projectId]);

  // Load messages when thread changes and join WS room
  useEffect(() => {
    if (!activeThreadId) return;
    const load = async () => {
      try {
        setIsLoadingMessages(true);
        const data = await messagesApi.getThread(activeThreadId);
        setMessages(data.messages);
        joinThread(activeThreadId);
      } catch {
        toast.error('Failed to load messages');
      } finally {
        setIsLoadingMessages(false);
      }
    };
    load();
    return () => { leaveThread(activeThreadId); };
  }, [activeThreadId, joinThread, leaveThread]);

  // Poll active thread every 3 s — reliable fallback for real-time messages
  useEffect(() => {
    if (!activeThreadId) return;
    const interval = setInterval(async () => {
      try {
        const data = await messagesApi.getThread(activeThreadId);
        setMessages((prev) => {
          const existingIds = new Set(prev.map((m) => m.id));
          const incoming = data.messages.filter((m) => !existingIds.has(m.id));
          if (incoming.length === 0) return prev;
          return [...prev, ...incoming].sort(
            (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
          );
        });
      } catch { /* silent */ }
    }, 3_000);
    return () => clearInterval(interval);
  }, [activeThreadId]);

  // WebSocket: register message listener on the live socket instance
  // Runs whenever `socket` changes (null → connected instance, or reconnect)
  useEffect(() => {
    if (!socket) return;
    const handleNewMessage = (message: Message) => {
      setMessages((prev) => {
        if (prev.some((m) => m.id === message.id)) return prev;
        if (message.thread_id !== activeThreadId) return prev;
        return [...prev, message].sort(
          (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
      });
      setThreads((prev) =>
        prev.map((t) =>
          t.id === message.thread_id
            ? { ...t, last_activity_at: message.created_at, message_count: t.message_count + 1 }
            : t
        )
      );
    };
    socket.on('message.created', handleNewMessage);
    return () => { socket.off('message.created', handleNewMessage); };
  }, [socket, activeThreadId]);

  const handleSendMessage = async (content: string, mentionedUserIds: string[]) => {
    if (!activeThreadId) return;
    try {
      await messagesApi.createMessage(activeThreadId, { content, mentionedUserIds });
    } catch (err: any) {
      toast.error(err.message || 'Failed to send message');
    }
  };

  const handleCreateThread = async (subject?: string) => {
    try {
      const data = await messagesApi.createThread(projectId, { subject });
      setThreads((prev) => [data.thread, ...prev]);
      setActiveThreadId(data.thread.id);
    } catch (err: any) {
      toast.error(err.message || 'Failed to create conversation');
    }
  };

  const handleSelectThread = (threadId: string) => {
    if (activeThreadId) leaveThread(activeThreadId);
    setActiveThreadId(threadId);
  };

  const activeThread = threads.find((t) => t.id === activeThreadId);

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Back navigation */}
      <div className="bg-white border-b border-neutral-200 px-4 py-2 shrink-0">
        <button
          onClick={() => router.push(`/projects/${projectId}`)}
          className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-900 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Project
        </button>
      </div>
      <div className="flex flex-1 bg-neutral-50 overflow-hidden">
      {/* Thread list — left panel */}
      <div className="w-72 border-r border-neutral-200 bg-white shrink-0">
        <ThreadList
          threads={threads}
          activeThreadId={activeThreadId || undefined}
          onSelectThread={handleSelectThread}
          onCreateThread={handleCreateThread}
          isLoading={isLoadingThreads}
        />
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {activeThreadId ? (
          <>
            {/* Chat header */}
            <div className="bg-white border-b border-neutral-200 px-6 py-3 shrink-0">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-neutral-900">
                  {activeThread?.subject || 'General'}
                </p>
                <div className="flex items-center gap-1.5">
                  <div className={cn('w-1.5 h-1.5 rounded-full', isConnected ? 'bg-neutral-900' : 'bg-neutral-300')} />
                  <span className="text-xs text-neutral-400">{isConnected ? 'Live' : 'Offline'}</span>
                </div>
              </div>
            </div>

            <MessageList messages={messages} isLoading={isLoadingMessages} />

            <MessageInput
              onSendMessage={handleSendMessage}
              collaborators={collaborators}
              onTyping={() => sendTyping(activeThreadId)}
              disabled={!isConnected}
            />
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <p className="text-sm text-neutral-400">Select a conversation or create a new one</p>
            </div>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}

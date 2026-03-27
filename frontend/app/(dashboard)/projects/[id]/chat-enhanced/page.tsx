"use client";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';
import { useSocket } from '@/hooks/use-socket';
import { messagesApi } from '@/lib/api/messages';
import { MessageList } from '@/components/chat/message-list';
import { MessageInput } from '@/components/chat/message-input';
import { ThreadList } from '@/components/chat/thread-list';
import { ChatSidebar } from '@/components/chat/chat-sidebar';
import { AiAssistantToggle } from '@/components/chat/ai-assistant-toggle';
import type { Thread, Message, Collaborator } from '@/types/messages.types';
import type { ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';

export default function ProjectChatEnhancedPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.id as string;

  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [isLoadingThreads, setIsLoadingThreads] = useState(true);
  const [isLoadingMessages, setIsLoadingMessages] = useState(false);

  // Mock project data - replace with actual API call
  const projectData = {
    name: 'Smith Wedding',
    event_type: 'wedding',
    event_date: '2026-06-15',
    guest_count: 150,
    venue_name: 'Grand Ballroom',
    budget: 25000,
    contract_status: 'draft',
  };

  const { isConnected, joinThread, leaveThread, sendTyping, on, off } = useSocket({
    onConnect: () => {
      console.log('WebSocket connected');
    },
    onDisconnect: () => {
      console.log('WebSocket disconnected');
    },
  });

  // Load threads on mount
  useEffect(() => {
    const loadThreads = async () => {
      try {
        setIsLoadingThreads(true);
        const data = await messagesApi.getThreads(projectId);
        setThreads(data.threads);

        // Auto-select first thread if available
        if (data.threads.length > 0 && !activeThreadId) {
          setActiveThreadId(data.threads[0].id);
        }
      } catch (error: any) {
        console.error('Failed to load threads:', error);
        toast.error('Failed to load conversations');
      } finally {
        setIsLoadingThreads(false);
      }
    };

    if (projectId) {
      loadThreads();
    }
  }, [projectId]);

  // Load collaborators
  useEffect(() => {
    const loadCollaborators = async () => {
      try {
        const data = await messagesApi.getCollaborators(projectId);
        setCollaborators(data.collaborators);
      } catch (error) {
        console.error('Failed to load collaborators:', error);
      }
    };

    if (projectId) {
      loadCollaborators();
    }
  }, [projectId]);

  // Load messages when active thread changes
  useEffect(() => {
    const loadMessages = async () => {
      if (!activeThreadId) return;

      try {
        setIsLoadingMessages(true);
        const data = await messagesApi.getThread(activeThreadId);
        setMessages(data.messages);

        // Join thread room for real-time updates
        joinThread(activeThreadId);
      } catch (error: any) {
        console.error('Failed to load messages:', error);
        toast.error('Failed to load messages');
      } finally {
        setIsLoadingMessages(false);
      }
    };

    loadMessages();

    return () => {
      if (activeThreadId) {
        leaveThread(activeThreadId);
      }
    };
  }, [activeThreadId]);

  // Listen for new messages via WebSocket
  useEffect(() => {
    const handleNewMessage = (message: Message) => {
      if (message.thread_id === activeThreadId) {
        setMessages((prev) => [...prev, message]);
      }

      // Update thread last activity
      setThreads((prev) =>
        prev.map((t) =>
          t.id === message.thread_id
            ? {
                ...t,
                last_activity_at: message.created_at,
                message_count: t.message_count + 1,
              }
            : t
        )
      );
    };

    const handleMention = (data: any) => {
      toast.info('You were mentioned in a message');
    };

    on('message.created', handleNewMessage);
    on('message.mentioned', handleMention);

    return () => {
      off('message.created', handleNewMessage);
      off('message.mentioned', handleMention);
    };
  }, [activeThreadId, on, off]);

  const handleSendMessage = async (content: string, mentionedUserIds: string[]) => {
    if (!activeThreadId) return;

    try {
      await messagesApi.createMessage(activeThreadId, {
        content,
        mentionedUserIds,
      });
      // Message will be added via WebSocket event
    } catch (error: any) {
      console.error('Failed to send message:', error);
      toast.error('Failed to send message');
    }
  };

  const handleCreateThread = async () => {
    try {
      const subject = prompt('Enter conversation subject (optional):');
      const data = await messagesApi.createThread(projectId, {
        subject: subject || undefined,
      });

      setThreads((prev) => [data.thread, ...prev]);
      setActiveThreadId(data.thread.id);
      toast.success('Conversation created');
    } catch (error: any) {
      console.error('Failed to create thread:', error);
      toast.error('Failed to create conversation');
    }
  };

  const handleSelectThread = (threadId: string) => {
    if (activeThreadId) {
      leaveThread(activeThreadId);
    }
    setActiveThreadId(threadId);
  };

  const handleAiComplete = (contractData: ContractData) => {
    toast.success('AI conversation complete! Data collected successfully.');
    console.log('Contract data:', contractData);
    // Optionally update project with AI data
  };

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
      <div className="flex flex-1 overflow-hidden">
      {/* Thread List - Left Sidebar */}
      <div className="w-80 border-r border-gray-200 bg-white">
        <ThreadList
          threads={threads}
          activeThreadId={activeThreadId || undefined}
          onSelectThread={handleSelectThread}
          onCreateThread={handleCreateThread}
          isLoading={isLoadingThreads}
        />
      </div>

      {/* Main Chat Area with AI Toggle */}
      <div className="flex-1 flex flex-col bg-gray-50">
        <AiAssistantToggle projectId={projectId} onComplete={handleAiComplete}>
          {/* Regular Team Chat */}
          {activeThreadId ? (
            <>
              {/* Chat Header */}
              <div className="bg-white border-b border-gray-200 px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h1 className="text-xl font-semibold text-gray-900">
                      {threads.find((t) => t.id === activeThreadId)?.subject || 'Conversation'}
                    </h1>
                    <div className="flex items-center gap-2 mt-1">
                      <div
                        className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-gray-400'}`}
                      />
                      <span className="text-sm text-gray-500">
                        {isConnected ? 'Connected' : 'Disconnected'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Messages */}
              <MessageList messages={messages} isLoading={isLoadingMessages} />

              {/* Message Input */}
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
                <p className="text-gray-500">Select a conversation or create a new one</p>
              </div>
            </div>
          )}
        </AiAssistantToggle>
      </div>

      {/* Project Info Sidebar - Right */}
      <ChatSidebar contractData={projectData} slotsFilled={0} totalSlots={0} />
      </div>
    </div>
  );
}

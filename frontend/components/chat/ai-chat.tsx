"use client";

import { useState, useEffect, useRef } from 'react';
import { Send, Loader2, CheckCircle2, Sparkles } from 'lucide-react';
import { chatAiApi } from '@/lib/api/chat-ai';
import type { ChatMessage, ChatState, ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { CommandDialog } from './command-dialog';

interface AiChatProps {
  projectId?: string;
  authorId?: string;
  userId?: string;
  initialThreadId?: string;
  onComplete?: (contractData: ContractData) => void;
  onThreadStart?: (threadId: string) => void;
  onSlotsUpdate?: (slots: Partial<ContractData>) => void;
}

const STORAGE_KEY = 'tc_chat_sessions';

function saveSessionToStorage(threadId: string) {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const sessions: { threadId: string; startedAt: string; lastActiveAt: string }[] =
      raw ? JSON.parse(raw) : [];
    const idx = sessions.findIndex((s) => s.threadId === threadId);
    const now = new Date().toISOString();
    if (idx >= 0) {
      sessions[idx].lastActiveAt = now;
    } else {
      sessions.push({ threadId, startedAt: now, lastActiveAt: now });
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // localStorage unavailable — ignore
  }
}

export function AiChat({ projectId, authorId, userId, initialThreadId, onComplete, onThreadStart, onSlotsUpdate }: AiChatProps) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    progress: { filled: 0, total: 20 },
    isComplete: false,
  });
  const [input, setInput] = useState('');
  const [commandDialog, setCommandDialog] = useState<{ isOpen: boolean; command: 'menu' | 'events' | null }>({
    isOpen: false,
    command: null,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const startedRef = useRef(false);
  const lastSlotsFilled = useRef(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages]);

  // Load existing conversation or start fresh
  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;

    if (initialThreadId) {
      loadConversationHistory(initialThreadId);
    } else {
      handleSendMessage('Hello! I need help planning my event.');
    }
  }, []);

  // Listen for help requests from sidebar
  useEffect(() => {
    const handleHelp = () => {
      handleSendMessage('/help - I need assistance from your team');
    };
    window.addEventListener('chat:help', handleHelp);
    return () => window.removeEventListener('chat:help', handleHelp);
  }, []);

  async function loadConversationHistory(threadId: string) {
    setState((prev) => ({ ...prev, isLoading: true }));
    try {
      const conv = await chatAiApi.getConversation(threadId);
      const messages: ChatMessage[] = (conv.messages ?? []).map((m: any) => ({
        role: m.sender_type === 'user' ? 'user' : 'ai',
        content: m.content,
        timestamp: new Date(m.created_at),
      }));
      setState((prev) => ({
        ...prev,
        messages,
        threadId,
        progress: { filled: conv.slots_filled ?? 0, total: 20 },
        isComplete: conv.is_completed ?? false,
        isLoading: false,
      }));
      saveSessionToStorage(threadId);
      onThreadStart?.(threadId);

      // If already complete, restore contract data for the CTA
      if (conv.is_completed && conv.slots) {
        setState((prev) => ({ ...prev, contractData: { ...conv.slots, thread_id: threadId } as any }));
      }
    } catch {
      setState((prev) => ({ ...prev, isLoading: false }));
      toast.error('Could not load conversation history.');
    }
  }

  const handleSendMessage = async (messageText?: string) => {
    const content = messageText || input.trim();
    if (!content || state.isLoading) return;

    if (content.startsWith('/')) {
      const command = content.toLowerCase();
      if (command.startsWith('/menu')) {
        setCommandDialog({ isOpen: true, command: 'menu' });
        setInput('');
        return;
      }
      if (command.startsWith('/event')) {
        setCommandDialog({ isOpen: true, command: 'events' });
        setInput('');
        return;
      }
      if (command.startsWith('/help')) {
        toast.success('Help request sent! Our team will assist you shortly.');
      }
    }

    setInput('');

    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
      error: undefined,
    }));

    try {
      const response = await chatAiApi.sendMessageWithRetry({
        message: content,
        threadId: state.threadId,
        projectId,
        authorId,
        userId,
      });

      const aiMessage: ChatMessage = {
        role: 'ai',
        content: response.message,
        timestamp: new Date(),
      };

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, aiMessage],
        threadId: response.thread_id,
        progress: {
          filled: response.slots_filled,
          total: response.total_slots,
        },
        isComplete: response.is_complete,
        isLoading: false,
      }));

      // Persist session to localStorage
      saveSessionToStorage(response.thread_id);
      if (!state.threadId) {
        onThreadStart?.(response.thread_id);
      }

      // Fire slot update when slots increase so parent can update project title
      if (onSlotsUpdate && response.slots_filled > lastSlotsFilled.current) {
        lastSlotsFilled.current = response.slots_filled;
        chatAiApi.getConversation(response.thread_id)
          .then((conv) => { if (conv.slots) onSlotsUpdate(conv.slots); })
          .catch(() => {});
      }

      if (response.is_complete) {
        toast.success('Event details collected! You can now create your project.');
        try {
          const conversation = await chatAiApi.getConversation(response.thread_id);
          const slots = { ...conversation.slots, thread_id: response.thread_id };
          setState((prev) => ({ ...prev, contractData: slots }));
        } catch (err) {
          console.error('Failed to fetch conversation slots:', err);
        }
      }
    } catch (error: any) {
      console.error('Failed to send message:', error);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to send message. Please try again.',
      }));
      toast.error('Failed to send message');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const progressPercentage = (state.progress.filled / state.progress.total) * 100;

  const handleCommandSelect = (selectedOption: string) => {
    handleSendMessage(`I'm interested in ${selectedOption}`);
  };

  return (
    <>
      <CommandDialog
        isOpen={commandDialog.isOpen}
        command={commandDialog.command}
        onClose={() => setCommandDialog({ isOpen: false, command: null })}
        onSelect={handleCommandSelect}
      />
      <div className="flex flex-col h-full bg-white">
        {/* Header with Progress */}
        <div className="border-b border-neutral-200 px-6 py-4">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-neutral-900">TheCateringCompany</h2>
              <p className="text-xs text-neutral-500">Let's plan your perfect event together</p>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-neutral-500 font-medium">
                {state.isComplete ? 'All details collected' : 'Gathering event details'}
              </span>
              <span className="text-neutral-900 font-semibold tabular-nums">
                {state.progress.filled} / {state.progress.total}
              </span>
            </div>
            <div className="relative h-1.5 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 bg-black rounded-full transition-all duration-500 ease-out"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {state.messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-black text-white'
                    : 'bg-neutral-100 text-neutral-900'
                }`}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                <span
                  className={`text-xs mt-1 block ${
                    msg.role === 'user' ? 'text-neutral-400' : 'text-neutral-400'
                  }`}
                >
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            </div>
          ))}

          {state.isLoading && (
            <div className="flex justify-start">
              <div className="bg-neutral-100 rounded-2xl px-4 py-3">
                <Loader2 className="w-5 h-5 text-neutral-400 animate-spin" />
              </div>
            </div>
          )}

          {state.error && (
            <div className="flex justify-center">
              <div className="bg-red-50 text-red-600 rounded-lg px-4 py-2 text-sm">
                {state.error}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Completion banner */}
        {state.isComplete && state.contractData && (
          <div className="border-t border-neutral-200 bg-neutral-50 px-6 py-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-neutral-900 mt-0.5 shrink-0" />
              <div className="flex-1">
                <h3 className="font-semibold text-neutral-900 mb-2">Event Summary</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {state.contractData.name && (
                    <div>
                      <span className="text-neutral-500 font-medium">Client:</span>
                      <span className="text-neutral-900 ml-2">{state.contractData.name}</span>
                    </div>
                  )}
                  {state.contractData.event_type && (
                    <div>
                      <span className="text-neutral-500 font-medium">Event:</span>
                      <span className="text-neutral-900 ml-2">{state.contractData.event_type}</span>
                    </div>
                  )}
                  {state.contractData.event_date && (
                    <div>
                      <span className="text-neutral-500 font-medium">Date:</span>
                      <span className="text-neutral-900 ml-2">{state.contractData.event_date}</span>
                    </div>
                  )}
                  {state.contractData.guest_count && (
                    <div>
                      <span className="text-neutral-500 font-medium">Guests:</span>
                      <span className="text-neutral-900 ml-2">{state.contractData.guest_count}</span>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => onComplete?.(state.contractData!)}
                  className="mt-3 w-full bg-black text-white py-2.5 rounded-lg text-sm font-semibold hover:bg-neutral-800 transition-colors"
                >
                  Create Project & Contract
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Input — always visible (allows modifications even after completion) */}
        <div className="border-t border-neutral-200 px-6 py-4 bg-white">
          <div className="flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={state.isComplete ? 'Request changes or ask questions…' : 'Type your message…'}
              className="flex-1 resize-none border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent min-h-[52px] max-h-[120px]"
              rows={1}
              disabled={state.isLoading}
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={!input.trim() || state.isLoading}
              className="bg-black text-white p-3 rounded-xl hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              {state.isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-xs text-neutral-400 mt-2">
            Enter to send · Shift+Enter for new line · Try{' '}
            <span className="font-mono text-neutral-600">/menu</span>{' '}
            <span className="font-mono text-neutral-600">/events</span>
          </p>
        </div>
      </div>
    </>
  );
}

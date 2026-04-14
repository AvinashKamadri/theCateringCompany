"use client";

import React, { useState, useEffect, useRef, Fragment } from 'react';
import { Send, Loader2, CheckCircle2, Sparkles, Check } from 'lucide-react';
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
  onProgressUpdate?: (progress: { filled: number; total: number }) => void;
}

const STORAGE_KEY = 'tc_chat_sessions';

// ─── Menu item parsing ────────────────────────────────────────────────────────

interface MenuItem {
  name: string;
  price: string;
}

function parseMenuItems(content: string): MenuItem[] | null {
  const lines = content.split('\n');
  const items: MenuItem[] = [];
  for (const line of lines) {
    // Match: "1. Item Name ($3.50)" or "1. Item Name ($3.50/per_person)"
    const m = line.match(/^\d+\.\s+(.+?)\s+\((\$[\d.,]+[^)]*)\)/);
    if (m) items.push({ name: m[1].trim(), price: m[2].trim() });
  }
  return items.length >= 4 ? items : null;
}

function splitMessageAndList(content: string): { intro: string; rest: string } {
  const firstListLine = content.search(/^\d+\.\s+/m);
  if (firstListLine === -1) return { intro: content, rest: '' };
  return {
    intro: content.slice(0, firstListLine).trimEnd(),
    rest: content.slice(firstListLine),
  };
}

// ─── Menu item card ───────────────────────────────────────────────────────────

function MenuItemCard({
  item,
  selected,
  onToggle,
}: {
  item: MenuItem;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`relative flex flex-col rounded-xl border-2 overflow-hidden text-left transition-all focus:outline-none ${
        selected
          ? 'border-black bg-black/5 shadow-sm'
          : 'border-neutral-200 bg-white hover:border-neutral-400'
      }`}
    >
      {/* Placeholder image / skeleton */}
      <div className="w-full h-16 bg-linear-to-br from-neutral-100 to-neutral-200 animate-pulse" />

      {/* Checkmark badge */}
      {selected && (
        <div className="absolute top-1.5 right-1.5 w-5 h-5 bg-black rounded-full flex items-center justify-center shadow">
          <Check className="w-3 h-3 text-white" strokeWidth={3} />
        </div>
      )}

      <div className="p-2 flex-1">
        <p className="text-xs font-semibold text-neutral-900 leading-tight line-clamp-2">{item.name}</p>
        <p className="text-xs text-neutral-500 mt-0.5">{item.price}</p>
      </div>
    </button>
  );
}

// ─── Menu grid ────────────────────────────────────────────────────────────────

function MenuGrid({
  items,
  selected,
  onSelectionChange,
}: {
  items: MenuItem[];
  selected: string[];
  onSelectionChange: (names: string[]) => void;
}) {
  const toggle = (name: string) => {
    const next = selected.includes(name)
      ? selected.filter((n) => n !== name)
      : [...selected, name];
    onSelectionChange(next);
  };

  return (
    <div className="mt-3 w-full">
      <div className="grid grid-cols-4 gap-2">
        {items.map((item) => (
          <MenuItemCard
            key={item.name}
            item={item}
            selected={selected.includes(item.name)}
            onToggle={() => toggle(item.name)}
          />
        ))}
      </div>
      {selected.length > 0 && (
        <p className="text-xs text-neutral-500 mt-2">
          <span className="font-medium text-neutral-800">{selected.length}</span> selected — hit Send to confirm
        </p>
      )}
    </div>
  );
}

// ─── Markdown renderer ────────────────────────────────────────────────────────

function MarkdownMessage({ content }: { content: string }) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    const headingMatch = line.match(/^(#{1,3})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const Tag = (`h${level}`) as keyof React.JSX.IntrinsicElements;
      const cls = level === 1 ? 'font-bold text-base mt-2 mb-1' : level === 2 ? 'font-semibold text-sm mt-2 mb-1' : 'font-semibold text-sm mt-1';
      elements.push(<Tag key={i} className={cls}>{inlineFormat(text)}</Tag>);
      i++; continue;
    }

    const numMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      const listItems: React.ReactNode[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\d+)\.\s+(.*)/);
        if (!m) break;
        listItems.push(
          <li key={i} className="flex gap-2 text-sm">
            <span className="text-neutral-400 shrink-0 w-5 text-right">{m[1]}.</span>
            <span>{inlineFormat(m[2])}</span>
          </li>
        );
        i++;
      }
      elements.push(<ol key={`ol-${i}`} className="space-y-1 my-1">{listItems}</ol>);
      continue;
    }

    const bulletMatch = line.match(/^[-*•]\s+(.*)/);
    if (bulletMatch) {
      const listItems: React.ReactNode[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^[-*•]\s+(.*)/);
        if (!m) break;
        listItems.push(
          <li key={i} className="flex gap-2 text-sm">
            <span className="text-neutral-400 shrink-0">•</span>
            <span>{inlineFormat(m[1])}</span>
          </li>
        );
        i++;
      }
      elements.push(<ul key={`ul-${i}`} className="space-y-1 my-1">{listItems}</ul>);
      continue;
    }

    if (line.trim() === '') {
      elements.push(<div key={i} className="h-1" />);
      i++; continue;
    }

    elements.push(<p key={i} className="text-sm">{inlineFormat(line)}</p>);
    i++;
  }

  return <div className="space-y-0.5">{elements}</div>;
}

function inlineFormat(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**'))
      return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
    if (part.startsWith('*') && part.endsWith('*'))
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith('`') && part.endsWith('`'))
      return <code key={i} className="bg-neutral-200 rounded px-1 text-xs font-mono">{part.slice(1, -1)}</code>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

// ─── Session storage ──────────────────────────────────────────────────────────

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

// ─── Main component ───────────────────────────────────────────────────────────

export function AiChat({ projectId, authorId, userId, initialThreadId, onComplete, onThreadStart, onSlotsUpdate, onProgressUpdate }: AiChatProps) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    progress: { filled: 0, total: 20 },
    isComplete: false,
  });
  const [input, setInput] = useState('');
  const [menuSelections, setMenuSelections] = useState<string[]>([]);
  const [activeMenuMsgIdx, setActiveMenuMsgIdx] = useState<number | null>(null);
  const [commandDialog, setCommandDialog] = useState<{ isOpen: boolean; command: 'menu' | 'events' | null }>({
    isOpen: false,
    command: null,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const startedRef = useRef(false);
  const lastSlotsFilled = useRef(0);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages]);

  // Keep input focused after every message
  useEffect(() => {
    if (!state.isLoading) inputRef.current?.focus();
  }, [state.isLoading, state.messages]);

  // When messages change, find the last AI message with menu items and activate it
  useEffect(() => {
    let lastMenuIdx: number | null = null;
    state.messages.forEach((msg, idx) => {
      if (msg.role === 'ai' && parseMenuItems(msg.content)) {
        lastMenuIdx = idx;
      }
    });
    // Only activate if it's the very last message (user hasn't responded yet)
    const lastMsgIdx = state.messages.length - 1;
    if (lastMenuIdx !== null && lastMenuIdx === lastMsgIdx) {
      setActiveMenuMsgIdx(lastMenuIdx);
    } else {
      setActiveMenuMsgIdx(null);
    }
  }, [state.messages]);

  // Sync menu selections to input
  const handleMenuSelectionChange = (names: string[]) => {
    setMenuSelections(names);
    setInput(names.join(', '));
  };

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    if (initialThreadId) {
      loadConversationHistory(initialThreadId);
    } else {
      handleSendMessage('Hello! I need help planning my event.');
    }
  }, []);

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
      if (conv.slots) onSlotsUpdate?.(conv.slots);
      onProgressUpdate?.({ filled: conv.slots_filled ?? 0, total: 20 });
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
    setMenuSelections([]);
    setActiveMenuMsgIdx(null);

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
        progress: { filled: response.slots_filled, total: response.total_slots },
        isComplete: response.is_complete,
        isLoading: false,
      }));

      onProgressUpdate?.({ filled: response.slots_filled, total: response.total_slots });
      saveSessionToStorage(response.thread_id);
      if (!state.threadId) onThreadStart?.(response.thread_id);

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
      setState((prev) => ({ ...prev, isLoading: false, error: 'Failed to send message. Please try again.' }));
      toast.error('Failed to send message');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

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
        {/* Header */}
        <div className="border-b border-neutral-200 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-neutral-900">Catering Assistant</h2>
              <p className="text-xs text-neutral-500">Let's plan your perfect event together</p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {state.messages.map((msg, idx) => {
            const isActive = idx === activeMenuMsgIdx;
            const menuItems = isActive ? parseMenuItems(msg.content) : null;

            if (msg.role === 'ai' && menuItems) {
              const { intro } = splitMessageAndList(msg.content);
              return (
                <div key={idx} className="flex justify-start flex-col">
                  {/* Intro text bubble */}
                  {intro && (
                    <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-neutral-100 text-neutral-900 mb-2">
                      <MarkdownMessage content={intro} />
                    </div>
                  )}
                  {/* Full-width grid */}
                  <div className="w-full">
                    <MenuGrid
                      items={menuItems}
                      selected={menuSelections}
                      onSelectionChange={handleMenuSelectionChange}
                    />
                    <span className="text-xs text-neutral-400 mt-1 block">
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                </div>
              );
            }

            return (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                    msg.role === 'user' ? 'bg-black text-white' : 'bg-neutral-100 text-neutral-900'
                  }`}
                >
                  {msg.role === 'user'
                    ? <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    : <MarkdownMessage content={msg.content} />
                  }
                  <span className="text-xs mt-1 block text-neutral-400">
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            );
          })}

          {state.isLoading && (
            <div className="flex justify-start">
              <div className="bg-neutral-100 rounded-2xl px-4 py-3">
                <Loader2 className="w-5 h-5 text-neutral-400 animate-spin" />
              </div>
            </div>
          )}

          {state.error && (
            <div className="flex justify-center">
              <div className="bg-red-50 text-red-600 rounded-lg px-4 py-2 text-sm">{state.error}</div>
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
                    <div><span className="text-neutral-500 font-medium">Client:</span><span className="text-neutral-900 ml-2">{state.contractData.name}</span></div>
                  )}
                  {state.contractData.event_type && (
                    <div><span className="text-neutral-500 font-medium">Event:</span><span className="text-neutral-900 ml-2">{state.contractData.event_type}</span></div>
                  )}
                  {state.contractData.event_date && (
                    <div><span className="text-neutral-500 font-medium">Date:</span><span className="text-neutral-900 ml-2">{state.contractData.event_date}</span></div>
                  )}
                  {state.contractData.guest_count && (
                    <div><span className="text-neutral-500 font-medium">Guests:</span><span className="text-neutral-900 ml-2">{state.contractData.guest_count}</span></div>
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

        {/* Input */}
        <div className={`border-t border-neutral-200 px-6 py-4 bg-white${state.isComplete && state.contractData ? ' hidden' : ''}`}>
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                // If user manually edits, clear grid selections
                if (activeMenuMsgIdx !== null) setMenuSelections([]);
              }}
              onKeyDown={handleKeyDown}
              placeholder={activeMenuMsgIdx !== null ? 'Select items above or type here…' : 'Type your message…'}
              className="flex-1 resize-none border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent min-h-[52px] max-h-[120px]"
              rows={1}
              disabled={state.isLoading}
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={!input.trim() || state.isLoading}
              className="bg-black text-white p-3 rounded-xl hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
            >
              {state.isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
          <p className="text-xs text-neutral-400 mt-2 text-center">
            {activeMenuMsgIdx !== null
              ? 'Click cards to select · Send to confirm'
              : <>Shift+Enter for new line · Use <span className="font-mono text-neutral-600">@ai</span> to update previous items</>
            }
          </p>
        </div>
      </div>
    </>
  );
}

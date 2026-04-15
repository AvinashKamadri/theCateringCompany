"use client";

import React, { useState, useEffect, useRef, Fragment } from 'react';
import { Send, Loader2, Sparkles, Check, ChevronDown } from 'lucide-react';
import { chatAiApi } from '@/lib/api/chat-ai';
import type { ChatMessage, ChatState, ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { CommandDialog } from './command-dialog';
import IntakeReviewPanel from './IntakeReviewPanel';

interface AiChatProps {
  projectId?: string;
  authorId?: string;
  userId?: string;
  userName?: string;
  initialThreadId?: string;
  onComplete?: (contractData: ContractData) => void;
  onThreadStart?: (threadId: string) => void;
  onSlotsUpdate?: (slots: Partial<ContractData>) => void;
  onProgressUpdate?: (progress: { filled: number; total: number }) => void;
}

const STORAGE_KEY = 'tc_chat_sessions';

// ─── List parsing ─────────────────────────────────────────────────────────────

interface ListItem {
  name: string;
  price?: string;
}

function parseListItems(content: string): ListItem[] | null {
  const items: ListItem[] = [];

  // First try line-by-line (normal multiline lists)
  const lines = content.split('\n');
  for (const line of lines) {
    const withPrice = line.match(/^(?:\d+\.|[-•*])\s+(.+?)\s+\((\$[\d.,]+[^)]*)\)/);
    if (withPrice) { items.push({ name: withPrice[1].trim(), price: withPrice[2].trim() }); continue; }
    const plain = line.match(/^(\d+)\.\s+(.{2,60})$/);
    if (plain) items.push({ name: plain[2].trim() });
  }
  if (items.length >= 2) return items;

  // Fallback: inline numbered list e.g. "1. Wedding 2. Birthday 3. Corporate"
  const inlineMatches = content.matchAll(/\d+\.\s+([A-Za-z][A-Za-z &'-]{1,40})(?=\s+\d+\.|$)/g);
  const inlineItems: ListItem[] = [];
  for (const m of inlineMatches) inlineItems.push({ name: m[1].trim() });
  if (inlineItems.length >= 2) return inlineItems;

  return null;
}

// Multi-select: items with prices OR more than 6 options (e.g. desserts).
// Single-select: few options like event types (≤6 items, no prices).
function isMultiSelect(items: ListItem[]): boolean {
  const withPrices = items.filter((i) => i.price).length;
  return (withPrices > 0 && items.length > 5) || items.length > 6;
}

// Confirmation messages list selected items — should be read-only, not interactive.
const CONFIRM_PATTERNS = [
  /just to confirm/i,
  /your (menu|selection|order|choices?) (includes?|contains?|is)/i,
  /to confirm.{0,30}(your|the) (menu|selection)/i,
  /here'?s? (a )?summary/i,
  /you('ve| have) selected/i,
  /confirming your/i,
];
function isConfirmationMessage(intro: string): boolean {
  return CONFIRM_PATTERNS.some((p) => p.test(intro));
}

function splitAtList(content: string): { intro: string } {
  const firstListLine = content.search(/^(?:\d+\.|[-•*])\s+/m);
  if (firstListLine === -1) return { intro: content };
  return { intro: content.slice(0, firstListLine).trimEnd() };
}

// ─── Option card (single-select square) ───────────────────────────────────────

function OptionCard({
  item,
  selected,
  onToggle,
}: {
  item: ListItem;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`relative flex flex-col items-start justify-end h-20 rounded-xl border-2 p-3 text-left transition-all focus:outline-none w-full ${
        selected
          ? 'border-black bg-black text-white'
          : 'border-neutral-200 bg-white hover:border-neutral-400 text-neutral-900'
      }`}
    >
      {selected && (
        <div className="absolute top-2.5 right-2.5 w-5 h-5 bg-white rounded-full flex items-center justify-center shadow">
          <Check className="w-3 h-3 text-black" strokeWidth={3} />
        </div>
      )}
      <span className="text-sm font-semibold leading-tight">{item.name}</span>
      {item.price && (
        <span className={`text-xs mt-0.5 ${selected ? 'text-neutral-300' : 'text-neutral-400'}`}>
          {item.price}
        </span>
      )}
    </button>
  );
}

// ─── Multi-select grid (menu items with prices) ───────────────────────────────

function MenuItemCard({
  item,
  selected,
  onToggle,
}: {
  item: ListItem;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`relative flex flex-col rounded-xl border-2 overflow-hidden text-left transition-all focus:outline-none ${
        selected ? 'border-black bg-black/5 shadow-sm' : 'border-neutral-200 bg-white hover:border-neutral-400'
      }`}
    >
      <div className="w-full h-14 bg-neutral-100" />
      {selected && (
        <div className="absolute top-1.5 right-1.5 w-5 h-5 bg-black rounded-full flex items-center justify-center shadow">
          <Check className="w-3 h-3 text-white" strokeWidth={3} />
        </div>
      )}
      <div className="p-2 flex-1">
        <p className="text-xs font-semibold text-neutral-900 leading-tight line-clamp-2">{item.name}</p>
        {item.price && <p className="text-xs text-neutral-500 mt-0.5">{item.price}</p>}
      </div>
    </button>
  );
}

// ─── Unified list UI ──────────────────────────────────────────────────────────

function ItemSelector({
  items,
  selected,
  onSelectionChange,
  multi,
  maxSelect,
}: {
  items: ListItem[];
  selected: string[];
  onSelectionChange: (names: string[]) => void;
  multi: boolean;
  maxSelect?: number;
}) {
  const toggle = (name: string) => {
    if (multi) {
      const isSelected = selected.includes(name);
      if (isSelected) {
        onSelectionChange(selected.filter((n) => n !== name));
      } else if (!maxSelect || selected.length < maxSelect) {
        onSelectionChange([...selected, name]);
      }
    } else {
      onSelectionChange(selected.includes(name) ? [] : [name]);
    }
  };

  if (multi) {
    return (
      <div className="mt-2 w-full">
        <div className="grid grid-cols-4 gap-2">
          {items.map((item) => (
            <MenuItemCard key={item.name} item={item} selected={selected.includes(item.name)} onToggle={() => toggle(item.name)} />
          ))}
        </div>
        {selected.length > 0 && (
          <p className="text-xs text-neutral-500 mt-2">
            <span className="font-medium text-neutral-800">{selected.length}</span>
            {maxSelect ? `/${maxSelect}` : ''} selected — hit Send to confirm
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="mt-2 w-full">
      <div className="grid grid-cols-3 gap-2">
        {items.map((item) => (
          <OptionCard key={item.name} item={item} selected={selected.includes(item.name)} onToggle={() => toggle(item.name)} />
        ))}
      </div>
      {selected.length > 0 && (
        <p className="text-xs text-neutral-500 mt-1">Hit Send to confirm</p>
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

// ─── Country codes ────────────────────────────────────────────────────────────
const COUNTRY_CODES = [
  { code: '+1',  flag: '🇺🇸', name: 'US' },
  { code: '+1',  flag: '🇨🇦', name: 'CA' },
  { code: '+44', flag: '🇬🇧', name: 'GB' },
  { code: '+91', flag: '🇮🇳', name: 'IN' },
  { code: '+61', flag: '🇦🇺', name: 'AU' },
  { code: '+64', flag: '🇳🇿', name: 'NZ' },
  { code: '+971', flag: '🇦🇪', name: 'AE' },
  { code: '+65', flag: '🇸🇬', name: 'SG' },
  { code: '+60', flag: '🇲🇾', name: 'MY' },
  { code: '+63', flag: '🇵🇭', name: 'PH' },
  { code: '+852', flag: '🇭🇰', name: 'HK' },
  { code: '+49', flag: '🇩🇪', name: 'DE' },
  { code: '+33', flag: '🇫🇷', name: 'FR' },
  { code: '+39', flag: '🇮🇹', name: 'IT' },
  { code: '+34', flag: '🇪🇸', name: 'ES' },
  { code: '+55', flag: '🇧🇷', name: 'BR' },
  { code: '+52', flag: '🇲🇽', name: 'MX' },
  { code: '+81', flag: '🇯🇵', name: 'JP' },
  { code: '+82', flag: '🇰🇷', name: 'KR' },
  { code: '+86', flag: '🇨🇳', name: 'CN' },
];

function isAskingForPhone(content: string): boolean {
  const lower = content.toLowerCase();
  return (lower.includes('phone') || lower.includes('mobile') || lower.includes('number to reach')) &&
    !lower.includes('guest') && !lower.includes('how many');
}

// ─── Main component ───────────────────────────────────────────────────────────

export function AiChat({ projectId, authorId, userId, userName = 'You', initialThreadId, onComplete, onThreadStart, onSlotsUpdate, onProgressUpdate }: AiChatProps) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    progress: { filled: 0, total: 20 },
    isComplete: false,
  });
  const [input, setInput] = useState('');
  const [countryCode, setCountryCode] = useState(COUNTRY_CODES[0]);
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

  // When messages change, activate last AI message with a list if it's the latest message
  useEffect(() => {
    let lastListIdx: number | null = null;
    state.messages.forEach((msg, idx) => {
      if (msg.role === 'ai' && parseListItems(msg.content)) lastListIdx = idx;
    });
    const lastMsgIdx = state.messages.length - 1;
    if (lastListIdx !== null && lastListIdx === lastMsgIdx) {
      setActiveMenuMsgIdx(lastListIdx);
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
            const userInitial = userName.charAt(0).toUpperCase();
            const time = msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            const isActive = idx === activeMenuMsgIdx;
            const listItems = isActive ? parseListItems(msg.content) : null;

            if (msg.role === 'ai' && listItems) {
              const { intro } = splitAtList(msg.content);
              const isConfirm = isConfirmationMessage(intro);

              // Confirmation messages: render as plain read-only list, not interactive cards
              if (isConfirm) {
                return (
                  <div key={idx} className="flex justify-start gap-2.5">
                    <div className="flex flex-col items-center gap-1 shrink-0">
                      <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center">
                        <Sparkles className="w-3.5 h-3.5 text-white" />
                      </div>
                      <span className="text-[10px] text-neutral-400">AI</span>
                    </div>
                    <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-neutral-100 text-neutral-900">
                      <MarkdownMessage content={msg.content} />
                      <span className="text-xs mt-1 block text-neutral-400">{time}</span>
                    </div>
                  </div>
                );
              }

              const multi = isMultiSelect(listItems);
              // Only cap desserts (items with no prices but exactly the dessert count ≤8)
              const isDesserts = !listItems.some((i) => i.price) && listItems.length <= 8 && listItems.length > 6;
              const maxSelect = isDesserts ? 4 : undefined;

              return (
                <div key={idx} className="flex justify-start gap-2.5">
                  <div className="flex flex-col items-center gap-1 shrink-0">
                    <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center">
                      <Sparkles className="w-3.5 h-3.5 text-white" />
                    </div>
                    <span className="text-[10px] text-neutral-400">AI</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    {intro && (
                      <div className="rounded-2xl px-4 py-3 bg-neutral-100 text-neutral-900 mb-2 inline-block max-w-[90%]">
                        <MarkdownMessage content={intro} />
                      </div>
                    )}
                    <ItemSelector
                      items={listItems}
                      selected={menuSelections}
                      onSelectionChange={handleMenuSelectionChange}
                      multi={multi}
                      maxSelect={maxSelect}
                    />
                    <span className="text-xs text-neutral-400 mt-1 block">{time}</span>
                  </div>
                </div>
              );
            }

            if (msg.role === 'user') {
              return (
                <div key={idx} className="flex justify-end gap-2.5">
                  <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-black text-white">
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    <span className="text-xs mt-1 block text-neutral-400">{time}</span>
                  </div>
                  <div className="flex flex-col items-center gap-1 shrink-0">
                    <div className="w-7 h-7 rounded-full bg-neutral-800 flex items-center justify-center">
                      <span className="text-xs font-bold text-white">{userInitial}</span>
                    </div>
                    <span className="text-[10px] text-neutral-400">You</span>
                  </div>
                </div>
              );
            }

            return (
              <div key={idx} className="flex justify-start gap-2.5">
                <div className="flex flex-col items-center gap-1 shrink-0">
                  <div className="w-7 h-7 rounded-full bg-black flex items-center justify-center">
                    <Sparkles className="w-3.5 h-3.5 text-white" />
                  </div>
                  <span className="text-[10px] text-neutral-400">AI</span>
                </div>
                <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-neutral-100 text-neutral-900">
                  <MarkdownMessage content={msg.content} />
                  <span className="text-xs mt-1 block text-neutral-400">{time}</span>
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

        {/* Completion — intake review accordion */}
        {state.isComplete && state.contractData && (
          <IntakeReviewPanel
            contractData={state.contractData}
            onConfirm={() => onComplete?.(state.contractData!)}
          />
        )}

        {/* Input */}
        {(() => {
          const lastAiMsg = [...state.messages].reverse().find((m) => m.role === 'ai');
          const isPhoneMode = !state.isLoading && !!lastAiMsg && isAskingForPhone(lastAiMsg.content) && activeMenuMsgIdx === null;
          return (
            <div className={`border-t border-neutral-200 px-6 py-4 bg-white${state.isComplete && state.contractData ? ' hidden' : ''}`}>
              <div className="flex items-end gap-3">
                {isPhoneMode ? (
                  /* Phone input with country code */
                  <div className="flex-1 flex items-center border border-neutral-200 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-black focus-within:border-transparent">
                    <div className="relative shrink-0">
                      <select
                        value={COUNTRY_CODES.indexOf(countryCode)}
                        onChange={(e) => setCountryCode(COUNTRY_CODES[Number(e.target.value)])}
                        className="appearance-none bg-neutral-50 border-r border-neutral-200 pl-3 pr-7 py-3 text-sm text-neutral-700 focus:outline-none cursor-pointer h-full"
                      >
                        {COUNTRY_CODES.map((c, i) => (
                          <option key={`${c.code}-${c.name}`} value={i}>
                            {c.flag} {c.name} {c.code}
                          </option>
                        ))}
                      </select>
                      <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
                    </div>
                    <input
                      type="tel"
                      value={input}
                      onChange={(e) => setInput(e.target.value.replace(/[^\d]/g, '').slice(0, 10))}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSendMessage(`${countryCode.code} ${input}`); setInput(''); } }}
                      placeholder="0000000000"
                      maxLength={10}
                      className="flex-1 px-3 py-3 text-sm focus:outline-none bg-white"
                      disabled={state.isLoading}
                    />
                  </div>
                ) : (
                  <textarea
                    ref={inputRef}
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value);
                      if (activeMenuMsgIdx !== null) setMenuSelections([]);
                    }}
                    onKeyDown={handleKeyDown}
                    placeholder={activeMenuMsgIdx !== null ? 'Select items above or type here…' : 'Type your message…'}
                    className="flex-1 resize-none border border-neutral-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent min-h-[52px] max-h-[120px]"
                    rows={1}
                    disabled={state.isLoading}
                  />
                )}
                <button
                  onClick={() => {
                    if (isPhoneMode) {
                      handleSendMessage(`${countryCode.code} ${input}`);
                      setInput('');
                    } else {
                      handleSendMessage();
                    }
                  }}
                  disabled={!input.trim() || state.isLoading}
                  className="bg-black text-white p-3 rounded-xl hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shrink-0"
                >
                  {state.isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </button>
              </div>
              <p className="text-xs text-neutral-400 mt-2 text-center">
                {isPhoneMode
                  ? 'Select your country code and enter your phone number'
                  : activeMenuMsgIdx !== null
                    ? 'Click cards to select · Send to confirm'
                    : <>Shift+Enter for new line · Use <span className="font-mono text-neutral-600">@ai</span> to update previous items</>
                }
              </p>
            </div>
          );
        })()}
      </div>
    </>
  );
}

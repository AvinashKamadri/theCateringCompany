"use client";

import { Suspense, useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AiChat, ChatHeader } from '@/components/chat/ai-chat';
import type { ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { chatAiApi } from '@/lib/api/chat-ai';
import {
  Plus, MessageSquare, ChevronRight, Loader2, Sparkles,
} from 'lucide-react';
import { AppNav } from '@/components/layout/app-nav';
import FoodPatternBg from '@/components/chat/FoodPatternBg';
import CornerDecorations from '@/components/ui/CornerDecorations';


const STAFF_DOMAINS = ['@catering-company.com'];
const STORAGE_KEY = 'tc_chat_sessions';

interface StoredSession {
  threadId: string;
  startedAt: string;
  lastActiveAt: string;
}

interface SessionSummary extends StoredSession {
  slotsFilled: number;
  totalSlots: number;
  isCompleted: boolean;
  clientName?: string;
  eventType?: string;
  eventDate?: string;
  loading: boolean;
  error?: boolean;
}

function formatRelativeTime(date: Date): string {
  const now = Date.now();
  const then = date.getTime();
  const diffSec = Math.round((now - then) / 1000);
  if (diffSec < 60) return 'just now';
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function loadStoredSessions(): StoredSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function removeSession(threadId: string) {
  try {
    const sessions = loadStoredSessions().filter((s) => s.threadId !== threadId);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {}
}

function AiIntakeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isAuthenticated } = useAuthStore();
  const [isSaving, setIsSaving] = useState(false);
  const [draftProjectId, setDraftProjectId] = useState<string | undefined>(undefined);
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>(
    searchParams?.get('thread') ?? undefined
  );
  const [view, setView] = useState<'picker' | 'chat'>(
    searchParams?.get('thread') ? 'chat' : 'picker'
  );
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);

  const isStaff = STAFF_DOMAINS.some((d) => user?.email?.toLowerCase().endsWith(d));

  useEffect(() => {
    if (!isAuthenticated) { router.push('/signin'); return; }
    if (isStaff) { router.replace('/contracts'); return; }
  }, [isAuthenticated, isStaff, router]);

  useEffect(() => {
    if (!isAuthenticated || isStaff) return;
    const stored = loadStoredSessions();
    if (stored.length === 0) {
      setLoadingSessions(false);
      setView('chat');
      return;
    }
    setSessions(
      stored.map((s) => ({ ...s, slotsFilled: 0, totalSlots: 20, isCompleted: false, loading: true }))
    );
    setLoadingSessions(false);

    // Hydrate sessions lazily — fetch one at a time with a small delay
    // to avoid hammering the ML agent with N simultaneous requests on load
    (async () => {
      for (const s of stored) {
        try {
          const conv = await chatAiApi.getConversation(s.threadId);
          setSessions((prev) =>
            prev.map((p) =>
              p.threadId === s.threadId
                ? {
                    ...p,
                    slotsFilled: conv.slots_filled ?? 0,
                    totalSlots: 20,
                    isCompleted: conv.is_completed ?? false,
                    clientName: (conv.slots as any)?.name ?? undefined,
                    eventType: (conv.slots as any)?.event_type ?? undefined,
                    eventDate: (conv.slots as any)?.event_date ?? undefined,
                    loading: false,
                  }
                : p
            )
          );
        } catch {
          setSessions((prev) =>
            prev.map((p) => p.threadId === s.threadId ? { ...p, loading: false, error: true } : p)
          );
        }
        // Small delay between requests to avoid overwhelming the ML agent
        await new Promise((r) => setTimeout(r, 300));
      }
    })();
  }, [isAuthenticated, isStaff]);

  const titleUpdatedRef = useRef(false);

  const handleSlotsUpdate = async (slots: Partial<ContractData>) => {
    // Update project title (once only)
    if (draftProjectId && !titleUpdatedRef.current) {
      const name = (slots as any).name;
      const eventType = (slots as any).event_type;
      if (name && eventType) {
        titleUpdatedRef.current = true;
        try {
          await apiClient.post('/projects/ai-intake', {
            project_id: draftProjectId,
            client_name: name,
            event_type: eventType,
            thread_id: activeThreadId,
          });
        } catch { /* non-fatal */ }
      }
    }
  };

  const handleComplete = async (contractData: ContractData) => {
    setIsSaving(true);
    try {
      const s = contractData;
      const parseList = (val: any): string[] => {
        if (!val || val === 'none' || val === 'no') return [];
        if (Array.isArray(val)) return val.filter(Boolean);
        return String(val).split(',').map((v: string) => v.trim()).filter(Boolean);
      };

      // Extract email and phone from slots
      const contactPhone = (s as any).phone || (s as any).contact_phone || undefined;
      const contactEmail = (s as any).email || (s as any).contact_email || undefined;
      const weddingCake =
        (s as any).wedding_cake && (s as any).wedding_cake !== 'none'
          ? (s as any).wedding_cake
          : undefined;

      const response = await apiClient.post('/projects/ai-intake', {
        client_name:          s.name,
        event_type:           s.event_type,
        event_date:           s.event_date,
        guest_count:          s.guest_count ? Number(s.guest_count) : undefined,
        service_type:         s.service_type,
        venue_name:           s.venue,
        venue_address:        s.venue,
        contact_email:        contactEmail,
        contact_phone:        contactPhone,
        main_dishes:          parseList(s.selected_dishes),
        appetizers:           parseList(s.appetizers),
        desserts:             parseList(s.desserts),
        menu_notes:           s.menu_notes || undefined,
        dietary_restrictions: s.dietary_concerns ? [s.dietary_concerns] : [],
        addons: [
          s.utensils && s.utensils !== 'no' ? `Utensils: ${s.utensils}` : null,
          s.rentals  && s.rentals  !== 'no' ? `Rentals: ${s.rentals}`   : null,
          s.florals  && s.florals  !== 'no' ? `Florals: ${s.florals}`   : null,
          weddingCake ? `Wedding Cake: ${weddingCake}` : null,
        ].filter(Boolean) as string[],
        modifications: s.special_requests && s.special_requests !== 'none'
          ? [s.special_requests] : [],
        project_id: draftProjectId,
        thread_id: activeThreadId || (s as any).thread_id || undefined,
        generate_contract: true,
      });

      const data = response as any;
      if (activeThreadId) removeSession(activeThreadId);
      if ((s as any).thread_id) removeSession((s as any).thread_id);

      toast.success(data.contract ? 'Project & Contract created! Pending staff approval.' : 'Project created!');
      router.push(data.project?.id ? `/projects/${data.project.id}` : '/projects');
    } catch (error: any) {
      toast.error(error.message || 'Failed to save project. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isAuthenticated || isStaff) return null;

  return (
    <div className="h-screen flex flex-col relative bg-[#f8f6f2]">
      <CornerDecorations />
      {view !== 'picker' && <FoodPatternBg />}
      <AppNav />

      {/* Full-width chat header spanning across both the chat column and the
          "Your Selections" sidebar. Background reaches all the way to the
          screen's top edge (under the floating nav pill); inner content is
          padded so it sits below the pill. */}
      {view === 'chat' && (
        <div className="shrink-0 pt-14 bg-white/85 backdrop-blur-xl backdrop-saturate-150">
          <div className="-mt-px">
            <ChatHeader
              isSaving={isSaving}
              showSessionsButton={sessions.filter((s) => !s.error).length > 0}
              onShowSessions={() => setView('picker')}
            />
          </div>
        </div>
      )}

      <div className={`flex flex-1 overflow-hidden min-h-0 ${view === 'chat' ? '' : 'pt-14'}`}>
        {/* Left: main content area */}
        <div className="flex-1 flex flex-col overflow-hidden min-w-0">
          {/* Thin top bar removed — "My chats" + saving indicator now render
              inside the AiChat header itself (see props on <AiChat /> below). */}

          {/* Session Picker */}
          {view === 'picker' && !loadingSessions && (
            <div className="flex-1 relative overflow-hidden bg-[#f8f6f2]">
              <FoodPatternBg cols={14} rows={20} opacity={0.22} />

              <div className="relative z-10 h-full overflow-y-auto">
                <div className="max-w-7xl mx-auto px-3 sm:px-6">
                {/* Headline */}
                <div className="pt-10 pb-6">
                  <p className="text-[11px] font-semibold tracking-widest uppercase text-neutral-600 mb-2">
                    Build Menu with A.I.
                  </p>
                  <h1 className="text-3xl sm:text-4xl font-bold text-neutral-950 leading-tight">
                    Crafted gatherings,<br />
                    <span className="italic font-light text-neutral-700">to the last detail.</span>
                  </h1>
                  <p className="mt-2.5 text-sm text-neutral-600 max-w-sm leading-relaxed">
                    Tell us what you&apos;re envisioning — we handle the menu, logistics, and everything in between.
                  </p>
                </div>

                {/* Session list */}
                <div className="pb-8">
                    {/* Section label */}
                    <div className="flex items-center justify-between mb-4 px-1">
                      <h2 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Your event chats</h2>
                      {sessions.length > 0 && (
                        <span className="text-[11px] font-medium text-neutral-400 bg-neutral-200 px-2 py-0.5 rounded-full tabular-nums">
                          {sessions.length}
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                      {/* New event CTA */}
                      <button
                        onClick={() => { setActiveThreadId(undefined); setView('chat'); }}
                        className="group flex items-center gap-4 px-5 py-5 rounded-2xl bg-neutral-900 hover:bg-neutral-800 transition-colors text-left shadow-sm"
                      >
                        <div className="w-11 h-11 rounded-xl bg-white/10 border border-white/10 flex items-center justify-center shrink-0">
                          <Plus className="w-5 h-5 text-white" strokeWidth={2.5} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-white text-base">Plan a new event</p>
                          <p className="text-sm text-white/40 mt-0.5">Start a fresh chat with the assistant</p>
                        </div>
                        <ChevronRight className="w-5 h-5 text-white/30 group-hover:text-white/70 group-hover:translate-x-0.5 transition-all shrink-0" />
                      </button>

                      {sessions.map((s) => {
                        const rawPct = s.totalSlots > 0 ? Math.round((s.slotsFilled / s.totalSlots) * 100) : 0;
                        const pct = Math.min(rawPct, 100);
                        const displayPct = s.isCompleted ? 100 : pct;
                        const initial = s.clientName?.trim().charAt(0).toUpperCase() || '';
                        const title = s.loading ? 'Loading…' : s.clientName || 'Untitled draft';
                        const subtitle = s.loading
                          ? ' '
                          : s.error
                            ? 'Unavailable'
                            : [
                                s.eventType,
                                s.eventDate && new Date(s.eventDate).toLocaleDateString([], { month: 'short', day: 'numeric' }),
                              ].filter(Boolean).join(' · ') || 'No details yet';
                        const relTime = formatRelativeTime(new Date(s.lastActiveAt));
                        return (
                          <button
                            key={s.threadId}
                            onClick={() => { setActiveThreadId(s.threadId); setView('chat'); }}
                            disabled={s.error}
                            className="group flex flex-col gap-3 px-5 py-5 rounded-2xl bg-white hover:bg-neutral-50 border border-neutral-200 hover:border-neutral-300 transition-all text-left shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
                          >
                            {/* Top row: avatar + meta */}
                            <div className="flex items-start gap-3.5">
                              <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 text-base font-bold ${
                                s.isCompleted
                                  ? 'bg-emerald-500 text-white'
                                  : initial
                                    ? 'bg-neutral-900 text-white'
                                    : 'bg-neutral-100 text-neutral-400'
                              }`}>
                                {s.loading
                                  ? <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
                                  : initial || <MessageSquare className="w-5 h-5" />}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 min-w-0">
                                  <p className="font-semibold text-neutral-900 truncate text-base">{title}</p>
                                  {s.isCompleted && !s.loading && (
                                    <span className="shrink-0 text-[10px] font-semibold bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full border border-emerald-200">Done</span>
                                  )}
                                </div>
                                <p className="text-sm text-neutral-400 truncate mt-0.5">{subtitle}</p>
                              </div>
                              <span className="text-xs text-neutral-400 whitespace-nowrap shrink-0">{relTime}</span>
                            </div>

                            {/* Progress bar */}
                            {!s.loading && !s.error && (
                              <div className="flex items-center gap-2">
                                <div className="flex-1 h-1 bg-neutral-100 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full rounded-full transition-all ${s.isCompleted ? 'bg-emerald-500' : 'bg-neutral-400'}`}
                                    style={{ width: `${Math.max(displayPct, 3)}%` }}
                                  />
                                </div>
                                <span className="text-xs text-neutral-400 tabular-nums font-medium w-8 text-right">{displayPct}%</span>
                              </div>
                            )}
                          </button>
                        );
                      })}
                    </div>
                </div>
                </div>{/* /max-w-7xl */}
              </div>
            </div>
          )}

          {/* Chat */}
          {view === 'chat' && (
            <div className="flex-1 overflow-hidden flex justify-center">
              <div className="w-full max-w-7xl px-3 sm:px-6 flex flex-col overflow-hidden">
                <AiChat
                  hideHeader
                  onComplete={handleComplete}
                  onSlotsUpdate={handleSlotsUpdate}
                  authorId={user?.id}
                  userId={user?.id}
                  userName={user?.email || 'You'}
                  initialThreadId={activeThreadId}
                  onThreadStart={async (threadId) => {
                    setActiveThreadId(threadId);
                    try {
                      const res = await apiClient.post('/projects/ai-intake', { thread_id: threadId }) as any;
                      setDraftProjectId(res.project?.id);
                    } catch { /* non-fatal */ }
                  }}
                />
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

export default function AiIntakePage() {
  return (
    <Suspense fallback={<div className="h-screen bg-neutral-50" />}>
      <AiIntakeContent />
    </Suspense>
  );
}


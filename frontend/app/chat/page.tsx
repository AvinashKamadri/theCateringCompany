"use client";

import { Suspense, useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AiChat } from '@/components/chat/ai-chat';
import type { ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { chatAiApi } from '@/lib/api/chat-ai';
import {
  Plus, MessageSquare, ChevronRight, Loader2,
  CalendarDays, Users, MapPin, UtensilsCrossed, ChevronDown,
} from 'lucide-react';
import { AppNav } from '@/components/layout/app-nav';

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
  loading: boolean;
  error?: boolean;
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

/** Right-side event plan panel */
function EventPlanPanel({ slots }: {
  slots: Partial<ContractData>;
}) {
  const [itemsOpen, setItemsOpen] = useState(false);
  const hasDate     = !!slots.event_date;
  const hasGuests   = !!slots.guest_count;
  const hasVenue    = !!slots.venue;
  const hasEventType = !!slots.event_type;
  const hasName     = !!slots.name;

  // Collect food items
  const foodItems: string[] = [];
  const parseItems = (val?: string | string[]) => {
    if (!val || val === 'none' || val === 'no') return;
    if (Array.isArray(val)) { foodItems.push(...val.filter(Boolean)); return; }
    val.split(',').map((v) => v.trim()).filter(Boolean).forEach((v) => foodItems.push(v));
  };
  parseItems(slots.selected_dishes);
  parseItems(slots.appetizers);
  parseItems(slots.desserts);

  const hasAnyDetail = hasDate || hasGuests || hasVenue || hasEventType || hasName || foodItems.length > 0;

  const formatDate = (d: string) => {
    try {
      return new Date(d).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
    } catch { return d; }
  };

  return (
    <div className="w-72 xl:w-80 bg-white border-l border-neutral-200 flex flex-col overflow-y-auto shrink-0">
      {/* Panel header */}
      <div className="px-5 pt-6 pb-4 border-b border-neutral-100">
        <p className="text-[10px] font-semibold tracking-widest text-neutral-400 uppercase">
          Your Event Plan
        </p>
      </div>

      <div className="px-5 py-5 flex-1">
        {!hasAnyDetail ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-10 h-10 rounded-full bg-neutral-100 flex items-center justify-center mb-3">
              <UtensilsCrossed className="w-5 h-5 text-neutral-300" />
            </div>
            <p className="text-sm text-neutral-400 leading-relaxed">
              Your event details will<br />appear here as we chat.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {/* Core event details */}
            {(hasName || hasEventType || hasDate || hasGuests || hasVenue) && (
              <div className="space-y-3">
                {hasName && (
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-md bg-neutral-100 flex items-center justify-center shrink-0 mt-0.5">
                      <Users className="w-3.5 h-3.5 text-neutral-500" />
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase">Client</p>
                      <p className="text-sm font-medium text-neutral-900 mt-0.5">{slots.name}</p>
                    </div>
                  </div>
                )}

                {hasEventType && (
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-md bg-neutral-100 flex items-center justify-center shrink-0 mt-0.5">
                      <UtensilsCrossed className="w-3.5 h-3.5 text-neutral-500" />
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase">Event</p>
                      <p className="text-sm font-medium text-neutral-900 mt-0.5">{slots.event_type}</p>
                    </div>
                  </div>
                )}

                {hasDate && (
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-md bg-neutral-100 flex items-center justify-center shrink-0 mt-0.5">
                      <CalendarDays className="w-3.5 h-3.5 text-neutral-500" />
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase">Date</p>
                      <p className="text-sm font-medium text-neutral-900 mt-0.5">{formatDate(slots.event_date!)}</p>
                    </div>
                  </div>
                )}

                {hasGuests && (
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-md bg-neutral-100 flex items-center justify-center shrink-0 mt-0.5">
                      <Users className="w-3.5 h-3.5 text-neutral-500" />
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase">Guests</p>
                      <p className="text-sm font-medium text-neutral-900 mt-0.5">{slots.guest_count} Attendees</p>
                    </div>
                  </div>
                )}

                {hasVenue && (
                  <div className="flex items-start gap-3">
                    <div className="w-7 h-7 rounded-md bg-neutral-100 flex items-center justify-center shrink-0 mt-0.5">
                      <MapPin className="w-3.5 h-3.5 text-neutral-500" />
                    </div>
                    <div>
                      <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase">Location</p>
                      <p className="text-sm font-medium text-neutral-900 mt-0.5">{slots.venue}</p>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Food items — peek 4.5 items, expand on click */}
            {foodItems.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] font-semibold tracking-widest text-neutral-400 uppercase">
                    Selected Items
                  </p>
                  <span className="text-xs text-neutral-400 tabular-nums">{foodItems.length}</span>
                </div>
                <div className="relative">
                  <div
                    className={`space-y-2 overflow-hidden transition-all duration-300 ${
                      itemsOpen ? 'max-h-[2000px]' : 'max-h-[198px]'
                    }`}
                  >
                    {foodItems.map((item, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2.5 p-2.5 rounded-lg bg-neutral-50 border border-neutral-100"
                      >
                        <div className="w-8 h-8 rounded-md bg-neutral-200 flex items-center justify-center shrink-0">
                          <UtensilsCrossed className="w-3.5 h-3.5 text-neutral-400" />
                        </div>
                        <p className="text-sm text-neutral-800 font-medium leading-tight">{item}</p>
                      </div>
                    ))}
                  </div>

                  {/* Blur + arrow overlay when collapsed and more items exist */}
                  {!itemsOpen && foodItems.length > 4 && (
                    <div className="absolute bottom-0 left-0 right-0 h-16 bg-linear-to-t from-white to-transparent pointer-events-none" />
                  )}
                </div>

                {foodItems.length > 4 && (
                  <button
                    onClick={() => setItemsOpen((o) => !o)}
                    className="mt-1 w-full flex items-center justify-center gap-1 text-xs text-neutral-500 hover:text-neutral-900 py-1 transition-colors"
                  >
                    <ChevronDown
                      className={`w-3.5 h-3.5 transition-transform ${itemsOpen ? 'rotate-180' : ''}`}
                    />
                    {itemsOpen ? 'Show less' : `View all ${foodItems.length} items`}
                  </button>
                )}
              </div>
            )}

            {/* Additional details */}
            {slots.service_type && (
              <div>
                <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase mb-1">
                  Service
                </p>
                <p className="text-sm text-neutral-800 capitalize">{slots.service_type.replace('-', ' ')}</p>
              </div>
            )}

            {slots.dietary_concerns && slots.dietary_concerns !== 'none' && (
              <div>
                <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase mb-1">
                  Dietary Notes
                </p>
                <p className="text-sm text-neutral-800">{slots.dietary_concerns}</p>
              </div>
            )}

            {slots.special_requests && slots.special_requests !== 'none' && (
              <div>
                <p className="text-[10px] font-semibold tracking-wider text-neutral-400 uppercase mb-1">
                  Special Requests
                </p>
                <p className="text-sm text-neutral-800">{slots.special_requests}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AiIntakeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isAuthenticated } = useAuthStore();
  const [isSaving, setIsSaving] = useState(false);
  const [draftProjectId, setDraftProjectId] = useState<string | undefined>(undefined);
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>(
    searchParams.get('thread') ?? undefined
  );
  const [view, setView] = useState<'picker' | 'chat'>(
    searchParams.get('thread') ? 'chat' : 'picker'
  );
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [currentSlots, setCurrentSlots] = useState<Partial<ContractData>>({});
  const [, setProgress] = useState<{ filled: number; total: number }>({ filled: 0, total: 20 });

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

    stored.forEach(async (s) => {
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
    });
  }, [isAuthenticated, isStaff]);

  const titleUpdatedRef = useRef(false);

  const handleSlotsUpdate = async (slots: Partial<ContractData>) => {
    setCurrentSlots((prev) => ({ ...prev, ...slots }));

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

      const response = await apiClient.post('/projects/ai-intake', {
        client_name:          s.name,
        event_type:           s.event_type,
        event_date:           s.event_date,
        guest_count:          s.guest_count ? Number(s.guest_count) : undefined,
        service_type:         s.service_type,
        venue_name:           s.venue,
        venue_address:        s.venue,
        main_dishes:          parseList(s.selected_dishes),
        appetizers:           parseList(s.appetizers),
        desserts:             parseList(s.desserts),
        menu_notes:           s.menu_notes || undefined,
        dietary_restrictions: s.dietary_concerns ? [s.dietary_concerns] : [],
        addons: [
          s.utensils && s.utensils !== 'no' ? `Utensils: ${s.utensils}` : null,
          s.rentals  && s.rentals  !== 'no' ? `Rentals: ${s.rentals}`   : null,
          s.florals  && s.florals  !== 'no' ? `Florals: ${s.florals}`   : null,
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
    <div className="h-screen flex flex-col bg-neutral-50">
      <AppNav />

      <div className="flex flex-1 overflow-hidden pt-14">
        {/* Left: main content area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Thin top bar for session switching + saving indicator */}
          {(view === 'chat' && sessions.filter((s) => !s.error).length > 0) || isSaving ? (
            <div className="bg-white border-b border-neutral-100 px-6 py-2 flex items-center justify-between shrink-0">
              <div />
              <div className="flex items-center gap-3">
                {view === 'chat' && sessions.filter((s) => !s.error).length > 0 && (
                  <button
                    onClick={() => setView('picker')}
                    className="text-xs text-neutral-500 hover:text-neutral-900 flex items-center gap-1.5 border border-neutral-200 rounded-md px-2.5 py-1 hover:border-neutral-300 transition-colors"
                  >
                    <MessageSquare className="w-3 h-3" />
                    My sessions
                  </button>
                )}
                {isSaving && (
                  <div className="flex items-center gap-1.5 text-neutral-500 text-xs">
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Saving…
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {/* Session Picker */}
          {view === 'picker' && !loadingSessions && (
            <div className="flex-1 overflow-y-auto p-6">
              <div className="max-w-lg mx-auto bg-white rounded-xl border border-neutral-200 overflow-hidden">
                <div className="px-6 py-5 border-b border-neutral-100">
                  <h2 className="font-semibold text-neutral-900">Your intake sessions</h2>
                  <p className="text-sm text-neutral-500 mt-0.5">Continue where you left off, or start fresh</p>
                </div>
                <div className="divide-y divide-neutral-100">
                  <button
                    onClick={() => { setActiveThreadId(undefined); setCurrentSlots({}); setProgress({ filled: 0, total: 20 }); setView('chat'); }}
                    className="w-full flex items-center gap-4 px-6 py-4 hover:bg-neutral-50 transition-colors text-left"
                  >
                    <div className="w-10 h-10 bg-black rounded-xl flex items-center justify-center shrink-0">
                      <Plus className="w-5 h-5 text-white" />
                    </div>
                    <div className="flex-1">
                      <p className="font-medium text-neutral-900">Start new session</p>
                      <p className="text-sm text-neutral-400">Begin a fresh event intake conversation</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-neutral-300" />
                  </button>

                  {sessions.map((s) => (
                    <button
                      key={s.threadId}
                      onClick={() => { setActiveThreadId(s.threadId); setView('chat'); }}
                      disabled={s.error}
                      className="w-full flex items-center gap-4 px-6 py-4 hover:bg-neutral-50 transition-colors text-left disabled:opacity-40"
                    >
                      <div className="w-10 h-10 bg-neutral-100 rounded-xl flex items-center justify-center shrink-0">
                        {s.loading
                          ? <Loader2 className="w-4 h-4 text-neutral-400 animate-spin" />
                          : <MessageSquare className="w-4 h-4 text-neutral-500" />
                        }
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-neutral-900 truncate">
                            {s.loading ? 'Loading…'
                              : s.clientName ? `${s.clientName}${s.eventType ? ` · ${s.eventType}` : ''}`
                              : 'Intake session'}
                          </p>
                          {s.isCompleted && !s.loading && (
                            <span className="shrink-0 text-xs bg-neutral-900 text-white px-2 py-0.5 rounded-full">
                              Complete
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 mt-1">
                          {!s.loading && !s.error && (
                            <>
                              <div className="flex items-center gap-1.5">
                                <div className="w-16 h-1 bg-neutral-100 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-black rounded-full"
                                    style={{ width: `${(s.slotsFilled / s.totalSlots) * 100}%` }}
                                  />
                                </div>
                                <span className="text-xs text-neutral-400 tabular-nums">
                                  {s.slotsFilled}/{s.totalSlots}
                                </span>
                              </div>
                              <span className="text-xs text-neutral-400">
                                {new Date(s.lastActiveAt).toLocaleDateString([], {
                                  month: 'short', day: 'numeric',
                                  hour: '2-digit', minute: '2-digit',
                                })}
                              </span>
                            </>
                          )}
                          {s.error && <span className="text-xs text-red-400">Unavailable</span>}
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-neutral-300 shrink-0" />
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Chat */}
          {view === 'chat' && (
            <div className="flex-1 overflow-hidden">
              <AiChat
                onComplete={handleComplete}
                onSlotsUpdate={handleSlotsUpdate}
                onProgressUpdate={setProgress}
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
          )}
        </div>

        {/* Right: event plan panel */}
        <EventPlanPanel slots={currentSlots} />
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

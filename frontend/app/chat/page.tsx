"use client";

import { Suspense, useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { AiChat } from '@/components/chat/ai-chat';
import type { ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { chatAiApi } from '@/lib/api/chat-ai';
import { Plus, MessageSquare, ChevronRight, Loader2 } from 'lucide-react';
import { AppNav } from '@/components/layout/app-nav';

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

  const isStaff = user?.role === 'staff' || user?.email?.toLowerCase().endsWith('@catering-company.com');

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
    if (!draftProjectId || titleUpdatedRef.current) return;
    const name = (slots as any).name;
    const eventType = (slots as any).event_type;
    if (!name || !eventType) return;
    titleUpdatedRef.current = true;
    try {
      await apiClient.post('/projects/ai-intake', {
        project_id: draftProjectId,
        client_name: name,
        event_type: eventType,
        thread_id: activeThreadId,
      });
    } catch { /* non-fatal */ }
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
    <div className="min-h-screen bg-neutral-50">
      <AppNav />

      <div className="pt-14 h-screen flex flex-col">
        {/* Content */}
        <div className="flex-1 overflow-hidden">
          <div className="max-w-4xl mx-auto h-full py-6 px-4 flex flex-col">
            {/* Sessions button — only shown when in chat view with existing sessions */}
            {view === 'chat' && sessions.filter((s) => !s.error).length > 0 && (
              <div className="flex justify-end mb-3 shrink-0">
                <button
                  onClick={() => setView('picker')}
                  className="text-sm text-neutral-600 hover:text-neutral-900 flex items-center gap-1.5 border border-neutral-200 rounded-lg px-3 py-1.5 hover:border-neutral-300 transition-colors bg-white"
                >
                  <MessageSquare className="w-3.5 h-3.5" />
                  My sessions
                </button>
                {isSaving && (
                  <div className="flex items-center gap-2 text-neutral-500 text-sm ml-3">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Saving…
                  </div>
                )}
              </div>
            )}

            {/* Session Picker */}
            {view === 'picker' && !loadingSessions && (
              <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
                <div className="px-6 py-5 border-b border-neutral-100">
                  <h2 className="font-semibold text-neutral-900">Your intake sessions</h2>
                  <p className="text-sm text-neutral-500 mt-0.5">Continue where you left off, or start fresh</p>
                </div>
                <div className="divide-y divide-neutral-100">
                  <button
                    onClick={() => { setActiveThreadId(undefined); setView('chat'); }}
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
            )}

            {/* Chat */}
            {view === 'chat' && (
              <div className="bg-white rounded-xl border border-neutral-200 h-full overflow-hidden">
                <AiChat
                  onComplete={handleComplete}
                  onSlotsUpdate={handleSlotsUpdate}
                  authorId={user?.id}
                  userId={user?.id}
                  initialThreadId={activeThreadId}
                  onThreadStart={async (threadId) => {
                    setActiveThreadId(threadId);
                    try {
                      const res = await apiClient.post('/projects/ai-intake', { thread_id: threadId }) as any;
                      setDraftProjectId(res.project?.id);
                    } catch { /* non-fatal — will create fresh on complete */ }
                  }}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AiIntakePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-neutral-50" />}>
      <AiIntakeContent />
    </Suspense>
  );
}

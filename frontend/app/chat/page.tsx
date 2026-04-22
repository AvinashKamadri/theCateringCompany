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
  Plus, MessageSquare, ChevronRight, Loader2,
  CalendarDays, Users, MapPin, UtensilsCrossed, ChevronDown, Sparkles,
} from 'lucide-react';
import { AppNav } from '@/components/layout/app-nav';

function getMenuImageUrl(name: string): string | null {
  // Only strip price-parens; keep flavor lists intact.
  const clean = name
    .replace(/\s*\([^)]*\$[^)]*\)\s*/g, '').replace(/\s*\$[\d.,]+\/?\w*/g, '').trim()
    .toLowerCase().replace(/[&]/g, 'and').replace(/[\/]/g, '-').replace(/w\//g, 'w-')
    .replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  return clean ? `/menu-images/${clean}.jpg` : null;
}

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

/** Right-side event plan panel — hover-only, transparent glass sidebar */
function EventPlanPanel({ slots }: { slots: Partial<ContractData> }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [itemsOpen, setItemsOpen] = useState(false);
  const hasDate     = !!slots.event_date;
  const hasGuests   = !!slots.guest_count;
  const hasVenue    = !!slots.venue;
  const hasEventType = !!slots.event_type;
  const hasName     = !!slots.name;
  const eventType = String(slots.event_type || '').toLowerCase();
  const isWedding = eventType.includes('wedding');
  const isCorporate = eventType.includes('corporate');
  const isBirthday = eventType.includes('birthday');
  const slotList = (val?: string | string[]) => {
    if (!val || val === 'none' || val === 'no') return [];
    if (Array.isArray(val)) return val.filter(Boolean);
    return String(val).split(',').map((v) => v.trim()).filter(Boolean);
  };
  const slotYesNo = (val?: boolean | string | null) => {
    if (val === true || val === 'true' || val === 'True') return 'Yes';
    if (val === false || val === 'false' || val === 'False') return 'No';
    return null;
  };

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

  const panelContent = (
    <div className="space-y-5">
      {!hasAnyDetail ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center mb-3">
            <UtensilsCrossed className="w-5 h-5 text-white/40" />
          </div>
          <p className="text-sm text-white/50 leading-relaxed">
            Your event details will<br />appear here as we chat.
          </p>
        </div>
      ) : (
        <>
          {(hasName || hasEventType || hasDate || hasGuests || hasVenue) && (
            <div className="space-y-3">
              {hasName && (
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                    <Users className="w-3.5 h-3.5 text-white/60" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase">Client</p>
                    <p className="text-sm font-medium text-white/90 mt-0.5">{slots.name}</p>
                  </div>
                </div>
              )}
              {hasEventType && (
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                    <UtensilsCrossed className="w-3.5 h-3.5 text-white/60" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase">Event</p>
                    <p className="text-sm font-medium text-white/90 mt-0.5">{slots.event_type}</p>
                  </div>
                </div>
              )}
              {hasDate && (
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                    <CalendarDays className="w-3.5 h-3.5 text-white/60" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase">Date</p>
                    <p className="text-sm font-medium text-white/90 mt-0.5">{formatDate(slots.event_date!)}</p>
                  </div>
                </div>
              )}
              {hasGuests && (
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                    <Users className="w-3.5 h-3.5 text-white/60" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase">Guests</p>
                    <p className="text-sm font-medium text-white/90 mt-0.5">{slots.guest_count} Attendees</p>
                  </div>
                </div>
              )}
              {hasVenue && (
                <div className="flex items-start gap-3">
                  <div className="w-7 h-7 rounded-md bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                    <MapPin className="w-3.5 h-3.5 text-white/60" />
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase">Location</p>
                    <p className="text-sm font-medium text-white/90 mt-0.5">{slots.venue}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {foodItems.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-[10px] font-semibold tracking-widest text-white/40 uppercase">Selected Items</p>
                <span className="text-xs text-white/40 tabular-nums">{foodItems.length}</span>
              </div>
              <div className="relative">
                <div className={`space-y-2 overflow-hidden transition-all duration-300 ${itemsOpen ? 'max-h-[2000px]' : 'max-h-[198px]'}`}>
                  {foodItems.map((item, i) => {
                    const imgUrl = getMenuImageUrl(item);
                    return (
                      <div key={i} className="flex items-center gap-2.5 p-2.5 rounded-lg bg-white/10 border border-white/10">
                        {imgUrl ? (
                          <img src={imgUrl} alt={item} className="w-8 h-8 rounded-md object-cover shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
                        ) : (
                          <div className="w-8 h-8 rounded-md bg-white/10 flex items-center justify-center shrink-0">
                            <UtensilsCrossed className="w-3.5 h-3.5 text-white/40" />
                          </div>
                        )}
                        <p className="text-sm text-white/80 font-medium leading-tight">{item}</p>
                      </div>
                    );
                  })}
                </div>
                {!itemsOpen && foodItems.length > 4 && (
                  <div className="absolute bottom-0 left-0 right-0 h-16 bg-linear-to-t from-black/40 to-transparent pointer-events-none" />
                )}
              </div>
              {foodItems.length > 4 && (
                <button onClick={() => setItemsOpen((o) => !o)} className="mt-1 w-full flex items-center justify-center gap-1 text-xs text-white/50 hover:text-white py-1 transition-colors">
                  <ChevronDown className={`w-3.5 h-3.5 transition-transform ${itemsOpen ? 'rotate-180' : ''}`} />
                  {itemsOpen ? 'Show less' : `View all ${foodItems.length} items`}
                </button>
              )}
            </div>
          )}

          {slots.service_type && (
            <div>
              <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase mb-1">Service</p>
              <p className="text-sm text-white/80 capitalize">{slots.service_type.replace('-', ' ')}</p>
            </div>
          )}
          {slots.dietary_concerns && slots.dietary_concerns !== 'none' && (
            <div>
              <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase mb-1">Dietary Notes</p>
              <p className="text-sm text-white/80">{slots.dietary_concerns}</p>
            </div>
          )}
          {slots.special_requests && slots.special_requests !== 'none' && (
            <div>
              <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase mb-1">Special Requests</p>
              <p className="text-sm text-white/80">{slots.special_requests}</p>
            </div>
          )}
          <div className="pt-1 border-t border-white/10">
            <p className="text-[10px] font-semibold tracking-wider text-white/40 uppercase mb-2">Full Intake Snapshot</p>
            <div className="space-y-1.5 text-sm">
              {isWedding && slots.partner_name && <p className="text-white/70"><span className="text-white/40">Partner:</span> {slots.partner_name}</p>}
              {isCorporate && slots.company_name && <p className="text-white/70"><span className="text-white/40">Company:</span> {slots.company_name}</p>}
              {isBirthday && slots.honoree_name && <p className="text-white/70"><span className="text-white/40">Honoree:</span> {slots.honoree_name}</p>}
              {slots.email && <p className="text-white/70"><span className="text-white/40">Email:</span> {slots.email}</p>}
              {slots.phone && <p className="text-white/70"><span className="text-white/40">Phone:</span> {slots.phone}</p>}
              {slots.wedding_cake && slots.wedding_cake !== 'none' && <p className="text-white/70"><span className="text-white/40">Wedding cake:</span> {slots.wedding_cake}</p>}
              {slots.meal_style && <p className="text-white/70"><span className="text-white/40">Meal style:</span> {slots.meal_style}</p>}
              {slots.appetizer_style && <p className="text-white/70"><span className="text-white/40">Appetizer style:</span> {slots.appetizer_style}</p>}
              {slots.tableware && <p className="text-white/70"><span className="text-white/40">Tableware:</span> {slots.tableware}</p>}
              {slots.utensils && <p className="text-white/70"><span className="text-white/40">Utensils:</span> {slots.utensils}</p>}
              {slotYesNo(slots.drinks) && <p className="text-white/70"><span className="text-white/40">Drinks:</span> {slotYesNo(slots.drinks)}</p>}
              {slotYesNo(slots.bar_service) && <p className="text-white/70"><span className="text-white/40">Bar service:</span> {slotYesNo(slots.bar_service)}</p>}
              {slots.bar_package && <p className="text-white/70"><span className="text-white/40">Bar package:</span> {slots.bar_package}</p>}
              {slotYesNo(slots.coffee_service) && <p className="text-white/70"><span className="text-white/40">Coffee service:</span> {slotYesNo(slots.coffee_service)}</p>}
              {slotYesNo(slots.linens) && <p className="text-white/70"><span className="text-white/40">Linens:</span> {slotYesNo(slots.linens)}</p>}
              {slotList(slots.rentals).length > 0 && <p className="text-white/70"><span className="text-white/40">Rentals:</span> {slotList(slots.rentals).join(', ')}</p>}
              {slots.additional_notes && slots.additional_notes !== 'none' && <p className="text-white/70"><span className="text-white/40">Additional notes:</span> {slots.additional_notes}</p>}
              {slotYesNo(slots.followup_call_requested) && <p className="text-white/70"><span className="text-white/40">Follow-up call:</span> {slotYesNo(slots.followup_call_requested)}</p>}
            </div>
          </div>
        </>
      )}
    </div>
  );

  return (
    <>
      {/* Hover trigger strip on right edge */}
      <div
        className="fixed right-0 top-0 bottom-0 w-3 z-40 hover:bg-white/5 transition-colors"
        onMouseEnter={() => setIsExpanded(true)}
      />
      {/* Transparent glass sidebar */}
      <div
        className={`fixed right-0 top-0 bottom-0 z-50 transition-transform duration-300 ease-in-out ${
          isExpanded ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ width: '320px' }}
        onMouseLeave={() => setIsExpanded(false)}
      >
        <div className="h-full flex flex-col overflow-y-auto bg-black/40 backdrop-blur-2xl backdrop-saturate-150 border-l border-white/10">
          <div className="px-5 pt-6 pb-4 border-b border-white/10 flex items-center justify-between">
            <p className="text-[10px] font-semibold tracking-widest text-white/50 uppercase">Your Selections</p>
            <button onClick={() => setIsExpanded(false)} className="text-white/50 hover:text-white transition-colors text-xs">Close</button>
          </div>
          <div className="px-5 py-5 flex-1">{panelContent}</div>
        </div>
      </div>
    </>
  );
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
    // Replace with the backend's latest filled-slot snapshot so removals and
    // event-type-driven clears don't linger in the sidebar.
    setCurrentSlots({ ...slots });

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

  const outerBg =
    view === 'chat'
      ? { backgroundImage: "url('/chat-bg2.jpg')" }
      : view === 'picker'
        ? { backgroundImage: "url('/cat-bg2.jpg')" }
        : undefined;

  return (
    <div
      className={`h-screen flex flex-col ${view === 'chat' || view === 'picker' ? 'bg-cover bg-center bg-fixed' : 'bg-neutral-50'}`}
      style={outerBg}
    >
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
            <div
              className="flex-1 overflow-y-auto p-3 sm:p-6 relative bg-cover bg-center bg-fixed"
              style={{ backgroundImage: "url('/cat-bg2.jpg')" }}
            >
              <div className="max-w-5xl mx-auto space-y-6">
              {/* Hero banner */}
              <div className="relative overflow-hidden rounded-2xl bg-linear-to-br from-neutral-900 via-neutral-800 to-neutral-900 px-6 sm:px-8 py-8 sm:py-10 text-white">
                <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, white 1px, transparent 0)', backgroundSize: '24px 24px' }} />
                <div className="relative z-10">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-8 h-8 rounded-lg bg-white/10 backdrop-blur flex items-center justify-center">
                      <Sparkles className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-xs font-medium tracking-wider uppercase text-white/60">AI-Powered</span>
                  </div>
                  <h1 className="text-2xl sm:text-3xl font-bold leading-tight mb-2">
                    Plan any event,<br />effortlessly.
                  </h1>
                  <p className="text-sm sm:text-base text-white/60 max-w-sm leading-relaxed">
                    Tell us what you&apos;re dreaming of — our AI handles the menu, the details, and the paperwork.
                  </p>
                  <button
                    onClick={() => { setActiveThreadId(undefined); setCurrentSlots({}); setProgress({ filled: 0, total: 20 }); setView('chat'); }}
                    className="mt-5 inline-flex items-center gap-2 bg-white text-black px-5 py-2.5 rounded-xl text-sm font-semibold hover:bg-neutral-100 transition-colors"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    Start planning
                  </button>
                </div>
              </div>

              {/* Session list */}
              <div className="tc-glossy rounded-2xl overflow-hidden">
                <div className="px-4 sm:px-6 py-4 sm:py-5 border-b border-neutral-100 flex items-end justify-between">
                  <div>
                    <h2 className="font-semibold text-neutral-900 text-base">Your event chats</h2>
                    <p className="text-xs text-neutral-500 mt-0.5">Pick up where you left off</p>
                  </div>
                  {sessions.length > 0 && (
                    <span className="text-[11px] font-medium text-neutral-400 tabular-nums">
                      {sessions.length} {sessions.length === 1 ? 'session' : 'sessions'}
                    </span>
                  )}
                </div>
                <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {/* New event — primary CTA row, spans full width */}
                  <button
                    onClick={() => { setActiveThreadId(undefined); setCurrentSlots({}); setProgress({ filled: 0, total: 20 }); setView('chat'); }}
                    className="sm:col-span-2 group w-full flex items-center gap-4 px-4 py-4 rounded-xl bg-white hover:bg-neutral-50 border border-neutral-200 hover:border-neutral-300 transition-colors text-left"
                  >
                    <div className="tc-glossy-dark w-11 h-11 rounded-xl flex items-center justify-center shrink-0 group-hover:scale-[1.04] transition-transform">
                      <Plus className="w-5 h-5 text-white" strokeWidth={2.5} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-neutral-900">Plan a new event</p>
                      <p className="text-xs text-neutral-500 mt-0.5">Start a fresh chat with the assistant</p>
                    </div>
                    <ChevronRight className="w-4 h-4 text-neutral-300 group-hover:text-neutral-600 group-hover:translate-x-0.5 transition-all" />
                  </button>

                  {sessions.map((s) => {
                    const pct = s.totalSlots > 0 ? Math.round((s.slotsFilled / s.totalSlots) * 100) : 0;
                    const initial = s.clientName?.trim().charAt(0).toUpperCase() || '';
                    const title = s.loading
                      ? 'Loading…'
                      : s.clientName
                        ? s.clientName
                        : 'Untitled draft';
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
                        className="group w-full flex items-center gap-4 px-4 py-4 rounded-xl bg-white hover:bg-neutral-50 border border-neutral-200 hover:border-neutral-300 transition-colors text-left disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 text-sm font-semibold ${
                          s.isCompleted
                            ? 'bg-linear-to-br from-emerald-500 to-emerald-700 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2)]'
                            : initial
                              ? 'bg-linear-to-br from-neutral-700 to-neutral-900 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.12)]'
                              : 'bg-neutral-100 text-neutral-400'
                        }`}>
                          {s.loading
                            ? <Loader2 className="w-4 h-4 animate-spin" />
                            : initial || <MessageSquare className="w-4 h-4" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-semibold text-neutral-900 truncate text-sm">{title}</p>
                            {s.isCompleted && !s.loading && (
                              <span className="shrink-0 text-[10px] font-medium bg-emerald-50 text-emerald-700 px-1.5 py-0.5 rounded-full border border-emerald-200">
                                Complete
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-neutral-500 truncate mt-0.5">{subtitle}</p>
                          {!s.loading && !s.error && (
                            <div className="flex items-center gap-2 mt-2">
                              <div className="flex-1 max-w-[140px] h-1 bg-neutral-100 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${s.isCompleted ? 'bg-emerald-600' : 'bg-neutral-900'}`}
                                  style={{ width: `${Math.max(pct, s.isCompleted ? 100 : 4)}%` }}
                                />
                              </div>
                              <span className="text-[10px] text-neutral-400 tabular-nums font-medium">
                                {pct}%
                              </span>
                            </div>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-1 shrink-0">
                          <span className="text-[11px] text-neutral-400 whitespace-nowrap">{relTime}</span>
                          <ChevronRight className="w-4 h-4 text-neutral-300 group-hover:text-neutral-600 group-hover:translate-x-0.5 transition-all" />
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
              </div>{/* /grid */}
            </div>
          )}

          {/* Chat */}
          {view === 'chat' && (
            <div
              className="flex-1 overflow-hidden bg-cover bg-center bg-fixed"
              style={{ backgroundImage: "url('/chat-bg2.jpg')" }}
            >
              <AiChat
                hideHeader
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

        {/* Right: event plan panel — hover-only transparent sidebar */}
        {view === 'chat' && (
          <EventPlanPanel slots={currentSlots} />
        )}
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


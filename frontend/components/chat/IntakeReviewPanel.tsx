'use client';

import { useEffect } from 'react';
import {
  CheckCircle2, X, Loader2, Calendar, Users, MapPin, Utensils, GlassWater,
  Sparkles, MessageSquare, ChevronRight,
} from 'lucide-react';
import type { ContractData } from '@/types/chat-ai.types';

interface Props {
  contractData: ContractData;
  onConfirm: () => void;
  onClose?: () => void;
  isSaving?: boolean;
}

function parseList(val?: string | string[] | null): string[] {
  if (!val) return [];
  if (Array.isArray(val)) return val.filter(Boolean);
  return val.split(',').map((s) => s.trim()).filter(Boolean);
}

function isTruthy(val: boolean | string | undefined | null): boolean {
  if (val === true || val === 'true' || val === 'True') return true;
  return false;
}

function yesNo(val: boolean | string | undefined | null): string | null {
  if (val === true || val === 'true' || val === 'True') return 'Yes';
  if (val === false || val === 'false' || val === 'False') return 'No';
  return null;
}

const TABLEWARE_LABEL: Record<string, string> = {
  standard_disposable: 'Standard disposable',
  silver_disposable: 'Silver disposable',
  gold_disposable: 'Gold disposable',
  china: 'Full china',
  no_tableware: 'No tableware needed',
};
const UTENSILS_LABEL: Record<string, string> = {
  standard_plastic: 'Standard plastic',
  eco_biodegradable: 'Eco / biodegradable',
  bamboo: 'Bamboo',
  no_utensils: 'No utensils',
};
const BAR_PACKAGE_LABEL: Record<string, string> = {
  beer_wine: 'Beer & wine',
  beer_wine_signature: 'Beer, wine + 2 signature drinks',
  full_open_bar: 'Full open bar',
};
const TRAVEL_FEE_LABEL: Record<string, string> = {
  tier1_150: 'Under 30 min (+$150)',
  tier2_250: 'Under 1 hr (+$250)',
  tier3_375plus: 'Extended distance (+$375+)',
};

function SectionCard({
  icon: Icon,
  title,
  subtitle,
  children,
}: {
  icon: any;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-neutral-200 bg-white overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-3 border-b border-neutral-100 bg-neutral-50/50">
        <div className="w-8 h-8 rounded-lg bg-neutral-900 flex items-center justify-center shrink-0">
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-neutral-900">{title}</p>
          {subtitle && <p className="text-[11px] text-neutral-400 truncate">{subtitle}</p>}
        </div>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="flex justify-between items-start py-1.5 text-sm gap-4">
      <span className="text-neutral-400 shrink-0">{label}</span>
      <span className="text-neutral-900 font-medium text-right">{String(value)}</span>
    </div>
  );
}

function TagList({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item, i) => (
        <span key={`${item}-${i}`} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">
          {item}
        </span>
      ))}
    </div>
  );
}

export default function IntakeReviewPanel({ contractData: d, onConfirm, onClose, isSaving }: Props) {
  const appetizers = parseList(d.appetizers);
  const mainDishes = parseList(d.selected_dishes);
  const dessertList = parseList(d.desserts);
  const hasValidDesserts = dessertList.length > 0 && dessertList[0].toLowerCase() !== 'no';
  const rentals = parseList(d.rentals);
  const hasRentals = rentals.length > 0 && rentals[0].toLowerCase() !== 'no' && rentals[0].toLowerCase() !== 'none';

  const isWedding = String(d.event_type || '').toLowerCase().includes('wedding');
  const isCorporate = String(d.event_type || '').toLowerCase().includes('corporate');
  const isBirthday = String(d.event_type || '').toLowerCase().includes('birthday');
  const isOnsite = String(d.service_type || '').toLowerCase() === 'onsite';

  const hasDrinks = isTruthy(d.drinks);
  const hasBarSvc = isTruthy(d.bar_service);
  const hasDrinksSection = d.drinks !== undefined && d.drinks !== null;

  const laborSlots: Array<{ key: keyof ContractData; label: string }> = [
    { key: 'labor_ceremony_setup', label: 'Ceremony setup' },
    { key: 'labor_table_setup', label: 'Table setup' },
    { key: 'labor_table_preset', label: 'Tables preset before guests' },
    { key: 'labor_cleanup', label: 'Cleanup after event' },
    { key: 'labor_trash', label: 'Trash removal' },
  ];
  const filledLaborSlots = isOnsite
    ? laborSlots.filter((slot) => d[slot.key] !== undefined && d[slot.key] !== null)
    : [];

  const hasNotes = (d.dietary_concerns && d.dietary_concerns !== 'none')
    || (d.special_requests && d.special_requests !== 'none')
    || d.additional_notes;

  // Count selections for header
  const itemCount = appetizers.length + mainDishes.length + (hasValidDesserts ? dessertList.length : 0);

  // Lock body scroll while modal is open
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Close on ESC
  useEffect(() => {
    if (!onClose) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const headline = [
    d.event_type,
    d.event_date,
    d.guest_count ? `${d.guest_count} guests` : null,
  ].filter(Boolean).join(' · ');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 tc-fade-in" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-neutral-900/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl max-h-[92vh] bg-neutral-50 rounded-3xl shadow-2xl flex flex-col overflow-hidden tc-pop-in">
        {/* Header */}
        <div className="relative px-6 pt-6 pb-5 bg-gradient-to-br from-neutral-900 via-neutral-900 to-neutral-800 text-white shrink-0">
          <div className="flex items-start gap-3">
            <div className="w-11 h-11 rounded-xl bg-white/10 border border-white/15 flex items-center justify-center shrink-0">
              <CheckCircle2 className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1 min-w-0 pr-10">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold">Review your event</h2>
                <span className="px-1.5 py-0.5 rounded bg-amber-400/20 text-amber-200 text-[10px] font-bold uppercase tracking-wider">Draft</span>
              </div>
              <p className="text-xs text-neutral-300 mt-1 truncate">
                {d.name ? `${d.name} · ` : ''}{headline || 'Event summary'}
              </p>
              <div className="flex items-center gap-3 mt-3 text-[11px] text-neutral-400">
                <span className="flex items-center gap-1"><Utensils className="h-3 w-3" /> {itemCount} items</span>
                {d.service_type && <span className="capitalize">· {d.service_type}</span>}
                {d.meal_style && <span className="capitalize">· {d.meal_style}</span>}
              </div>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              aria-label="Close"
              className="absolute top-5 right-5 w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 border border-white/15 flex items-center justify-center transition-colors"
            >
              <X className="h-4 w-4 text-white" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-3">
          <SectionCard icon={Calendar} title="Event Details" subtitle="Who, when and where">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Row label="Name" value={d.name} />
              <Row label="Email" value={d.email} />
              <Row label="Phone" value={d.phone} />
              <Row label="Event type" value={d.event_type} />
              {isWedding && <Row label="Partner" value={d.partner_name} />}
              {isCorporate && <Row label="Company" value={d.company_name} />}
              {isBirthday && <Row label="Honoree" value={d.honoree_name} />}
              <Row label="Date" value={d.event_date} />
              <Row label="Guests" value={d.guest_count} />
              <Row label="Venue" value={d.venue} />
              <Row label="Service" value={d.service_type} />
              {isWedding && <Row label="Cocktail hour" value={yesNo(d.cocktail_hour)} />}
            </div>
          </SectionCard>

          <SectionCard icon={Utensils} title="Menu" subtitle={d.meal_style ? `${d.meal_style} · ${itemCount} items` : `${itemCount} items`}>
            {appetizers.length > 0 && (
              <div className="mb-4">
                <p className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-2">
                  {isWedding ? 'Cocktail Hour / Appetizers' : 'Appetizers'}
                  {d.appetizer_style && <span className="normal-case text-neutral-400"> · {d.appetizer_style}</span>}
                </p>
                <TagList items={appetizers} />
              </div>
            )}
            {mainDishes.length > 0 && (
              <div className="mb-4">
                <p className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-2">Main Course</p>
                <TagList items={mainDishes} />
              </div>
            )}
            <div>
              <p className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-2">Desserts</p>
              {hasValidDesserts ? <TagList items={dessertList} /> : <p className="text-xs text-neutral-400 italic">None</p>}
            </div>
            {d.menu_notes && (
              <p className="mt-4 px-3 py-2 rounded-lg bg-neutral-50 border border-neutral-100 text-xs text-neutral-600 italic">{d.menu_notes}</p>
            )}
          </SectionCard>

          {hasDrinksSection && (
            <SectionCard icon={GlassWater} title="Drinks & Bar">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
                <Row label="Drinks" value={yesNo(d.drinks)} />
                {hasDrinks && <Row label="Bar service" value={yesNo(d.bar_service)} />}
                {hasDrinks && hasBarSvc && d.bar_package && (
                  <Row label="Bar package" value={BAR_PACKAGE_LABEL[d.bar_package] ?? d.bar_package} />
                )}
                {hasDrinks && <Row label="Coffee bar" value={yesNo(d.coffee_service)} />}
              </div>
            </SectionCard>
          )}

          {(d.tableware || d.utensils) && (
            <SectionCard icon={Sparkles} title="Tableware & Utensils">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
                {d.tableware && <Row label="Tableware" value={TABLEWARE_LABEL[d.tableware] ?? d.tableware} />}
                {d.utensils && <Row label="Utensils" value={UTENSILS_LABEL[d.utensils] ?? d.utensils} />}
              </div>
            </SectionCard>
          )}

          {(d.linens !== undefined || hasRentals || filledLaborSlots.length > 0 || d.travel_fee) && (
            <SectionCard icon={MapPin} title="Services & Rentals">
              {d.linens !== undefined && d.linens !== null && <Row label="Linens" value={yesNo(d.linens)} />}
              {hasRentals && (
                <div className="mt-3 mb-1">
                  <p className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-2">Additional Rentals</p>
                  <TagList items={rentals} />
                </div>
              )}
              {filledLaborSlots.length > 0 && (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold text-neutral-400 uppercase tracking-wider mb-1">Staffing</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
                    {filledLaborSlots.map((slot) => (
                      <Row key={slot.key} label={slot.label} value={yesNo(d[slot.key] as boolean | string)} />
                    ))}
                  </div>
                </div>
              )}
              {d.travel_fee && <Row label="Travel fee" value={TRAVEL_FEE_LABEL[d.travel_fee] ?? d.travel_fee} />}
            </SectionCard>
          )}

          {(hasNotes || d.followup_call_requested !== undefined) && (
            <SectionCard icon={MessageSquare} title="Notes & Requests">
              {d.dietary_concerns && d.dietary_concerns !== 'none' && <Row label="Dietary concerns" value={d.dietary_concerns} />}
              {d.special_requests && d.special_requests !== 'none' && <Row label="Special requests" value={d.special_requests} />}
              {d.additional_notes && d.additional_notes !== 'none' && <Row label="Additional notes" value={d.additional_notes} />}
              {d.followup_call_requested !== undefined && d.followup_call_requested !== null && (
                <Row label="Follow-up call" value={yesNo(d.followup_call_requested)} />
              )}
            </SectionCard>
          )}

          <p className="text-[11px] text-neutral-400 text-center pt-2 pb-1">
            This is a starting point — everything can be adjusted before your event.
          </p>
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-neutral-200 bg-white/95 backdrop-blur px-4 sm:px-6 py-4 flex items-center gap-3">
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
              className="px-4 py-2.5 rounded-xl border border-neutral-200 text-neutral-700 text-sm font-semibold hover:bg-neutral-50 disabled:opacity-50 transition-colors"
            >
              Back to chat
            </button>
          )}
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSaving}
            className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-gradient-to-b from-neutral-800 to-black hover:from-neutral-700 hover:to-neutral-900 disabled:opacity-60 transition-colors shadow-[inset_0_1px_0_rgba(255,255,255,0.15),0_6px_14px_-4px_rgba(0,0,0,0.35)]"
          >
            {isSaving ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Sending to our team…</>
            ) : (
              <>Looks good — send to our team <ChevronRight className="h-4 w-4" /></>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

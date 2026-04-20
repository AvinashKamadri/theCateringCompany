'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react';
import type { ContractData } from '@/types/chat-ai.types';

interface Props {
  contractData: ContractData;
  onConfirm: () => void;
}

function parseList(val?: string | string[] | null): string[] {
  if (!val) return [];
  if (Array.isArray(val)) return val.filter(Boolean);
  return val.split(',').map((s) => s.trim()).filter(Boolean);
}

function isTruthy(val: boolean | string | undefined | null): boolean {
  if (val === true || val === 'true' || val === 'True') return true;
  if (val === false || val === 'false' || val === 'False' || val === null || val === undefined) return false;
  return false;
}

function yesNo(val: boolean | string | undefined | null): string | null {
  if (val === true || val === 'true' || val === 'True') return 'Yes';
  if (val === false || val === 'false' || val === 'False') return 'No';
  return null;
}

function Section({
  title,
  children,
  defaultOpen = false,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-neutral-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-neutral-50 transition-colors text-left"
      >
        <span className="text-sm font-semibold text-neutral-900">{title}</span>
        {open ? (
          <ChevronUp className="h-4 w-4 text-neutral-400 shrink-0" />
        ) : (
          <ChevronDown className="h-4 w-4 text-neutral-400 shrink-0" />
        )}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 bg-white border-t border-neutral-100">
          {children}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="flex justify-between items-start py-1.5 text-sm">
      <span className="text-neutral-500 shrink-0 mr-4">{label}</span>
      <span className="text-neutral-900 font-medium text-right">{String(value)}</span>
    </div>
  );
}

function TagList({ items, emptyLabel }: { items: string[]; emptyLabel?: string }) {
  if (!items.length) {
    if (emptyLabel) return <p className="text-xs text-neutral-400 italic">{emptyLabel}</p>;
    return null;
  }
  return (
    <div className="flex flex-wrap gap-1.5 mt-1">
      {items.map((item) => (
        <span key={item} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">
          {item}
        </span>
      ))}
    </div>
  );
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

export default function IntakeReviewPanel({ contractData: d, onConfirm }: Props) {
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

  return (
    <div className="border-t border-neutral-200 bg-neutral-50 px-4 py-4 space-y-3 max-h-[70vh] overflow-y-auto">
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2 className="w-5 h-5 text-neutral-900 shrink-0" />
        <div>
          <h3 className="text-sm font-bold text-neutral-900">Your Event Summary</h3>
          <p className="text-xs text-neutral-400">Here&apos;s what we&apos;ve got - we&apos;ll finalize pricing together</p>
        </div>
      </div>

      <Section title="Event Details" defaultOpen>
        <Row label="Name" value={d.name} />
        <Row label="Email" value={d.email} />
        <Row label="Phone" value={d.phone} />
        <Row label="Event Type" value={d.event_type} />
        {isWedding && <Row label="Partner / Fiancee" value={d.partner_name} />}
        {isCorporate && <Row label="Company" value={d.company_name} />}
        {isBirthday && <Row label="Honoree" value={d.honoree_name} />}
        <Row label="Date" value={d.event_date} />
        <Row label="Venue" value={d.venue} />
        <Row label="Guests" value={d.guest_count} />
        <Row label="Service" value={d.service_type} />
        {isWedding && <Row label="Cocktail Hour" value={yesNo(d.cocktail_hour)} />}
      </Section>

      <Section title="Menu">
        {d.meal_style && (
          <Row
            label="Meal Style"
            value={d.meal_style === 'plated' ? 'Plated' : d.meal_style === 'buffet' ? 'Buffet' : d.meal_style}
          />
        )}
        {appetizers.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">
              {isWedding ? 'Cocktail Hour / Appetizers' : 'Appetizers'}
            </p>
            {d.appetizer_style && (
              <p className="text-xs text-neutral-500 mb-1 capitalize">Style: {d.appetizer_style}</p>
            )}
            <TagList items={appetizers} />
          </div>
        )}
        {mainDishes.length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Main Course</p>
            <TagList items={mainDishes} />
          </div>
        )}
        <div className="mb-1">
          <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Desserts</p>
          {hasValidDesserts ? (
            <TagList items={dessertList} />
          ) : (
            <p className="text-xs text-neutral-400 italic">None</p>
          )}
        </div>
        {d.menu_notes && (
          <p className="text-xs text-neutral-500 italic mt-2">{d.menu_notes}</p>
        )}
      </Section>

      {hasDrinksSection && (
        <Section title="Drinks & Bar">
          <Row label="Drinks" value={yesNo(d.drinks)} />
          {hasDrinks && (
            <>
              <Row label="Bar service" value={yesNo(d.bar_service)} />
              {hasBarSvc && d.bar_package && (
                <Row label="Bar package" value={BAR_PACKAGE_LABEL[d.bar_package] ?? d.bar_package} />
              )}
              <Row label="Coffee bar" value={yesNo(d.coffee_service)} />
            </>
          )}
        </Section>
      )}

      {(d.tableware || d.utensils) && (
        <Section title="Tableware & Utensils">
          {d.tableware && (
            <Row label="Tableware" value={TABLEWARE_LABEL[d.tableware] ?? d.tableware} />
          )}
          {d.utensils && (
            <Row label="Utensils" value={UTENSILS_LABEL[d.utensils] ?? d.utensils} />
          )}
        </Section>
      )}

      {(d.linens !== undefined || hasRentals || filledLaborSlots.length > 0 || d.travel_fee) && (
        <Section title="Services & Rentals">
          {d.linens !== undefined && d.linens !== null && (
            <Row label="Linens" value={yesNo(d.linens)} />
          )}
          {hasRentals && (
            <div className="mt-1 mb-2">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Additional Rentals</p>
              <TagList items={rentals} />
            </div>
          )}
          {filledLaborSlots.length > 0 && (
            <div className="mt-1">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Staffing</p>
              {filledLaborSlots.map((slot) => (
                <Row key={slot.key} label={slot.label} value={yesNo(d[slot.key] as boolean | string)} />
              ))}
            </div>
          )}
          {d.travel_fee && (
            <Row label="Travel fee" value={TRAVEL_FEE_LABEL[d.travel_fee] ?? d.travel_fee} />
          )}
        </Section>
      )}

      {(hasNotes || d.followup_call_requested !== undefined) && (
        <Section title="Notes & Requests">
          {d.dietary_concerns && d.dietary_concerns !== 'none' && (
            <Row label="Dietary concerns" value={d.dietary_concerns} />
          )}
          {d.special_requests && d.special_requests !== 'none' && (
            <Row label="Special requests" value={d.special_requests} />
          )}
          {d.additional_notes && d.additional_notes !== 'none' && (
            <Row label="Additional notes" value={d.additional_notes} />
          )}
          {d.followup_call_requested !== undefined && d.followup_call_requested !== null && (
            <Row label="Follow-up call" value={yesNo(d.followup_call_requested)} />
          )}
        </Section>
      )}

      <p className="text-[11px] text-neutral-400 text-center pt-1">
        This is just the starting point - everything can be adjusted before your event.
      </p>

      <button
        onClick={onConfirm}
        className="w-full bg-black text-white py-3 rounded-xl text-sm font-semibold hover:bg-neutral-800 transition-colors"
      >
        Looks good - send to our team -&gt;
      </button>
    </div>
  );
}

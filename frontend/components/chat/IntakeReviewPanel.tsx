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
  if (!value && value !== 0) return null;
  return (
    <div className="flex justify-between items-start py-1.5 text-sm">
      <span className="text-neutral-500 shrink-0 mr-4">{label}</span>
      <span className="text-neutral-900 font-medium text-right capitalize">{String(value)}</span>
    </div>
  );
}

function TagList({ items }: { items: string[] }) {
  if (!items.length) return <p className="text-xs text-neutral-400 italic">None selected</p>;
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

export default function IntakeReviewPanel({ contractData: d, onConfirm }: Props) {
  const appetizers   = parseList(d.appetizers);
  const mainDishes   = parseList(d.selected_dishes);
  const desserts     = parseList(d.desserts);
  const hasMenu      = appetizers.length > 0 || mainDishes.length > 0 || desserts.length > 0;
  const rentals      = parseList(d.rentals);
  const hasRentals   = rentals.length > 0 && rentals[0] !== 'no';
  const hasAddons    = (d.utensils && d.utensils !== 'no') || hasRentals;
  const hasNotes     = (d.dietary_concerns && d.dietary_concerns !== 'none') ||
                       (d.special_requests && d.special_requests !== 'none') ||
                       d.additional_notes;

  return (
    <div className="border-t border-neutral-200 bg-neutral-50 px-4 py-4 space-y-3 max-h-[70vh] overflow-y-auto">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2 className="w-5 h-5 text-neutral-900 shrink-0" />
        <div>
          <h3 className="text-sm font-bold text-neutral-900">Your Event Summary</h3>
          <p className="text-xs text-neutral-400">Review your selections — no pricing yet, we'll finalize that together</p>
        </div>
      </div>

      {/* Event Details */}
      <Section title="Event Details" defaultOpen>
        <Row label="Name"         value={d.name} />
        <Row label="Event Type"   value={d.event_type} />
        <Row label="Date"         value={d.event_date} />
        <Row label="Venue"        value={d.venue} />
        <Row label="Guest Count"  value={d.guest_count} />
        <Row label="Service"      value={d.service_type} />
        {d.service_style && <Row label="Style" value={d.service_style} />}
      </Section>

      {/* Menu */}
      {hasMenu && (
        <Section title="Menu">
          {appetizers.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Cocktail Hour / Appetizers</p>
              <TagList items={appetizers} />
            </div>
          )}
          {mainDishes.length > 0 && (
            <div className="mb-3">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Main Course</p>
              <TagList items={mainDishes} />
            </div>
          )}
          {desserts.length > 0 && desserts[0] !== 'no' && (
            <div>
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Desserts</p>
              <TagList items={desserts} />
            </div>
          )}
          {d.menu_notes && (
            <p className="text-xs text-neutral-500 italic mt-2">{d.menu_notes}</p>
          )}
        </Section>
      )}

      {/* Services & Rentals */}
      {hasAddons && (
        <Section title="Services & Rentals">
          {d.utensils && d.utensils !== 'no' && (
            <Row label="Utensils" value={d.utensils} />
          )}
          {hasRentals && (
            <div className="mt-1">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-1">Rentals</p>
              <TagList items={rentals} />
            </div>
          )}
        </Section>
      )}

      {/* Notes */}
      {hasNotes && (
        <Section title="Notes & Requests">
          {d.dietary_concerns && d.dietary_concerns !== 'none' && (
            <Row label="Dietary" value={d.dietary_concerns} />
          )}
          {d.special_requests && d.special_requests !== 'none' && (
            <Row label="Special Requests" value={d.special_requests} />
          )}
          {d.additional_notes && (
            <Row label="Additional Notes" value={d.additional_notes} />
          )}
        </Section>
      )}

      <p className="text-[11px] text-neutral-400 text-center pt-1">
        Menus are a starting point — everything can be adjusted before your event.
      </p>

      <button
        onClick={onConfirm}
        className="w-full bg-black text-white py-3 rounded-xl text-sm font-semibold hover:bg-neutral-800 transition-colors"
      >
        Create Project & Contract →
      </button>
    </div>
  );
}

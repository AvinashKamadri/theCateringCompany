"use client";

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Calendar, Users, MapPin, FileText,
  Clock, CheckCircle2, AlertCircle, Loader2, Building2,
  ThumbsUp, ThumbsDown, X, Plus, Trash2, DollarSign, Calculator,
  ShieldAlert, Leaf, ChevronDown, ChevronRight, Search,
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import BentoInfoCard from '@/components/ui/BentoInfoCard';

const STAFF_DOMAINS = ['@catering-company.com', '@catering-company.com'];

interface Contract {
  id: string;
  title: string | null;
  status: string;
  version_number: number;
  total_amount: number | null;
  pdf_path: string | null;
  created_at: string;
  updated_at: string;
  body: any;
  metadata: any;
  projects_contracts_project_idToprojects: {
    id: string;
    title: string;
    event_date: string | null;
    guest_count: number | null;
    status: string;
    ai_event_summary: any;
    venues: { id: string; name: string; address: string } | null;
  } | null;
}

const STATUS_CONFIG: Record<string, { label: string; icon: any; style: string }> = {
  pending_staff_approval: {
    label: 'Pending Staff Approval',
    icon: Clock,
    style: 'bg-gradient-to-br from-amber-50 to-amber-100 text-amber-900 border-amber-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]',
  },
  approved: {
    label: 'Approved — Sending to Client',
    icon: CheckCircle2,
    style: 'bg-gradient-to-br from-sky-50 to-sky-100 text-sky-900 border-sky-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]',
  },
  sent: {
    label: 'Sent for Signature',
    icon: FileText,
    style: 'bg-gradient-to-br from-violet-50 to-violet-100 text-violet-900 border-violet-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]',
  },
  signed: {
    label: 'Signed',
    icon: CheckCircle2,
    style: 'bg-gradient-to-br from-emerald-50 to-emerald-100 text-emerald-900 border-emerald-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]',
  },
  rejected: {
    label: 'Rejected',
    icon: AlertCircle,
    style: 'bg-gradient-to-br from-red-50 to-red-100 text-red-900 border-red-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]',
  },
  draft: {
    label: 'Draft',
    icon: FileText,
    style: 'bg-gradient-to-br from-neutral-50 to-neutral-100 text-neutral-800 border-neutral-200 shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]',
  },
};

interface MenuComboOption {
  id: string;
  name: string;
  unit_price: number | string | null;
  allergens?: string[];
  menu_categories?: { name: string } | null;
}

function MenuItemCombobox({
  value,
  onChange,
  onPick,
  options,
  placeholder,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  onPick: (item: MenuComboOption) => void;
  options: MenuComboOption[];
  placeholder?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const wrapRef = useRef<HTMLDivElement>(null);

  const q = value.trim().toLowerCase();
  const matches = useMemo(() => {
    if (!q || options.length === 0) return [];
    const scored: Array<{ item: MenuComboOption; score: number }> = [];
    for (const it of options) {
      const n = it.name.toLowerCase();
      const cat = it.menu_categories?.name?.toLowerCase() ?? '';
      let score = 0;
      if (n === q) score = 100;
      else if (n.startsWith(q)) score = 60;
      else if (n.includes(q)) score = 40;
      else if (cat.includes(q)) score = 15;
      else {
        // token-wise match
        const toks = q.split(/\s+/).filter(Boolean);
        const allHit = toks.every((t) => n.includes(t));
        if (allHit) score = 20;
      }
      if (score > 0) scored.push({ item: it, score });
    }
    scored.sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name));
    return scored.slice(0, 8).map((s) => s.item);
  }, [q, options]);

  useEffect(() => { setActive(0); }, [q]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const select = (it: MenuComboOption) => {
    onPick(it);
    setOpen(false);
  };

  return (
    <div ref={wrapRef} className="relative">
      <input
        type="text"
        placeholder={placeholder}
        value={value}
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (!open || matches.length === 0) return;
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, matches.length - 1)); }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
          else if (e.key === 'Enter') { e.preventDefault(); const it = matches[active]; if (it) select(it); }
          else if (e.key === 'Escape') { setOpen(false); }
        }}
        className={className}
      />
      {open && matches.length > 0 && (
        <div className="absolute left-0 right-0 top-full mt-1 z-20 bg-white border border-neutral-200 rounded-lg shadow-lg overflow-hidden max-h-72 overflow-y-auto">
          <div className="px-3 py-1.5 text-[10px] font-semibold text-neutral-400 uppercase tracking-wider bg-neutral-50 border-b border-neutral-100 flex items-center gap-1.5">
            <Search className="h-3 w-3" /> {matches.length} menu match{matches.length === 1 ? '' : 'es'}
          </div>
          {matches.map((it, i) => {
            const price = Number(it.unit_price ?? 0);
            const hasAllergens = Array.isArray(it.allergens) && it.allergens.length > 0;
            return (
              <button
                key={it.id}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); select(it); }}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  'w-full flex items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors border-b border-neutral-50 last:border-0',
                  i === active ? 'bg-neutral-900 text-white' : 'hover:bg-neutral-50',
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium truncate flex items-center gap-1.5">
                    {it.name}
                    {hasAllergens && (
                      <ShieldAlert className={cn('h-3 w-3 shrink-0', i === active ? 'text-amber-300' : 'text-amber-500')} />
                    )}
                  </div>
                  <div className={cn('text-[11px] truncate', i === active ? 'text-neutral-400' : 'text-neutral-400')}>
                    {it.menu_categories?.name || 'Uncategorized'}
                    {hasAllergens && <> · {(it.allergens || []).join(', ')}</>}
                  </div>
                </div>
                <span className={cn('text-sm font-semibold tabular-nums shrink-0', i === active ? 'text-white' : 'text-neutral-900')}>
                  ${price.toFixed(2)}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ContractDetailPage() {
  const params = useParams();
  const router = useRouter();
  const contractId = params?.id as string;
  const { user } = useAuthStore();

  const isStaff = STAFF_DOMAINS.some((d) => user?.email?.toLowerCase().endsWith(d));

  const [contract, setContract] = useState<Contract | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [savingPricing, setSavingPricing] = useState(false);
  const [calculatingPricing, setCalculatingPricing] = useState(false);
  const [pricingBreakdown, setPricingBreakdown] = useState<any>(null);
  const [lineItems, setLineItems] = useState<Array<{ description: string; quantity: number; unitPrice: number }>>([]);
  const [taxRate, setTaxRate] = useState(9.4);
  const [onsiteServiceRate, setOnsiteServiceRate] = useState(6.5);
  const [gratuityRate, setGratuityRate] = useState(15);
  const [discount, setDiscount] = useState(0);

  interface LineItemBreakdown {
    description: string;
    matched_menu_item_id: string | null;
    matched_name: string | null;
    dishes: Array<{ id: string; name: string; ingredients: Array<{ id: string; name: string; allergens: string[] }> }>;
    menu_item_allergens: string[];
    warnings: string[];
  }
  const [breakdowns, setBreakdowns] = useState<Record<string, LineItemBreakdown>>({});
  const [expandedLines, setExpandedLines] = useState<Record<number, boolean>>({});

  interface MenuFeedItem {
    id: string;
    name: string;
    unit_price: number | string | null;
    allergens?: string[];
    menu_categories?: { name: string } | null;
  }
  const [menuFeed, setMenuFeed] = useState<MenuFeedItem[]>([]);
  useEffect(() => {
    if (!isStaff) return;
    apiClient.get('/inventory/menu-feed')
      .then((data: any) => { if (Array.isArray(data)) setMenuFeed(data); })
      .catch(() => { /* silent — autocomplete is supplemental */ });
  }, [isStaff]);

  useEffect(() => {
    const controller = new AbortController();
    apiClient.get(`/contracts/${contractId}`, { signal: controller.signal })
      .then((data: any) => {
        setContract(data);
        const pricing = (data.body as any)?.pricing;
        if (Array.isArray(pricing?.lineItems) && pricing.lineItems.length > 0) setLineItems(pricing.lineItems);
        if (pricing?.taxRate != null) setTaxRate(Number(pricing.taxRate));
        if (pricing?.onsiteServiceRate != null) setOnsiteServiceRate(Number(pricing.onsiteServiceRate));
        if (pricing?.gratuityRate != null) setGratuityRate(Number(pricing.gratuityRate));
        if (pricing?.discount != null) setDiscount(Number(pricing.discount));
      })
      .catch((err: any) => {
        if (controller.signal.aborted) return;
        setError(err.message || 'Failed to load contract');
        toast.error('Failed to load contract');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [contractId]);

  // Resolve line items → dishes + ingredients + allergen warnings (debounced)
  useEffect(() => {
    if (!contract) return;
    const body = (contract.body as any) || {};
    const menu = body.menu || {};
    const slots = body.slots || {};
    const diets: string[] = menu.dietary_restrictions || (slots.dietary_concerns ? [slots.dietary_concerns] : []);
    const descriptions = lineItems.map((li) => li.description).filter(Boolean);
    if (descriptions.length === 0) {
      setBreakdowns({});
      return;
    }
    const t = setTimeout(() => {
      apiClient
        .post('/inventory/resolve-line-items', { descriptions, dietary_restrictions: diets })
        .then((res: any) => {
          const map: Record<string, LineItemBreakdown> = {};
          for (const b of res.items || []) map[b.description] = b;
          setBreakdowns(map);
        })
        .catch(() => {
          // silent — inventory integration is supplemental
        });
    }, 400);
    return () => clearTimeout(t);
  }, [contract, lineItems]);

  const handlePreviewPdf = async () => {
    setPreviewing(true);
    try {
      await apiClient.post(`/contracts/${contractId}/preview-pdf`, {});
      const updated: any = await apiClient.get(`/contracts/${contractId}`);
      setContract(updated);
      window.open(`/api/contracts/${contractId}/pdf`, '_blank');
    } catch (err: any) {
      toast.error(err.message || 'Failed to generate preview PDF');
    } finally {
      setPreviewing(false);
    }
  };

  const handleApprove = async () => {
    setApproving(true);
    try {
      await apiClient.post(`/staff/contracts/${contractId}/approve`, {
        message: 'Approved by staff',
      });
      toast.success('Contract approved and sent to client for signature');
      setContract((prev) => prev ? { ...prev, status: 'sent' } : prev);
    } catch (err: any) {
      toast.error(err.message || 'Failed to approve contract');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      toast.error('Please enter a rejection reason');
      return;
    }
    setRejecting(true);
    try {
      await apiClient.post(`/staff/contracts/${contractId}/reject`, {
        reason: rejectReason.trim(),
      });
      toast.success('Contract rejected');
      setContract((prev) => prev ? { ...prev, status: 'rejected' } : prev);
      setShowRejectModal(false);
    } catch (err: any) {
      toast.error(err.message || 'Failed to reject contract');
    } finally {
      setRejecting(false);
    }
  };

  const pricingTotal        = lineItems.reduce((s, i) => s + i.quantity * i.unitPrice, 0);
  const pricingTaxableBase  = Math.max(pricingTotal - discount, 0);
  const pricingTax          = Math.round(pricingTaxableBase * (taxRate / 100) * 100) / 100;
  const pricingOnsiteSvc    = Math.round(pricingTaxableBase * (onsiteServiceRate / 100) * 100) / 100;
  const pricingGratuity     = Math.round(pricingTaxableBase * (gratuityRate / 100) * 100) / 100;
  const pricingGrandTotal   = Math.max(pricingTaxableBase + pricingTax + pricingOnsiteSvc + pricingGratuity, 0);
  const pricingDeposit      = Math.round(pricingGrandTotal * 0.50 * 100) / 100;
  const pricingBalance      = Math.round((pricingGrandTotal - pricingDeposit) * 100) / 100;

  const STAFFING_KEYWORDS = ['Table & Chair Setup', 'Table Preset', 'Reception Cleanup', 'Trash Removal', 'China Service Staffing', 'On-site Service & Labor'];
  const TRAVEL_KEYWORDS = ['Travel Fee', 'Travel'];
  const isStaffingRow = (desc: string) => STAFFING_KEYWORDS.some((kw) => desc.includes(kw));
  const isTravelRow = (desc: string) => TRAVEL_KEYWORDS.some((kw) => desc.toLowerCase().includes(kw.toLowerCase()));
  const lineCategory = (desc: string): 'staffing' | 'travel' | 'food' => {
    if (isTravelRow(desc)) return 'travel';
    if (isStaffingRow(desc)) return 'staffing';
    return 'food';
  };
  const foodSubtotal = lineItems.filter(li => lineCategory(li.description) === 'food').reduce((s, i) => s + i.quantity * i.unitPrice, 0);
  const staffSubtotal = lineItems.filter(li => lineCategory(li.description) === 'staffing').reduce((s, i) => s + i.quantity * i.unitPrice, 0);
  const travelSubtotal = lineItems.filter(li => lineCategory(li.description) === 'travel').reduce((s, i) => s + i.quantity * i.unitPrice, 0);
  const fmt = (n: number) => n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const handleAutoCalculate = async () => {
    setCalculatingPricing(true);
    try {
      const result: any = await apiClient.post(`/staff/contracts/${contractId}/calculate-pricing`, {});
      setPricingBreakdown(result);
      if (Array.isArray(result.lineItems) && result.lineItems.length > 0) {
        const menuItems = result.lineItems.map((li: any) => ({
          description: li.description,
          quantity: li.quantity,
          unitPrice: li.unitPrice,
        }));
        if (result.serviceSurcharge > 0) {
          menuItems.push({ description: 'On-site Service & Labor', quantity: 1, unitPrice: result.serviceSurcharge });
        }
        // Preserve existing staffing rows — only replace menu/package rows
        const existingStaffing = lineItems.filter((li) => isStaffingRow(li.description));
        setLineItems([...menuItems, ...existingStaffing]);
        toast.success(`Calculated: $${Number(result.grandTotal).toLocaleString()} total — review and save`);
      } else {
        toast.info('No menu items matched in pricing database. Add items manually.');
      }
    } catch (err: any) {
      toast.error(err.message || 'Failed to calculate pricing');
    } finally {
      setCalculatingPricing(false);
    }
  };

  const handleSavePricing = async () => {
    setSavingPricing(true);
    try {
      const grandTotal = pricingGrandTotal;
      await apiClient.patch(`/staff/contracts/${contractId}/pricing`, {
        pricing: { lineItems, subtotal: pricingTotal, total: grandTotal, taxRate, onsiteServiceRate, gratuityRate, discount },
      });
      toast.success('Pricing saved');
      const updated: any = await apiClient.get(`/contracts/${contractId}`);
      setContract(updated);
    } catch (err: any) {
      toast.error(err.message || 'Failed to save pricing');
    } finally {
      setSavingPricing(false);
    }
  };

  const handlePrefillStaffing = () => {
    const body   = contract?.body || {};
    const slots  = body.slots || {};
    const evDet  = body.event_details || {};
    const guests = Number(evDet.guest_count || slots.guest_count || contract?.projects_contracts_project_idToprojects?.guest_count || 0);
    const svcType = (evDet.service_type || slots.service_type || '').toLowerCase();
    const isOnsite = svcType.includes('on') || svcType.includes('onsite');
    const hasChina = (slots.utensils || '').toLowerCase().includes('china') ||
                     (evDet.serviceware || '').toLowerCase().includes('china');

    if (!guests) { toast.error('No guest count on contract — cannot pre-fill staffing'); return; }

    const items: { description: string; quantity: number; unitPrice: number }[] = [];

    if (isOnsite) {
      items.push({ description: 'Table & Chair Setup (tables, chairs, linens) — $2.00/pp', quantity: guests, unitPrice: 2.00 });
      items.push({ description: 'Table Preset (plates, napkins, cutlery) — $1.75/pp',       quantity: guests, unitPrice: 1.75 });
      items.push({ description: 'Reception Cleanup — $3.75/pp',                              quantity: guests, unitPrice: 3.75 });
      items.push({ description: 'Trash Removal (flat)',                                       quantity: 1,      unitPrice: 175  });

      if (hasChina) {
        const chinaStaffing =
          guests <= 50  ? 175 :
          guests <= 75  ? 250 :
          guests <= 100 ? 325 :
          guests <= 125 ? 425 : 550;
        items.push({ description: `China Service Staffing (~${guests} guests)`, quantity: 1, unitPrice: chinaStaffing });
        // China bumps gratuity to 18%
        setGratuityRate(18);
      }
    } else {
      // Drop-off: minimal staffing
      items.push({ description: 'Trash Removal (flat)', quantity: 1, unitPrice: 175 });
    }

    // Travel placeholder — staff fills in actual distance bucket
    items.push({ description: 'Travel Fee (confirm distance: $150 / $250 / $375+)', quantity: 1, unitPrice: 0 });

    // Merge: keep any existing line items, append staffing ones (avoid duplicates by description prefix)
    const existing = lineItems.filter(
      (li) => !items.some((s) => li.description.startsWith(s.description.split('—')[0].trim()))
    );
    setLineItems([...existing, ...items]);
    toast.success(`${items.length} staffing line items added — review and adjust as needed`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-3" />
          <p className="text-gray-500 text-sm">Loading contract...</p>
        </div>
      </div>
    );
  }

  if (error || !contract) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center max-w-md">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-4">
            <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-2" />
            <p className="text-red-700 font-medium">Contract not found</p>
            <p className="text-red-500 text-sm mt-1">{error}</p>
          </div>
          <button
            onClick={() => router.push('/contracts')}
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            ← Back to Contracts
          </button>
        </div>
      </div>
    );
  }

  const project = contract.projects_contracts_project_idToprojects;
  const statusCfg = STATUS_CONFIG[contract.status] ?? STATUS_CONFIG.draft;
  const StatusIcon = statusCfg.icon;
  const body = contract.body || {};

  const clientInfo = body.client_info || {};
  const eventDetails = body.event_details || {};
  const menu = body.menu || {};
  const slots = body.slots || {};
  const summary = body.summary || body.contract_text || null;

  const clientName = clientInfo.name || slots.name || project?.title || '—';
  const eventType = eventDetails.type || slots.event_type || '—';
  const eventDate = eventDetails.date || slots.event_date
    || (project?.event_date ? new Date(project.event_date).toLocaleDateString() : null);
  const guestCount = eventDetails.guest_count || slots.guest_count || project?.guest_count;
  const serviceType = eventDetails.service_type || slots.service_type;
  const venueName = eventDetails.venue?.name || slots.venue || project?.venues?.name;
  const venueAddress = eventDetails.venue?.address || project?.venues?.address;
  const parseCommaSep = (v: any): string[] => {
    if (!v || v === 'none' || v === 'no') return [];
    if (Array.isArray(v)) return v.filter(Boolean);
    return String(v).split(',').map((s: string) => s.trim()).filter(Boolean);
  };
  const appetizers: string[] = menu.appetizers?.length
    ? menu.appetizers.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
    : parseCommaSep(slots.appetizers);
  const mainDishes: string[] = menu.main_dishes?.length
    ? menu.main_dishes.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
    : (menu.items?.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
        || parseCommaSep(slots.selected_dishes));
  const desserts: string[] = menu.desserts?.length
    ? menu.desserts.map((i: any) => (typeof i === 'string' ? i : i.name || i)).filter(Boolean)
    : parseCommaSep(slots.desserts);
  const utensils: string = slots.utensils && slots.utensils !== 'no' ? String(slots.utensils) : '';
  const rentals: string = slots.rentals && slots.rentals !== 'no' ? String(slots.rentals) : '';
  const florals: string = slots.florals && slots.florals !== 'no' ? String(slots.florals) : '';
  const dietaryRestrictions: string[] = menu.dietary_restrictions || (slots.dietary_concerns ? [slots.dietary_concerns] : []);
  const addons: string[] = body.additional?.addons || [];
  const specialRequests: string[] = body.additional?.modifications || [];

  const isPending = contract.status === 'pending_staff_approval';
  const hasPricingSaved = !!(contract.total_amount && Number(contract.total_amount) > 0);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Reject modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-neutral-900">Reject Contract</h2>
              <button onClick={() => setShowRejectModal(false)} className="text-neutral-400 hover:text-neutral-700">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-neutral-500 mb-3">Provide a reason so the client understands what needs to change.</p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Menu details are incomplete, guest count needs confirmation..."
              rows={4}
              className="w-full border border-neutral-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black resize-none"
            />
            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowRejectModal(false)} className="flex-1 px-4 py-2 border border-neutral-200 text-neutral-700 rounded-xl hover:bg-neutral-50 text-sm">Cancel</button>
              <button
                onClick={handleReject}
                disabled={rejecting || !rejectReason.trim()}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-xl hover:bg-red-700 disabled:opacity-50 text-sm flex items-center justify-center gap-2"
              >
                {rejecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsDown className="h-4 w-4" />}
                Reject
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-6xl mx-auto px-3 sm:px-6 py-5">
          <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm text-neutral-400 hover:text-neutral-900 mb-4 transition-colors">
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-neutral-900">{contract.title || `Contract v${contract.version_number}`}</h1>
              {project && (
                <button onClick={() => router.push(`/projects/${project.id}`)} className="text-sm text-neutral-500 hover:text-black mt-0.5 transition-colors">
                  {project.title}
                </button>
              )}
            </div>
            <span className={cn('inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border self-start', statusCfg.style)}>
              <StatusIcon className="h-4 w-4" />
              {statusCfg.label}
            </span>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-3 sm:px-6 py-6">

        {/* Staff Quote Builder — industry-standard invoice-style calculator */}
        {isStaff && isPending && (() => {
          const allWarnings = new Set<string>();
          for (const b of Object.values(breakdowns)) for (const w of b.warnings) allWarnings.add(w);

          const groups: Array<{ key: 'food' | 'staffing' | 'travel'; label: string; hint: string }> = [
            { key: 'food',     label: 'Food & Beverage',    hint: 'Menu items, packages, drinks' },
            { key: 'staffing', label: 'Staffing & Service', hint: 'Setup, labor, cleanup' },
            { key: 'travel',   label: 'Travel',             hint: 'Distance-based travel fees' },
          ];
          const indexedItems = lineItems.map((li, i) => ({ ...li, idx: i, cat: lineCategory(li.description) }));
          const firstVisibleGroupKey = groups.find((g) => indexedItems.some((it) => it.cat === g.key))?.key;
          const addToGroup = (cat: 'food' | 'staffing' | 'travel') => {
            const seed = cat === 'travel' ? 'Travel Fee ' : cat === 'staffing' ? 'Service ' : '';
            setLineItems((prev) => [...prev, { description: seed, quantity: 1, unitPrice: 0 }]);
          };

          return (
            <section className="mb-6">
              {/* Action bar */}
              <div className="bg-white border border-neutral-200 rounded-2xl mb-4 px-5 py-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 tc-shadow-soft">
                <div className="flex items-center gap-4 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-neutral-900 flex items-center justify-center shrink-0 shadow-[inset_0_1px_0_rgba(255,255,255,0.15)]">
                    <Calculator className="h-5 w-5 text-white" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <h2 className="text-base font-semibold text-neutral-900">Quote Builder</h2>
                      <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 text-[10px] font-bold uppercase tracking-wider">Draft</span>
                    </div>
                    <p className="text-xs text-neutral-500 mt-0.5 truncate tabular-nums">
                      {clientName !== '—' && <>{clientName} · </>}
                      {eventDate && <>{eventDate} · </>}
                      {guestCount && <>{guestCount} guests · </>}
                      v{contract.version_number}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => setShowRejectModal(true)}
                    className="flex items-center gap-2 px-3.5 py-2 border border-neutral-200 text-neutral-700 rounded-lg hover:bg-red-50 hover:border-red-200 hover:text-red-700 text-sm font-medium transition-colors">
                    <ThumbsDown className="h-3.5 w-3.5" /> Request Changes
                  </button>
                  <button onClick={handlePreviewPdf} disabled={previewing}
                    className="flex items-center gap-2 px-3.5 py-2 bg-neutral-100 text-neutral-700 rounded-lg hover:bg-neutral-200 disabled:opacity-50 text-sm font-medium transition-colors">
                    {previewing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                    {previewing ? 'Generating…' : contract.pdf_path ? 'Regenerate PDF' : 'Preview PDF'}
                  </button>
                  <button onClick={handleApprove} disabled={approving || !hasPricingSaved} title={!hasPricingSaved ? 'Save pricing first' : undefined}
                    className="tc-btn-glossy flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold">
                    {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ThumbsUp className="h-3.5 w-3.5" />}
                    Approve & Send
                  </button>
                </div>
              </div>

              {/* Banners */}
              {!hasPricingSaved && lineItems.length > 0 && (
                <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-2.5 flex items-center gap-2 text-sm text-amber-900">
                  <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
                  Unsaved changes — save the quote before approving.
                </div>
              )}
              {allWarnings.size > 0 && dietaryRestrictions.length > 0 && (
                <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 flex items-start gap-3">
                  <ShieldAlert className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
                  <div className="text-sm min-w-0">
                    <div className="font-semibold text-red-900">Allergen conflict detected</div>
                    <div className="text-red-800 mt-1">
                      Guest restrictions: <span className="font-medium">{dietaryRestrictions.join(', ')}</span>
                    </div>
                    <div className="text-red-700 mt-1 flex flex-wrap items-center gap-1">
                      Flagged:
                      {Array.from(allWarnings).map((w) => (
                        <span key={w} className="px-1.5 py-0.5 rounded bg-red-100 text-red-800 text-xs font-medium">{w}</span>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Invoice two-column layout */}
              <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-5">
                {/* LEFT: grouped line items + rate controls */}
                <div className="space-y-4">
                  {/* Line-item groups */}
                  <div className="bg-white border border-neutral-200 rounded-2xl overflow-hidden tc-shadow-soft">
                    {/* Toolbar */}
                    <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-100">
                      <div>
                        <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">Line Items</p>
                        <p className="text-xs text-neutral-400 mt-0.5">{lineItems.length} {lineItems.length === 1 ? 'item' : 'items'} · ${fmt(pricingTotal)} subtotal</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={handlePrefillStaffing}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-neutral-700 border border-neutral-200 rounded-md hover:bg-neutral-50 text-xs font-semibold transition-colors">
                          <Users className="h-3.5 w-3.5" /> Add Staffing
                        </button>
                        <button onClick={handleAutoCalculate} disabled={calculatingPricing}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-900 text-white rounded-md hover:bg-black disabled:opacity-50 text-xs font-semibold transition-colors">
                          {calculatingPricing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Calculator className="h-3.5 w-3.5" />}
                          Auto-Price
                        </button>
                      </div>
                    </div>

                    {lineItems.length === 0 ? (
                      <div className="px-4 py-16 text-center">
                        <div className="w-12 h-12 mx-auto mb-3 rounded-2xl bg-neutral-100 flex items-center justify-center">
                          <Calculator className="h-5 w-5 text-neutral-400" />
                        </div>
                        <p className="text-sm font-medium text-neutral-700">No line items yet</p>
                        <p className="text-xs text-neutral-400 mt-1">Click <span className="font-semibold text-neutral-600">Auto-Price</span> to pull from the menu, or add manually.</p>
                      </div>
                    ) : (
                      groups.map((group, gi) => {
                        const items = indexedItems.filter((it) => it.cat === group.key);
                        if (items.length === 0) return null;
                        const groupSubtotal = items.reduce((s, it) => s + it.quantity * it.unitPrice, 0);
                        return (
                          <div key={group.key} className={cn('group', gi > 0 && 'border-t border-neutral-100')}>
                            {/* Group header */}
                            <div className="px-4 py-2 bg-neutral-50 flex items-center justify-between">
                              <div className="flex items-baseline gap-2">
                                <span className="text-[11px] font-bold text-neutral-700 uppercase tracking-wider">{group.label}</span>
                                <span className="text-[11px] text-neutral-400">{group.hint}</span>
                              </div>
                              <span className="text-xs font-semibold text-neutral-700 tabular-nums">${fmt(groupSubtotal)}</span>
                            </div>

                            {/* Column headers (only on first visible group) */}
                            {group.key === firstVisibleGroupKey && (
                              <div className="grid grid-cols-[1fr_80px_110px_110px_28px] gap-2 px-4 py-2 border-b border-neutral-100 text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
                                <span>Description</span>
                                <span className="text-right">Qty</span>
                                <span className="text-right">Rate</span>
                                <span className="text-right">Amount</span>
                                <span></span>
                              </div>
                            )}

                            {/* Rows */}
                            <div className="divide-y divide-neutral-50">
                              {items.map((item) => {
                                const idx = item.idx;
                                const lineTotal = item.quantity * item.unitPrice;
                                const breakdown = breakdowns[item.description];
                                const hasBreakdown = !!breakdown && (breakdown.dishes.length > 0 || breakdown.warnings.length > 0);
                                const expanded = !!expandedLines[idx];
                                return (
                                  <div key={idx} className="group/row">
                                    <div className="grid grid-cols-[1fr_80px_110px_110px_28px] gap-2 px-4 py-2 items-center hover:bg-neutral-50/60 transition-colors">
                                      {item.cat === 'food' ? (
                                        <MenuItemCombobox
                                          value={item.description}
                                          onChange={(v) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, description: v } : li))}
                                          onPick={(picked) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, description: picked.name, unitPrice: Number(picked.unit_price ?? 0) } : li))}
                                          options={menuFeed}
                                          placeholder="Search menu…"
                                          className="w-full border border-transparent focus:border-neutral-300 rounded-md px-2 py-1.5 text-sm bg-transparent focus:bg-white focus:outline-none focus:ring-1 focus:ring-neutral-900"
                                        />
                                      ) : (
                                        <input type="text" placeholder="Description…" value={item.description}
                                          onChange={(e) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, description: e.target.value } : li))}
                                          className="border border-transparent focus:border-neutral-300 rounded-md px-2 py-1.5 text-sm bg-transparent focus:bg-white focus:outline-none focus:ring-1 focus:ring-neutral-900" />
                                      )}
                                      <input type="number" placeholder="0" min={1} value={item.quantity}
                                        onChange={(e) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, quantity: Number(e.target.value) || 1 } : li))}
                                        className="border border-transparent focus:border-neutral-300 rounded-md px-2 py-1.5 text-sm bg-transparent focus:bg-white focus:outline-none focus:ring-1 focus:ring-neutral-900 text-right tabular-nums" />
                                      <div className="relative">
                                        <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-neutral-400 pointer-events-none">$</span>
                                        <input type="number" placeholder="0.00" min={0} step="0.01" value={item.unitPrice}
                                          onChange={(e) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, unitPrice: Number(e.target.value) || 0 } : li))}
                                          className="w-full border border-transparent focus:border-neutral-300 rounded-md pl-5 pr-2 py-1.5 text-sm bg-transparent focus:bg-white focus:outline-none focus:ring-1 focus:ring-neutral-900 text-right tabular-nums" />
                                      </div>
                                      <span className="text-sm font-semibold text-neutral-900 text-right tabular-nums">${fmt(lineTotal)}</span>
                                      <button onClick={() => setLineItems((prev) => prev.filter((_, i) => i !== idx))}
                                        title="Remove" className="text-neutral-300 hover:text-red-500 transition-colors opacity-0 group-hover/row:opacity-100">
                                        <Trash2 className="h-3.5 w-3.5" />
                                      </button>
                                    </div>
                                    {hasBreakdown && (
                                      <div className="px-4 pb-2 -mt-0.5">
                                        <button type="button"
                                          onClick={() => setExpandedLines((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                                          className="flex items-center gap-1 text-[11px] text-neutral-500 hover:text-neutral-900">
                                          {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                                          {breakdown.matched_name
                                            ? `${breakdown.matched_name} — ${breakdown.dishes.length} dish${breakdown.dishes.length === 1 ? '' : 'es'}`
                                            : 'No menu match'}
                                          {breakdown.warnings.length > 0 && (
                                            <span className="ml-1.5 inline-flex items-center gap-0.5 px-1 py-0.5 rounded bg-red-100 text-red-700 text-[9px] font-bold uppercase">
                                              <ShieldAlert className="h-2.5 w-2.5" />
                                              {breakdown.warnings.length}
                                            </span>
                                          )}
                                        </button>
                                        {expanded && (
                                          <div className="mt-1.5 ml-4 space-y-1.5">
                                            {breakdown.warnings.length > 0 && (
                                              <div className="text-[11px] text-red-700 flex flex-wrap items-center gap-1">
                                                Contains:
                                                {breakdown.warnings.map((w) => (
                                                  <span key={w} className="px-1.5 py-0.5 rounded bg-red-100 text-red-800 font-medium">⚠ {w}</span>
                                                ))}
                                              </div>
                                            )}
                                            {breakdown.dishes.length > 0 && (
                                              <ul className="space-y-1">
                                                {breakdown.dishes.map((dish) => (
                                                  <li key={dish.id} className="text-[11px]">
                                                    <div className="font-medium text-neutral-700">{dish.name}</div>
                                                    {dish.ingredients.length > 0 && (
                                                      <div className="mt-0.5 flex flex-wrap gap-1">
                                                        {dish.ingredients.map((ing) => (
                                                          <span key={ing.id}
                                                            className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px]',
                                                              ing.allergens.length > 0 ? 'bg-amber-50 text-amber-800' : 'bg-emerald-50 text-emerald-700')}>
                                                            <Leaf className="h-2 w-2" />
                                                            {ing.name}
                                                            {ing.allergens.length > 0 && <span className="opacity-70"> · {ing.allergens.join(', ')}</span>}
                                                          </span>
                                                        ))}
                                                      </div>
                                                    )}
                                                  </li>
                                                ))}
                                              </ul>
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>

                            {/* Add row to group */}
                            <button onClick={() => addToGroup(group.key)}
                              className="w-full flex items-center justify-center gap-1.5 px-4 py-2 text-xs text-neutral-400 hover:text-neutral-900 hover:bg-neutral-50 font-medium transition-colors">
                              <Plus className="h-3.5 w-3.5" /> Add {group.label.toLowerCase()} line
                            </button>
                          </div>
                        );
                      })
                    )}

                    {/* Global add row (for items that don't fit categories yet) */}
                    {lineItems.length > 0 && indexedItems.every(it => it.cat === 'food') && (
                      <button onClick={() => setLineItems(prev => [...prev, { description: '', quantity: 1, unitPrice: 0 }])}
                        className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 text-sm text-neutral-600 hover:text-black hover:bg-neutral-50 font-semibold transition-colors border-t border-neutral-100">
                        <Plus className="h-4 w-4" /> Add Line Item
                      </button>
                    )}
                  </div>

                  {/* Rates & adjustments */}
                  <div className="bg-white border border-neutral-200 rounded-2xl p-4 tc-shadow-soft">
                    <p className="text-[11px] font-semibold text-neutral-500 uppercase tracking-wider mb-3">Tax, Fees & Discount</p>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {[
                        { label: 'Sales Tax',   hint: 'Applied after discount', value: taxRate,           setter: setTaxRate,           step: 0.1, suffix: '%' },
                        { label: 'Onsite Fee',  hint: 'Service & setup',        value: onsiteServiceRate, setter: setOnsiteServiceRate, step: 0.5, suffix: '%' },
                        { label: 'Gratuity',    hint: 'Service staff tip',      value: gratuityRate,      setter: setGratuityRate,      step: 0.5, suffix: '%' },
                        { label: 'Discount',    hint: 'Flat amount off',        value: discount,          setter: setDiscount,          step: 25,  prefix: '$' },
                      ].map(({ label, hint, value, setter, step, suffix, prefix }) => (
                        <div key={label}>
                          <label className="block text-xs font-semibold text-neutral-700 mb-1">{label}</label>
                          <div className="relative">
                            {prefix && <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-neutral-400 pointer-events-none">{prefix}</span>}
                            <input type="number" min={0} max={label === 'Discount' ? 999999 : 50} step={step} value={value}
                              onChange={(e) => setter(Number(e.target.value) || 0)}
                              className={cn('w-full border border-neutral-200 rounded-lg py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-neutral-900 tabular-nums',
                                prefix ? 'pl-6 pr-2' : 'pl-3 pr-7')} />
                            {suffix && <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-sm text-neutral-400 font-medium pointer-events-none">{suffix}</span>}
                          </div>
                          <p className="text-[10px] text-neutral-400 mt-1">{hint}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* RIGHT: sticky summary panel */}
                <aside className="lg:sticky lg:top-4 h-max">
                  <div className="bg-white border border-neutral-200 rounded-2xl overflow-hidden tc-shadow-soft">
                    {/* Header */}
                    <div className="px-5 py-4 bg-gradient-to-br from-neutral-900 to-neutral-800 text-white">
                      <p className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">Invoice Summary</p>
                      <p className="text-2xl font-bold tabular-nums mt-1">${fmt(pricingGrandTotal)}</p>
                      {guestCount && Number(guestCount) > 0 && pricingGrandTotal > 0 ? (
                        <p className="text-xs text-neutral-400 tabular-nums mt-0.5">${fmt(pricingGrandTotal / Number(guestCount))} per guest</p>
                      ) : null}
                    </div>

                    {/* Breakdown */}
                    <div className="px-5 py-4 space-y-1.5 text-sm tabular-nums">
                      {foodSubtotal > 0 && (
                        <div className="flex justify-between text-neutral-600">
                          <span>Food & Beverage</span>
                          <span>${fmt(foodSubtotal)}</span>
                        </div>
                      )}
                      {staffSubtotal > 0 && (
                        <div className="flex justify-between text-neutral-600">
                          <span>Staffing & Service</span>
                          <span>${fmt(staffSubtotal)}</span>
                        </div>
                      )}
                      {travelSubtotal > 0 && (
                        <div className="flex justify-between text-neutral-600">
                          <span>Travel</span>
                          <span>${fmt(travelSubtotal)}</span>
                        </div>
                      )}

                      <div className="h-px bg-neutral-100 my-2" />

                      <div className="flex justify-between text-neutral-900 font-semibold">
                        <span>Subtotal</span>
                        <span>${fmt(pricingTotal)}</span>
                      </div>
                      {discount > 0 && (
                        <div className="flex justify-between text-emerald-700">
                          <span>Discount</span>
                          <span>−${fmt(discount)}</span>
                        </div>
                      )}
                      <div className="flex justify-between text-neutral-500 text-xs">
                        <span>Sales Tax ({taxRate}%)</span>
                        <span>${fmt(pricingTax)}</span>
                      </div>
                      <div className="flex justify-between text-neutral-500 text-xs">
                        <span>Onsite Fee ({onsiteServiceRate}%)</span>
                        <span>${fmt(pricingOnsiteSvc)}</span>
                      </div>
                      <div className="flex justify-between text-neutral-500 text-xs">
                        <span>Gratuity ({gratuityRate}%)</span>
                        <span>${fmt(pricingGratuity)}</span>
                      </div>

                      <div className="h-px bg-neutral-200 my-2" />

                      <div className="flex justify-between items-baseline">
                        <span className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider">Grand Total</span>
                        <span className="text-lg font-bold text-neutral-900">${fmt(pricingGrandTotal)}</span>
                      </div>
                    </div>

                    {/* Payment schedule */}
                    {pricingGrandTotal > 0 && (
                      <div className="mx-5 mb-4 p-3 rounded-xl bg-neutral-50 border border-neutral-100 space-y-1.5 text-xs tabular-nums">
                        <p className="text-[10px] font-bold text-neutral-500 uppercase tracking-wider mb-1.5">Payment Schedule</p>
                        <div className="flex justify-between">
                          <span className="text-neutral-600">Deposit <span className="text-neutral-400">(50% at signing)</span></span>
                          <span className="font-semibold text-neutral-900">${fmt(pricingDeposit)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-neutral-600">Balance <span className="text-neutral-400">(at event)</span></span>
                          <span className="font-semibold text-neutral-900">${fmt(pricingBalance)}</span>
                        </div>
                      </div>
                    )}

                    {/* Save */}
                    <div className="px-5 pb-5">
                      <button onClick={handleSavePricing} disabled={savingPricing || lineItems.length === 0}
                        className="tc-btn-glossy w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-semibold">
                        {savingPricing ? <Loader2 className="h-4 w-4 animate-spin" /> : <DollarSign className="h-4 w-4" />}
                        {savingPricing ? 'Saving Quote…' : hasPricingSaved ? 'Update Quote' : 'Save Quote'}
                      </button>
                    </div>
                  </div>
                </aside>
              </div>
            </section>
          );
        })()}

        {/* Bento grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 auto-rows-min">

          {/* ── Event Details ── 2 cols */}
          <BentoInfoCard className="lg:col-span-2 p-6">
            <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Event Details</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
              {eventDate && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-neutral-400 flex items-center gap-1"><Calendar className="h-3 w-3" /> Date</span>
                  <span className="text-sm font-semibold text-neutral-900">{eventDate}</span>
                </div>
              )}
              {guestCount != null && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-neutral-400 flex items-center gap-1"><Users className="h-3 w-3" /> Guests</span>
                  <span className="text-sm font-semibold text-neutral-900">{guestCount}</span>
                </div>
              )}
              {eventType !== '—' && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-neutral-400">Event Type</span>
                  <span className="text-sm font-semibold text-neutral-900 capitalize">{eventType}</span>
                </div>
              )}
              {serviceType && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-neutral-400">Service</span>
                  <span className="text-sm font-semibold text-neutral-900 capitalize">{serviceType}</span>
                </div>
              )}
              {venueName && (
                <div className="flex flex-col gap-1 sm:col-span-2">
                  <span className="text-xs text-neutral-400 flex items-center gap-1"><MapPin className="h-3 w-3" /> Venue</span>
                  <span className="text-sm font-semibold text-neutral-900">{venueName}</span>
                  {venueAddress && <span className="text-xs text-neutral-400">{venueAddress}</span>}
                </div>
              )}
            </div>
            {dietaryRestrictions.length > 0 && (
              <div className="mt-4 pt-4 border-t border-neutral-100">
                <span className="text-xs text-neutral-400">Dietary</span>
                <p className="text-sm text-neutral-700 mt-0.5">{dietaryRestrictions.join(', ')}</p>
              </div>
            )}
          </BentoInfoCard>

          {/* ── Contract Info + Client ── 1 col */}
          <div className="flex flex-col gap-4">
            {/* Contract info tile */}
            <BentoInfoCard className="p-5">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Contract Info</p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-neutral-400">Version</span><span className="font-semibold">v{contract.version_number}</span></div>
                <div className="flex justify-between"><span className="text-neutral-400">Created</span><span className="font-medium">{new Date(contract.created_at).toLocaleDateString()}</span></div>
                {/* Pricing is staff-only until the client signs. Once signed,
                    the commitment is made so the client can see the totals too. */}
                {(isStaff || contract.status === 'signed') && (
                  lineItems.length > 0 ? (
                    <>
                      <div className="flex justify-between text-xs"><span className="text-neutral-400">Subtotal</span><span className="tabular-nums">${fmt(pricingTotal)}</span></div>
                      {discount > 0 && <div className="flex justify-between text-xs"><span className="text-neutral-400">Discount</span><span className="tabular-nums text-emerald-700">−${fmt(discount)}</span></div>}
                      <div className="flex justify-between text-xs"><span className="text-neutral-400">Tax ({taxRate}%)</span><span className="tabular-nums">${fmt(pricingTax)}</span></div>
                      <div className="flex justify-between text-xs"><span className="text-neutral-400">Onsite Fee ({onsiteServiceRate}%)</span><span className="tabular-nums">${fmt(pricingOnsiteSvc)}</span></div>
                      <div className="flex justify-between text-xs"><span className="text-neutral-400">Gratuity ({gratuityRate}%)</span><span className="tabular-nums">${fmt(pricingGratuity)}</span></div>
                      <div className="flex justify-between border-t border-neutral-100 pt-2"><span className="font-semibold text-neutral-900">Grand Total</span><span className="font-bold text-neutral-900 tabular-nums">${fmt(pricingGrandTotal)}</span></div>
                      <div className="flex justify-between text-xs"><span className="text-neutral-400">Deposit</span><span className="tabular-nums">${fmt(pricingDeposit)}</span></div>
                      <div className="flex justify-between text-xs"><span className="text-neutral-400">Balance</span><span className="tabular-nums">${fmt(pricingBalance)}</span></div>
                    </>
                  ) : contract.total_amount != null ? (
                    <div className="flex justify-between border-t border-neutral-100 pt-2">
                      <span className="font-semibold text-neutral-900">Grand Total</span>
                      <span className="font-bold text-neutral-900">${Number(contract.total_amount).toLocaleString()}</span>
                    </div>
                  ) : null
                )}
                {!isStaff && contract.status !== 'signed' && (
                  <div className="flex justify-between border-t border-neutral-100 pt-2 text-xs">
                    <span className="text-neutral-400">Pricing</span>
                    <span className="text-neutral-500 italic">Available after signing</span>
                  </div>
                )}
                <div className="flex justify-between pt-1"><span className="text-neutral-400 text-xs">Contract ID</span><span className="font-mono text-xs text-neutral-400 truncate max-w-[110px]">{contract.id}</span></div>
              </div>
            </BentoInfoCard>

            {/* Client tile */}
            {(clientName !== '—' || clientInfo.email || clientInfo.phone) && (
              <BentoInfoCard className="p-5">
                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Client</p>
                <div className="space-y-1 text-sm">
                  {clientName !== '—' && <p className="font-semibold text-neutral-900">{clientName}</p>}
                  {clientInfo.email && <p className="text-neutral-500 text-xs">{clientInfo.email}</p>}
                  {clientInfo.phone && <p className="text-neutral-500 text-xs">{clientInfo.phone}</p>}
                </div>
              </BentoInfoCard>
            )}

            {/* Actions tile */}
            <BentoInfoCard className="p-5 space-y-2" enableTilt={false}>
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Actions</p>
              {isStaff && contract.pdf_path && (
                <a href={`/api/contracts/${contract.id}/pdf`} target="_blank" rel="noopener noreferrer"
                  className="tc-btn-glossy w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium">
                  <FileText className="h-4 w-4" /> View PDF
                </a>
              )}
              {project && (
                <button onClick={() => router.push(`/projects/${project.id}`)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-neutral-200 text-neutral-700 rounded-xl hover:bg-neutral-50 transition text-sm">
                  View Project
                </button>
              )}
            </BentoInfoCard>

            {/* Status notes */}
            {!isStaff && isPending && (
              <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
                <p className="text-xs font-semibold text-amber-800 mb-1">Awaiting Staff Review</p>
                <p className="text-xs text-amber-700">Our team will review and approve this contract before sending it to you for signature.</p>
              </div>
            )}
            {contract.status === 'sent' && (
              <div className="bg-purple-50 border border-purple-200 rounded-2xl p-4">
                <p className="text-xs font-semibold text-purple-800 mb-1">Sent for Signature</p>
                <p className="text-xs text-purple-700">The client has been emailed a link to sign this contract.</p>
              </div>
            )}
            {contract.status === 'signed' && (
              <div className="bg-green-50 border border-green-200 rounded-2xl p-4">
                <CheckCircle2 className="h-5 w-5 text-green-600 mb-2" />
                <p className="text-xs font-semibold text-green-800 mb-1">Contract Signed</p>
                <p className="text-xs text-green-700">This contract has been fully executed.</p>
              </div>
            )}
            {contract.status === 'rejected' && contract.metadata?.rejection_reason && (
              <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                <AlertCircle className="h-5 w-5 text-red-500 mb-2" />
                <p className="text-xs font-semibold text-red-800 mb-1">Rejected</p>
                <p className="text-xs text-red-700">{contract.metadata.rejection_reason}</p>
              </div>
            )}
          </div>

          {/* ── Menu & Services ── 2 cols */}
          {(appetizers.length > 0 || mainDishes.length > 0 || desserts.length > 0 || utensils || rentals || florals) && (
            <BentoInfoCard className="lg:col-span-2 p-6">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Menu & Services</p>
              <div className="space-y-5">
                {appetizers.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-2">Appetizers / Hors d'Oeuvres</p>
                    <div className="flex flex-wrap gap-1.5">
                      {appetizers.map((item, i) => <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{item}</span>)}
                    </div>
                  </div>
                )}
                {mainDishes.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-2">Main Dishes</p>
                    <div className="flex flex-wrap gap-1.5">
                      {mainDishes.map((item, i) => <span key={i} className="px-2.5 py-1 bg-neutral-900 text-white rounded-lg text-xs font-medium">{item}</span>)}
                    </div>
                  </div>
                )}
                {desserts.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-2">Desserts</p>
                    <div className="flex flex-wrap gap-1.5">
                      {desserts.map((item, i) => <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{item}</span>)}
                    </div>
                  </div>
                )}
                {(utensils || rentals || florals) && (
                  <div className="pt-3 border-t border-neutral-100 space-y-1 text-xs text-neutral-600">
                    {utensils && <p><span className="font-medium text-neutral-400">Utensils: </span>{utensils}</p>}
                    {rentals && <p><span className="font-medium text-neutral-400">Rentals: </span>{rentals}</p>}
                    {florals && <p><span className="font-medium text-neutral-400">Florals: </span>{florals}</p>}
                  </div>
                )}
              </div>
            </BentoInfoCard>
          )}

          {/* ── Add-ons & Requests ── 1 col */}
          {(addons.length > 0 || specialRequests.length > 0) && (
            <BentoInfoCard className="p-6">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Add-ons & Requests</p>
              {addons.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs text-neutral-400 mb-2">Add-ons</p>
                  <div className="flex flex-wrap gap-1.5">
                    {addons.map((a, i) => <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{a}</span>)}
                  </div>
                </div>
              )}
              {specialRequests.length > 0 && (
                <div>
                  <p className="text-xs text-neutral-400 mb-2">Special Requests</p>
                  <ul className="space-y-1">
                    {specialRequests.map((r, i) => <li key={i} className="text-xs text-neutral-700">{r}</li>)}
                  </ul>
                </div>
              )}
            </BentoInfoCard>
          )}

          {/* ── Contract Summary ── full width */}
          {summary && (
            <BentoInfoCard className="lg:col-span-3 p-6" enableTilt={false}>
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Contract Summary</p>
              <div className="prose prose-sm max-w-none text-neutral-700 whitespace-pre-wrap leading-relaxed text-sm">
                {summary}
              </div>
            </BentoInfoCard>
          )}

        </div>
      </div>
    </div>
  );
}

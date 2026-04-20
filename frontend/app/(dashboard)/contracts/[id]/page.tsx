"use client";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Calendar, Users, MapPin, FileText,
  Clock, CheckCircle2, AlertCircle, Loader2,
  ThumbsUp, ThumbsDown, X, Plus, Trash2, DollarSign, Calculator, Lock,
  UtensilsCrossed, AlertTriangle, PartyPopper, ConciergeBell, Download,
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

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
    style: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  },
  approved: {
    label: 'Approved — Sending to Client',
    icon: CheckCircle2,
    style: 'bg-blue-50 text-blue-800 border-blue-200',
  },
  sent: {
    label: 'Sent for Signature',
    icon: FileText,
    style: 'bg-purple-50 text-purple-800 border-purple-200',
  },
  signed: {
    label: 'Signed',
    icon: CheckCircle2,
    style: 'bg-green-50 text-green-800 border-green-200',
  },
  rejected: {
    label: 'Rejected',
    icon: AlertCircle,
    style: 'bg-red-50 text-red-800 border-red-200',
  },
  draft: {
    label: 'Draft',
    icon: FileText,
    style: 'bg-gray-50 text-gray-700 border-gray-200',
  },
};

function formatEventDate(date: string): string {
  try {
    const d = new Date(date.includes('T') ? date : date + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  } catch {
    return date;
  }
}

function dishNameToSlug(name: string): string {
  return name
    .replace(/\s*\(\$[\d.,]+\/pp\)/gi, '')
    .replace(/\s*\(\$[\d.,]+\)/gi, '')
    .replace(/&/g, 'and')
    .replace(/[^a-z0-9\s]/gi, '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-');
}

function bestImageSlug(name: string, slugList: string[]): string | null {
  if (!slugList.length) return null;
  const slug = dishNameToSlug(name);
  if (slugList.includes(slug)) return slug;

  const stem = (s: string) => s.replace(/s$/, '');
  const words = (s: string) => s.split('-').filter(w => w.length > 1).map(stem);
  const nameWords = words(slug);
  if (!nameWords.length) return null;

  let best: string | null = null;
  let bestScore = 0.25;

  for (const img of slugList) {
    const imgWords = words(img);
    const hits = nameWords.filter(w => imgWords.includes(w)).length;
    if (!hits) continue;
    const score = hits / Math.max(nameWords.length, imgWords.length);
    if (score > bestScore) { bestScore = score; best = img; }
  }

  return best;
}

function DishCard({ name, dark = false, slugList = [] }: { name: string; dark?: boolean; slugList?: string[] }) {
  const [imgFailed, setImgFailed] = useState(false);
  const matchedSlug = bestImageSlug(name, slugList);
  const hasImage = !!matchedSlug && !imgFailed;
  const displayName = name
    .replace(/\s*\(\$[\d.,]+\/pp\)/gi, '')
    .replace(/\s*\(\$[\d.,]+\)/gi, '')
    .trim();

  return (
    <div className="relative aspect-square rounded-xl overflow-hidden shadow-sm transition-transform hover:scale-[1.02] cursor-default group">
      {hasImage ? (
        <img
          src={`/menu-images/${matchedSlug}.jpg`}
          alt={displayName}
          className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <div className={cn(
          'w-full h-full flex items-center justify-center',
          dark
            ? 'bg-gradient-to-br from-neutral-600 to-neutral-800'
            : 'bg-gradient-to-br from-stone-100 to-stone-200'
        )}>
          <UtensilsCrossed className={cn('h-8 w-8', dark ? 'text-neutral-400' : 'text-neutral-300')} />
        </div>
      )}
      <div className={cn(
        'absolute inset-x-0 bottom-0 pt-6 pb-2.5 px-2.5',
        hasImage
          ? 'bg-gradient-to-t from-black/75 via-black/30 to-transparent'
          : dark ? 'bg-black/20' : 'bg-white/60'
      )}>
        <p className={cn(
          'text-xs font-semibold leading-tight',
          hasImage || dark ? 'text-white drop-shadow-sm' : 'text-neutral-700'
        )}>{displayName}</p>
      </div>
    </div>
  );
}

export default function ContractDetailPage() {
  const params = useParams();
  const router = useRouter();
  const contractId = params.id as string;
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
  const [menuImageSlugs, setMenuImageSlugs] = useState<string[]>([]);
  const [savingPricing, setSavingPricing] = useState(false);
  const [calculatingPricing, setCalculatingPricing] = useState(false);
  const [pricingBreakdown, setPricingBreakdown] = useState<any>(null);
  const [lineItems, setLineItems] = useState<Array<{ description: string; quantity: number; unitPrice: number }>>([]);
  const [taxRate, setTaxRate] = useState(9.4);
  const [onsiteServiceRate, setOnsiteServiceRate] = useState(6.5);
  const [gratuityRate, setGratuityRate] = useState(15);

  useEffect(() => {
    fetch('/api/menu-images')
      .then(r => r.json())
      .then(setMenuImageSlugs)
      .catch(() => {});
  }, []);

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
      })
      .catch((err: any) => {
        if (controller.signal.aborted) return;
        setError(err.message || 'Failed to load contract');
        toast.error('Failed to load contract');
      })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [contractId]);

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
  const pricingTax          = Math.round(pricingTotal * (taxRate / 100) * 100) / 100;
  const pricingOnsiteSvc    = Math.round(pricingTotal * (onsiteServiceRate / 100) * 100) / 100;
  const pricingGratuity     = Math.round(pricingTotal * (gratuityRate / 100) * 100) / 100;
  const pricingGrandTotal   = pricingTotal + pricingTax + pricingOnsiteSvc + pricingGratuity;
  const pricingDeposit      = Math.round(pricingGrandTotal * 0.50 * 100) / 100;

  const STAFFING_KEYWORDS = ['Table & Chair Setup', 'Table Preset', 'Reception Cleanup', 'Trash Removal', 'China Service Staffing', 'Travel Fee', 'On-site Service & Labor'];
  const isStaffingRow = (desc: string) => STAFFING_KEYWORDS.some((kw) => desc.includes(kw));

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
        pricing: { lineItems, subtotal: pricingTotal, total: grandTotal, taxRate, onsiteServiceRate, gratuityRate },
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
  const isContractVisible = ['sent', 'signed'].includes(contract.status);

  return (
    <div className="min-h-screen tc-page-bg">
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
                className="flex-1 px-4 py-2 bg-neutral-900 text-white rounded-xl hover:bg-black disabled:opacity-50 text-sm flex items-center justify-center gap-2"
              >
                {rejecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsDown className="h-4 w-4" />}
                Reject
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-6 pb-20">
        {/* Breadcrumb */}
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-900 mb-5 transition-colors">
          <ArrowLeft className="h-3 w-3" /> Back
        </button>

        {/* Hero */}
        <div className="flex items-end justify-between gap-4 pb-6 border-b border-neutral-200/60 mb-6 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-neutral-900">
              {contract.title || `Contract v${contract.version_number}`}
            </h1>
            {project && (
              <p className="text-sm text-neutral-500 mt-2">
                <span className="capitalize">{eventType !== '—' ? eventType : 'Event'}</span>
                {' · '}
                <button onClick={() => router.push(`/projects/${project.id}`)} className="font-semibold text-neutral-700 hover:text-black transition-colors">
                  {project.title}
                </button>
              </p>
            )}
          </div>
          {contract.status === 'pending_staff_approval' ? (
            <span className="inline-flex items-center gap-2.5 pl-3.5 pr-4 py-2 rounded-full bg-neutral-900 text-white text-xs font-semibold shadow-[0_4px_14px_rgba(0,0,0,0.18)]">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full rounded-full bg-white opacity-50 animate-ping" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-white" />
              </span>
              {statusCfg.label}
            </span>
          ) : (
            <span className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold',
              contract.status === 'signed' ? 'bg-neutral-900 text-white' :
              contract.status === 'rejected' ? 'bg-neutral-100 text-neutral-700 border border-neutral-200' :
              'bg-neutral-100 text-neutral-700 border border-neutral-200'
            )}>
              <StatusIcon className="h-3.5 w-3.5" />
              {statusCfg.label}
            </span>
          )}
        </div>

        {/* Quick summary strip — 4 monochrome tiles */}
        {(eventDate || guestCount != null || eventType !== '—' || serviceType) && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
            {eventDate && (
              <div className="group relative overflow-hidden bg-white border border-neutral-200/70 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5">
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400">Date</span>
                  <div className="w-8 h-8 rounded-lg bg-neutral-900 text-white grid place-items-center">
                    <Calendar className="h-3.5 w-3.5" />
                  </div>
                </div>
                <p className="text-base font-extrabold text-neutral-900 leading-tight">{formatEventDate(eventDate)}</p>
              </div>
            )}
            {guestCount != null && (
              <div className="group relative overflow-hidden bg-white border border-neutral-200/70 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5">
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400">Guests</span>
                  <div className="w-8 h-8 rounded-lg bg-neutral-900 text-white grid place-items-center">
                    <Users className="h-3.5 w-3.5" />
                  </div>
                </div>
                <p className="text-base font-extrabold text-neutral-900 leading-tight">
                  {guestCount}
                  <span className="block text-[11px] font-medium text-neutral-500 mt-0.5">Attendees</span>
                </p>
              </div>
            )}
            {eventType !== '—' && (
              <div className="group relative overflow-hidden bg-white border border-neutral-200/70 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5">
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400">Type</span>
                  <div className="w-8 h-8 rounded-lg bg-neutral-900 text-white grid place-items-center">
                    <PartyPopper className="h-3.5 w-3.5" />
                  </div>
                </div>
                <p className="text-base font-extrabold text-neutral-900 leading-tight capitalize">{eventType}</p>
              </div>
            )}
            {serviceType && (
              <div className="group relative overflow-hidden bg-white border border-neutral-200/70 rounded-2xl p-4 shadow-sm hover:shadow-md transition-all hover:-translate-y-0.5">
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400">Service</span>
                  <div className="w-8 h-8 rounded-lg bg-neutral-900 text-white grid place-items-center">
                    <ConciergeBell className="h-3.5 w-3.5" />
                  </div>
                </div>
                <p className="text-base font-extrabold text-neutral-900 leading-tight capitalize">{serviceType}</p>
              </div>
            )}
          </div>
        )}

        {/* Staff review panel — full width */}
        {isStaff && isPending && (
          <div className="bg-white border border-neutral-200 rounded-2xl mb-4 overflow-hidden">
            {/* Panel header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-100">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-black animate-pulse" />
                <div>
                  <p className="text-sm font-semibold text-neutral-900">Staff Review Required</p>
                  <p className="text-xs text-neutral-400 mt-0.5">Set pricing, preview the PDF, then approve or reject.</p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button onClick={handlePreviewPdf} disabled={previewing}
                  className="flex items-center gap-1.5 px-3 py-2 bg-neutral-100 text-neutral-700 rounded-xl hover:bg-neutral-200 disabled:opacity-50 text-xs font-medium transition-colors">
                  {previewing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                  {previewing ? 'Generating…' : contract.pdf_path ? 'Regenerate PDF' : 'Preview PDF'}
                </button>
                <button onClick={handleApprove} disabled={approving || !hasPricingSaved} title={!hasPricingSaved ? 'Save pricing first' : undefined}
                  className="flex items-center gap-1.5 px-4 py-2 bg-black text-white rounded-xl hover:bg-neutral-800 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-semibold transition-colors">
                  {approving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ThumbsUp className="h-3.5 w-3.5" />}
                  Approve & Send
                </button>
                <button onClick={() => setShowRejectModal(true)}
                  className="flex items-center gap-1.5 px-4 py-2 border border-neutral-200 text-neutral-700 rounded-xl hover:bg-neutral-50 text-xs font-semibold transition-colors">
                  <ThumbsDown className="h-3.5 w-3.5" /> Reject
                </button>
              </div>
            </div>

            {/* Pricing editor */}
            <div className="px-6 py-5">
              {!hasPricingSaved && (
                <p className="text-xs text-neutral-500 font-medium mb-4 flex items-center gap-1.5">
                  <AlertCircle className="h-3.5 w-3.5 text-neutral-400" /> Save pricing below before approving.
                </p>
              )}

              {/* Toolbar */}
              <div className="flex items-center justify-between mb-4">
                <p className="text-xs font-semibold text-neutral-700 flex items-center gap-1.5">
                  <DollarSign className="h-3.5 w-3.5 text-neutral-400" /> Line Items
                </p>
                <div className="flex items-center gap-1.5">
                  <button onClick={handlePrefillStaffing}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 bg-neutral-100 text-neutral-700 border border-neutral-200 rounded-lg hover:bg-neutral-200 text-xs font-medium transition-colors">
                    <Users className="h-3 w-3" /> Pre-fill Staffing
                  </button>
                  <button onClick={handleAutoCalculate} disabled={calculatingPricing}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 bg-black text-white rounded-lg hover:bg-neutral-800 disabled:opacity-50 text-xs font-medium transition-colors">
                    {calculatingPricing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Calculator className="h-3 w-3" />}
                    {calculatingPricing ? 'Calculating…' : 'Auto-Calculate'}
                  </button>
                </div>
              </div>

              {/* Rate inputs */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                {[
                  { label: 'Sales & Meals Tax', value: taxRate, setter: setTaxRate, step: 0.1 },
                  { label: 'Onsite Service Fee', value: onsiteServiceRate, setter: setOnsiteServiceRate, step: 0.5 },
                  { label: 'Gratuity', value: gratuityRate, setter: setGratuityRate, step: 0.5 },
                ].map(({ label, value, setter, step }) => (
                  <div key={label}>
                    <label className="block text-xs text-neutral-500 font-medium mb-1">{label}</label>
                    <div className="relative">
                      <input type="number" min={0} max={50} step={step} value={value}
                        onChange={(e) => setter(Number(e.target.value) || 0)}
                        className="w-full border border-neutral-200 rounded-lg px-2 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-black pr-6" />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-neutral-400">%</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Line items table */}
              <div className="space-y-1.5 mb-4">
                {lineItems.map((item, idx) => (
                  <div key={idx} className="flex gap-2 items-center">
                    <input type="text" placeholder="Description" value={item.description}
                      onChange={(e) => setLineItems(prev => prev.map((li, i) => i === idx ? { ...li, description: e.target.value } : li))}
                      className="flex-1 border border-neutral-200 rounded-lg px-2.5 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-black" />
                    <input type="number" placeholder="Qty" min={1} value={item.quantity}
                      onChange={(e) => setLineItems(prev => prev.map((li, i) => i === idx ? { ...li, quantity: Number(e.target.value) || 1 } : li))}
                      className="w-14 border border-neutral-200 rounded-lg px-2 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-black" />
                    <input type="number" placeholder="Price" min={0} value={item.unitPrice}
                      onChange={(e) => setLineItems(prev => prev.map((li, i) => i === idx ? { ...li, unitPrice: Number(e.target.value) || 0 } : li))}
                      className="w-20 border border-neutral-200 rounded-lg px-2 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-black" />
                    <button onClick={() => setLineItems(prev => prev.filter((_, i) => i !== idx))} className="text-neutral-300 hover:text-red-500 transition-colors">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <button onClick={() => setLineItems(prev => [...prev, { description: '', quantity: 1, unitPrice: 0 }])}
                  className="flex items-center gap-1 text-xs text-neutral-500 hover:text-black font-medium transition-colors mt-1">
                  <Plus className="h-3.5 w-3.5" /> Add item
                </button>
              </div>

              {/* Pricing summary */}
              {lineItems.length > 0 && (
                <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-4 mb-4 text-xs space-y-1.5">
                  {pricingBreakdown?.packageName && (
                    <div className="flex justify-between text-neutral-500">
                      <span>Package</span>
                      <span>{pricingBreakdown.packageName} (${pricingBreakdown.packagePerPersonRate}/pp)</span>
                    </div>
                  )}
                  <div className="flex justify-between text-neutral-600">
                    <span>Subtotal</span>
                    <span>${pricingTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between text-neutral-500">
                    <span>Sales & Meals Tax ({taxRate}%)</span>
                    <span>${pricingTax.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between text-neutral-500">
                    <span>Onsite Service Fee ({onsiteServiceRate}%)</span>
                    <span>${pricingOnsiteSvc.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between text-neutral-500">
                    <span>Gratuity ({gratuityRate}%)</span>
                    <span>${pricingGratuity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between font-bold text-neutral-900 border-t border-neutral-200 pt-2">
                    <span>Grand Total</span>
                    <span>${pricingGrandTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                  <div className="flex justify-between text-neutral-400">
                    <span>50% Deposit Due</span>
                    <span>${pricingDeposit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                  </div>
                </div>
              )}

              {lineItems.length > 0 && (
                <button onClick={handleSavePricing} disabled={savingPricing}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-black text-white rounded-xl hover:bg-neutral-800 disabled:opacity-50 text-xs font-semibold transition-colors">
                  {savingPricing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <DollarSign className="h-3.5 w-3.5" />}
                  {savingPricing ? 'Saving…' : 'Save Pricing'}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-5">

          {/* ═════════ MAIN AREA ═════════ */}
          <div className="flex flex-col gap-5 min-w-0">

            {/* Event Details */}
            <div className="bg-white border border-neutral-200/70 rounded-2xl p-6 sm:p-7 shadow-sm">
              <div className="flex items-start justify-between mb-1">
                <h2 className="text-lg font-bold text-neutral-900 tracking-tight">Event Details</h2>
              </div>
              <p className="text-xs text-neutral-500 mb-6">All confirmed information for this booking</p>

              {venueName && (
                <div className="pb-5 mb-5 border-b border-neutral-200/70">
                  <p className="flex items-center gap-1.5 text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-3">
                    <MapPin className="h-3 w-3" /> Venue
                  </p>
                  <div className="flex items-start gap-3.5">
                    <div className="w-9 h-9 rounded-xl bg-neutral-50 border border-neutral-200/70 grid place-items-center text-neutral-500 shrink-0">
                      <MapPin className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-neutral-900">{venueName}</p>
                      {venueAddress && <p className="text-xs text-neutral-500 mt-0.5">{venueAddress}</p>}
                    </div>
                  </div>
                </div>
              )}

              <div>
                <p className="flex items-center gap-1.5 text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-3">
                  <AlertTriangle className="h-3 w-3" /> Dietary Concerns
                </p>
                {dietaryRestrictions.length === 0 ? (
                  <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-neutral-100 border border-neutral-200/70 text-xs font-medium text-neutral-600">
                    <span className="h-1.5 w-1.5 rounded-full bg-neutral-400" />
                    No restrictions
                  </span>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {dietaryRestrictions.map((d, i) => (
                      <span key={i} className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-neutral-900 text-white text-xs font-medium">
                        <span className="h-1.5 w-1.5 rounded-full bg-white" />
                        {d}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Menu & Services */}
            {(appetizers.length > 0 || mainDishes.length > 0 || desserts.length > 0) && (
              <div className="bg-white border border-neutral-200/70 rounded-2xl p-6 sm:p-7 shadow-sm">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-bold text-neutral-900 tracking-tight">Menu &amp; Services</h2>
                    <p className="text-xs text-neutral-500 mt-0.5">
                      {appetizers.length + mainDishes.length + desserts.length} items
                      {!isContractVisible && <span className="text-neutral-400"> · Pricing available after signing</span>}
                    </p>
                  </div>
                  <div className="w-9 h-9 rounded-xl bg-neutral-100 grid place-items-center shrink-0">
                    <UtensilsCrossed className="h-4 w-4 text-neutral-500" />
                  </div>
                </div>

                <div className="space-y-7">
                  {appetizers.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <p className="text-[11px] font-bold tracking-[0.1em] uppercase text-neutral-400">Appetizers / Hors d'Oeuvres</p>
                        <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-2 rounded-full bg-neutral-100 text-neutral-600 text-[10px] font-bold">{appetizers.length}</span>
                        <div className="flex-1 h-px bg-gradient-to-r from-neutral-200 to-transparent" />
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                        {appetizers.map((item, i) => <DishCard key={i} name={item} slugList={menuImageSlugs} />)}
                      </div>
                    </div>
                  )}
                  {mainDishes.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <p className="text-[11px] font-bold tracking-[0.1em] uppercase text-neutral-400">Main Dishes</p>
                        <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-2 rounded-full bg-neutral-100 text-neutral-600 text-[10px] font-bold">{mainDishes.length}</span>
                        <div className="flex-1 h-px bg-gradient-to-r from-neutral-200 to-transparent" />
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                        {mainDishes.map((item, i) => <DishCard key={i} name={item} slugList={menuImageSlugs} />)}
                      </div>
                    </div>
                  )}
                  {desserts.length > 0 && (
                    <div>
                      <div className="flex items-center gap-2 mb-3">
                        <p className="text-[11px] font-bold tracking-[0.1em] uppercase text-neutral-400">Desserts</p>
                        <span className="inline-flex items-center justify-center min-w-[22px] h-5 px-2 rounded-full bg-neutral-100 text-neutral-600 text-[10px] font-bold">{desserts.length}</span>
                        <div className="flex-1 h-px bg-gradient-to-r from-neutral-200 to-transparent" />
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                        {desserts.map((item, i) => <DishCard key={i} name={item} slugList={menuImageSlugs} />)}
                      </div>
                    </div>
                  )}
                </div>

                {(utensils || rentals || florals) && (
                  <div className="mt-6 pt-5 border-t border-neutral-200/70 flex flex-wrap gap-2">
                    {utensils && (
                      <span className="px-3 py-1.5 bg-neutral-50 border border-neutral-200/70 rounded-full text-xs font-medium text-neutral-700">
                        <span className="text-neutral-400">Utensils · </span>{utensils}
                      </span>
                    )}
                    {rentals && (
                      <span className="px-3 py-1.5 bg-neutral-50 border border-neutral-200/70 rounded-full text-xs font-medium text-neutral-700">
                        <span className="text-neutral-400">Rentals · </span>{rentals}
                      </span>
                    )}
                    {florals && (
                      <span className="px-3 py-1.5 bg-neutral-50 border border-neutral-200/70 rounded-full text-xs font-medium text-neutral-700">
                        <span className="text-neutral-400">Florals · </span>{florals}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Add-ons & Special Requests */}
            {(addons.length > 0 || specialRequests.length > 0) && (
              <div className="bg-white border border-neutral-200/70 rounded-2xl p-6 shadow-sm">
                <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-4">Add-ons &amp; Special Requests</p>
                {addons.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-4 last:mb-0">
                    {addons.map((a, i) => (
                      <span key={i} className="px-3.5 py-2 bg-neutral-50 border border-neutral-200/70 rounded-xl text-xs font-medium text-neutral-700">{a}</span>
                    ))}
                  </div>
                )}
                {specialRequests.length > 0 && (
                  <div className="bg-neutral-50 border-l-2 border-neutral-900 rounded-r-xl px-4 py-3">
                    <p className="text-[10px] font-bold tracking-[0.1em] uppercase text-neutral-500 mb-2">Special Requests</p>
                    <ul className="space-y-1.5">
                      {specialRequests.map((r, i) => (
                        <li key={i} className="text-xs text-neutral-700 flex items-start gap-2">
                          <span className="text-neutral-400 mt-0.5">—</span>{r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Contract Summary */}
            {summary && (
              <div className="bg-white border border-neutral-200/70 rounded-2xl overflow-hidden relative shadow-sm">
                <span aria-hidden className="pointer-events-none select-none absolute -top-4 left-6 text-[160px] font-serif leading-none text-neutral-100">&ldquo;</span>
                <span aria-hidden className="pointer-events-none select-none absolute -bottom-8 right-6 text-[160px] font-serif leading-none text-neutral-100">&rdquo;</span>
                <div className="relative px-7 sm:px-8 py-7">
                  <p className="flex items-center gap-1.5 text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-5">
                    <FileText className="h-3 w-3" /> Contract Summary
                  </p>
                  <p className="text-base font-medium text-neutral-700 leading-relaxed whitespace-pre-wrap italic">
                    {summary}
                  </p>
                  <div className="mt-6 pt-4 border-t border-neutral-200/70 flex items-center justify-between flex-wrap gap-2">
                    <p className="text-xs text-neutral-400">
                      v{contract.version_number} · {new Date(contract.created_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* ═════════ SIDEBAR ═════════ */}
          <div className="flex flex-col gap-4 min-w-0">

            {/* Status notices */}
            {!isStaff && isPending && (
              <div className="relative overflow-hidden bg-gradient-to-br from-neutral-50 to-neutral-100 border border-neutral-200/70 rounded-2xl p-5">
                <div className="absolute top-0 left-0 w-[3px] h-full bg-gradient-to-b from-neutral-900 to-neutral-600" />
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-6 h-6 rounded-full bg-neutral-900 text-white grid place-items-center">
                    <Clock className="h-3 w-3" />
                  </div>
                  <p className="text-sm font-bold text-neutral-900">Awaiting Staff Review</p>
                </div>
                <p className="text-xs text-neutral-600 leading-relaxed">Our team will review and approve this contract before sending it to you for signature.</p>
              </div>
            )}
            {contract.status === 'sent' && (
              <div className="relative overflow-hidden bg-gradient-to-br from-neutral-50 to-neutral-100 border border-neutral-200/70 rounded-2xl p-5">
                <div className="absolute top-0 left-0 w-[3px] h-full bg-gradient-to-b from-neutral-900 to-neutral-600" />
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-6 h-6 rounded-full bg-neutral-900 text-white grid place-items-center">
                    <FileText className="h-3 w-3" />
                  </div>
                  <p className="text-sm font-bold text-neutral-900">Sent for Signature</p>
                </div>
                <p className="text-xs text-neutral-600 leading-relaxed">The client has been emailed a link to sign this contract.</p>
              </div>
            )}
            {contract.status === 'signed' && (
              <div className="relative overflow-hidden bg-neutral-900 text-white border border-neutral-800 rounded-2xl p-5">
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-6 h-6 rounded-full bg-white text-neutral-900 grid place-items-center">
                    <CheckCircle2 className="h-3 w-3" />
                  </div>
                  <p className="text-sm font-bold">Contract Signed</p>
                </div>
                <p className="text-xs text-neutral-400 leading-relaxed">This contract has been fully executed.</p>
              </div>
            )}
            {contract.status === 'rejected' && contract.metadata?.rejection_reason && (
              <div className="relative overflow-hidden bg-gradient-to-br from-neutral-50 to-neutral-100 border border-neutral-200/70 rounded-2xl p-5">
                <div className="absolute top-0 left-0 w-[3px] h-full bg-neutral-900" />
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-6 h-6 rounded-full bg-neutral-900 text-white grid place-items-center">
                    <AlertCircle className="h-3 w-3" />
                  </div>
                  <p className="text-sm font-bold text-neutral-900">Rejected</p>
                </div>
                <p className="text-xs text-neutral-600 leading-relaxed">{contract.metadata.rejection_reason}</p>
              </div>
            )}

            {/* Contract Info — dark elegant card */}
            <div className="relative overflow-hidden bg-neutral-900 text-white border border-neutral-800 rounded-2xl p-5 shadow-lg">
              <div className="absolute -top-24 -right-16 w-64 h-64 rounded-full bg-white/[0.04] blur-2xl pointer-events-none" />
              <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-500 mb-4">Contract Info</p>
              <div className={cn('transition-all duration-300', !isContractVisible && 'blur-sm select-none pointer-events-none')}>
                <div className="flex items-center justify-between py-2.5 border-t border-white/10 first:border-t-0 first:pt-0">
                  <span className="text-[11px] text-neutral-500">Version</span>
                  <span className="text-sm font-semibold">v{contract.version_number}</span>
                </div>
                <div className="flex items-center justify-between py-2.5 border-t border-white/10">
                  <span className="text-[11px] text-neutral-500">Created</span>
                  <span className="text-sm font-semibold">{new Date(contract.created_at).toLocaleDateString()}</span>
                </div>
                {lineItems.length > 0 ? (
                  <>
                    <div className="flex items-center justify-between py-2 border-t border-white/10 text-xs">
                      <span className="text-neutral-500">Subtotal</span>
                      <span>${pricingTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 text-xs">
                      <span className="text-neutral-500">Tax ({taxRate}%)</span>
                      <span>${pricingTax.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 text-xs">
                      <span className="text-neutral-500">Onsite Fee ({onsiteServiceRate}%)</span>
                      <span>${pricingOnsiteSvc.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 text-xs">
                      <span className="text-neutral-500">Gratuity ({gratuityRate}%)</span>
                      <span>${pricingGratuity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between py-2.5 border-t border-white/20 mt-1">
                      <span className="text-xs font-semibold">Grand Total</span>
                      <span className="text-base font-extrabold">${pricingGrandTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between pb-1 text-xs">
                      <span className="text-neutral-500">50% Deposit</span>
                      <span>${pricingDeposit.toLocaleString()}</span>
                    </div>
                  </>
                ) : contract.total_amount != null ? (
                  <div className="flex items-center justify-between py-3 border-t border-white/20 mt-1">
                    <span className="text-xs font-semibold">Grand Total</span>
                    <span className="text-base font-extrabold">${Number(contract.total_amount).toLocaleString()}</span>
                  </div>
                ) : null}
                <div className="flex items-center justify-between pt-2.5 mt-1 border-t border-white/10">
                  <span className="text-[11px] text-neutral-500">Contract ID</span>
                  <span className="font-mono text-[10px] text-neutral-400 truncate max-w-[150px]">{contract.id}</span>
                </div>
              </div>
              {!isContractVisible && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-neutral-900/95 rounded-2xl">
                  <div className="w-8 h-8 rounded-lg bg-white/10 grid place-items-center mb-2">
                    <Lock className="h-3.5 w-3.5 text-white/70" />
                  </div>
                  <p className="text-[11px] font-medium text-white/70 text-center px-6 leading-relaxed">Pricing becomes available once the contract is sent to the client</p>
                </div>
              )}
            </div>

            {/* Client */}
            {(clientName !== '—' || clientInfo.email || clientInfo.phone) && (
              <div className="bg-white border border-neutral-200/70 rounded-2xl p-5 shadow-sm">
                <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-4">Client</p>
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-xl bg-neutral-900 text-white grid place-items-center font-bold text-sm shrink-0">
                    {(clientName !== '—' ? clientName : 'C')
                      .split(' ').map((n: string) => n[0] ?? '').join('').slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    {clientName !== '—' && <p className="text-sm font-bold text-neutral-900 truncate">{clientName}</p>}
                    {clientInfo.email && <p className="text-xs text-neutral-500 truncate">{clientInfo.email}</p>}
                    {clientInfo.phone && <p className="text-xs text-neutral-500">{clientInfo.phone}</p>}
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="bg-white border border-neutral-200/70 rounded-2xl p-5 shadow-sm">
              <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-4">Actions</p>
              {project && (
                <button onClick={() => router.push(`/projects/${project.id}`)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-neutral-900 text-white rounded-xl hover:bg-black transition text-sm font-semibold">
                  View Project
                </button>
              )}
              {isStaff && contract.pdf_path && (
                <a href={`/api/contracts/${contract.id}/pdf`} target="_blank" rel="noopener noreferrer"
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-neutral-200 text-neutral-700 rounded-xl hover:bg-neutral-50 hover:border-neutral-400 transition text-sm font-semibold mt-2">
                  <Download className="h-4 w-4" /> Download PDF
                </a>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

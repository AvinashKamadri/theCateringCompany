"use client";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Calendar, Users, MapPin, FileText,
  Clock, CheckCircle2, AlertCircle, Loader2, Building2,
  ThumbsUp, ThumbsDown, X, DollarSign, Calculator, Plus, Trash2,
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
  const [savingPricing, setSavingPricing] = useState(false);
  const [calculatingPricing, setCalculatingPricing] = useState(false);
  const [pricingBreakdown, setPricingBreakdown] = useState<any>(null);
  const [lineItems, setLineItems] = useState<Array<{ description: string; quantity: number; unitPrice: number }>>([]);
  const [taxRate, setTaxRate] = useState(9.4);
  const [onsiteServiceRate, setOnsiteServiceRate] = useState(6.5);
  const [gratuityRate, setGratuityRate] = useState(15);

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

  const hasPricingSaved = !!(contract?.body as any)?.pricing?.lineItems?.length;
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
        <div className="max-w-6xl mx-auto px-6 py-5">
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

      <div className="max-w-6xl mx-auto px-6 py-6">

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

        {/* Bento grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 auto-rows-min">

          {/* ── Event Details ── 2 cols, compact */}
          <BentoInfoCard className="lg:col-span-2 p-4">
            <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Event Details</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {eventDate && (
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs text-neutral-400 flex items-center gap-1"><Calendar className="h-3 w-3" /> Date</span>
                  <span className="text-sm font-semibold text-neutral-900">{eventDate}</span>
                </div>
              )}
              {guestCount != null && (
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs text-neutral-400 flex items-center gap-1"><Users className="h-3 w-3" /> Guests</span>
                  <span className="text-sm font-semibold text-neutral-900">{guestCount}</span>
                </div>
              )}
              {eventType !== '—' && (
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs text-neutral-400">Event Type</span>
                  <span className="text-sm font-semibold text-neutral-900 capitalize">{eventType}</span>
                </div>
              )}
              {serviceType && (
                <div className="flex flex-col gap-0.5">
                  <span className="text-xs text-neutral-400">Service</span>
                  <span className="text-sm font-semibold text-neutral-900 capitalize">{serviceType}</span>
                </div>
              )}
              {venueName && (
                <div className="flex flex-col gap-0.5 sm:col-span-2">
                  <span className="text-xs text-neutral-400 flex items-center gap-1"><MapPin className="h-3 w-3" /> Venue</span>
                  <span className="text-sm font-semibold text-neutral-900">{venueName}</span>
                  {venueAddress && <span className="text-xs text-neutral-400">{venueAddress}</span>}
                </div>
              )}
            </div>
            {dietaryRestrictions.length > 0 && (
              <div className="mt-3 pt-3 border-t border-neutral-100">
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
                {lineItems.length > 0 ? (
                  <>
                    <div className="flex justify-between text-xs"><span className="text-neutral-400">Subtotal</span><span>${pricingTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-neutral-400">Tax ({taxRate}%)</span><span>${pricingTax.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-neutral-400">Onsite Fee ({onsiteServiceRate}%)</span><span>${pricingOnsiteSvc.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-neutral-400">Gratuity ({gratuityRate}%)</span><span>${pricingGratuity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span></div>
                    <div className="flex justify-between border-t border-neutral-100 pt-2"><span className="font-semibold text-neutral-900">Grand Total</span><span className="font-bold text-neutral-900">${pricingGrandTotal.toLocaleString()}</span></div>
                    <div className="flex justify-between text-xs"><span className="text-neutral-400">50% Deposit</span><span>${pricingDeposit.toLocaleString()}</span></div>
                  </>
                ) : contract.total_amount != null ? (
                  <div className="flex justify-between border-t border-neutral-100 pt-2">
                    <span className="font-semibold text-neutral-900">Grand Total</span>
                    <span className="font-bold text-neutral-900">${Number(contract.total_amount).toLocaleString()}</span>
                  </div>
                ) : null}
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
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-black text-white rounded-xl hover:bg-neutral-800 transition text-sm font-medium">
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

          {/* ── Menu & Services ── full width, prominent */}
          {(appetizers.length > 0 || mainDishes.length > 0 || desserts.length > 0 || utensils || rentals || florals) && (
            <BentoInfoCard className="lg:col-span-3 p-8">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-5">Menu & Services</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-8">
                {appetizers.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-3">Appetizers / Hors d'Oeuvres</p>
                    <div className="flex flex-wrap gap-2">
                      {appetizers.map((item, i) => <span key={i} className="px-3 py-1.5 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{item}</span>)}
                    </div>
                  </div>
                )}
                {mainDishes.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-3">Main Dishes</p>
                    <div className="flex flex-wrap gap-2">
                      {mainDishes.map((item, i) => <span key={i} className="px-3 py-1.5 bg-neutral-900 text-white rounded-lg text-xs font-medium">{item}</span>)}
                    </div>
                  </div>
                )}
                {desserts.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-3">Desserts</p>
                    <div className="flex flex-wrap gap-2">
                      {desserts.map((item, i) => <span key={i} className="px-3 py-1.5 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{item}</span>)}
                    </div>
                  </div>
                )}
              </div>
              {(utensils || rentals || florals) && (
                <div className="mt-6 pt-5 border-t border-neutral-100 grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-neutral-600">
                  {utensils && <p><span className="font-medium text-neutral-400">Utensils: </span>{utensils}</p>}
                  {rentals && <p><span className="font-medium text-neutral-400">Rentals: </span>{rentals}</p>}
                  {florals && <p><span className="font-medium text-neutral-400">Florals: </span>{florals}</p>}
                </div>
              )}
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

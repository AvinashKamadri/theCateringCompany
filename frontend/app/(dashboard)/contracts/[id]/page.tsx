"use client";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Calendar, Users, MapPin, FileText,
  Clock, CheckCircle2, AlertCircle, Loader2, Building2,
  ThumbsUp, ThumbsDown, X, Plus, Trash2, DollarSign,
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const STAFF_DOMAINS = ['@flashbacklabs.com', '@flashbacklabs.inc'];

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
    label: 'Approved',
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
  const [lineItems, setLineItems] = useState<Array<{ description: string; quantity: number; unitPrice: number }>>([]);

  useEffect(() => {
    apiClient.get(`/contracts/${contractId}`)
      .then((data: any) => {
        setContract(data);
        const existing = (data.body as any)?.pricing?.lineItems;
        if (Array.isArray(existing) && existing.length > 0) setLineItems(existing);
      })
      .catch((err: any) => {
        setError(err.message || 'Failed to load contract');
        toast.error('Failed to load contract');
      })
      .finally(() => setLoading(false));
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

  const pricingTotal = lineItems.reduce((s, i) => s + i.quantity * i.unitPrice, 0);

  const handleSavePricing = async () => {
    setSavingPricing(true);
    try {
      await apiClient.patch(`/staff/contracts/${contractId}/pricing`, {
        pricing: { lineItems, total: pricingTotal },
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
  const menuItems: string[] = menu.items?.map((i: any) => i.name || i) || [];
  const dietaryRestrictions: string[] = menu.dietary_restrictions || [];
  const addons: string[] = body.additional?.addons || [];
  const specialRequests: string[] = body.additional?.modifications || [];

  const isPending = contract.status === 'pending_staff_approval';

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      {/* Reject modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Reject Contract</h2>
              <button onClick={() => setShowRejectModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-3">
              Provide a reason so the client understands what needs to change.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Menu details are incomplete, guest count needs confirmation..."
              rows={4}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 resize-none"
            />
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setShowRejectModal(false)}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={rejecting || !rejectReason.trim()}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm flex items-center justify-center gap-2"
              >
                {rejecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsDown className="h-4 w-4" />}
                Reject Contract
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">

        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-gray-500 hover:text-gray-800 mb-4 text-sm"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>

          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {contract.title || `Contract v${contract.version_number}`}
              </h1>
              {project && (
                <button
                  onClick={() => router.push(`/projects/${project.id}`)}
                  className="text-sm text-blue-600 hover:underline mt-1"
                >
                  {project.title}
                </button>
              )}
            </div>

            <span className={cn(
              'inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border self-start',
              statusCfg.style,
            )}>
              <StatusIcon className="h-4 w-4" />
              {statusCfg.label}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* Left — main content */}
          <div className="lg:col-span-2 space-y-6">

            {/* Staff action banner — shown only when pending and user is staff */}
            {isStaff && isPending && (
              <div className="bg-yellow-50 border border-yellow-300 rounded-xl p-5">
                <p className="text-sm font-semibold text-yellow-900 mb-1">Staff Review Required</p>
                <p className="text-sm text-yellow-700 mb-4">
                  Review the contract details below. Preview the PDF first, then approve to send to the client for signature, or reject with a reason.
                </p>
                {/* Pricing Editor */}
                <div className="mb-4">
                  <p className="text-xs font-semibold text-yellow-900 mb-2 flex items-center gap-1">
                    <DollarSign className="h-3.5 w-3.5" /> Pricing (optional — add before generating PDF)
                  </p>
                  <div className="space-y-2">
                    {lineItems.map((item, idx) => (
                      <div key={idx} className="flex gap-2 items-center">
                        <input
                          type="text"
                          placeholder="Description"
                          value={item.description}
                          onChange={(e) => setLineItems(prev => prev.map((li, i) => i === idx ? { ...li, description: e.target.value } : li))}
                          className="flex-1 border border-yellow-300 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-yellow-400"
                        />
                        <input
                          type="number"
                          placeholder="Qty"
                          min={1}
                          value={item.quantity}
                          onChange={(e) => setLineItems(prev => prev.map((li, i) => i === idx ? { ...li, quantity: Number(e.target.value) || 1 } : li))}
                          className="w-14 border border-yellow-300 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-yellow-400"
                        />
                        <input
                          type="number"
                          placeholder="Price"
                          min={0}
                          value={item.unitPrice}
                          onChange={(e) => setLineItems(prev => prev.map((li, i) => i === idx ? { ...li, unitPrice: Number(e.target.value) || 0 } : li))}
                          className="w-20 border border-yellow-300 rounded px-2 py-1 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-yellow-400"
                        />
                        <button
                          onClick={() => setLineItems(prev => prev.filter((_, i) => i !== idx))}
                          className="text-red-400 hover:text-red-600"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                    <div className="flex gap-2">
                      <button
                        onClick={() => setLineItems(prev => [...prev, { description: '', quantity: 1, unitPrice: 0 }])}
                        className="flex items-center gap-1 text-xs text-yellow-800 hover:text-yellow-900 font-medium"
                      >
                        <Plus className="h-3.5 w-3.5" /> Add item
                      </button>
                      {lineItems.length > 0 && (
                        <span className="ml-auto text-xs font-semibold text-yellow-900">
                          Total: ${pricingTotal.toLocaleString()}
                        </span>
                      )}
                    </div>
                    {lineItems.length > 0 && (
                      <button
                        onClick={handleSavePricing}
                        disabled={savingPricing}
                        className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-yellow-700 text-white rounded-lg hover:bg-yellow-800 disabled:opacity-50 text-xs font-medium"
                      >
                        {savingPricing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <DollarSign className="h-3.5 w-3.5" />}
                        {savingPricing ? 'Saving...' : 'Save Pricing'}
                      </button>
                    )}
                  </div>
                </div>

                {/* Preview PDF */}
                <button
                  onClick={handlePreviewPdf}
                  disabled={previewing}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 mb-3 bg-white border border-yellow-400 text-yellow-900 rounded-lg hover:bg-yellow-100 disabled:opacity-50 text-sm font-medium"
                >
                  {previewing
                    ? <Loader2 className="h-4 w-4 animate-spin" />
                    : <FileText className="h-4 w-4" />}
                  {previewing ? 'Generating PDF...' : contract.pdf_path ? 'Regenerate & View PDF' : 'Preview PDF'}
                </button>
                {/* Approve / Reject */}
                <div className="flex gap-3">
                  <button
                    onClick={handleApprove}
                    disabled={approving}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
                  >
                    {approving
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : <ThumbsUp className="h-4 w-4" />}
                    {approving ? 'Approving...' : 'Approve & Send'}
                  </button>
                  <button
                    onClick={() => setShowRejectModal(true)}
                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm font-medium"
                  >
                    <ThumbsDown className="h-4 w-4" />
                    Reject
                  </button>
                </div>
              </div>
            )}

            {/* Event Details */}
            <div className="bg-white rounded-xl shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Event Details</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {eventDate && (
                  <div className="flex items-start gap-3">
                    <Calendar className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Date</p>
                      <p className="font-medium text-gray-900">{eventDate}</p>
                    </div>
                  </div>
                )}
                {guestCount != null && (
                  <div className="flex items-start gap-3">
                    <Users className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Guests</p>
                      <p className="font-medium text-gray-900">{guestCount}</p>
                    </div>
                  </div>
                )}
                {eventType !== '—' && (
                  <div className="flex items-start gap-3">
                    <FileText className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Event Type</p>
                      <p className="font-medium text-gray-900">{eventType}</p>
                    </div>
                  </div>
                )}
                {serviceType && (
                  <div className="flex items-start gap-3">
                    <Building2 className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Service Type</p>
                      <p className="font-medium text-gray-900">{serviceType}</p>
                    </div>
                  </div>
                )}
                {venueName && (
                  <div className="flex items-start gap-3 sm:col-span-2">
                    <MapPin className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Venue</p>
                      <p className="font-medium text-gray-900">{venueName}</p>
                      {venueAddress && <p className="text-sm text-gray-500">{venueAddress}</p>}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Menu */}
            {menuItems.length > 0 && (
              <div className="bg-white rounded-xl shadow-sm p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-3">Menu</h2>
                <ul className="space-y-1">
                  {menuItems.map((item, i) => (
                    <li key={i} className="flex items-center gap-2 text-gray-700 text-sm">
                      <span className="h-1.5 w-1.5 rounded-full bg-blue-500 shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
                {dietaryRestrictions.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-gray-100">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Dietary</p>
                    <p className="text-sm text-gray-700">{dietaryRestrictions.join(', ')}</p>
                  </div>
                )}
              </div>
            )}

            {/* Add-ons / Special Requests */}
            {(addons.length > 0 || specialRequests.length > 0) && (
              <div className="bg-white rounded-xl shadow-sm p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-3">Add-ons & Requests</h2>
                {addons.length > 0 && (
                  <div className="mb-3">
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Add-ons</p>
                    <ul className="space-y-1">
                      {addons.map((a, i) => (
                        <li key={i} className="text-sm text-gray-700">{a}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {specialRequests.length > 0 && (
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Special Requests</p>
                    <ul className="space-y-1">
                      {specialRequests.map((r, i) => (
                        <li key={i} className="text-sm text-gray-700">{r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Contract Summary Text */}
            {summary && (
              <div className="bg-white rounded-xl shadow-sm p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-3">Contract Summary</h2>
                <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {summary}
                </div>
              </div>
            )}
          </div>

          {/* Right — sidebar */}
          <div className="space-y-4">

            {/* Status card */}
            <div className="bg-white rounded-xl shadow-sm p-5">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Contract Info</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Version</span>
                  <span className="font-medium text-gray-900">v{contract.version_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Created</span>
                  <span className="font-medium text-gray-900">
                    {new Date(contract.created_at).toLocaleDateString()}
                  </span>
                </div>
                {contract.total_amount != null && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Total</span>
                    <span className="font-semibold text-gray-900">
                      ${Number(contract.total_amount).toLocaleString()}
                    </span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-gray-500">Contract ID</span>
                  <span className="font-mono text-xs text-gray-500 truncate max-w-[120px]">{contract.id}</span>
                </div>
              </div>
            </div>

            {/* Client card */}
            {(clientName !== '—' || clientInfo.email || clientInfo.phone) && (
              <div className="bg-white rounded-xl shadow-sm p-5">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">Client</h3>
                <div className="space-y-2 text-sm">
                  {clientName !== '—' && (
                    <p className="font-medium text-gray-900">{clientName}</p>
                  )}
                  {clientInfo.email && (
                    <p className="text-gray-600">{clientInfo.email}</p>
                  )}
                  {clientInfo.phone && (
                    <p className="text-gray-600">{clientInfo.phone}</p>
                  )}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="bg-white rounded-xl shadow-sm p-5 space-y-2">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Actions</h3>
              {contract.pdf_path && (
                <a
                  href={`/api/contracts/${contract.id}/pdf`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
                >
                  <FileText className="h-4 w-4" />
                  View PDF
                </a>
              )}
              {project && (
                <button
                  onClick={() => router.push(`/projects/${project.id}`)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition text-sm"
                >
                  View Project
                </button>
              )}
            </div>

            {/* Status notes */}
            {!isStaff && isPending && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
                <p className="text-xs font-semibold text-yellow-800 mb-1">Awaiting Staff Review</p>
                <p className="text-xs text-yellow-700">
                  Our team will review and approve this contract before sending it to you for signature.
                </p>
              </div>
            )}

            {contract.status === 'sent' && (
              <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
                <FileText className="h-5 w-5 text-purple-600 mb-2" />
                <p className="text-xs font-semibold text-purple-800 mb-1">Sent for Signature</p>
                <p className="text-xs text-purple-700">The client has been emailed a link to sign this contract.</p>
              </div>
            )}

            {contract.status === 'signed' && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-4">
                <CheckCircle2 className="h-5 w-5 text-green-600 mb-2" />
                <p className="text-xs font-semibold text-green-800 mb-1">Contract Signed</p>
                <p className="text-xs text-green-700">This contract has been fully executed.</p>
              </div>
            )}

            {contract.status === 'rejected' && contract.metadata?.rejection_reason && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                <AlertCircle className="h-5 w-5 text-red-500 mb-2" />
                <p className="text-xs font-semibold text-red-800 mb-1">Rejected</p>
                <p className="text-xs text-red-700">{contract.metadata.rejection_reason}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

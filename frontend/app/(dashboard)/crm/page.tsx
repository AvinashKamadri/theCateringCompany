"use client";

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Users, Calendar, FileText, Sparkles, ExternalLink,
  Clock, Eye, Loader2, AlertCircle,
  DollarSign, Calculator, Plus, Trash2,
  ChevronDown, X, ThumbsUp, ThumbsDown,
  BarChart2, LayoutGrid, List, CheckCircle2,
} from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Lead {
  id: string;
  title: string;
  status: 'draft' | 'active' | 'confirmed' | 'completed' | 'cancelled';
  event_date: string | null;
  guest_count: number | null;
  created_at: string;
  created_via_ai_intake: boolean;
  client_name: string | null;
  client_email: string;
  contract_count: number;
  member_count: number;
  paid_amount: number;
}

interface Stats {
  total: number;
  by_status: Record<string, number>;
  avg_guests: number;
  via_ai: number;
}

interface PendingContract {
  id: string;
  title: string;
  status: string;
  created_at: string;
  body: any;
  projects_contracts_project_idToprojects: {
    id: string;
    title: string;
    event_date: string;
    guest_count: number;
    ai_event_summary: any;
  };
  users_contracts_created_byTousers: { email: string };
}

// ─── Config ───────────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; order: number; color: string }> = {
  draft:     { label: 'Draft',     order: 0, color: '#d4d4d4' },
  active:    { label: 'Active',    order: 1, color: '#a3a3a3' },
  confirmed: { label: 'Confirmed', order: 2, color: '#525252' },
  completed: { label: 'Completed', order: 3, color: '#000000' },
  cancelled: { label: 'Cancelled', order: 4, color: '#e5e5e5' },
};

const STAGES = Object.entries(STATUS_CONFIG).sort((a, b) => a[1].order - b[1].order);

// ─── Pure SVG Charts ──────────────────────────────────────────────────────────

function DonutChart({ data }: { data: { label: string; value: number; color: string }[] }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  if (total === 0) {
    return (
      <div className="relative w-36 h-36 mx-auto">
        <svg viewBox="0 0 100 100" className="w-full h-full">
          <circle cx="50" cy="50" r="38" fill="none" stroke="#f5f5f5" strokeWidth="14" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-xs text-neutral-300">No data</p>
        </div>
      </div>
    );
  }
  const r = 38;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  const segs = data.map((d) => {
    const dash = (d.value / total) * circ;
    const seg = { ...d, offset, dash };
    offset += dash;
    return seg;
  });
  return (
    <div className="relative">
      <svg viewBox="0 0 100 100" className="w-36 h-36 mx-auto -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#f5f5f5" strokeWidth="14" />
        {segs.filter((s) => s.value > 0).map((seg, i) => (
          <circle
            key={i} cx="50" cy="50" r={r}
            fill="none" stroke={seg.color} strokeWidth="14"
            strokeDasharray={`${seg.dash} ${circ - seg.dash}`}
            strokeDashoffset={-seg.offset}
          />
        ))}
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="text-center">
          <p className="text-2xl font-bold text-black">{total}</p>
          <p className="text-xs text-neutral-400">total</p>
        </div>
      </div>
    </div>
  );
}

function MonthlyBarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  const W = 100;
  const H = 70;
  const colW = W / data.length;
  const bw = colW * 0.55;
  const gap = (colW - bw) / 2;

  return (
    <svg viewBox={`0 0 ${W} ${H + 12}`} className="w-full h-32" preserveAspectRatio="none">
      {data.map((d, i) => {
        const h = Math.max((d.value / max) * (H - 8), d.value > 0 ? 3 : 0);
        const x = i * colW + gap;
        const y = H - h;
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={h} fill={h === 0 ? '#f5f5f5' : '#171717'} rx="1.5" />
            {d.value > 0 && (
              <text x={x + bw / 2} y={y - 2.5} textAnchor="middle" fontSize="4.5" fill="#525252" fontWeight="600">
                {d.value}
              </text>
            )}
            <text x={x + bw / 2} y={H + 9} textAnchor="middle" fontSize="4" fill="#a3a3a3">
              {d.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function calcPricing(
  items: Array<{ description: string; quantity: number; unitPrice: number }>,
  taxRate: number,
  gratuityRate: number,
) {
  const subtotal = items.reduce((s, i) => s + i.quantity * i.unitPrice, 0);
  const tax = Math.round(subtotal * (taxRate / 100));
  const gratuity = Math.round(subtotal * (gratuityRate / 100));
  const grand = subtotal + tax + gratuity;
  const deposit = Math.round(grand * 0.5);
  return { subtotal, tax, gratuity, grand, deposit };
}

function fmt(n: number) {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ─── Main Page ────────────────────────────────────────────────────────────────

type Tab = 'pipeline' | 'contracts' | 'analytics';
type PipelineView = 'kanban' | 'list';

export default function CRMPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();

  // Pipeline
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Contracts tab
  const [contracts, setContracts] = useState<PendingContract[]>([]);
  const [contractsLoading, setContractsLoading] = useState(false);
  const [contractsFetched, setContractsFetched] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeContract, setActiveContract] = useState<PendingContract | null>(null);

  // Contract actions
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  // Pricing editor state
  const [lineItems, setLineItems] = useState<Array<{ description: string; quantity: number; unitPrice: number }>>([]);
  const [taxRate, setTaxRate] = useState(9.4);
  const [gratuityRate, setGratuityRate] = useState(20);
  const [calculating, setCalculating] = useState(false);
  const [savingPricing, setSavingPricing] = useState(false);

  // UI
  const [tab, setTab] = useState<Tab>('pipeline');
  const [pipelineView, setPipelineView] = useState<PipelineView>('kanban');

  useEffect(() => {
    if (!isAuthenticated) { router.push('/signin'); return; }
    if (user && user.role !== 'staff') { router.push('/projects'); return; }
    loadDashboard();
  }, [isAuthenticated, user, router]);

  const loadDashboard = async () => {
    try {
      const [leadsData, statsData] = await Promise.all([
        apiClient.get('/crm/leads') as Promise<any>,
        apiClient.get('/crm/stats') as Promise<any>,
      ]);
      setLeads(leadsData);
      setStats(statsData);
    } catch {
      /* silent */
    } finally {
      setIsLoading(false);
    }
  };

  const loadContracts = async () => {
    setContractsLoading(true);
    try {
      const data: any = await apiClient.get('/staff/contracts/pending');
      setContracts(data.contracts || []);
      setContractsFetched(true);
    } catch (err: any) {
      toast.error('Failed to load contracts');
    } finally {
      setContractsLoading(false);
    }
  };

  const handleTabChange = (t: Tab) => {
    setTab(t);
    if (t === 'contracts' && !contractsFetched) loadContracts();
  };

  const toggleExpand = (contract: PendingContract) => {
    if (expandedId === contract.id) {
      setExpandedId(null);
      setActiveContract(null);
      return;
    }
    setExpandedId(contract.id);
    setActiveContract(contract);
    // Reset pricing state for this contract
    const pricing = contract.body?.pricing;
    setLineItems(Array.isArray(pricing?.lineItems) ? pricing.lineItems : []);
    setTaxRate(pricing?.taxRate != null ? Number(pricing.taxRate) : 9.4);
    setGratuityRate(pricing?.gratuityRate != null ? Number(pricing.gratuityRate) : 20);
  };

  const getClientInfo = (c: PendingContract) => {
    const project = c.projects_contracts_project_idToprojects;
    let aiData: any = {};
    try { aiData = project?.ai_event_summary ? JSON.parse(project.ai_event_summary) : {}; } catch { /* */ }
    const creatorEmail = c.users_contracts_created_byTousers?.email || '';
    return {
      name: c.body?.client_info?.name || aiData.client_name || creatorEmail.split('@')[0] || 'Client',
      email: c.body?.client_info?.email || aiData.contact_email || creatorEmail,
    };
  };

  const handleApprove = async () => {
    if (!activeContract) return;
    setActionLoading(true);
    try {
      await apiClient.post(`/staff/contracts/${activeContract.id}/approve`, { message: 'Approved by staff' });
      toast.success('Contract approved and sent to client!');
      await loadContracts();
      setExpandedId(null);
      setActiveContract(null);
    } catch (err: any) {
      toast.error(err.message || 'Failed to approve');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!activeContract) return;
    if (!rejectReason.trim()) { toast.error('Please provide a rejection reason'); return; }
    setActionLoading(true);
    try {
      await apiClient.post(`/staff/contracts/${activeContract.id}/reject`, { reason: rejectReason });
      toast.success('Contract rejected');
      await loadContracts();
      setExpandedId(null);
      setActiveContract(null);
      setRejectOpen(false);
      setRejectReason('');
    } catch (err: any) {
      toast.error(err.message || 'Failed to reject');
    } finally {
      setActionLoading(false);
    }
  };

  const handleAutoCalculate = async () => {
    if (!activeContract) return;
    setCalculating(true);
    try {
      const result: any = await apiClient.post(`/staff/contracts/${activeContract.id}/calculate-pricing`, {});
      const items = (result.lineItems || []).map((li: any) => ({
        description: li.description,
        quantity: li.quantity,
        unitPrice: li.unitPrice,
      }));
      if (result.serviceSurcharge > 0) {
        items.push({ description: 'On-site Service & Labor', quantity: 1, unitPrice: result.serviceSurcharge });
      }
      setLineItems(items);
      toast.success('Pricing calculated — review and save');
    } catch (err: any) {
      toast.error(err.message || 'Failed to calculate pricing');
    } finally {
      setCalculating(false);
    }
  };

  const handleSavePricing = async () => {
    if (!activeContract) return;
    setSavingPricing(true);
    const { subtotal, grand } = calcPricing(lineItems, taxRate, gratuityRate);
    try {
      await apiClient.patch(`/staff/contracts/${activeContract.id}/pricing`, {
        pricing: { lineItems, subtotal, total: grand, taxRate, gratuityRate },
      });
      toast.success('Pricing saved');
    } catch (err: any) {
      toast.error(err.message || 'Failed to save pricing');
    } finally {
      setSavingPricing(false);
    }
  };

  // Analytics
  const analytics = useMemo(() => {
    const byStatus = stats?.by_status ?? {};
    const donutData = STAGES.map(([key, cfg]) => ({
      label: cfg.label,
      value: byStatus[key] ?? 0,
      color: cfg.color,
    }));
    const monthMap: Record<string, number> = {};
    leads.forEach((l) => {
      if (!l.event_date) return;
      const mo = new Date(l.event_date).toLocaleString('en-US', { month: 'short' });
      monthMap[mo] = (monthMap[mo] ?? 0) + 1;
    });
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const monthBar = months.map((m) => ({ label: m, value: monthMap[m] ?? 0 }));
    const totalRevenue = leads.reduce((s, l) => s + (l.paid_amount || 0), 0);
    const aiRate = stats ? Math.round((stats.via_ai / Math.max(stats.total, 1)) * 100) : 0;
    const completedCount = byStatus.completed ?? 0;
    const convRate = stats ? Math.round((completedCount / Math.max(stats.total, 1)) * 100) : 0;
    return { donutData, monthBar, totalRevenue, aiRate, convRate };
  }, [leads, stats]);

  const pricing = calcPricing(lineItems, taxRate, gratuityRate);

  if (!isAuthenticated || user?.role !== 'staff') return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 rounded-full border-2 border-neutral-200 border-t-black animate-spin" />
          <p className="text-sm text-neutral-400">Loading CRM…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">

      {/* ── Reject modal ── */}
      {rejectOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-black">Reject Contract</h2>
              <button onClick={() => setRejectOpen(false)} className="text-neutral-400 hover:text-black">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-neutral-500 mb-3">
              Provide a reason so the client knows what needs to change.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Menu details incomplete, guest count needs confirmation…"
              rows={4}
              className="w-full border border-neutral-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black resize-none"
            />
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setRejectOpen(false)}
                className="flex-1 px-4 py-2 border border-neutral-200 text-neutral-700 rounded-lg hover:bg-neutral-50 text-sm"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading || !rejectReason.trim()}
                className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 text-sm flex items-center justify-center gap-2"
              >
                {actionLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ThumbsDown className="h-4 w-4" />}
                Reject
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-6 py-5">

          <div className="flex items-start justify-between mb-5">
            <div>
              <h1 className="text-xl font-bold text-black">CRM Dashboard</h1>
              <p className="text-sm text-neutral-400 mt-0.5">Staff workspace — pipeline, contracts &amp; analytics</p>
            </div>
          </div>

          {/* Stat cards */}
          {stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
              {[
                { label: 'Total Projects',  value: stats.total,  sub: 'all time',    icon: FileText },
                { label: 'Total Revenue',   value: `$${analytics.totalRevenue.toLocaleString()}`, sub: 'paid amount', icon: DollarSign },
                { label: 'Avg Guests',      value: Math.round(stats.avg_guests), sub: 'per event', icon: Users },
                { label: 'AI Intake',       value: `${analytics.aiRate}%`, sub: `${stats.via_ai} of ${stats.total}`, icon: Sparkles },
              ].map(({ label, value, sub, icon: Icon }) => (
                <div key={label} className="rounded-xl border border-neutral-200 bg-white p-4">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs text-neutral-500 font-medium">{label}</p>
                    <div className="p-1.5 bg-neutral-50 rounded-md">
                      <Icon className="h-3.5 w-3.5 text-neutral-400" />
                    </div>
                  </div>
                  <p className="text-2xl font-bold text-black tabular-nums">{value}</p>
                  <p className="text-xs text-neutral-400 mt-0.5">{sub}</p>
                </div>
              ))}
            </div>
          )}

          {/* Tab nav */}
          <div className="flex items-center gap-1">
            {([
              { key: 'pipeline',  label: 'Pipeline',   icon: LayoutGrid },
              { key: 'contracts', label: 'Contracts',  icon: FileText,  badge: contractsFetched ? contracts.length : undefined },
              { key: 'analytics', label: 'Analytics',  icon: BarChart2 },
            ] as const).map(({ key, label, icon: Icon, badge }: any) => (
              <button
                key={key}
                onClick={() => handleTabChange(key)}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                  tab === key
                    ? 'bg-black text-white'
                    : 'text-neutral-600 hover:text-black hover:bg-neutral-100',
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
                {badge != null && badge > 0 && (
                  <span className={cn(
                    'ml-0.5 px-1.5 py-0.5 rounded-full text-xs font-semibold',
                    tab === key ? 'bg-white/20 text-white' : 'bg-neutral-200 text-neutral-700',
                  )}>
                    {badge}
                  </span>
                )}
              </button>
            ))}

            {/* Pipeline sub-view toggle */}
            {tab === 'pipeline' && (
              <div className="ml-auto flex items-center border border-neutral-200 rounded-md overflow-hidden">
                {(['kanban', 'list'] as const).map((v) => (
                  <button
                    key={v}
                    onClick={() => setPipelineView(v)}
                    className={cn(
                      'px-3 py-1.5 text-xs font-medium transition-colors capitalize',
                      pipelineView === v
                        ? 'bg-neutral-900 text-white'
                        : 'text-neutral-500 hover:text-black hover:bg-neutral-50',
                    )}
                  >
                    {v === 'kanban' ? 'Kanban' : 'List'}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Tab content ── */}
      <div className="max-w-7xl mx-auto px-6 py-6">

        {/* ── PIPELINE — Kanban ── */}
        {tab === 'pipeline' && pipelineView === 'kanban' && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {STAGES.map(([status, { label, color }]) => {
              const stageLeads = leads.filter((l) => l.status === status);
              return (
                <div key={status} className="bg-white rounded-xl border border-neutral-200 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                      <h3 className="text-sm font-semibold text-black">{label}</h3>
                    </div>
                    <span className="text-xs text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded-full">
                      {stageLeads.length}
                    </span>
                  </div>
                  <div className="space-y-2">
                    {stageLeads.length === 0 && (
                      <p className="text-xs text-neutral-300 text-center py-4">Empty</p>
                    )}
                    {stageLeads.map((lead) => (
                      <Link
                        key={lead.id}
                        href={`/projects/${lead.id}`}
                        className="block bg-neutral-50 border border-neutral-200 rounded-lg p-3 hover:border-black transition-colors group"
                      >
                        <div className="flex items-start justify-between gap-1 mb-1.5">
                          <h4 className="text-xs font-semibold text-black leading-tight line-clamp-2 group-hover:underline">
                            {lead.title}
                          </h4>
                          <ExternalLink className="h-3 w-3 text-neutral-300 shrink-0 mt-0.5" />
                        </div>
                        <p className="text-xs text-neutral-500 truncate">
                          {lead.client_name || lead.client_email}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1">
                          {lead.event_date && (
                            <span className="flex items-center gap-0.5 text-xs text-neutral-400">
                              <Calendar className="h-3 w-3" />
                              {new Date(lead.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                            </span>
                          )}
                          {lead.guest_count != null && (
                            <span className="flex items-center gap-0.5 text-xs text-neutral-400">
                              <Users className="h-3 w-3" />{lead.guest_count}
                            </span>
                          )}
                        </div>
                        {lead.created_via_ai_intake && (
                          <span className="mt-1.5 inline-flex items-center gap-1 text-xs text-neutral-400">
                            <Sparkles className="h-3 w-3" />AI
                          </span>
                        )}
                      </Link>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── PIPELINE — List ── */}
        {tab === 'pipeline' && pipelineView === 'list' && (
          <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-neutral-200 bg-neutral-50">
                <tr>
                  {['Project', 'Client', 'Event Date', 'Guests', 'Status', 'Contracts', ''].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-neutral-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-black">{lead.title}</p>
                      {lead.created_via_ai_intake && (
                        <span className="inline-flex items-center gap-1 text-xs text-neutral-400 mt-0.5">
                          <Sparkles className="h-3 w-3" />AI intake
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-black">{lead.client_name || '—'}</p>
                      <p className="text-xs text-neutral-400">{lead.client_email}</p>
                    </td>
                    <td className="px-4 py-3 text-sm text-neutral-600">
                      {lead.event_date
                        ? new Date(lead.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                        : <span className="text-neutral-300">TBD</span>}
                    </td>
                    <td className="px-4 py-3 text-sm text-neutral-600">
                      {lead.guest_count ?? <span className="text-neutral-300">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded-md text-xs font-medium border',
                          lead.status === 'confirmed' || lead.status === 'completed'
                            ? 'bg-black text-white border-black'
                            : lead.status === 'cancelled'
                            ? 'bg-neutral-700 text-white border-neutral-700'
                            : 'bg-neutral-100 text-neutral-600 border-neutral-200',
                        )}
                      >
                        {STATUS_CONFIG[lead.status]?.label ?? lead.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-neutral-600">{lead.contract_count}</td>
                    <td className="px-4 py-3">
                      <Link href={`/projects/${lead.id}`} className="text-xs font-medium text-neutral-500 hover:text-black transition-colors">
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
                {leads.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-sm text-neutral-400">No projects yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* ── CONTRACTS TAB ── */}
        {tab === 'contracts' && (
          <div>
            {contractsLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="h-6 w-6 animate-spin text-neutral-300" />
              </div>
            ) : contracts.length === 0 ? (
              <div className="bg-white rounded-xl border border-neutral-200 p-16 text-center">
                <CheckCircle2 className="h-10 w-10 text-neutral-200 mx-auto mb-3" />
                <h3 className="text-base font-semibold text-black mb-1">All clear</h3>
                <p className="text-sm text-neutral-400">No contracts pending review right now.</p>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-xs font-medium text-neutral-400 uppercase tracking-wide">
                  {contracts.length} contract{contracts.length !== 1 ? 's' : ''} pending review
                </p>

                {contracts.map((contract) => {
                  const client = getClientInfo(contract);
                  const project = contract.projects_contracts_project_idToprojects;
                  const isExpanded = expandedId === contract.id;

                  return (
                    <div key={contract.id} className="bg-white rounded-xl border border-neutral-200 overflow-hidden">

                      {/* Row header */}
                      <button
                        onClick={() => toggleExpand(contract)}
                        className="w-full flex items-center justify-between px-5 py-4 hover:bg-neutral-50 transition-colors text-left"
                      >
                        <div className="flex items-center gap-4 min-w-0">
                          <div className="p-2 bg-neutral-100 rounded-lg shrink-0">
                            <FileText className="h-4 w-4 text-neutral-500" />
                          </div>
                          <div className="min-w-0">
                            <p className="font-semibold text-black text-sm">{contract.title}</p>
                            <p className="text-xs text-neutral-500 mt-0.5">
                              {client.name}
                              {project?.title ? ` · ${project.title}` : ''}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 shrink-0 ml-4">
                          <span className="hidden sm:inline-flex items-center gap-1 px-2.5 py-1 bg-neutral-100 text-neutral-600 text-xs font-medium rounded-full">
                            <Clock className="h-3 w-3" /> Pending Review
                          </span>
                          {project?.event_date && (
                            <span className="hidden md:flex items-center gap-1 text-xs text-neutral-400">
                              <Calendar className="h-3.5 w-3.5" />
                              {new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                            </span>
                          )}
                          {project?.guest_count && (
                            <span className="hidden lg:flex items-center gap-1 text-xs text-neutral-400">
                              <Users className="h-3.5 w-3.5" />
                              {project.guest_count}
                            </span>
                          )}
                          <ChevronDown className={cn('h-4 w-4 text-neutral-400 transition-transform duration-200', isExpanded && 'rotate-180')} />
                        </div>
                      </button>

                      {/* Expanded review panel */}
                      {isExpanded && (
                        <div className="border-t border-neutral-100 px-5 pb-6 pt-5">
                          <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

                            {/* Left: event + menu info */}
                            <div className="lg:col-span-2 space-y-5">
                              <div>
                                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wide mb-2">Client</p>
                                <p className="text-sm font-semibold text-black">{client.name}</p>
                                <p className="text-xs text-neutral-500">{client.email}</p>
                              </div>

                              {project && (
                                <div>
                                  <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wide mb-2">Event</p>
                                  <div className="space-y-1.5 text-sm text-neutral-700">
                                    {project.event_date && (
                                      <p className="flex items-center gap-2">
                                        <Calendar className="h-3.5 w-3.5 text-neutral-400 shrink-0" />
                                        {new Date(project.event_date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                                      </p>
                                    )}
                                    {project.guest_count && (
                                      <p className="flex items-center gap-2">
                                        <Users className="h-3.5 w-3.5 text-neutral-400 shrink-0" />
                                        {project.guest_count} guests
                                      </p>
                                    )}
                                    {contract.body?.event_details?.type && (
                                      <p className="text-neutral-600">{contract.body.event_details.type}</p>
                                    )}
                                    {contract.body?.event_details?.service_type && (
                                      <p className="text-neutral-500 text-xs">{contract.body.event_details.service_type}</p>
                                    )}
                                  </div>
                                </div>
                              )}

                              {(contract.body?.menu?.items?.length > 0 || contract.body?.menu?.main_dishes?.length > 0) && (
                                <div>
                                  <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wide mb-2">Menu</p>
                                  <ul className="space-y-1">
                                    {(contract.body.menu.main_dishes || contract.body.menu.items || []).map((item: any, i: number) => (
                                      <li key={i} className="flex items-center gap-2 text-sm text-neutral-700">
                                        <span className="h-1.5 w-1.5 rounded-full bg-black shrink-0" />
                                        {typeof item === 'string' ? item : item.name || item}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              <div className="flex gap-2 pt-1">
                                <Link
                                  href={`/contracts/${contract.id}`}
                                  className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-neutral-200 text-neutral-700 rounded-lg hover:bg-neutral-50 text-xs font-medium"
                                >
                                  <Eye className="h-3.5 w-3.5" /> Full Contract
                                </Link>
                              </div>
                            </div>

                            {/* Right: pricing editor */}
                            <div className="lg:col-span-3">
                              <div className="flex items-center justify-between mb-3">
                                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wide">Pricing</p>
                                <button
                                  onClick={handleAutoCalculate}
                                  disabled={calculating}
                                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-black text-white rounded-md hover:bg-neutral-800 disabled:opacity-50 text-xs font-medium"
                                >
                                  {calculating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Calculator className="h-3 w-3" />}
                                  {calculating ? 'Calculating…' : 'Auto-Calculate'}
                                </button>
                              </div>

                              {/* Rate inputs */}
                              <div className="flex gap-3 mb-3">
                                {[
                                  { label: 'Tax %', value: taxRate, setter: setTaxRate, step: 0.1 },
                                  { label: 'Gratuity %', value: gratuityRate, setter: setGratuityRate, step: 0.5 },
                                ].map(({ label, value, setter, step }) => (
                                  <div key={label} className="flex-1">
                                    <label className="block text-xs text-neutral-500 mb-1">{label}</label>
                                    <div className="relative">
                                      <input
                                        type="number" min={0} max={50} step={step} value={value}
                                        onChange={(e) => setter(Number(e.target.value) || 0)}
                                        className="w-full border border-neutral-200 rounded-md px-2.5 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-black pr-7"
                                      />
                                      <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-neutral-400">%</span>
                                    </div>
                                  </div>
                                ))}
                              </div>

                              {/* Line items table */}
                              <div className="border border-neutral-200 rounded-xl overflow-hidden mb-3">
                                <table className="w-full text-xs">
                                  <thead className="bg-neutral-50 border-b border-neutral-200">
                                    <tr>
                                      <th className="px-3 py-2.5 text-left font-semibold text-neutral-500">Description</th>
                                      <th className="px-3 py-2.5 text-center font-semibold text-neutral-500 w-14">Qty</th>
                                      <th className="px-3 py-2.5 text-right font-semibold text-neutral-500 w-24">Unit $</th>
                                      <th className="px-3 py-2.5 text-right font-semibold text-neutral-500 w-24">Total</th>
                                      <th className="w-8" />
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-neutral-100">
                                    {lineItems.map((item, idx) => (
                                      <tr key={idx} className="group">
                                        <td className="px-2 py-2">
                                          <input
                                            type="text"
                                            value={item.description}
                                            placeholder="Item description"
                                            onChange={(e) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, description: e.target.value } : li))}
                                            className="w-full border-0 bg-transparent focus:bg-neutral-50 rounded px-1 py-0.5 focus:outline-none"
                                          />
                                        </td>
                                        <td className="px-2 py-2">
                                          <input
                                            type="number" min={1} value={item.quantity}
                                            onChange={(e) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, quantity: Number(e.target.value) || 1 } : li))}
                                            className="w-full border-0 bg-transparent focus:bg-neutral-50 rounded px-1 py-0.5 focus:outline-none text-center"
                                          />
                                        </td>
                                        <td className="px-2 py-2">
                                          <input
                                            type="number" min={0} value={item.unitPrice}
                                            onChange={(e) => setLineItems((prev) => prev.map((li, i) => i === idx ? { ...li, unitPrice: Number(e.target.value) || 0 } : li))}
                                            className="w-full border-0 bg-transparent focus:bg-neutral-50 rounded px-1 py-0.5 focus:outline-none text-right"
                                          />
                                        </td>
                                        <td className="px-3 py-2 text-right font-semibold text-black whitespace-nowrap">
                                          ${fmt(item.quantity * item.unitPrice)}
                                        </td>
                                        <td className="px-2 py-2">
                                          <button
                                            onClick={() => setLineItems((prev) => prev.filter((_, i) => i !== idx))}
                                            className="text-neutral-200 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100"
                                          >
                                            <Trash2 className="h-3.5 w-3.5" />
                                          </button>
                                        </td>
                                      </tr>
                                    ))}
                                    {lineItems.length === 0 && (
                                      <tr>
                                        <td colSpan={5} className="px-3 py-8 text-center text-neutral-300 text-xs">
                                          No items yet — use Auto-Calculate or add manually
                                        </td>
                                      </tr>
                                    )}
                                  </tbody>
                                </table>

                                {/* Table footer */}
                                <div className="border-t border-neutral-200 bg-neutral-50">
                                  <div className="px-3 py-2.5">
                                    <button
                                      onClick={() => setLineItems((prev) => [...prev, { description: '', quantity: 1, unitPrice: 0 }])}
                                      className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-black font-medium"
                                    >
                                      <Plus className="h-3.5 w-3.5" /> Add line item
                                    </button>
                                  </div>
                                  {lineItems.length > 0 && (
                                    <div className="border-t border-neutral-200 px-3 py-3 space-y-1.5">
                                      {[
                                        { label: 'Subtotal', value: pricing.subtotal },
                                        { label: `Tax (${taxRate}%)`, value: pricing.tax },
                                        { label: `Gratuity (${gratuityRate}%)`, value: pricing.gratuity },
                                      ].map(({ label, value }) => (
                                        <div key={label} className="flex justify-between text-xs text-neutral-600">
                                          <span>{label}</span>
                                          <span>${fmt(value)}</span>
                                        </div>
                                      ))}
                                      <div className="flex justify-between text-sm font-bold text-black border-t border-neutral-300 pt-2 mt-1">
                                        <span>Grand Total</span>
                                        <span>${fmt(pricing.grand)}</span>
                                      </div>
                                      <div className="flex justify-between text-xs text-neutral-500">
                                        <span>50% Deposit Due</span>
                                        <span>${fmt(pricing.deposit)}</span>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>

                              {lineItems.length > 0 && (
                                <button
                                  onClick={handleSavePricing}
                                  disabled={savingPricing}
                                  className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-neutral-800 text-white rounded-lg hover:bg-black disabled:opacity-50 text-xs font-medium mb-3"
                                >
                                  {savingPricing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <DollarSign className="h-3.5 w-3.5" />}
                                  {savingPricing ? 'Saving…' : 'Save Pricing'}
                                </button>
                              )}

                              {/* Approve / Reject */}
                              <div className="flex gap-2">
                                <button
                                  onClick={handleApprove}
                                  disabled={actionLoading}
                                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-black text-white rounded-lg hover:bg-neutral-800 disabled:opacity-50 text-sm font-semibold"
                                >
                                  {actionLoading
                                    ? <Loader2 className="h-4 w-4 animate-spin" />
                                    : <ThumbsUp className="h-4 w-4" />}
                                  Approve & Send
                                </button>
                                <button
                                  onClick={() => setRejectOpen(true)}
                                  disabled={actionLoading}
                                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 border border-neutral-200 text-neutral-700 rounded-lg hover:bg-neutral-50 disabled:opacity-50 text-sm font-medium"
                                >
                                  <ThumbsDown className="h-4 w-4" />
                                  Reject
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── ANALYTICS TAB ── */}
        {tab === 'analytics' && stats && (
          <div className="space-y-6">

            {/* KPI row */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[
                {
                  label: 'Conversion Rate',
                  value: `${analytics.convRate}%`,
                  sub: `${stats.by_status.completed ?? 0} completed of ${stats.total} total`,
                },
                {
                  label: 'AI Adoption',
                  value: `${analytics.aiRate}%`,
                  sub: `${stats.via_ai} leads via AI intake`,
                },
                {
                  label: 'Avg Guest Count',
                  value: Math.round(stats.avg_guests).toString(),
                  sub: 'per event across all projects',
                },
              ].map(({ label, value, sub }) => (
                <div key={label} className="bg-white rounded-xl border border-neutral-200 p-5">
                  <p className="text-xs text-neutral-500 font-medium mb-2">{label}</p>
                  <p className="text-4xl font-bold text-black tabular-nums">{value}</p>
                  <p className="text-xs text-neutral-400 mt-2">{sub}</p>
                </div>
              ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

              {/* Status donut */}
              <div className="bg-white rounded-xl border border-neutral-200 p-6">
                <h3 className="text-sm font-semibold text-black mb-0.5">Projects by Status</h3>
                <p className="text-xs text-neutral-400 mb-5">Distribution across all pipeline stages</p>
                <div className="flex items-center gap-8">
                  <DonutChart data={analytics.donutData} />
                  <div className="space-y-3 flex-1">
                    {analytics.donutData.map(({ label, value, color }) => (
                      <div key={label} className="flex items-center gap-2.5">
                        <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                        <span className="text-xs text-neutral-600 flex-1">{label}</span>
                        <span className="text-xs font-bold text-black tabular-nums">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Monthly bar */}
              <div className="bg-white rounded-xl border border-neutral-200 p-6">
                <h3 className="text-sm font-semibold text-black mb-0.5">Events by Month</h3>
                <p className="text-xs text-neutral-400 mb-5">Based on event dates across all projects</p>
                <MonthlyBarChart data={analytics.monthBar} />
              </div>

              {/* Lead source */}
              <div className="bg-white rounded-xl border border-neutral-200 p-6">
                <h3 className="text-sm font-semibold text-black mb-0.5">Lead Source</h3>
                <p className="text-xs text-neutral-400 mb-6">AI intake vs manually created projects</p>
                <div className="space-y-4">
                  {[
                    { label: 'AI Intake', count: stats.via_ai, pct: analytics.aiRate, icon: Sparkles, dark: true },
                    { label: 'Manual Entry', count: stats.total - stats.via_ai, pct: 100 - analytics.aiRate, icon: FileText, dark: false },
                  ].map(({ label, count, pct, icon: Icon, dark }) => (
                    <div key={label}>
                      <div className="flex justify-between items-center mb-1.5">
                        <span className="flex items-center gap-1.5 text-xs font-medium text-neutral-600">
                          <Icon className="h-3.5 w-3.5 text-neutral-400" />{label}
                        </span>
                        <span className="text-xs font-bold text-black tabular-nums">{count} <span className="text-neutral-400 font-normal">({pct}%)</span></span>
                      </div>
                      <div className="h-2.5 bg-neutral-100 rounded-full overflow-hidden">
                        <div
                          className={cn('h-full rounded-full transition-all', dark ? 'bg-black' : 'bg-neutral-400')}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-6 pt-5 border-t border-neutral-100 grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <p className="text-3xl font-bold text-black">{analytics.aiRate}%</p>
                    <p className="text-xs text-neutral-400 mt-1">AI-generated</p>
                  </div>
                  <div className="text-center">
                    <p className="text-3xl font-bold text-black">{100 - analytics.aiRate}%</p>
                    <p className="text-xs text-neutral-400 mt-1">Manual entry</p>
                  </div>
                </div>
              </div>

              {/* Pipeline breakdown */}
              <div className="bg-white rounded-xl border border-neutral-200 p-6">
                <h3 className="text-sm font-semibold text-black mb-0.5">Pipeline Breakdown</h3>
                <p className="text-xs text-neutral-400 mb-6">Count and share per stage</p>
                <div className="space-y-4">
                  {STAGES.map(([key, { label, color }]) => {
                    const count = stats.by_status[key] ?? 0;
                    const pct = stats.total ? Math.round((count / stats.total) * 100) : 0;
                    return (
                      <div key={key}>
                        <div className="flex justify-between items-center mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                            <span className="text-xs font-medium text-neutral-600">{label}</span>
                          </div>
                          <span className="text-xs font-bold text-black tabular-nums">
                            {count} <span className="text-neutral-400 font-normal">({pct}%)</span>
                          </span>
                        </div>
                        <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{ width: `${pct}%`, backgroundColor: color }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-6 pt-4 border-t border-neutral-100 flex justify-between text-xs text-neutral-500">
                  <span>Total projects</span>
                  <span className="font-bold text-black">{stats.total}</span>
                </div>
              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  );
}

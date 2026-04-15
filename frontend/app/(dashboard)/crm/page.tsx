"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { RoleGuard } from '@/components/auth/RoleGuard';
import {
  Users,
  TrendingUp,
  Calendar,
  FileText,
  Sparkles,
  ExternalLink,
  Clock,
  CheckCircle2,
  AlertCircle,
  BarChart3,
  MessageSquare,
} from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

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

interface Analytics {
  monthly_bookings: { month: string; bookings: number; total_guests: number }[];
  monthly_revenue: { month: string; revenue: number }[];
  guest_buckets: { bucket: string; count: number }[];
}

const STATUS_CONFIG: Record<string, { label: string; order: number }> = {
  draft:     { label: 'Draft',     order: 0 },
  active:    { label: 'Active',    order: 1 },
  confirmed: { label: 'Confirmed', order: 2 },
  completed: { label: 'Completed', order: 3 },
  cancelled: { label: 'Cancelled', order: 4 },
  rejected:  { label: 'Rejected',  order: 5 },
};

const PIE_COLORS = ['#111', '#555', '#888', '#aaa', '#ddd'];

const CustomTooltip = ({ active, payload, label, prefix = '', suffix = '' }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-neutral-200 rounded-lg px-3 py-2 shadow-lg text-xs">
      <p className="font-semibold text-neutral-700 mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-medium">
          {p.name}: {prefix}{typeof p.value === 'number' ? p.value.toLocaleString() : p.value}{suffix}
        </p>
      ))}
    </div>
  );
};

export default function CRMPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [pendingContracts, setPendingContracts] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'overview' | 'pipeline' | 'list'>('overview');

  useEffect(() => {
    if (!isAuthenticated) { router.push('/signin'); return; }
    if (user && user.role !== 'staff') { router.push('/projects'); return; }

    const load = async () => {
      try {
        const [leadsData, statsData, analyticsData, pendingData] = await Promise.all([
          apiClient.get('/crm/leads') as Promise<any>,
          apiClient.get('/crm/stats') as Promise<any>,
          apiClient.get('/crm/analytics').catch(() => null) as Promise<any>,
          apiClient.get('/staff/contracts/pending').catch(() => ({ contracts: [] })) as Promise<any>,
        ]);
        setLeads(leadsData);
        setStats(statsData);
        if (analyticsData) setAnalytics(analyticsData);
        setPendingContracts(pendingData?.contracts ?? []);
      } catch (err) {
        console.error('Failed to load CRM data', err);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [isAuthenticated, user, router]);

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

  const byStage = (status: string) => leads.filter((l) => l.status === status);
  const stages = Object.entries(STATUS_CONFIG).sort((a, b) => a[1].order - b[1].order);

  // Pipeline funnel data from stats
  const pipelineData = stats
    ? stages.map(([key, { label }]) => ({
        name: label,
        value: stats.by_status[key] ?? 0,
      }))
    : [];

  return (
    <RoleGuard role="staff">
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h1 className="text-xl font-bold text-black">CRM</h1>
              <p className="text-sm text-neutral-400 mt-0.5">Project pipeline — staff view</p>
            </div>
          </div>

          {/* KPI row */}
          {stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
              {[
                { label: 'Total Projects',  value: stats.total,                       icon: FileText,   sub: `${stats.by_status.active ?? 0} active` },
                { label: 'Confirmed',       value: stats.by_status.confirmed ?? 0,    icon: TrendingUp, sub: `${stats.by_status.completed ?? 0} completed` },
                { label: 'Avg Guest Count', value: stats.avg_guests,                  icon: Users,      sub: 'per event' },
                { label: 'Via AI Intake',   value: stats.via_ai,                      icon: Sparkles,   sub: `${stats.total ? Math.round((stats.via_ai / stats.total) * 100) : 0}% of total` },
              ].map(({ label, value, icon: Icon, sub }) => (
                <div key={label} className="rounded-xl border border-neutral-200 bg-white p-4">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs text-neutral-500">{label}</p>
                    <div className="p-1.5 bg-neutral-100 rounded-lg">
                      <Icon className="h-3.5 w-3.5 text-neutral-500" />
                    </div>
                  </div>
                  <p className="text-2xl font-bold text-black">{value}</p>
                  <p className="text-xs text-neutral-400 mt-0.5">{sub}</p>
                </div>
              ))}
            </div>
          )}

          {/* View toggle */}
          <div className="flex gap-1.5">
            {(['overview', 'pipeline', 'list'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-sm font-medium transition-colors capitalize',
                  viewMode === mode
                    ? 'bg-black text-white'
                    : 'text-neutral-600 hover:text-black hover:bg-neutral-100'
                )}
              >
                {mode === 'overview' ? 'Overview' : mode === 'pipeline' ? 'Pipeline' : 'List'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">

        {/* ── OVERVIEW ── */}
        {viewMode === 'overview' && (
          <div className="space-y-5">

            {/* Charts row 1: Bookings trend + Pipeline funnel */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

              {/* Monthly bookings area chart */}
              <div className="lg:col-span-2 bg-white rounded-xl border border-neutral-200 p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-sm font-semibold text-black">Monthly Bookings</h3>
                    <p className="text-xs text-neutral-400">New projects over last 12 months</p>
                  </div>
                  <BarChart3 className="h-4 w-4 text-neutral-300" />
                </div>
                {analytics?.monthly_bookings && analytics.monthly_bookings.length > 0 ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <AreaChart data={analytics.monthly_bookings} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="bookGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#111" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="#111" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} />
                      <YAxis tick={{ fontSize: 10, fill: '#aaa' }} tickLine={false} axisLine={false} allowDecimals={false} />
                      <Tooltip content={<CustomTooltip />} />
                      <Area type="monotone" dataKey="bookings" name="Bookings" stroke="#111" strokeWidth={2} fill="url(#bookGrad)" dot={{ fill: '#111', r: 3 }} activeDot={{ r: 5 }} />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[200px] flex items-center justify-center text-xs text-neutral-300">
                    No booking data yet
                  </div>
                )}
              </div>

              {/* Pipeline funnel / pie */}
              <div className="bg-white rounded-xl border border-neutral-200 p-5">
                <div className="mb-4">
                  <h3 className="text-sm font-semibold text-black">Pipeline Status</h3>
                  <p className="text-xs text-neutral-400">Projects by stage</p>
                </div>
                {pipelineData.some((d) => d.value > 0) ? (
                  <ResponsiveContainer width="100%" height={200}>
                    <PieChart>
                      <Pie
                        data={pipelineData.filter((d) => d.value > 0)}
                        cx="50%"
                        cy="45%"
                        innerRadius={48}
                        outerRadius={72}
                        paddingAngle={3}
                        dataKey="value"
                      >
                        {pipelineData.filter((d) => d.value > 0).map((_, i) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: any, n: any) => [v, n]} />
                      <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, paddingTop: 8 }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[200px] flex items-center justify-center text-xs text-neutral-300">
                    No pipeline data yet
                  </div>
                )}
              </div>
            </div>

            {/* Row 2: Pending approval queue + Upcoming events */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

              {/* Contracts pending staff review */}
              <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-neutral-400" />
                    <h3 className="text-sm font-semibold text-black">Awaiting Review</h3>
                    {pendingContracts.length > 0 && (
                      <span className="px-1.5 py-0.5 bg-black text-white text-[10px] font-bold rounded-full">
                        {pendingContracts.length}
                      </span>
                    )}
                  </div>
                  <Link href="/contracts" className="text-xs text-neutral-400 hover:text-black transition-colors">
                    All contracts →
                  </Link>
                </div>
                {pendingContracts.length === 0 ? (
                  <div className="px-5 py-10 text-center">
                    <CheckCircle2 className="h-6 w-6 text-neutral-200 mx-auto mb-2" />
                    <p className="text-xs text-neutral-400">All caught up — no contracts pending review</p>
                  </div>
                ) : (
                  <div className="divide-y divide-neutral-50">
                    {pendingContracts.slice(0, 5).map((c: any) => {
                      const project = c.projects_contracts_project_idToprojects;
                      return (
                        <Link
                          key={c.id}
                          href={`/contracts/${c.id}`}
                          className="flex items-center justify-between px-5 py-3 hover:bg-neutral-50 transition-colors group"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-black truncate group-hover:underline">
                              {c.title || project?.title || `Contract v${c.version_number}`}
                            </p>
                            <div className="flex items-center gap-3 mt-0.5">
                              {project?.event_date && (
                                <span className="text-xs text-neutral-400 flex items-center gap-1">
                                  <Calendar className="h-3 w-3" />
                                  {new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                                </span>
                              )}
                              {project?.guest_count && (
                                <span className="text-xs text-neutral-400 flex items-center gap-1">
                                  <Users className="h-3 w-3" />
                                  {project.guest_count}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0 ml-3">
                            {c.created_via_ai_intake && (
                              <span className="flex items-center gap-0.5 text-[10px] text-neutral-400">
                                <Sparkles className="h-3 w-3" />AI
                              </span>
                            )}
                            <span className="text-xs text-neutral-300 group-hover:text-black transition-colors">→</span>
                          </div>
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Upcoming events (next 60 days) */}
              <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
                <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-neutral-400" />
                    <h3 className="text-sm font-semibold text-black">Upcoming Events</h3>
                  </div>
                  <span className="text-xs text-neutral-400">Next 60 days</span>
                </div>
                {(() => {
                  const now = new Date();
                  const cutoff = new Date(now.getTime() + 60 * 24 * 60 * 60 * 1000);
                  const upcoming = leads
                    .filter((l) => l.event_date && new Date(l.event_date) >= now && new Date(l.event_date) <= cutoff)
                    .sort((a, b) => new Date(a.event_date!).getTime() - new Date(b.event_date!).getTime());

                  if (upcoming.length === 0) return (
                    <div className="px-5 py-10 text-center">
                      <Calendar className="h-6 w-6 text-neutral-200 mx-auto mb-2" />
                      <p className="text-xs text-neutral-400">No events in the next 60 days</p>
                    </div>
                  );

                  return (
                    <div className="divide-y divide-neutral-50">
                      {upcoming.slice(0, 5).map((lead) => {
                        const eventDate = new Date(lead.event_date!);
                        const daysUntil = Math.ceil((eventDate.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
                        return (
                          <Link
                            key={lead.id}
                            href={`/projects/${lead.id}`}
                            className="flex items-center justify-between px-5 py-3 hover:bg-neutral-50 transition-colors group"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="shrink-0 w-10 text-center">
                                <p className="text-[10px] text-neutral-400 uppercase leading-none">
                                  {eventDate.toLocaleDateString('en-US', { month: 'short' })}
                                </p>
                                <p className="text-lg font-bold text-black leading-tight">
                                  {eventDate.getDate()}
                                </p>
                              </div>
                              <div className="min-w-0">
                                <p className="text-sm font-medium text-black truncate group-hover:underline">
                                  {lead.title}
                                </p>
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span className="text-xs text-neutral-400">{lead.client_name || lead.client_email}</span>
                                  {lead.guest_count && (
                                    <span className="text-xs text-neutral-300">· {lead.guest_count} guests</span>
                                  )}
                                </div>
                              </div>
                            </div>
                            <span className={cn(
                              'shrink-0 ml-3 text-[10px] font-semibold px-2 py-0.5 rounded-full',
                              daysUntil <= 7 ? 'bg-black text-white' : 'bg-neutral-100 text-neutral-600'
                            )}>
                              {daysUntil === 0 ? 'Today' : daysUntil === 1 ? 'Tomorrow' : `${daysUntil}d`}
                            </span>
                          </Link>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Recent projects mini-table */}
            <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-neutral-100 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-black">All Projects</h3>
                <span className="text-xs text-neutral-400">{leads.length} total</span>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-neutral-50 border-b border-neutral-100">
                  <tr>
                    {['Project', 'Client', 'Event Date', 'Guests', 'Status'].map((h) => (
                      <th key={h} className="px-4 py-2.5 text-left text-xs font-medium text-neutral-400 uppercase tracking-wide">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-50">
                  {leads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-neutral-50 transition-colors">
                      <td className="px-4 py-3">
                        <Link href={`/projects/${lead.id}`} className="font-medium text-black hover:underline text-sm">
                          {lead.title}
                        </Link>
                        {lead.created_via_ai_intake && (
                          <span className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] text-neutral-400">
                            <Sparkles className="h-2.5 w-2.5" />AI
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-neutral-600">
                        {lead.client_name || lead.client_email}
                      </td>
                      <td className="px-4 py-3 text-sm text-neutral-500">
                        {lead.event_date
                          ? new Date(lead.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                          : <span className="text-neutral-300">TBD</span>}
                      </td>
                      <td className="px-4 py-3 text-sm text-neutral-500">
                        {lead.guest_count ?? <span className="text-neutral-300">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          'px-2 py-0.5 rounded-md text-xs font-medium',
                          lead.status === 'confirmed' || lead.status === 'completed'
                            ? 'bg-black text-white'
                            : lead.status === 'cancelled'
                            ? 'bg-neutral-600 text-white'
                            : 'bg-neutral-100 text-neutral-600'
                        )}>
                          {STATUS_CONFIG[lead.status]?.label ?? lead.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {leads.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-10 text-center text-sm text-neutral-300">
                        No projects yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── PIPELINE ── */}
        {viewMode === 'pipeline' && (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {stages.map(([status, { label }]) => {
              const stageLeads = byStage(status);
              return (
                <div key={status} className="bg-white rounded-xl border border-neutral-200 p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-black">{label}</h3>
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

        {/* ── LIST ── */}
        {viewMode === 'list' && (
          <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-neutral-200 bg-neutral-50">
                <tr>
                  {['Project', 'Client', 'Event Date', 'Guests', 'Status', 'Contracts', ''].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wide">
                      {h}
                    </th>
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
                      <span className={cn(
                        'px-2 py-0.5 rounded-md text-xs font-medium border',
                        lead.status === 'confirmed' || lead.status === 'completed'
                          ? 'bg-black text-white border-black'
                          : lead.status === 'cancelled'
                          ? 'bg-neutral-700 text-white border-neutral-700'
                          : 'bg-neutral-100 text-neutral-600 border-neutral-200'
                      )}>
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
                    <td colSpan={7} className="px-4 py-12 text-center text-sm text-neutral-400">
                      No projects yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
    </RoleGuard>
  );
}

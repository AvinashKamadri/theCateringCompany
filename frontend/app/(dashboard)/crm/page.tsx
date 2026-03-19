"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Users,
  TrendingUp,
  Calendar,
  FileText,
  Sparkles,
  ExternalLink,
} from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';

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

const STATUS_CONFIG: Record<string, { label: string; order: number }> = {
  draft:     { label: 'Draft',     order: 0 },
  active:    { label: 'Active',    order: 1 },
  confirmed: { label: 'Confirmed', order: 2 },
  completed: { label: 'Completed', order: 3 },
  cancelled: { label: 'Cancelled', order: 4 },
};

export default function CRMPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [viewMode, setViewMode] = useState<'pipeline' | 'list'>('pipeline');

  useEffect(() => {
    if (!isAuthenticated) { router.push('/signin'); return; }
    if (user && user.role !== 'staff') { router.push('/projects'); return; }

    const load = async () => {
      try {
        const [leadsData, statsData] = await Promise.all([
          apiClient.get('/crm/leads') as Promise<any>,
          apiClient.get('/crm/stats') as Promise<any>,
        ]);
        setLeads(leadsData);
        setStats(statsData);
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

  return (
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

          {/* Stats row */}
          {stats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
              {[
                { label: 'Total Projects', value: stats.total, icon: FileText },
                { label: 'Confirmed', value: stats.by_status.confirmed ?? 0, icon: TrendingUp },
                { label: 'Avg Guests', value: stats.avg_guests, icon: Users },
                { label: 'Via AI Intake', value: stats.via_ai, icon: Sparkles },
              ].map(({ label, value, icon: Icon }) => (
                <div key={label} className="rounded-lg border border-neutral-200 bg-white p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className="h-4 w-4 text-neutral-400" />
                    <p className="text-xs text-neutral-500">{label}</p>
                  </div>
                  <p className="text-2xl font-bold text-black">{value}</p>
                </div>
              ))}
            </div>
          )}

          {/* View toggle */}
          <div className="flex gap-1.5">
            {(['pipeline', 'list'] as const).map((mode) => (
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
                {mode} view
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {viewMode === 'pipeline' ? (
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
                              {new Date(lead.event_date).toLocaleDateString('en-US', {
                                month: 'short', day: 'numeric',
                              })}
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
        ) : (
          <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="border-b border-neutral-200 bg-neutral-50">
                <tr>
                  {['Project', 'Client', 'Event Date', 'Guests', 'Status', 'Contracts', ''].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-medium text-neutral-500 uppercase tracking-wide"
                    >
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
                        ? new Date(lead.event_date).toLocaleDateString('en-US', {
                            month: 'short', day: 'numeric', year: 'numeric',
                          })
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
                            : 'bg-neutral-100 text-neutral-600 border-neutral-200'
                        )}
                      >
                        {STATUS_CONFIG[lead.status]?.label ?? lead.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-neutral-600">{lead.contract_count}</td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/projects/${lead.id}`}
                        className="text-xs font-medium text-neutral-500 hover:text-black transition-colors"
                      >
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
  );
}

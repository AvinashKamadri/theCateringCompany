"use client";

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { FileText, Loader2, Sparkles, Search, X } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import Folder from '@/components/ui/Folder';

interface Contract {
  id: string;
  title: string | null;
  status: string;
  version_number: number;
  total_amount: number | null;
  created_at: string;
  projects_contracts_project_idToprojects: {
    id: string;
    title: string;
    event_date: string | null;
    guest_count: number | null;
    status: string;
  } | null;
}

const STATUS_LABEL: Record<string, string> = {
  pending_staff_approval: 'Pending Review',
  approved:               'Approved',
  sent:                   'Sent',
  signed:                 'Signed',
  rejected:               'Rejected',
  draft:                  'Draft',
};

const STATUS_STYLES: Record<string, string> = {
  pending_staff_approval: 'bg-neutral-100 text-neutral-700',
  approved:               'bg-neutral-900 text-white',
  sent:                   'bg-neutral-200 text-neutral-800',
  signed:                 'bg-black text-white',
  rejected:               'bg-neutral-100 text-neutral-400',
  draft:                  'bg-neutral-100 text-neutral-500',
};

const FOLDER_COLOR = '#1a1a1a';
const STAFF_DOMAINS = ['@catering-company.com'];

export default function ContractsPage() {
  const { user } = useAuthStore();
  const isStaff = STAFF_DOMAINS.some((d) => user?.email?.toLowerCase().endsWith(d));
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce search query
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedQuery(searchQuery), 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [searchQuery]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (debouncedQuery.trim()) params.set('q', debouncedQuery.trim());
    if (filterStatus !== 'all') params.set('status', filterStatus);
    const qs = params.toString();
    const endpoint = `/contracts${qs ? `?${qs}` : ''}`;
    apiClient.get(endpoint, { signal: controller.signal })
      .then((data: any) => setContracts(data))
      .catch(() => { if (!controller.signal.aborted) toast.error('Failed to load contracts'); })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false); });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStaff, debouncedQuery, filterStatus]);

  const filtered = contracts;

  // Status pill counts (always from full list)
  const statusKeys = ['pending_staff_approval', 'approved', 'sent', 'signed', 'rejected', 'draft'] as const;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-5 w-5 animate-spin text-neutral-300" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Page header */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-6 py-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h1 className="text-xl font-bold text-neutral-900">Contracts</h1>
              <p className="text-sm text-neutral-400 mt-0.5">
                {isStaff ? 'Review and manage all client contracts' : 'Your event agreements'}
              </p>
            </div>
            {!isStaff && (
              <Link
                href="/chat"
                className="flex items-center gap-2 px-4 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Plan an event
              </Link>
            )}
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
            <input
              type="text"
              placeholder="Search by title or project name…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-9 py-2 text-sm border border-neutral-200 rounded-lg bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
            />
            {searchQuery && (
              <button
                onClick={() => { setSearchQuery(''); setDebouncedQuery(''); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-black"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Status filter pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {(['all', ...statusKeys] as const).map((s) => {
              const label = s === 'all' ? 'All' : STATUS_LABEL[s] ?? s;
              const count = s === 'all' ? contracts.length : contracts.filter((c) => c.status === s).length;
              if (s !== 'all' && count === 0) return null;
              return (
                <button
                  key={s}
                  onClick={() => setFilterStatus(s)}
                  className={cn(
                    'px-3 py-1 rounded-full text-xs font-medium transition-colors border',
                    filterStatus === s
                      ? 'bg-black text-white border-black'
                      : 'bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400 hover:text-black'
                  )}
                >
                  {label}
                  <span className={cn('ml-1.5', filterStatus === s ? 'text-neutral-300' : 'text-neutral-400')}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {contracts.length === 0 ? (
          <div className="bg-white rounded-xl border border-neutral-200 p-16 text-center">
            <div className="flex justify-center mb-4">
              <div className="p-4 bg-neutral-100 rounded-full">
                <FileText className="h-8 w-8 text-neutral-300" />
              </div>
            </div>
            <h3 className="text-base font-semibold text-neutral-900 mb-1">No contracts yet</h3>
            <p className="text-sm text-neutral-500 mb-6 max-w-xs mx-auto">
              {isStaff
                ? 'No contracts have been submitted by clients yet.'
                : 'Chat with us to plan your event — we\'ll create your contract once everything\'s set.'}
            </p>
            {!isStaff && (
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Start planning
              </Link>
            )}
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-neutral-200 p-16 text-center">
            <h3 className="text-base font-semibold text-neutral-900 mb-1">No results</h3>
            <p className="text-sm text-neutral-400">Try a different search or status filter.</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-6">
            {filtered.map((contract) => {
              const project = contract.projects_contracts_project_idToprojects;
              const statusLabel = STATUS_LABEL[contract.status] ?? contract.status.replace(/_/g, ' ');
              const statusStyle = STATUS_STYLES[contract.status] ?? STATUS_STYLES.draft;
              const title = contract.title || (project?.title ?? `Contract v${contract.version_number}`);
              const createdAt = new Date(contract.created_at).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric',
              });

              const folderItems = [
                <div key="p1" style={{ padding: '6px 7px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {project?.event_date && (
                    <span style={{ fontSize: 11, color: '#333', fontWeight: 700, lineHeight: 1.3 }}>
                      {new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  )}
                  {project?.guest_count != null && (
                    <span style={{ fontSize: 10, color: '#666', lineHeight: 1.3 }}>
                      {project.guest_count} guests
                    </span>
                  )}
                  {!project?.event_date && !project?.guest_count && (
                    <span style={{ fontSize: 10, color: '#999', lineHeight: 1.3 }}>No event info</span>
                  )}
                </div>,
                <div key="p2" style={{ padding: '6px 7px', display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {(isStaff || contract.status === 'signed') && contract.total_amount != null ? (
                    <>
                      <span style={{ fontSize: 9, color: '#888', textTransform: 'uppercase' as const, letterSpacing: '0.05em' }}>Total</span>
                      <span style={{ fontSize: 13, fontWeight: 800, color: '#111', lineHeight: 1.2 }}>
                        ${contract.total_amount.toLocaleString()}
                      </span>
                    </>
                  ) : !isStaff && contract.total_amount != null ? (
                    <span style={{ fontSize: 10, color: '#999', fontStyle: 'italic' }}>After signing</span>
                  ) : (
                    <span style={{ fontSize: 10, color: '#999' }}>No amount</span>
                  )}
                </div>,
                <div key="p3" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '4px' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#222', textTransform: 'uppercase' as const, letterSpacing: '0.06em', textAlign: 'center' as const }}>
                    {statusLabel}
                  </span>
                </div>,
              ];

              return (
                <Link
                  key={contract.id}
                  href={`/contracts/${contract.id}`}
                  className="flex flex-col items-center gap-3 group"
                >
                  <div className="w-[180px] h-[162px] flex items-end justify-center rounded-2xl tc-shadow-soft-hover">
                    <Folder color={FOLDER_COLOR} size={1.8} items={folderItems} />
                  </div>
                  <div className="text-center w-[180px] px-1">
                    <p className="text-sm font-semibold text-neutral-900 truncate group-hover:text-black leading-snug">
                      {title}
                    </p>
                    <div className="flex items-center justify-center gap-1.5 mt-1 flex-wrap">
                      {project?.event_date && (
                        <span className="text-[11px] text-neutral-500">
                          {new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </span>
                      )}
                      {project?.guest_count != null && (
                        <span className="text-[11px] text-neutral-400">· {project.guest_count} guests</span>
                      )}
                      {contract.total_amount != null && (isStaff || contract.status === 'signed') && (
                        <span className="text-[11px] text-neutral-500">· ${contract.total_amount.toLocaleString()}</span>
                      )}
                    </div>
                    <div className="flex items-center justify-center gap-2 mt-1 flex-wrap">
                      <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', statusStyle)}>
                        {statusLabel}
                      </span>
                      <span className="text-[11px] text-neutral-400">{createdAt}</span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

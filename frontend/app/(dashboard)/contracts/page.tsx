"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FileText, Loader2, Sparkles } from 'lucide-react';
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
  const router = useRouter();
  const { isAuthenticated, user } = useAuthStore();
  const isStaff = STAFF_DOMAINS.some((d) => user?.email?.toLowerCase().endsWith(d));
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated) { router.push('/signin'); return; }

    const controller = new AbortController();
    const endpoint = isStaff ? '/staff/contracts' : '/contracts';
    apiClient.get(endpoint, { signal: controller.signal })
      .then((data: any) => setContracts(data))
      .catch(() => { if (!controller.signal.aborted) toast.error('Failed to load contracts'); })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false); });
    return () => controller.abort();
  }, [isAuthenticated, router, isStaff]);

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
        <div className="max-w-5xl mx-auto px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-neutral-900">Contracts</h1>
            <p className="text-sm text-neutral-500 mt-0.5">
              {contracts.length} contract{contracts.length !== 1 ? 's' : ''}
              {isStaff ? ' · staff view' : ''}
            </p>
          </div>
          {!isStaff && (
            <Link
              href="/chat"
              className="flex items-center gap-2 px-4 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
            >
              <Sparkles className="h-3.5 w-3.5" />
              New intake
            </Link>
          )}
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8">
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
                : 'Contracts are created after completing the AI intake chat.'}
            </p>
            {!isStaff && (
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Start AI Intake
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-6">
            {contracts.map((contract) => {
              const project = contract.projects_contracts_project_idToprojects;
              const statusLabel = STATUS_LABEL[contract.status] ?? contract.status.replace(/_/g, ' ');
              const statusStyle = STATUS_STYLES[contract.status] ?? STATUS_STYLES.draft;
              const title = contract.title || (project?.title ?? `Contract v${contract.version_number}`);
              const createdAt = new Date(contract.created_at).toLocaleDateString('en-US', {
                month: 'short', day: 'numeric', year: 'numeric',
              });

              const folderItems = [
                // Paper 1 — event date & guests
                <div key="p1" style={{ padding: '4px 5px', display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {project?.event_date && (
                    <span style={{ fontSize: 8, color: '#555', fontWeight: 600, lineHeight: 1.3 }}>
                      {new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </span>
                  )}
                  {project?.guest_count != null && (
                    <span style={{ fontSize: 8, color: '#777', lineHeight: 1.3 }}>
                      {project.guest_count} guests
                    </span>
                  )}
                  {!project?.event_date && !project?.guest_count && (
                    <span style={{ fontSize: 8, color: '#999', lineHeight: 1.3 }}>No event info</span>
                  )}
                </div>,
                // Paper 2 — amount
                <div key="p2" style={{ padding: '4px 5px', display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {contract.total_amount != null ? (
                    <>
                      <span style={{ fontSize: 7, color: '#888', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Total</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: '#222', lineHeight: 1.2 }}>
                        ${contract.total_amount.toLocaleString()}
                      </span>
                    </>
                  ) : (
                    <span style={{ fontSize: 8, color: '#999' }}>No amount</span>
                  )}
                </div>,
                // Paper 3 — status
                <div key="p3" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <span style={{ fontSize: 7, fontWeight: 700, color: '#333', textTransform: 'uppercase', letterSpacing: '0.05em', textAlign: 'center' }}>
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
                  {/* Fixed-size box so scaled folder doesn't bleed into adjacent cells */}
                  <div className="w-[180px] h-[155px] flex items-center justify-center" style={{ transformOrigin: 'top center' }}>
                    <Folder color={FOLDER_COLOR} size={1.8} items={folderItems} />
                  </div>

                  {/* Label below folder */}
                  <div className="text-center w-[180px] px-1">
                    <p className="text-sm font-semibold text-neutral-900 truncate group-hover:text-black leading-snug">
                      {title}
                    </p>
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

"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FileText, Calendar, Users, Loader2, ArrowRight, Sparkles } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

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

      <div className="max-w-5xl mx-auto px-6 py-6">
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
          <div className="space-y-2">
            {contracts.map((contract) => {
              const project = contract.projects_contracts_project_idToprojects;
              const statusLabel = STATUS_LABEL[contract.status] ?? contract.status.replace(/_/g, ' ');
              const statusStyle = STATUS_STYLES[contract.status] ?? STATUS_STYLES.draft;

              return (
                <Link
                  key={contract.id}
                  href={`/contracts/${contract.id}`}
                  className="flex items-center justify-between bg-white rounded-xl border border-neutral-200 hover:border-neutral-400 transition-colors px-5 py-4 group"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="p-2 bg-neutral-100 rounded-lg shrink-0">
                      <FileText className="h-4 w-4 text-neutral-500" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-neutral-900 truncate text-sm">
                        {contract.title || `Contract v${contract.version_number}`}
                      </p>
                      {project && (
                        <p className="text-xs text-neutral-500 truncate mt-0.5">{project.title}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-5 shrink-0 ml-4">
                    {project?.event_date && (
                      <div className="hidden sm:flex items-center gap-1.5 text-xs text-neutral-400">
                        <Calendar className="h-3.5 w-3.5" />
                        {new Date(project.event_date).toLocaleDateString('en-US', {
                          month: 'short', day: 'numeric', year: 'numeric',
                        })}
                      </div>
                    )}
                    {project?.guest_count != null && (
                      <div className="hidden md:flex items-center gap-1.5 text-xs text-neutral-400">
                        <Users className="h-3.5 w-3.5" />
                        {project.guest_count}
                      </div>
                    )}
                    {contract.total_amount != null && (
                      <span className="hidden md:block text-xs font-medium text-neutral-600 tabular-nums">
                        ${contract.total_amount.toLocaleString()}
                      </span>
                    )}
                    <span className={cn('px-2.5 py-1 rounded-full text-xs font-medium', statusStyle)}>
                      {statusLabel}
                    </span>
                    <ArrowRight className="h-4 w-4 text-neutral-300 group-hover:text-neutral-600 transition-colors" />
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

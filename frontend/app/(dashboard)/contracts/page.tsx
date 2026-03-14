"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FileText, Calendar, Users, Loader2, ArrowRight } from 'lucide-react';
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

const STATUS_STYLES: Record<string, string> = {
  pending_staff_approval: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  approved:               'bg-blue-100 text-blue-800 border-blue-200',
  sent:                   'bg-purple-100 text-purple-800 border-purple-200',
  signed:                 'bg-green-100 text-green-800 border-green-200',
  rejected:               'bg-red-100 text-red-800 border-red-200',
  draft:                  'bg-gray-100 text-gray-700 border-gray-200',
};

const STAFF_DOMAINS = ['@flashbacklabs.com', '@flashbacklabs.inc'];

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
      .catch((err: any) => { if (!controller.signal.aborted) toast.error('Failed to load contracts'); })
      .finally(() => { if (!controller.signal.aborted) setIsLoading(false); });
    return () => controller.abort();
  }, [isAuthenticated, router, isStaff]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <h1 className="text-2xl font-bold text-gray-900">Contracts</h1>
          <p className="text-sm text-gray-500 mt-1">{contracts.length} contract{contracts.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {contracts.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <div className="flex justify-center mb-4">
              <div className="p-4 bg-gray-100 rounded-full">
                <FileText className="h-12 w-12 text-gray-400" />
              </div>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No contracts yet</h3>
            <p className="text-gray-500 mb-6">
              {isStaff
                ? 'No contracts have been submitted by clients yet.'
                : 'Contracts are created after completing the AI intake chat.'}
            </p>
            {!isStaff && (
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                Start AI Intake
              </Link>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {contracts.map((contract) => {
              const project = contract.projects_contracts_project_idToprojects;
              return (
                <Link
                  key={contract.id}
                  href={`/contracts/${contract.id}`}
                  className="flex items-center justify-between bg-white rounded-lg border border-gray-200 hover:border-blue-400 hover:shadow-sm transition-all px-6 py-4 group"
                >
                  <div className="flex items-center gap-4 min-w-0">
                    <div className="p-2 bg-blue-50 rounded-lg shrink-0">
                      <FileText className="h-5 w-5 text-blue-600" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-gray-900 truncate">
                        {contract.title || `Contract v${contract.version_number}`}
                      </p>
                      {project && (
                        <p className="text-sm text-gray-500 truncate">{project.title}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-6 shrink-0 ml-4">
                    {project?.event_date && (
                      <div className="hidden sm:flex items-center gap-1.5 text-sm text-gray-500">
                        <Calendar className="h-4 w-4" />
                        {new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </div>
                    )}
                    {project?.guest_count != null && (
                      <div className="hidden md:flex items-center gap-1.5 text-sm text-gray-500">
                        <Users className="h-4 w-4" />
                        {project.guest_count} guests
                      </div>
                    )}
                    <span className={cn(
                      'px-2.5 py-1 rounded-full text-xs font-medium border',
                      STATUS_STYLES[contract.status] ?? STATUS_STYLES.draft
                    )}>
                      {contract.status.replace(/_/g, ' ')}
                    </span>
                    <ArrowRight className="h-4 w-4 text-gray-400 group-hover:text-blue-500 transition" />
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

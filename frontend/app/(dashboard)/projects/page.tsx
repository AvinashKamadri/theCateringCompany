"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Plus,
  Search,
  Calendar,
  Users,
  MapPin,
  FileText,
  KeyRound,
  DollarSign,
} from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { projectsApi, type Project } from '@/lib/api/projects';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const STATUS_LABELS: Record<string, string> = {
  inquiry: 'Inquiry',
  proposal_sent: 'Proposal Sent',
  confirmed: 'Confirmed',
  completed: 'Completed',
  draft: 'Draft',
};

export default function ProjectsPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/signin');
      return;
    }
    const load = async () => {
      try {
        setIsLoading(true);
        setProjects(await projectsApi.getAll());
      } catch {
        toast.error('Failed to load projects');
        setProjects([]);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, [isAuthenticated, router]);

  const filtered = projects.filter((p) => {
    // Hide nameless AI intake drafts — they haven't collected an event name yet
    if (p.name === 'AI Intake (draft)') return false;
    const matchSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchStatus = filterStatus === 'all' || p.status === filterStatus;
    return matchSearch && matchStatus;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 rounded-full border-2 border-neutral-200 border-t-black animate-spin" />
          <p className="text-sm text-neutral-400">Loading projects…</p>
        </div>
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
              <h1 className="text-xl font-bold text-black">Projects</h1>
              <p className="text-sm text-neutral-400 mt-0.5">
                {user?.email}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/projects/join"
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-neutral-600 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50 hover:text-black transition-colors"
              >
                <KeyRound className="h-3.5 w-3.5" />
                Join
              </Link>
              <Link
                href="/projects/new"
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-neutral-800 transition-colors"
              >
                <Plus className="h-4 w-4" />
                New Project
              </Link>
            </div>
          </div>

          {/* Search + filter */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400" />
              <input
                type="text"
                placeholder="Search projects…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-4 py-2 text-sm border border-neutral-200 rounded-lg bg-white text-black placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
              />
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white text-black focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent"
            >
              <option value="all">All Status</option>
              <option value="draft">Draft</option>
              <option value="inquiry">Inquiry</option>
              <option value="proposal_sent">Proposal Sent</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {filtered.length === 0 ? (
          <div className="bg-white rounded-xl border border-neutral-200 p-16 text-center">
            <div className="flex justify-center mb-4">
              <div className="h-12 w-12 rounded-full bg-neutral-100 flex items-center justify-center">
                <FileText className="h-6 w-6 text-neutral-400" />
              </div>
            </div>
            <h3 className="text-base font-semibold text-black mb-1">No projects found</h3>
            <p className="text-sm text-neutral-400 mb-6">
              {searchQuery ? 'Try adjusting your search or filter.' : 'Create your first project to get started.'}
            </p>
            {!searchQuery && (
              <Link
                href="/projects/new"
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-black rounded-lg hover:bg-neutral-800 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Create project
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="bg-white rounded-xl border border-neutral-200 hover:border-black hover:shadow-sm transition-all group"
              >
                <div className="p-5">
                  {/* Card header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-semibold text-black truncate group-hover:text-black">
                        {project.name}
                      </h3>
                      <p className="text-xs text-neutral-400 capitalize mt-0.5">{project.event_type ?? '—'}</p>
                    </div>
                    <span
                      className={cn(
                        'ml-3 shrink-0 px-2 py-0.5 rounded-md text-xs font-medium border',
                        project.status === 'confirmed'
                          ? 'bg-black text-white border-black'
                          : project.status === 'completed'
                          ? 'bg-neutral-800 text-white border-neutral-800'
                          : 'bg-neutral-100 text-neutral-600 border-neutral-200'
                      )}
                    >
                      {STATUS_LABELS[project.status] ?? project.status}
                    </span>
                  </div>

                  {/* Meta */}
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs text-neutral-500">
                      <Calendar className="h-3.5 w-3.5 text-neutral-400 shrink-0" />
                      {project.event_date
                        ? new Date(project.event_date).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })
                        : 'Date TBD'}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-neutral-500">
                      <Users className="h-3.5 w-3.5 text-neutral-400 shrink-0" />
                      {project.guest_count != null ? `${project.guest_count} guests` : 'Guests TBD'}
                    </div>
                    {project.venue_name && (
                      <div className="flex items-center gap-2 text-xs text-neutral-500">
                        <MapPin className="h-3.5 w-3.5 text-neutral-400 shrink-0" />
                        <span className="truncate">{project.venue_name}</span>
                      </div>
                    )}
                    {project.total_price != null && (
                      <div className="flex items-center gap-2 text-xs font-semibold text-black">
                        <DollarSign className="h-3.5 w-3.5 text-neutral-400 shrink-0" />
                        ${project.total_price.toLocaleString()}
                      </div>
                    )}
                  </div>

                  {/* Footer */}
                  <div className="mt-4 pt-4 border-t border-neutral-100">
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        router.push(`/projects/${project.id}`);
                      }}
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-black hover:bg-neutral-100 rounded-md transition-colors"
                    >
                      <FileText className="h-3.5 w-3.5" />
                      Details
                    </button>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

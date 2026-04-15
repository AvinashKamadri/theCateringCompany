"use client";

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Plus, Search, FileText, KeyRound } from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { projectsApi, type Project } from '@/lib/api/projects';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import Folder from '@/components/ui/Folder';

const STATUS_LABELS: Record<string, string> = {
  inquiry: 'Inquiry',
  proposal_sent: 'Proposal Sent',
  confirmed: 'Confirmed',
  completed: 'Completed',
  draft: 'Draft',
};

const STATUS_STYLES: Record<string, string> = {
  confirmed:     'bg-neutral-900 text-white',
  completed:     'bg-neutral-800 text-white',
  proposal_sent: 'bg-neutral-200 text-neutral-800',
  inquiry:       'bg-neutral-100 text-neutral-600',
  draft:         'bg-neutral-100 text-neutral-500',
};

const FOLDER_COLOR = '#1a1a1a';

export default function ProjectsPage() {
  const { user } = useAuthStore();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  useEffect(() => {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = projects.filter((p) => {
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
              <p className="text-sm text-neutral-400 mt-0.5">{user?.email}</p>
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
                href="/chat"
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
      <div className="max-w-7xl mx-auto px-6 py-8">
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
                href="/chat"
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-white bg-black rounded-lg hover:bg-neutral-800 transition-colors"
              >
                <Plus className="h-4 w-4" />
                Create project
              </Link>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {filtered.map((project) => {
              const statusStyle = STATUS_STYLES[project.status] ?? STATUS_STYLES.draft;

              const folderItems = [
                // Paper 1 — date & guests
                <div key="p1" style={{ padding: '6px 7px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 11, color: '#333', fontWeight: 700, lineHeight: 1.3 }}>
                    {project.event_date
                      ? new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
                      : 'Date TBD'}
                  </span>
                  <span style={{ fontSize: 10, color: '#666', lineHeight: 1.3 }}>
                    {project.guest_count != null ? `${project.guest_count} guests` : 'Guests TBD'}
                  </span>
                </div>,
                // Paper 2 — venue & event type
                <div key="p2" style={{ padding: '6px 7px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ fontSize: 11, color: '#333', fontWeight: 700, lineHeight: 1.3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                    {project.venue_name || 'Venue TBD'}
                  </span>
                  <span style={{ fontSize: 10, color: '#666', lineHeight: 1.3, textTransform: 'capitalize' as const }}>
                    {project.event_type || '—'}
                  </span>
                </div>,
                // Paper 3 — status
                <div key="p3" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '4px' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: '#222', textTransform: 'uppercase' as const, letterSpacing: '0.06em', textAlign: 'center' as const }}>
                    {STATUS_LABELS[project.status] ?? project.status}
                  </span>
                </div>,
              ];

              return (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="flex flex-col items-center gap-3 group"
                >
                  {/* Folder visual — transform-origin bottom so scale grows upward */}
                  <div className="w-[180px] h-[162px] flex items-end justify-center">
                    <Folder color={FOLDER_COLOR} size={1.8} items={folderItems} />
                  </div>

                  {/* Label below folder */}
                  <div className="text-center w-[180px] px-1">
                    <p className="text-sm font-semibold text-neutral-900 truncate group-hover:text-black leading-snug">
                      {project.name}
                    </p>
                    <div className="flex items-center justify-center gap-1.5 mt-1 flex-wrap">
                      {project.event_date && (
                        <span className="text-[11px] text-neutral-500">
                          {new Date(project.event_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                        </span>
                      )}
                      {project.guest_count != null && (
                        <span className="text-[11px] text-neutral-400">· {project.guest_count} guests</span>
                      )}
                    </div>
                    <div className="flex items-center justify-center gap-2 mt-1 flex-wrap">
                      <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', statusStyle)}>
                        {STATUS_LABELS[project.status] ?? project.status}
                      </span>
                      {project.event_type && (
                        <span className="text-[10px] text-neutral-400 capitalize">{project.event_type}</span>
                      )}
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

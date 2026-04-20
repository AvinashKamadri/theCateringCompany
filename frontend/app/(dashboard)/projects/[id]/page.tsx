"use client";

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api/client';
import { projectsApi, Collaborator, CollaboratorRole } from '@/lib/api/projects';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import {
  Calendar, Users, MapPin, FileText, MessageSquare, Loader2,
  ArrowLeft, UserPlus, Trash2, Copy, Check, Crown, Shield, Link2,
  UtensilsCrossed, Sparkles,
} from 'lucide-react';
import AiHint from '@/components/ui/AiHint';

function getMenuImageUrl(name: string): string | null {
  const clean = name
    .replace(/\s*\([^)]*\$[^)]*\)\s*/g, '').replace(/\s*\$[\d.,]+\/?\w*/g, '').trim()
    .toLowerCase().replace(/[&]/g, 'and').replace(/[\/]/g, '-').replace(/w\//g, 'w-')
    .replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  return clean ? `/menu-images/${clean}.jpg` : null;
}

interface Contract {
  id: string;
  status: string;
  title: string;
  body: any;
  total_amount: number | null;
  created_at: string;
  version_number: number;
}

interface Project {
  id: string;
  title: string;
  event_date: string | null;
  event_end_date: string | null;
  guest_count: number | null;
  status: string;
  ai_event_summary: any;
  venue_id: string | null;
  created_at: string;
  updated_at: string;
  latestActiveContract: Contract | null;
}

const CONTRACT_STATUS_LABEL: Record<string, string> = {
  pending_staff_approval: 'Pending Review',
  approved: 'Approved',
  sent: 'Sent',
  signed: 'Signed',
  rejected: 'Rejected',
  draft: 'Draft',
};

const CONTRACT_STATUS_STYLE: Record<string, string> = {
  pending_staff_approval: 'bg-amber-50 text-amber-800 border border-amber-200',
  approved: 'bg-neutral-900 text-white',
  sent: 'bg-neutral-200 text-neutral-800',
  signed: 'bg-black text-white',
  rejected: 'bg-red-50 text-red-700',
  draft: 'bg-neutral-100 text-neutral-500',
};

const ROLE_BADGE: Record<CollaboratorRole, string> = {
  owner: 'bg-neutral-900 text-white',
  manager: 'bg-neutral-200 text-neutral-800',
  collaborator: 'bg-neutral-100 text-neutral-700',
  viewer: 'bg-neutral-100 text-neutral-500',
};

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.id as string;
  const currentUser = useAuthStore((s) => s.user);

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [myRole, setMyRole] = useState<CollaboratorRole | null>(null);
  const [joinCode, setJoinCode] = useState<string | null>(null);
  const [codeCopied, setCodeCopied] = useState(false);
  const [addEmail, setAddEmail] = useState('');
  const [addRole, setAddRole] = useState<CollaboratorRole>('collaborator');
  const [addingCollaborator, setAddingCollaborator] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const pollRef = useRef<NodeJS.Timeout | undefined>(undefined);

  useEffect(() => {
    fetchProject();
    fetchCollaborators();
  }, [projectId]);

  useEffect(() => {
    if (!project) return;
    const summary = parseSummary(project.ai_event_summary);
    const hasActiveConversation = project.status === 'draft' && !!summary.thread_id;
    if (!hasActiveConversation) { clearInterval(pollRef.current); return; }
    pollRef.current = setInterval(() => fetchProject(true), 5000);
    return () => clearInterval(pollRef.current);
  }, [project?.status, (project?.ai_event_summary as any)?.thread_id ?? '']);

  const parseSummary = (raw: any) => {
    if (!raw) return {};
    if (typeof raw === 'string') { try { return JSON.parse(raw); } catch { return {}; } }
    return raw;
  };

  const fetchProject = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const data = await apiClient.get(`/projects/${projectId}`);
      setProject(data as unknown as Project);
      setError(null);
    } catch (err: any) {
      if (!silent) { setError(err.message || 'Failed to load project'); toast.error('Failed to load project details'); }
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchCollaborators = async () => {
    try {
      const data = await projectsApi.listCollaborators(projectId);
      setCollaborators(data.collaborators);
      if (currentUser) {
        const me = data.collaborators.find((c) => c.user_id === currentUser.id);
        setMyRole((me?.role ?? null) as CollaboratorRole | null);
      }
    } catch { /* non-fatal */ }
  };

  const loadJoinCode = async () => {
    if (joinCode) return;
    try {
      const data = await projectsApi.getJoinCode(projectId);
      setJoinCode(data.join_code);
    } catch { toast.error('Could not load invite link'); }
  };

  const joinUrl = joinCode
    ? `${typeof window !== 'undefined' ? window.location.origin : ''}/projects/join?code=${joinCode}`
    : null;

  const copyCode = async () => {
    if (!joinUrl) return;
    await navigator.clipboard.writeText(joinUrl);
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 2000);
  };

  const handleAddCollaborator = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addEmail.trim()) return;
    setAddingCollaborator(true);
    try {
      await projectsApi.addCollaborator(projectId, addEmail.trim(), addRole);
      toast.success(`${addEmail} added as ${addRole}`);
      setAddEmail('');
      setShowAddForm(false);
      fetchCollaborators();
    } catch (err: any) {
      toast.error(err.message || 'Failed to add collaborator');
    } finally {
      setAddingCollaborator(false);
    }
  };

  const handleUpdateRole = async (userId: string, newRole: CollaboratorRole) => {
    try {
      await projectsApi.updateCollaboratorRole(projectId, userId, newRole);
      toast.success('Role updated');
      fetchCollaborators();
    } catch (err: any) { toast.error(err.message || 'Failed to update role'); }
  };

  const handleRemove = async (userId: string, email: string) => {
    if (!confirm(`Remove ${email} from this project?`)) return;
    try {
      await projectsApi.removeCollaborator(projectId, userId);
      toast.success(`${email} removed`);
      fetchCollaborators();
    } catch (err: any) { toast.error(err.message || 'Failed to remove collaborator'); }
  };

  const handleDeleteProject = async () => {
    if (!confirm(`Delete "${project?.title}"? This cannot be undone.`)) return;
    try {
      await projectsApi.deleteProject(projectId);
      toast.success('Project deleted');
      router.push('/projects');
    } catch (err: any) { toast.error(err.message || 'Failed to delete project'); }
  };

  const roleIcon = (role: CollaboratorRole) => {
    if (role === 'owner') return <Crown className="h-3.5 w-3.5 text-neutral-400" />;
    if (role === 'manager') return <Shield className="h-3.5 w-3.5 text-neutral-400" />;
    return null;
  };

  const canManage = myRole === 'owner' || myRole === 'manager';

  if (loading) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <Loader2 className="h-5 w-5 animate-spin text-neutral-300" />
    </div>
  );

  if (error || !project) return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center">
        <p className="text-sm text-neutral-500 mb-4">{error || 'Project not found'}</p>
        <button onClick={() => router.push('/projects')} className="text-sm font-medium hover:underline">← Back to Projects</button>
      </div>
    </div>
  );

  const summary = parseSummary(project.ai_event_summary);
  const contract = project.latestActiveContract;

  const menuItems: string[] = [
    ...(Array.isArray(summary.main_dishes) ? summary.main_dishes : []),
    ...(Array.isArray(summary.appetizers) ? summary.appetizers : []),
    ...(Array.isArray(summary.desserts) ? summary.desserts : []),
    ...(Array.isArray(summary.menu_items) ? summary.menu_items : []),
  ].filter(Boolean);

  const addons: string[] = (Array.isArray(summary.addons) ? summary.addons : []).filter(Boolean);

  const filledFieldCount = [
    project.event_date, project.guest_count != null,
    (summary.venue_name || summary.venue), summary.event_type,
    summary.service_type, summary.dietary_concerns,
  ].filter(Boolean).length;
  const totalFields = 6;
  const readinessPct = Math.round((filledFieldCount / totalFields) * 100);

  const eventDate = project.event_date ? new Date(project.event_date) : null;

  return (
    <div className="min-h-screen tc-page-bg">
      {/* Container */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-6 pb-20">
        {/* Breadcrumb */}
        <button
          onClick={() => router.push('/projects')}
          className="flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-900 mb-5 transition-colors"
        >
          <ArrowLeft className="h-3 w-3" /> Projects · <span className="capitalize">{summary.event_type || 'Event'}</span>
        </button>

        {/* Hero row */}
        <div className="flex items-end justify-between gap-4 pb-6 border-b border-neutral-200/60 mb-6 flex-wrap">
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-neutral-900">
                {project.title}
              </h1>
              {project.status === 'draft' && summary.thread_id && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-green-50 border border-green-200 rounded-full text-xs font-semibold text-green-700">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                  Live
                </span>
              )}
            </div>
            <p className="text-sm text-neutral-500 mt-2">
              Created {new Date(project.created_at).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {myRole === 'owner' && (
              <button
                onClick={handleDeleteProject}
                className="flex items-center gap-2 px-3 py-2 text-sm text-neutral-500 border border-neutral-200 rounded-xl bg-white/70 backdrop-blur-sm hover:border-neutral-400 hover:text-neutral-900 transition-colors"
              >
                <Trash2 className="h-3.5 w-3.5" /> Delete
              </button>
            )}
            {summary.thread_id && (
              <button
                onClick={() => router.push(`/chat?thread=${summary.thread_id}`)}
                className="tc-btn-glossy flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                {contract ? 'View Chat' : 'Continue Planning'}
              </button>
            )}
          </div>
        </div>

        {/* Progress strip */}
        <div className="flex items-center gap-5 bg-white/70 backdrop-blur-sm border border-neutral-200/70 rounded-2xl px-5 py-4 mb-6 flex-wrap">
          <span className="text-xs font-semibold text-neutral-600 shrink-0">
            <span className="text-neutral-900">Event readiness</span> — {filledFieldCount} of {totalFields} fields complete
          </span>
          <div className="flex-1 min-w-[120px] h-1.5 bg-neutral-200/70 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-neutral-900 to-neutral-600 rounded-full transition-all"
              style={{ width: `${readinessPct}%` }}
            />
          </div>
          <span className={cn(
            'text-xs font-semibold flex items-center gap-1.5 shrink-0',
            readinessPct === 100 ? 'text-green-600' : readinessPct >= 60 ? 'text-neutral-900' : 'text-neutral-500'
          )}>
            <span className={cn(
              'h-1.5 w-1.5 rounded-full',
              readinessPct === 100 ? 'bg-green-500' : readinessPct >= 60 ? 'bg-neutral-900' : 'bg-neutral-400'
            )} />
            {readinessPct === 100 ? 'Ready' : readinessPct >= 60 ? 'Almost ready' : 'Getting started'}
          </span>
        </div>

        {/* Two-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-5">

          {/* ═════════════ LEFT SIDEBAR ═════════════ */}
          <div className="flex flex-col gap-4">
            {/* Event Snapshot */}
            <div className="bg-white border border-neutral-200/70 rounded-2xl p-6 shadow-sm">
              <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-4">Event Snapshot</p>
              {eventDate ? (
                <div className="leading-none">
                  <div className="text-4xl font-extrabold tracking-tight text-neutral-900">
                    {eventDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                  </div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-neutral-400 mt-2">
                    {eventDate.getFullYear()}
                  </div>
                </div>
              ) : (
                <div className="text-sm font-medium text-neutral-500">Date TBD</div>
              )}
              {summary.event_type && (
                <span className="inline-block mt-4 px-3 py-1 rounded-full bg-neutral-900 text-white text-[11px] font-semibold capitalize">
                  {summary.event_type} Event
                </span>
              )}

              {(project.guest_count != null || summary.service_type || summary.venue_name || summary.venue) && (
                <div className="mt-5 pt-4 border-t border-neutral-200/70 flex flex-col gap-3">
                  {project.guest_count != null && (
                    <div className="flex items-center gap-3 text-sm text-neutral-700">
                      <div className="w-7 h-7 rounded-lg bg-neutral-100 grid place-items-center shrink-0">
                        <Users className="h-3.5 w-3.5 text-neutral-500" />
                      </div>
                      <div><strong className="font-semibold text-neutral-900">{project.guest_count}</strong> guests</div>
                    </div>
                  )}
                  {summary.service_type && (
                    <div className="flex items-center gap-3 text-sm text-neutral-700">
                      <div className="w-7 h-7 rounded-lg bg-neutral-100 grid place-items-center shrink-0">
                        <UtensilsCrossed className="h-3.5 w-3.5 text-neutral-500" />
                      </div>
                      <strong className="font-semibold text-neutral-900 capitalize">{summary.service_type}</strong>
                    </div>
                  )}
                  {(summary.venue_name || summary.venue) && (
                    <div className="flex items-center gap-3 text-sm text-neutral-700">
                      <div className="w-7 h-7 rounded-lg bg-neutral-100 grid place-items-center shrink-0">
                        <MapPin className="h-3.5 w-3.5 text-neutral-500" />
                      </div>
                      <span><strong className="font-semibold text-neutral-900">{summary.venue_name || summary.venue}</strong></span>
                    </div>
                  )}
                </div>
              )}

              {summary.dietary_concerns && (
                <div className="mt-4 pt-4 border-t border-neutral-200/70">
                  <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-1">Dietary</p>
                  <p className="text-sm text-neutral-700">{summary.dietary_concerns}</p>
                </div>
              )}
              {summary.special_requests && summary.special_requests !== 'none' && (
                <div className="mt-4 pt-4 border-t border-neutral-200/70">
                  <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-1">Special Requests</p>
                  <p className="text-sm text-neutral-700">{summary.special_requests}</p>
                </div>
              )}
            </div>

            {/* Contract — dark elegant card */}
            {contract ? (
              <div className="relative bg-neutral-900 text-white border border-neutral-800 rounded-2xl p-6 overflow-hidden shadow-lg">
                <div className="absolute -top-24 -right-16 w-64 h-64 rounded-full bg-white/[0.04] blur-2xl pointer-events-none" />
                <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-500 mb-4">Contract</p>
                <p className="text-[10px] uppercase tracking-[0.08em] text-neutral-500 mb-1.5">Total amount</p>
                <div className="text-4xl font-extrabold tracking-tight">
                  {contract.total_amount != null
                    ? `$${contract.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                    : '—'}
                </div>
                <div className="flex gap-4 mt-5 py-3 border-t border-b border-white/10">
                  <div className="flex-1">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-neutral-500">Status</p>
                    <div className="mt-1">
                      <span className={cn('inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold', CONTRACT_STATUS_STYLE[contract.status] ?? CONTRACT_STATUS_STYLE.draft)}>
                        {CONTRACT_STATUS_LABEL[contract.status] ?? contract.status.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                  <div className="flex-1">
                    <p className="text-[10px] uppercase tracking-[0.08em] text-neutral-500">Version</p>
                    <p className="mt-1 text-sm font-semibold">v{contract.version_number}</p>
                  </div>
                </div>
                <button
                  onClick={() => router.push(`/contracts/${contract.id}`)}
                  className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2.5 bg-white text-black text-sm font-semibold rounded-xl hover:bg-neutral-100 transition-colors"
                >
                  <FileText className="h-3.5 w-3.5" /> View Contract
                </button>
              </div>
            ) : (
              <div className="bg-neutral-900 text-white border border-neutral-800 rounded-2xl p-6 shadow-lg">
                <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-500 mb-3">Contract</p>
                <p className="text-sm font-semibold mb-1">No contract yet</p>
                <p className="text-xs text-neutral-400 mb-4">
                  {summary.thread_id ? 'The intake is in progress.' : 'Complete the AI intake to generate a contract.'}
                </p>
                <button
                  onClick={() => router.push(summary.thread_id ? `/chat?thread=${summary.thread_id}` : '/chat')}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-white text-black text-sm font-semibold rounded-xl hover:bg-neutral-100 transition-colors"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  {summary.thread_id ? 'Continue Planning' : 'Plan This Event'}
                </button>
              </div>
            )}

            {/* Client card */}
            {(summary.client_name || summary.contact_email || summary.contact_phone || summary.name) && (
              <div className="bg-white border border-neutral-200/70 rounded-2xl p-5 shadow-sm">
                <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-3">Client</p>
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-xl bg-neutral-900 text-white grid place-items-center font-bold text-lg shrink-0">
                    {((summary.client_name || summary.name) as string)?.[0]?.toUpperCase() ?? '?'}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-bold text-neutral-900 truncate">{summary.client_name || summary.name}</p>
                    {summary.contact_email && (
                      <p className="text-xs text-neutral-500 truncate">{summary.contact_email}</p>
                    )}
                  </div>
                </div>
                {summary.contact_phone && (
                  <p className="text-xs text-neutral-500 mt-3 pt-3 border-t border-neutral-200/70">{summary.contact_phone}</p>
                )}
              </div>
            )}

            {/* Status card — subtle */}
            <div className="bg-white border border-neutral-200/70 rounded-2xl p-5 shadow-sm">
              <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-3">Status</p>
              <span className={cn(
                'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold',
                project.status === 'confirmed' ? 'bg-green-50 border border-green-200 text-green-700' :
                project.status === 'completed' ? 'bg-neutral-900 text-white' :
                project.status === 'cancelled' ? 'bg-red-50 border border-red-200 text-red-700' :
                'bg-neutral-100 text-neutral-700 border border-neutral-200'
              )}>
                <span className={cn(
                  'h-1.5 w-1.5 rounded-full',
                  project.status === 'confirmed' ? 'bg-green-500' :
                  project.status === 'completed' ? 'bg-white' :
                  project.status === 'cancelled' ? 'bg-red-500' :
                  'bg-neutral-400'
                )} />
                <span className="capitalize">{project.status}</span>
              </span>
            </div>
          </div>

          {/* ═════════════ MAIN AREA ═════════════ */}
          <div className="flex flex-col gap-5">

            {/* Menu Selection */}
            {menuItems.length > 0 && (
              <div className="bg-white border border-neutral-200/70 rounded-2xl p-6 sm:p-7 shadow-sm">
                <div className="flex items-start justify-between mb-6">
                  <div>
                    <h2 className="text-lg font-bold text-neutral-900 tracking-tight">Menu Selection</h2>
                    <p className="text-xs text-neutral-500 mt-0.5">{menuItems.length} items</p>
                  </div>
                  <div className="w-9 h-9 rounded-xl bg-neutral-100 grid place-items-center shrink-0">
                    <UtensilsCrossed className="h-4 w-4 text-neutral-500" />
                  </div>
                </div>

                {summary.appetizers?.length > 0 && (
                  <MenuSection title="Appetizers" items={summary.appetizers} />
                )}
                {summary.main_dishes?.length > 0 && (
                  <MenuSection title="Main Dishes" items={summary.main_dishes} highlighted />
                )}
                {summary.desserts?.length > 0 && (
                  <MenuSection title="Desserts" items={summary.desserts} />
                )}
              </div>
            )}

            {/* Add-ons */}
            {addons.length > 0 && (
              <div className="bg-white border border-neutral-200/70 rounded-2xl p-6 shadow-sm">
                <p className="text-[10px] font-bold tracking-[0.12em] uppercase text-neutral-400 mb-4">Add-ons</p>
                <div className="flex flex-wrap gap-2">
                  {addons.map((addon: string, i: number) => (
                    <span key={i} className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-neutral-50 border border-neutral-200/70 text-xs font-medium text-neutral-700">
                      <Sparkles className="h-3 w-3 text-neutral-400" />
                      {addon}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Collaborators */}
            <div className="bg-white border border-neutral-200/70 rounded-2xl p-6 sm:p-7 shadow-sm">
              <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
                <div className="flex items-start gap-3">
                  <div>
                    <h2 className="text-lg font-bold text-neutral-900 tracking-tight flex items-center gap-3">
                      Collaborators
                      {collaborators.length > 0 && (
                        <div className="flex">
                          {collaborators.slice(0, 4).map((c, i) => (
                            <div
                              key={c.user_id}
                              className={cn(
                                'w-7 h-7 rounded-full bg-neutral-900 text-white border-2 border-white grid place-items-center text-[10px] font-semibold uppercase',
                                i > 0 && '-ml-2'
                              )}
                            >
                              {c.first_name?.[0] ?? c.email[0]}
                            </div>
                          ))}
                          {collaborators.length > 4 && (
                            <div className="w-7 h-7 rounded-full bg-neutral-200 text-neutral-700 border-2 border-white grid place-items-center text-[10px] font-semibold -ml-2">
                              +{collaborators.length - 4}
                            </div>
                          )}
                        </div>
                      )}
                    </h2>
                    <p className="text-xs text-neutral-500 mt-1">
                      {collaborators.length} member{collaborators.length !== 1 ? 's' : ''}
                      {myRole === 'owner' && ' · you are the owner'}
                    </p>
                  </div>
                  {canManage && (
                    <AiHint
                      placement="bottom-right"
                      message="Click Generate Link to share a join URL, or Add Collaborator to invite someone by email and assign them a role."
                    />
                  )}
                </div>
                {canManage && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={async () => { await loadJoinCode(); }}
                      className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-neutral-700 border border-neutral-200 rounded-xl bg-white hover:bg-neutral-50 hover:border-neutral-400 transition-colors"
                    >
                      <Link2 className="h-3.5 w-3.5" />
                      {joinUrl ? 'Invite Link' : 'Generate Link'}
                    </button>
                    <button
                      onClick={() => { setShowAddForm(!showAddForm); loadJoinCode(); }}
                      className="tc-btn-glossy flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl"
                    >
                      <UserPlus className="h-3.5 w-3.5" />
                      Add Collaborator
                    </button>
                  </div>
                )}
              </div>

              {joinUrl && canManage && (
                <div className="flex items-center gap-2 bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3 mb-4">
                  <Link2 className="h-4 w-4 text-neutral-400 shrink-0" />
                  <span className="flex-1 text-xs text-neutral-600 truncate select-all">{joinUrl}</span>
                  <button
                    onClick={copyCode}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-black text-white text-xs font-medium rounded-lg hover:bg-neutral-800 transition-colors shrink-0"
                  >
                    {codeCopied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    {codeCopied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
              )}

              {showAddForm && canManage && (
                <form onSubmit={handleAddCollaborator} className="bg-neutral-50 rounded-xl border border-neutral-200 p-4 mb-4">
                  <p className="text-sm font-semibold text-neutral-900 mb-3">Add by email</p>
                  <div className="flex gap-2 flex-wrap">
                    <input
                      type="email"
                      required
                      placeholder="colleague@email.com"
                      value={addEmail}
                      onChange={(e) => setAddEmail(e.target.value)}
                      className="flex-1 min-w-[200px] px-3 py-2 text-sm border border-neutral-200 rounded-xl focus:ring-2 focus:ring-black outline-none bg-white"
                      disabled={addingCollaborator}
                    />
                    <select
                      value={addRole}
                      onChange={(e) => setAddRole(e.target.value as CollaboratorRole)}
                      className="px-3 py-2 text-sm border border-neutral-200 rounded-xl focus:ring-2 focus:ring-black outline-none bg-white"
                      disabled={addingCollaborator}
                    >
                      {myRole === 'owner' && <option value="manager">Manager</option>}
                      <option value="collaborator">Collaborator</option>
                      <option value="viewer">Viewer</option>
                    </select>
                    <button
                      type="submit"
                      disabled={addingCollaborator}
                      className="px-5 py-2 text-sm font-semibold bg-black text-white rounded-xl hover:bg-neutral-800 disabled:opacity-50 transition-colors"
                    >
                      {addingCollaborator ? 'Adding…' : 'Add'}
                    </button>
                  </div>
                </form>
              )}

              {/* Collaborator row list */}
              {collaborators.length === 0 ? (
                <div className="text-center py-10 text-neutral-400">
                  <Users className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No collaborators yet. Invite someone to get started.</p>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {collaborators.map((c) => (
                    <div key={c.user_id} className="flex items-center gap-4 px-4 py-3 rounded-xl bg-neutral-50 border border-neutral-200/70">
                      <div className="w-10 h-10 rounded-xl bg-neutral-900 text-white grid place-items-center text-sm font-bold uppercase shrink-0">
                        {c.first_name?.[0] ?? c.email[0]}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          {roleIcon(c.role)}
                          <span className="text-sm font-bold text-neutral-900 truncate">
                            {c.first_name && c.last_name ? `${c.first_name} ${c.last_name}` : c.email}
                          </span>
                        </div>
                        {(c.first_name || c.last_name) && (
                          <p className="text-xs text-neutral-500 truncate mt-0.5">{c.email}</p>
                        )}
                      </div>
                      {canManage && c.role !== 'owner' && c.user_id !== currentUser?.id ? (
                        <div className="flex items-center gap-1 shrink-0">
                          <select
                            value={c.role}
                            onChange={(e) => handleUpdateRole(c.user_id, e.target.value as CollaboratorRole)}
                            className="text-xs border border-neutral-200 rounded-lg px-1.5 py-1 bg-white outline-none"
                          >
                            {myRole === 'owner' && <option value="manager">Manager</option>}
                            <option value="collaborator">Collaborator</option>
                            <option value="viewer">Viewer</option>
                          </select>
                          <button
                            onClick={() => handleRemove(c.user_id, c.email)}
                            className="p-1.5 text-neutral-300 hover:text-red-500 transition-colors"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <span className={cn('text-xs px-3 py-1 rounded-full font-semibold shrink-0 capitalize', ROLE_BADGE[c.role])}>
                          {c.role}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MenuSection({ title, items, highlighted }: { title: string; items: string[]; highlighted?: boolean }) {
  return (
    <div className="mb-5 last:mb-0">
      <div className="flex items-center gap-3 mb-3">
        <p className="text-[10px] font-bold tracking-[0.1em] uppercase text-neutral-400">{title}</p>
        <div className="flex-1 h-px bg-gradient-to-r from-neutral-200 to-transparent" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {items.map((item: string, i: number) => {
          const img = getMenuImageUrl(item);
          return (
            <div
              key={i}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-xl border text-sm transition-colors',
                highlighted
                  ? 'bg-neutral-900 border-neutral-900 text-white'
                  : 'bg-neutral-50 border-neutral-200/70 text-neutral-800 hover:border-neutral-300'
              )}
            >
              <div className={cn(
                'w-8 h-8 rounded-lg shrink-0 overflow-hidden grid place-items-center',
                highlighted ? 'bg-white/10' : 'bg-neutral-200/60'
              )}>
                {img ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={img}
                    alt=""
                    className="w-full h-full object-cover"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                  />
                ) : (
                  <UtensilsCrossed className={cn('h-3.5 w-3.5', highlighted ? 'text-white/60' : 'text-neutral-400')} />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold truncate leading-tight">{item}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

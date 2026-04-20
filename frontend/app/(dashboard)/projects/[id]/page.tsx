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
  ArrowLeft, UserPlus, Trash2, Copy, Check, Crown, Shield, Link2, Flame, X,
  ArrowLeft, UserPlus, Trash2, Copy, Check, Crown, Shield, Link2, Info,
} from 'lucide-react';
import BentoInfoCard from '@/components/ui/BentoInfoCard';
import AiHint from '@/components/ui/AiHint';

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
  const [wasteOpen, setWasteOpen] = useState(false);
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
  const isStaff = currentUser?.email?.endsWith('@catering-company.com') ?? false;

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

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-6xl mx-auto px-3 sm:px-6 py-5">
          <button
            onClick={() => router.push('/projects')}
            className="flex items-center gap-1.5 text-sm text-neutral-400 hover:text-neutral-900 mb-4 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Projects
          </button>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-xl font-bold text-neutral-900">{project.title}</h1>
                {project.status === 'draft' && summary.thread_id && (
                  <span className="flex items-center gap-1 px-2 py-0.5 bg-green-50 border border-green-200 rounded-full text-xs font-medium text-green-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                    Live
                  </span>
                )}
              </div>
              <p className="text-sm text-neutral-400 mt-0.5">
                Created {new Date(project.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {summary.thread_id && (
                <button
                  onClick={() => router.push(`/chat?thread=${summary.thread_id}`)}
                  className="tc-btn-glossy flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  {contract ? 'View Chat' : 'Continue Planning'}
                </button>
              )}
              {myRole === 'owner' && (
                <button
                  onClick={handleDeleteProject}
                  className="flex items-center gap-2 px-3 py-2 text-sm text-neutral-500 border border-neutral-200 rounded-lg hover:border-neutral-400 hover:text-neutral-900 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Bento grid */}
      <div className="max-w-6xl mx-auto px-3 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 auto-rows-min">

          {/* ── Event Details (with Status inside) ── spans 2 cols */}
          <BentoInfoCard className="lg:col-span-2 p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Event Details</p>
              {(() => {
                const filled = [
                  project.event_date, project.guest_count != null,
                  (summary.venue_name || summary.venue), summary.event_type,
                  summary.service_type, summary.dietary_concerns,
                ].filter(Boolean).length;
                return (
                  <span className="text-[10px] font-medium text-neutral-400 tabular-nums">
                    {filled}/6 fields
                  </span>
                );
              })()}
            </div>
            {(() => {
              const hasAny =
                project.event_date || project.guest_count != null ||
                summary.venue_name || summary.venue || summary.event_type ||
                summary.service_type || summary.dietary_concerns;
              if (!hasAny) {
                return (
                  <div className="flex flex-col items-center justify-center py-10 text-center">
                    <div className="w-12 h-12 rounded-2xl bg-neutral-100 flex items-center justify-center mb-3">
                      <Calendar className="h-5 w-5 text-neutral-400" />
                    </div>
                    <p className="text-sm font-medium text-neutral-700">Details will appear here</p>
                    <p className="text-xs text-neutral-500 mt-1 max-w-xs">
                      {summary.thread_id
                        ? 'Finish the AI intake and we\'ll populate the date, venue, guest count, and more.'
                        : 'Start the AI intake to capture the event information.'}
                    </p>
                  </div>
                );
              }
              return (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-5">
                  {project.event_date && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-neutral-400 flex items-center gap-1"><Calendar className="h-3 w-3" /> Date</span>
                      <span className="text-sm font-semibold text-neutral-900">
                        {new Date(project.event_date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                    </div>
                  )}
                  {project.guest_count != null && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-neutral-400 flex items-center gap-1"><Users className="h-3 w-3" /> Guests</span>
                      <span className="text-sm font-semibold text-neutral-900">{project.guest_count}</span>
                    </div>
                  )}
                  {(summary.venue_name || summary.venue) && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-neutral-400 flex items-center gap-1"><MapPin className="h-3 w-3" /> Venue</span>
                      <span className="text-sm font-semibold text-neutral-900">{summary.venue_name || summary.venue}</span>
                    </div>
                  )}
                  {summary.event_type && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-neutral-400">Event Type</span>
                      <span className="text-sm font-semibold text-neutral-900 capitalize">{summary.event_type}</span>
                    </div>
                  )}
                  {summary.service_type && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-neutral-400">Service</span>
                      <span className="text-sm font-semibold text-neutral-900 capitalize">{summary.service_type}</span>
                    </div>
                  )}
                  {summary.dietary_concerns && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-neutral-400">Dietary</span>
                      <span className="text-sm font-semibold text-neutral-900">{summary.dietary_concerns}</span>
                    </div>
                  )}
                </div>
              );
            })()}
            {summary.special_requests && summary.special_requests !== 'none' && (
              <div className="mt-4 pt-4 border-t border-neutral-100">
                <span className="text-xs text-neutral-400">Special Requests</span>
                <p className="text-sm text-neutral-700 mt-1">{summary.special_requests}</p>
              </div>
            )}
          </BentoInfoCard>

          {/* ── Status + Contract ── 1 col */}
          <div className="flex flex-col gap-4">
            {/* Status tile */}
            <BentoInfoCard className="p-5">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Status</p>
              <div className={cn(
                'inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold shadow-[inset_0_1px_0_rgba(255,255,255,0.15)]',
                project.status === 'confirmed' ? 'bg-gradient-to-br from-emerald-500 to-emerald-700 text-white' :
                project.status === 'completed' ? 'bg-gradient-to-br from-neutral-800 to-black text-white' :
                project.status === 'cancelled' ? 'bg-gradient-to-br from-red-500 to-red-700 text-white' :
                'bg-gradient-to-br from-neutral-100 to-neutral-200 text-neutral-800 border border-neutral-300 shadow-none'
              )}>
                <span className={cn(
                  'h-1.5 w-1.5 rounded-full',
                  project.status === 'confirmed' ? 'bg-emerald-200' :
                  project.status === 'completed' ? 'bg-white' :
                  project.status === 'cancelled' ? 'bg-red-200' :
                  'bg-neutral-500'
                )} />
                <span className="capitalize">{project.status}</span>
              </div>
            </BentoInfoCard>
            {/* Status — moved inside Event Details */}
            <div className="mt-4 pt-4 border-t border-neutral-100">
              <span className="text-xs text-neutral-400 uppercase tracking-wider font-semibold">Status</span>
              <div className="mt-2">
                <span className={cn(
                  'inline-flex px-3 py-1.5 rounded-xl text-xs font-semibold',
                  project.status === 'confirmed' ? 'bg-neutral-900 text-white' :
                  project.status === 'completed' ? 'bg-black text-white' :
                  'bg-neutral-100 text-neutral-700'
                )}>
                  {project.status}
                </span>
              </div>
            </div>
          </BentoInfoCard>

          {/* ── Client + Contract ── right col (where Status used to be) */}
          <div className="flex flex-col gap-4">
            {/* Client tile */}
            {(summary.client_name || summary.contact_email || summary.contact_phone || summary.name) && (
              <BentoInfoCard className="p-5">
                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Client</p>
                <div className="space-y-3">
                  {(summary.client_name || summary.name) && (
                    <div>
                      <p className="text-xs text-neutral-400">Name</p>
                      <p className="text-sm font-semibold text-neutral-900 mt-0.5">{summary.client_name || summary.name}</p>
                    </div>
                  )}
                  {summary.contact_email && (
                    <div>
                      <p className="text-xs text-neutral-400">Email</p>
                      <p className="text-sm font-medium text-neutral-900 mt-0.5">{summary.contact_email}</p>
                    </div>
                  )}
                  {summary.contact_phone && (
                    <div>
                      <p className="text-xs text-neutral-400">Phone</p>
                      <p className="text-sm font-medium text-neutral-900 mt-0.5">{summary.contact_phone}</p>
                    </div>
                  )}
                </div>
              </BentoInfoCard>
            )}

            {/* Contract tile — Amount row removed */}
            {contract ? (
              <BentoInfoCard className="p-5">
                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Contract</p>
                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-neutral-400">Status</span>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', CONTRACT_STATUS_STYLE[contract.status] ?? CONTRACT_STATUS_STYLE.draft)}>
                      {CONTRACT_STATUS_LABEL[contract.status] ?? contract.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-neutral-400">Version</span>
                    <span className="text-xs font-semibold text-neutral-700">v{contract.version_number}</span>
                  </div>
                </div>
                <button
                  onClick={() => router.push(`/contracts/${contract.id}`)}
                  className="tc-btn-glossy w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl"
                >
                  <FileText className="h-3.5 w-3.5" /> View Contract
                </button>
              </BentoInfoCard>
            ) : (
              <BentoInfoCard className="p-5 bg-neutral-900! border-neutral-700!" glowColor="255, 255, 255">
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
            </BentoInfoCard>
            )}

            {isStaff && (
              <BentoInfoCard className="p-5">
                <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-3">Food Waste</p>
                <p className="text-xs text-neutral-500 mb-3">Log ingredients discarded or over-prepped for this event.</p>
                <button
                  onClick={() => setWasteOpen(true)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl border border-neutral-200 hover:border-neutral-400 text-neutral-800 transition-colors"
                >
                  <Flame className="h-3.5 w-3.5" /> Log waste
                </button>
              </BentoInfoCard>
              </BentoInfoCard>
            )}
          </div>

          {/* ── Menu ── full width for more prominence */}
          {menuItems.length > 0 && (
            <BentoInfoCard className="lg:col-span-3 p-6">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Menu</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                {summary.appetizers?.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-2">Appetizers</p>
                    <div className="flex flex-wrap gap-1.5">
                      {summary.appetizers.map((item: string, i: number) => (
                        <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{item}</span>
                      ))}
                    </div>
                  </div>
                )}
                {summary.main_dishes?.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-2">Main Dishes</p>
                    <div className="flex flex-wrap gap-1.5">
                      {summary.main_dishes.map((item: string, i: number) => (
                        <span key={i} className="px-2.5 py-1 bg-neutral-900 text-white rounded-lg text-xs font-medium">{item}</span>
                      ))}
                    </div>
                  </div>
                )}
                {summary.desserts?.length > 0 && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-2">Desserts</p>
                    <div className="flex flex-wrap gap-1.5">
                      {summary.desserts.map((item: string, i: number) => (
                        <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{item}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </BentoInfoCard>
          )}

          {/* ── Add-ons ── 1 col */}
          {addons.length > 0 && (
            <BentoInfoCard className="p-6">
              <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider mb-4">Add-ons</p>
              <div className="flex flex-wrap gap-1.5">
                {addons.map((addon: string, i: number) => (
                  <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-lg text-xs font-medium text-neutral-700">{addon}</span>
                ))}
              </div>
            </BentoInfoCard>
          )}

          {/* ── Collaborators ── spans full width */}
          <BentoInfoCard className="lg:col-span-3 p-6" enableTilt={false}>
            <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
              <div className="flex items-center gap-2">
                <div>
                  <p className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Collaborators</p>
                  <p className="text-sm text-neutral-500 mt-0.5">{collaborators.length} member{collaborators.length !== 1 ? 's' : ''}</p>
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
                  {/* Generate invite link button */}
                  <button
                    onClick={async () => { await loadJoinCode(); }}
                    className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-neutral-700 border border-neutral-200 rounded-xl hover:bg-neutral-50 hover:border-neutral-400 transition-colors"
                  >
                    <Link2 className="h-3.5 w-3.5" />
                    {joinUrl ? 'Invite Link' : 'Generate Link'}
                  </button>
                  {/* Add collaborator button */}
                  <button
                    onClick={() => { setShowAddForm(!showAddForm); loadJoinCode(); }}
                    className="tc-btn-glossy flex items-center gap-2 px-4 py-2 text-sm font-semibold rounded-xl"
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    Add Collaborator
                  </button>
                </div>
                    {/* Generate invite link button */}
                    <button
                      onClick={async () => { await loadJoinCode(); }}
                      className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-neutral-700 border border-neutral-200 rounded-xl hover:bg-neutral-50 hover:border-neutral-400 transition-colors"
                    >
                      <Link2 className="h-3.5 w-3.5" />
                      {joinUrl ? 'Invite Link' : 'Generate Link'}
                    </button>
                    {/* Add collaborator button */}
                    <button
                      onClick={() => { setShowAddForm(!showAddForm); loadJoinCode(); }}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-black text-white rounded-xl hover:bg-neutral-800 transition-colors"
                    >
                      <UserPlus className="h-3.5 w-3.5" />
                      Add Collaborator
                    </button>
                    {/* Info tooltip */}
                    <div className="relative group">
                      <div className="flex items-center justify-center w-7 h-7 rounded-full border border-neutral-200 text-neutral-400 hover:text-neutral-700 hover:border-neutral-400 transition-colors cursor-help">
                        <Info className="h-3.5 w-3.5" />
                      </div>
                      <div className="absolute right-0 top-full mt-2 w-56 px-3 py-2 bg-neutral-900 text-white text-xs rounded-lg shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 z-50 pointer-events-none">
                        Click <span className="font-semibold">Generate Link</span> to invite collaborators or <span className="font-semibold">Add</span> through email
                        <div className="absolute -top-1 right-3 w-2 h-2 bg-neutral-900 rotate-45" />
                      </div>
                    </div>
                  </div>
              )}
            </div>

            {/* Invite link bar */}
            {joinUrl && canManage && (
              <div className="flex items-center gap-2 bg-neutral-50 border border-neutral-200 rounded-xl px-4 py-3 mb-5">
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

            {/* Add collaborator form */}
            {showAddForm && canManage && (
              <form onSubmit={handleAddCollaborator} className="bg-neutral-50 rounded-xl border border-neutral-200 p-4 mb-5">
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

            {/* Collaborator list */}
            {collaborators.length === 0 ? (
              <div className="text-center py-8 text-neutral-400">
                <Users className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No collaborators yet. Invite someone to get started.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {collaborators.map((c) => (
                  <div key={c.user_id} className="flex items-center gap-3 p-3 rounded-xl border border-neutral-200 bg-neutral-50">
                    <div className="w-9 h-9 rounded-full bg-neutral-200 flex items-center justify-center text-sm font-semibold text-neutral-600 uppercase shrink-0">
                      {c.first_name?.[0] ?? c.email[0]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        {roleIcon(c.role)}
                        <span className="text-sm font-semibold text-neutral-900 truncate">
                          {c.first_name && c.last_name ? `${c.first_name} ${c.last_name}` : c.email}
                        </span>
                      </div>
                      {(c.first_name || c.last_name) && (
                        <p className="text-xs text-neutral-400 truncate">{c.email}</p>
                      )}
                    </div>
                    {canManage && c.role !== 'owner' && c.user_id !== currentUser?.id ? (
                      <div className="flex items-center gap-1 shrink-0">
                        <select
                          value={c.role}
                          onChange={(e) => handleUpdateRole(c.user_id, e.target.value as CollaboratorRole)}
                          className="text-xs border border-neutral-200 rounded-lg px-1.5 py-0.5 bg-white outline-none"
                        >
                          {myRole === 'owner' && <option value="manager">Manager</option>}
                          <option value="collaborator">Collaborator</option>
                          <option value="viewer">Viewer</option>
                        </select>
                        <button
                          onClick={() => handleRemove(c.user_id, c.email)}
                          className="p-1 text-neutral-300 hover:text-red-500 transition-colors"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ) : (
                      <span className={cn('text-xs px-2.5 py-1 rounded-full font-medium shrink-0', ROLE_BADGE[c.role])}>
                        {c.role}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </BentoInfoCard>

        </div>
      </div>

      {wasteOpen && (
        <LogWasteModal
          projectId={projectId}
          onClose={() => setWasteOpen(false)}
          onSaved={() => { setWasteOpen(false); toast.success('Waste logged'); }}
        />
      )}
    </div>
  );
}

interface Ingredient { id: string; name: string; default_unit: string }

function LogWasteModal({
  projectId,
  onClose,
  onSaved,
}: {
  projectId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [ingredientId, setIngredientId] = useState('');
  const [amount, setAmount] = useState('');
  const [unit, setUnit] = useState<'g' | 'ml'>('g');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiClient.get('/inventory/ingredients')
      .then((data: any) => {
        const list = Array.isArray(data) ? data : [];
        setIngredients(list);
        if (list.length > 0) {
          setIngredientId(list[0].id);
          setUnit((list[0].default_unit === 'ml' ? 'ml' : 'g') as 'g' | 'ml');
        }
      })
      .catch(() => toast.error('Failed to load ingredients'));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ingredientId || !amount) return;
    const qty = Math.abs(Number(amount));
    if (!Number.isFinite(qty) || qty <= 0) { toast.error('Enter a valid amount'); return; }
    setSaving(true);
    try {
      await apiClient.post('/inventory/stock-log', {
        ingredient_id: ingredientId,
        delta_g: unit === 'g' ? -qty : null,
        delta_ml: unit === 'ml' ? -qty : null,
        source: 'waste',
        project_id: projectId,
        notes: notes.trim() || null,
      });
      onSaved();
    } catch (err: any) {
      toast.error(err.message || 'Failed to log waste');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-neutral-200">
        <div className="flex items-center justify-between p-5 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">Log food waste</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-900">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <div>
            <label className="text-xs font-medium text-neutral-600 mb-1 block">Ingredient</label>
            <select
              value={ingredientId}
              onChange={(e) => {
                setIngredientId(e.target.value);
                const ing = ingredients.find((i) => i.id === e.target.value);
                if (ing) setUnit((ing.default_unit === 'ml' ? 'ml' : 'g') as 'g' | 'ml');
              }}
              className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-neutral-900 focus:outline-none"
              required
            >
              {ingredients.length === 0 && <option value="">No ingredients available</option>}
              {ingredients.map((i) => (
                <option key={i.id} value={i.id}>{i.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <div>
              <label className="text-xs font-medium text-neutral-600 mb-1 block">Amount</label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-neutral-900 focus:outline-none"
                placeholder="e.g. 250"
                required
              />
            </div>
            <div>
              <label className="text-xs font-medium text-neutral-600 mb-1 block">Unit</label>
              <select
                value={unit}
                onChange={(e) => setUnit(e.target.value as 'g' | 'ml')}
                className="px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-neutral-900 focus:outline-none"
              >
                <option value="g">g</option>
                <option value="ml">ml</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-neutral-600 mb-1 block">Notes <span className="text-neutral-400">(optional)</span></label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-neutral-900 focus:outline-none resize-none"
              placeholder="Over-prepped, spoiled, dropped..."
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg text-neutral-600 hover:bg-neutral-100">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !ingredientId || !amount}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-neutral-900 text-white hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Logging…' : 'Log waste'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

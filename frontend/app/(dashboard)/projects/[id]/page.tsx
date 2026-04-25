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
} from 'lucide-react';

interface Contract {
  id: string;
  status: string;
  title: string;
  body: any;
  total_amount: number | null;
  created_at: string;
  version_number: number;
}

interface EventWasteLog {
  id: string;
  total_weight_kg: number | null;
  reason: string | null;
  notes: string | null;
  logged_at: string;
  logged_by: { id: string; email: string } | null;
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
  pending_staff_approval: 'bg-amber-100 text-amber-800',
  approved: 'bg-white text-neutral-900',
  sent: 'bg-neutral-200 text-neutral-800',
  signed: 'bg-white text-neutral-900',
  rejected: 'bg-red-100 text-red-700',
  draft: 'bg-neutral-700 text-neutral-200',
};

const ROLE_BADGE: Record<CollaboratorRole, string> = {
  owner: 'bg-neutral-900 text-white',
  manager: 'bg-neutral-200 text-neutral-800',
  collaborator: 'bg-neutral-100 text-neutral-700',
  viewer: 'bg-neutral-100 text-neutral-500',
};

const relativeTime = (dateStr: string) => {
  const diff = Date.now() - new Date(dateStr).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days !== 1 ? 's' : ''} ago`;
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const getFoodEmoji = (item: string): string => {
  const l = item.toLowerCase();
  if (l.includes('chicken')) return '🍗';
  if (l.includes('ham') || l.includes('beef') || l.includes('steak') || l.includes('pork')) return '🥩';
  if (l.includes('fish') || l.includes('salmon') || l.includes('seafood') || l.includes('shrimp')) return '🐟';
  if (l.includes('salad')) return '🥗';
  if (l.includes('pasta') || l.includes('noodle')) return '🍝';
  if (l.includes('potato')) return '🥔';
  if (l.includes('fruit')) return '🍓';
  if (l.includes('bread') || l.includes('roll')) return '🥖';
  if (l.includes('soup')) return '🍲';
  if (l.includes('cheese')) return '🧀';
  if (l.includes('meatball') || l.includes('bbq') || l.includes('grill')) return '🍖';
  if (l.includes('slider') || l.includes('burger')) return '🍔';
  if (l.includes('cake') || l.includes('tart') || l.includes('brownie')) return '🎂';
  if (l.includes('mini') || l.includes('dessert') || l.includes('sweet') || l.includes('cookie')) return '🍬';
  if (l.includes('pizza')) return '🍕';
  if (l.includes('rice') || l.includes('grain')) return '🍚';
  if (l.includes('vegetable') || l.includes('veggie') || l.includes('veg')) return '🥦';
  if (l.includes('bar')) return '🍽️';
  if (l.includes('platter')) return '🍱';
  return '🍽️';
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
  const [eventWasteOpen, setEventWasteOpen] = useState(false);
  const [eventWasteLogs, setEventWasteLogs] = useState<EventWasteLog[]>([]);
  const pollRef = useRef<NodeJS.Timeout | undefined>(undefined);

  useEffect(() => {
    fetchProject();
    fetchCollaborators();
    fetchEventWasteLogs();
  }, [projectId]);

  const fetchEventWasteLogs = async () => {
    try {
      const data = await apiClient.get(`/projects/${projectId}/waste-logs`);
      setEventWasteLogs((Array.isArray(data) ? data : []) as EventWasteLog[]);
    } catch {
      // silent
    }
  };

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

  const filledCount = [
    project.event_date,
    project.guest_count != null,
    (summary.venue_name || summary.venue),
    summary.event_type,
    summary.service_type,
    summary.dietary_concerns,
  ].filter(Boolean).length;

  const readinessLabel = filledCount === 6 ? 'Complete' : filledCount >= 5 ? 'Almost ready' : filledCount >= 3 ? 'In progress' : 'Just started';
  const readinessColor = filledCount >= 5 ? 'text-emerald-600' : filledCount >= 3 ? 'text-amber-500' : 'text-neutral-500';

  return (
    <div className="min-h-screen bg-[#f5f4f0]">
      {/* Header */}
      <div className="bg-white border-b border-neutral-100">
        <div className="max-w-6xl mx-auto px-6 py-5">
          <div className="flex items-center gap-1.5 text-sm text-neutral-400 mb-3">
            <button
              onClick={() => router.push('/projects')}
              className="hover:text-neutral-700 transition-colors"
            >
              ← Projects
            </button>
            {summary.event_type && (
              <>
                <span>·</span>
                <span className="capitalize">{summary.event_type}</span>
              </>
            )}
          </div>
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h1 className="text-2xl font-bold text-neutral-900">{project.title}</h1>
                {project.status === 'draft' && summary.thread_id && (
                  <span className="flex items-center gap-1.5 px-2.5 py-0.5 bg-green-50 border border-green-200 rounded-full text-xs font-semibold text-green-700">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                    Live
                  </span>
                )}
              </div>
              <p className="text-sm text-neutral-400 mt-1">
                Created {new Date(project.created_at).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                {' · '}Last updated {relativeTime(project.updated_at)}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {myRole === 'owner' && (
                <button
                  onClick={handleDeleteProject}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-neutral-600 border border-neutral-200 rounded-xl hover:border-neutral-400 hover:text-neutral-900 transition-colors"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete
                </button>
              )}
              {summary.thread_id && (
                <button
                  onClick={() => router.push(`/chat?thread=${summary.thread_id}`)}
                  className="tc-btn-glossy flex items-center gap-2 px-5 py-2 text-sm font-semibold rounded-xl"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  {contract ? 'View Chat' : 'Continue Planning'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Event readiness bar */}
      <div className="max-w-6xl mx-auto px-6 pt-5 pb-2">
        <div className="bg-white rounded-xl border border-neutral-200 px-5 py-4 flex items-center gap-4">
          <span className="text-sm font-medium text-neutral-700 shrink-0">
            Event readiness — <span className="font-semibold">{filledCount} of 6 fields complete</span>
          </span>
          <div className="flex-1 h-2 bg-neutral-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-neutral-900 rounded-full transition-all"
              style={{ width: `${(filledCount / 6) * 100}%` }}
            />
          </div>
          <span className={`text-xs font-semibold shrink-0 ${readinessColor}`}>{readinessLabel}</span>
        </div>
      </div>

      {/* Main layout */}
      <div className="max-w-6xl mx-auto px-6 py-5 pb-16">
        <div className="flex flex-col lg:flex-row gap-5">

          {/* Left sidebar */}
          <div className="w-full lg:w-72 shrink-0 space-y-4">

            {/* EVENT SNAPSHOT */}
            <div className="bg-white rounded-2xl border border-neutral-100 p-5">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-5">Event Snapshot</p>
              {project.event_date ? (
                <div className="mb-4">
                  <div className="text-4xl font-black text-neutral-900 leading-none tracking-tight">
                    {new Date(project.event_date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                  </div>
                  <div className="text-sm text-neutral-500 mt-1.5">
                    {new Date(project.event_date).getFullYear()}
                  </div>
                </div>
              ) : (
                <div className="mb-4 text-sm text-neutral-400">No date set</div>
              )}
              {summary.event_type && (
                <span className="inline-block px-3 py-1 bg-neutral-900 text-white text-xs font-semibold rounded-full mb-5 capitalize">
                  {summary.event_type} Event
                </span>
              )}
              <div className="space-y-3">
                {project.guest_count != null && (
                  <div className="flex items-center gap-2.5 text-sm text-neutral-700">
                    <Users className="h-4 w-4 text-neutral-400 shrink-0" />
                    <span>{project.guest_count} guests</span>
                  </div>
                )}
                {summary.service_type && (
                  <div className="flex items-center gap-2.5 text-sm text-neutral-700">
                    <FileText className="h-4 w-4 text-neutral-400 shrink-0" />
                    <span className="capitalize">{summary.service_type}</span>
                  </div>
                )}
                {(summary.venue_name || summary.venue) && (
                  <div className="flex items-center gap-2.5 text-sm text-neutral-700">
                    <MapPin className="h-4 w-4 text-neutral-400 shrink-0" />
                    <span>{summary.venue_name || summary.venue}</span>
                  </div>
                )}
              </div>
            </div>

            {/* CONTRACT dark card */}
            {contract ? (
              <div className="bg-neutral-900 rounded-2xl p-5 text-white">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500 mb-4">Contract</p>
                <p className="text-[10px] uppercase tracking-[0.15em] text-neutral-500 mb-1">Total Amount</p>
                <p className="text-3xl font-black leading-none mb-5">
                  ${contract.total_amount?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '—'}
                </p>
                <div className="flex items-center justify-between mb-5">
                  <span className={cn('px-2.5 py-1 rounded-full text-xs font-semibold', CONTRACT_STATUS_STYLE[contract.status] ?? CONTRACT_STATUS_STYLE.draft)}>
                    {CONTRACT_STATUS_LABEL[contract.status] ?? contract.status.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs text-neutral-500 font-medium">v{contract.version_number}</span>
                </div>
                <button
                  onClick={() => router.push(`/contracts/${contract.id}`)}
                  className="w-full flex items-center justify-center gap-2 py-3 bg-white/10 hover:bg-white/15 text-white text-sm font-semibold rounded-xl transition-colors"
                >
                  <FileText className="h-3.5 w-3.5" /> View Contract
                </button>
              </div>
            ) : (
              <div className="bg-neutral-900 rounded-2xl p-5 text-white">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500 mb-3">Contract</p>
                <p className="text-sm text-neutral-400 mb-4">
                  {summary.thread_id ? 'Intake in progress…' : 'Complete the AI intake to generate a contract.'}
                </p>
                <button
                  onClick={() => router.push(summary.thread_id ? `/chat?thread=${summary.thread_id}` : '/chat')}
                  className="w-full flex items-center justify-center gap-2 py-3 bg-white text-black text-sm font-semibold rounded-xl hover:bg-neutral-100 transition-colors"
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  {summary.thread_id ? 'Continue Planning' : 'Plan This Event'}
                </button>
              </div>
            )}

            {/* CLIENT card */}
            {(summary.client_name || summary.name) && (
              <div className="bg-white rounded-2xl border border-neutral-100 p-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-neutral-200 flex items-center justify-center text-sm font-bold text-neutral-600 uppercase shrink-0">
                    {(summary.client_name || summary.name)?.[0]}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-neutral-900">{summary.client_name || summary.name}</p>
                    <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-neutral-400 mt-0.5">Client</p>
                  </div>
                </div>
                {summary.contact_email && (
                  <p className="text-xs text-neutral-400 mt-3">{summary.contact_email}</p>
                )}
              </div>
            )}

            {/* Food Waste (staff only) */}
            {isStaff && (
              <div className="bg-white rounded-2xl border border-neutral-100 p-5">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-4">Food Waste</p>
                {eventWasteLogs.length > 0 && (
                  <div className="mb-3 max-h-36 overflow-y-auto space-y-1.5">
                    {eventWasteLogs.slice(0, 4).map((w) => (
                      <div key={w.id} className="flex items-start justify-between gap-2 text-xs border-b border-neutral-100 pb-1.5 last:border-b-0">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            {w.total_weight_kg != null && <span className="font-semibold text-neutral-900">{w.total_weight_kg} kg</span>}
                            {w.reason && <span className="text-neutral-600 truncate">· {w.reason}</span>}
                          </div>
                          {w.notes && <p className="text-neutral-400 truncate">{w.notes}</p>}
                          <p className="text-[10px] text-neutral-400 mt-0.5">{new Date(w.logged_at).toLocaleDateString()}</p>
                        </div>
                        <button
                          onClick={async () => {
                            if (!confirm('Delete this waste log?')) return;
                            try {
                              await apiClient.delete(`/projects/${projectId}/waste-logs/${w.id}`);
                              setEventWasteLogs((prev) => prev.filter((x) => x.id !== w.id));
                            } catch (e: any) { toast.error(e.message || 'Failed to delete'); }
                          }}
                          className="text-neutral-300 hover:text-red-600 shrink-0 p-0.5"
                          title="Delete"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
                <div className="space-y-2">
                  <button
                    onClick={() => setEventWasteOpen(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-xl bg-neutral-900 text-white hover:bg-black transition-colors"
                  >
                    <Flame className="h-3.5 w-3.5" /> Log event waste
                  </button>
                  <button
                    onClick={() => setWasteOpen(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium rounded-xl border border-neutral-200 hover:border-neutral-400 text-neutral-600 transition-colors"
                  >
                    Log ingredient waste
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right main content */}
          <div className="flex-1 min-w-0 space-y-4">

            {/* Menu Selection */}
            {(summary.appetizers?.length > 0 || summary.main_dishes?.length > 0 || summary.desserts?.length > 0) ? (
              <div className="bg-white rounded-2xl border border-neutral-100 p-6">
                <div className="flex items-baseline justify-between mb-5">
                  <h2 className="text-base font-bold text-neutral-900">Menu Selection</h2>
                  <p className="text-xs text-neutral-400">{menuItems.length} item{menuItems.length !== 1 ? 's' : ''}</p>
                </div>

                {summary.appetizers?.length > 0 && (
                  <div className="mb-6">
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-3">Appetizers</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2">
                      {summary.appetizers.map((item: string, i: number) => (
                        <div key={i} className="rounded-xl border border-neutral-100 p-3 hover:border-neutral-200 transition-colors">
                          <span className="text-xl mb-2 block">{getFoodEmoji(item)}</span>
                          <p className="text-xs font-medium text-neutral-800 leading-snug">{item}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {summary.main_dishes?.length > 0 && (
                  <div className="mb-6">
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-3">Main Dishes</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2">
                      {summary.main_dishes.map((item: string, i: number) => (
                        <div key={i} className="rounded-xl bg-neutral-900 p-3">
                          <span className="text-xl mb-2 block">{getFoodEmoji(item)}</span>
                          <p className="text-xs font-medium text-white leading-snug">{item}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {summary.desserts?.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-3">Desserts</p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2">
                      {summary.desserts.map((item: string, i: number) => (
                        <div key={i} className="rounded-xl border border-neutral-100 p-3 hover:border-neutral-200 transition-colors">
                          <span className="text-xl mb-2 block">{getFoodEmoji(item)}</span>
                          <p className="text-xs font-medium text-neutral-800 leading-snug">{item}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : menuItems.length > 0 ? (
              <div className="bg-white rounded-2xl border border-neutral-100 p-6">
                <h2 className="text-base font-bold text-neutral-900 mb-4">Menu Selection</h2>
                <div className="flex flex-wrap gap-2">
                  {menuItems.map((item, i) => (
                    <span key={i} className="px-3 py-1.5 bg-neutral-100 rounded-xl text-xs font-medium text-neutral-700">{item}</span>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Add-ons */}
            {addons.length > 0 && (
              <div className="bg-white rounded-2xl border border-neutral-100 p-6">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400 mb-3">Add-ons</p>
                <div className="flex flex-wrap gap-2">
                  {addons.map((addon: string, i: number) => (
                    <span key={i} className="flex items-center gap-1.5 px-3 py-1.5 bg-neutral-50 border border-neutral-200 rounded-full text-xs font-medium text-neutral-700">
                      🌿 {addon}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Collaborators */}
            <div className="bg-white rounded-2xl border border-neutral-100 p-6">
              <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
                <div>
                  <h2 className="text-base font-bold text-neutral-900">Collaborators</h2>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    {collaborators.length} member{collaborators.length !== 1 ? 's' : ''}
                    {myRole === 'owner' ? ' — you are the owner' : ''}
                  </p>
                </div>
                {canManage && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={async () => { await loadJoinCode(); }}
                      className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-neutral-600 border border-neutral-200 rounded-xl hover:bg-neutral-50 hover:border-neutral-400 transition-colors"
                    >
                      <Link2 className="h-3.5 w-3.5" />
                      {joinUrl ? 'Invite Link' : 'Generate Link'}
                    </button>
                    <button
                      onClick={() => { setShowAddForm(!showAddForm); loadJoinCode(); }}
                      className="tc-btn-glossy flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-xl"
                    >
                      <UserPlus className="h-3.5 w-3.5" />
                      + Add Collaborator
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

              {collaborators.length === 0 ? (
                <div className="text-center py-8 text-neutral-400">
                  <Users className="h-8 w-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No collaborators yet. Invite someone to get started.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {collaborators.map((c) => (
                    <div key={c.user_id} className="flex items-center gap-3 p-3 rounded-xl border border-neutral-100 bg-neutral-50">
                      <div className="w-10 h-10 rounded-full bg-neutral-200 flex items-center justify-center text-sm font-bold text-neutral-600 uppercase shrink-0">
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
                        <span className={cn('text-xs px-2.5 py-1 rounded-full font-semibold shrink-0', ROLE_BADGE[c.role])}>
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

      {wasteOpen && (
        <LogWasteModal
          projectId={projectId}
          onClose={() => setWasteOpen(false)}
          onSaved={() => { setWasteOpen(false); toast.success('Waste logged'); }}
        />
      )}

      {eventWasteOpen && (
        <LogEventWasteModal
          projectId={projectId}
          onClose={() => setEventWasteOpen(false)}
          onSaved={() => { setEventWasteOpen(false); toast.success('Event waste logged'); fetchEventWasteLogs(); }}
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

function LogEventWasteModal({
  projectId,
  onClose,
  onSaved,
}: {
  projectId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [weight, setWeight] = useState('');
  const [reason, setReason] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const kg = weight ? Number(weight) : null;
    if (kg != null && (!Number.isFinite(kg) || kg < 0)) {
      toast.error('Enter a valid weight'); return;
    }
    if (kg == null && !reason.trim() && !notes.trim()) {
      toast.error('Provide at least a weight, reason, or notes'); return;
    }
    setSaving(true);
    try {
      await apiClient.post(`/projects/${projectId}/waste-logs`, {
        total_weight_kg: kg,
        reason: reason.trim() || null,
        notes: notes.trim() || null,
      });
      onSaved();
    } catch (err: any) {
      toast.error(err.message || 'Failed to log event waste');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-neutral-200">
        <div className="flex items-center justify-between p-5 border-b border-neutral-100">
          <h3 className="text-base font-semibold text-neutral-900">Log event waste</h3>
          <button onClick={onClose} className="text-neutral-400 hover:text-neutral-900">
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4">
          <p className="text-xs text-neutral-500">
            Record higher-level waste for this event — not tied to a specific inventory ingredient.
          </p>
          <div>
            <label className="text-xs font-medium text-neutral-600 mb-1 block">Total weight (kg) <span className="text-neutral-400">(optional)</span></label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-neutral-900 focus:outline-none"
              placeholder="e.g. 5.5"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-neutral-600 mb-1 block">Reason <span className="text-neutral-400">(optional)</span></label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-neutral-900 focus:outline-none"
              placeholder="Over-prepared, spoiled, uneaten leftovers…"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-neutral-600 mb-1 block">Notes <span className="text-neutral-400">(optional)</span></label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-lg border border-neutral-200 focus:border-neutral-900 focus:outline-none resize-none"
              placeholder="Optional details about what was wasted and why."
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm rounded-lg text-neutral-600 hover:bg-neutral-100">
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-neutral-900 text-white hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Logging…' : 'Log event waste'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

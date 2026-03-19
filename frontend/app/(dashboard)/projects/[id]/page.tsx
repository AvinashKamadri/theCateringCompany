"use client";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api/client';
import { projectsApi, Collaborator, CollaboratorRole } from '@/lib/api/projects';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import {
  Calendar, Users, MapPin, FileText, MessageSquare, Loader2,
  ArrowLeft, UserPlus, Trash2, Copy, Check, Crown, Shield,
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
  pending_staff_approval: 'bg-neutral-100 text-neutral-700',
  approved: 'bg-neutral-900 text-white',
  sent: 'bg-neutral-200 text-neutral-800',
  signed: 'bg-black text-white',
  rejected: 'bg-neutral-100 text-neutral-400',
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
  const projectId = params.id as string;
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

  useEffect(() => {
    fetchProject();
    fetchCollaborators();
  }, [projectId]);

  const fetchProject = async () => {
    try {
      setLoading(true);
      const data = await apiClient.get(`/projects/${projectId}`);
      setProject(data as Project);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load project');
      toast.error('Failed to load project details');
    } finally {
      setLoading(false);
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
    } catch {
      // Non-fatal
    }
  };

  const loadJoinCode = async () => {
    if (joinCode) return;
    try {
      const data = await projectsApi.getJoinCode(projectId);
      setJoinCode(data.join_code);
    } catch {
      toast.error('Could not load invite link');
    }
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
    } catch (err: any) {
      toast.error(err.message || 'Failed to update role');
    }
  };

  const handleRemove = async (userId: string, email: string) => {
    if (!confirm(`Remove ${email} from this project?`)) return;
    try {
      await projectsApi.removeCollaborator(projectId, userId);
      toast.success(`${email} removed`);
      fetchCollaborators();
    } catch (err: any) {
      toast.error(err.message || 'Failed to remove collaborator');
    }
  };

  const canManage = myRole === 'owner' || myRole === 'manager';

  const roleIcon = (role: CollaboratorRole) => {
    if (role === 'owner') return <Crown className="h-3.5 w-3.5 text-neutral-500" />;
    if (role === 'manager') return <Shield className="h-3.5 w-3.5 text-neutral-400" />;
    return null;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-5 w-5 animate-spin text-neutral-300" />
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <p className="text-sm text-neutral-500 mb-4">{error || 'Project not found'}</p>
          <button
            onClick={() => router.push('/projects')}
            className="text-sm font-medium text-neutral-900 hover:underline"
          >
            ← Back to Projects
          </button>
        </div>
      </div>
    );
  }

  const summary = (() => {
    const raw = project.ai_event_summary;
    if (!raw) return {};
    if (typeof raw === 'string') { try { return JSON.parse(raw); } catch { return {}; } }
    return raw;
  })();
  const contract = project.latestActiveContract;

  // Gather menu items from various possible fields
  const menuItems: string[] = [
    ...(Array.isArray(summary.main_dishes) ? summary.main_dishes : []),
    ...(Array.isArray(summary.appetizers) ? summary.appetizers : []),
    ...(Array.isArray(summary.desserts) ? summary.desserts : []),
    ...(Array.isArray(summary.menu_items) ? summary.menu_items : []),
  ].filter(Boolean);

  const addons: string[] = (Array.isArray(summary.addons) ? summary.addons : []).filter(Boolean);

  return (
    <div className="min-h-screen bg-neutral-50">
      {/* Page header */}
      <div className="bg-white border-b border-neutral-200">
        <div className="max-w-5xl mx-auto px-6 py-5">
          <button
            onClick={() => router.push('/projects')}
            className="flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-900 mb-4 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Projects
          </button>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-lg font-semibold text-neutral-900">{project.title}</h1>
              <p className="text-sm text-neutral-500 mt-0.5">
                Created {new Date(project.created_at).toLocaleDateString('en-US', {
                  month: 'short', day: 'numeric', year: 'numeric',
                })}
              </p>
            </div>
            {summary.thread_id && (
              <button
                onClick={() => router.push(`/chat?thread=${summary.thread_id}`)}
                className="flex items-center gap-2 px-4 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors shrink-0"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                {contract ? 'View Conversation' : 'Continue Intake'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

          {/* Main content */}
          <div className="lg:col-span-2 space-y-4">

            {/* Event Details */}
            <div className="bg-white rounded-xl border border-neutral-200 p-5">
              <h2 className="text-sm font-semibold text-neutral-900 mb-4">Event Details</h2>
              <div className="grid grid-cols-2 gap-x-6 gap-y-4">

                {(summary.event_type || summary.service_type) && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-0.5">Event type</p>
                    <p className="text-sm font-medium text-neutral-900">
                      {summary.event_type}{summary.event_type && summary.service_type ? ' · ' : ''}{summary.service_type}
                    </p>
                  </div>
                )}

                {project.event_date && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-0.5">Date</p>
                    <p className="text-sm font-medium text-neutral-900 flex items-center gap-1.5">
                      <Calendar className="h-3.5 w-3.5 text-neutral-400" />
                      {new Date(project.event_date).toLocaleDateString('en-US', {
                        weekday: 'short', month: 'short', day: 'numeric', year: 'numeric',
                      })}
                    </p>
                  </div>
                )}

                {project.guest_count != null && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-0.5">Guests</p>
                    <p className="text-sm font-medium text-neutral-900 flex items-center gap-1.5">
                      <Users className="h-3.5 w-3.5 text-neutral-400" />
                      {project.guest_count}
                    </p>
                  </div>
                )}

                {(summary.venue_name || summary.venue) && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-0.5">Venue</p>
                    <p className="text-sm font-medium text-neutral-900 flex items-center gap-1.5">
                      <MapPin className="h-3.5 w-3.5 text-neutral-400" />
                      {summary.venue_name || summary.venue}
                    </p>
                  </div>
                )}

                {summary.dietary_concerns && (
                  <div>
                    <p className="text-xs text-neutral-400 mb-0.5">Dietary</p>
                    <p className="text-sm font-medium text-neutral-900">{summary.dietary_concerns}</p>
                  </div>
                )}

                {summary.special_requests && summary.special_requests !== 'none' && (
                  <div className="col-span-2">
                    <p className="text-xs text-neutral-400 mb-0.5">Special requests</p>
                    <p className="text-sm text-neutral-700">{summary.special_requests}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Client Info */}
            {(summary.client_name || summary.contact_email || summary.contact_phone || summary.name) && (
              <div className="bg-white rounded-xl border border-neutral-200 p-5">
                <h2 className="text-sm font-semibold text-neutral-900 mb-4">Client</h2>
                <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                  {(summary.client_name || summary.name) && (
                    <div>
                      <p className="text-xs text-neutral-400 mb-0.5">Name</p>
                      <p className="text-sm font-medium text-neutral-900">{summary.client_name || summary.name}</p>
                    </div>
                  )}
                  {summary.contact_email && (
                    <div>
                      <p className="text-xs text-neutral-400 mb-0.5">Email</p>
                      <p className="text-sm font-medium text-neutral-900">{summary.contact_email}</p>
                    </div>
                  )}
                  {summary.contact_phone && (
                    <div>
                      <p className="text-xs text-neutral-400 mb-0.5">Phone</p>
                      <p className="text-sm font-medium text-neutral-900">{summary.contact_phone}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Menu */}
            {menuItems.length > 0 && (
              <div className="bg-white rounded-xl border border-neutral-200 p-5">
                <h2 className="text-sm font-semibold text-neutral-900 mb-4">Menu</h2>
                <div className="space-y-3">
                  {summary.main_dishes?.length > 0 && (
                    <div>
                      <p className="text-xs text-neutral-400 mb-1.5">Main dishes</p>
                      <div className="flex flex-wrap gap-1.5">
                        {summary.main_dishes.map((item: string, i: number) => (
                          <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-full text-xs text-neutral-700">{item}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {summary.appetizers?.length > 0 && (
                    <div>
                      <p className="text-xs text-neutral-400 mb-1.5">Appetizers</p>
                      <div className="flex flex-wrap gap-1.5">
                        {summary.appetizers.map((item: string, i: number) => (
                          <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-full text-xs text-neutral-700">{item}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {summary.desserts?.length > 0 && (
                    <div>
                      <p className="text-xs text-neutral-400 mb-1.5">Desserts</p>
                      <div className="flex flex-wrap gap-1.5">
                        {summary.desserts.map((item: string, i: number) => (
                          <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-full text-xs text-neutral-700">{item}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {summary.menu_notes && (
                    <div>
                      <p className="text-xs text-neutral-400 mb-0.5">Notes</p>
                      <p className="text-sm text-neutral-700">{summary.menu_notes}</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Add-ons */}
            {addons.length > 0 && (
              <div className="bg-white rounded-xl border border-neutral-200 p-5">
                <h2 className="text-sm font-semibold text-neutral-900 mb-3">Add-ons</h2>
                <div className="flex flex-wrap gap-1.5">
                  {addons.map((addon: string, i: number) => (
                    <span key={i} className="px-2.5 py-1 bg-neutral-100 rounded-full text-xs text-neutral-700">{addon}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">

            {/* Status */}
            <div className="bg-white rounded-xl border border-neutral-200 p-5">
              <h3 className="text-sm font-semibold text-neutral-900 mb-3">Status</h3>
              <span className={cn(
                'inline-flex px-2.5 py-1 rounded-full text-xs font-medium',
                project.status === 'active' ? 'bg-neutral-900 text-white' :
                project.status === 'completed' ? 'bg-black text-white' :
                'bg-neutral-100 text-neutral-600'
              )}>
                {project.status}
              </span>
            </div>

            {/* Contract */}
            {contract ? (
              <div className="bg-white rounded-xl border border-neutral-200 p-5">
                <h3 className="text-sm font-semibold text-neutral-900 mb-3">Contract</h3>
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-neutral-400">Status</span>
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                      CONTRACT_STATUS_STYLE[contract.status] ?? CONTRACT_STATUS_STYLE.draft
                    )}>
                      {CONTRACT_STATUS_LABEL[contract.status] ?? contract.status.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-neutral-400">Version</span>
                    <span className="text-xs font-medium text-neutral-700">v{contract.version_number}</span>
                  </div>
                  {contract.total_amount != null && (
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-neutral-400">Amount</span>
                      <span className="text-xs font-medium text-neutral-900 tabular-nums">
                        ${contract.total_amount.toLocaleString()}
                      </span>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => router.push(`/contracts/${contract.id}`)}
                  className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
                >
                  <FileText className="h-3.5 w-3.5" />
                  View Contract
                </button>
              </div>
            ) : (
              <div className="bg-white rounded-xl border border-neutral-200 p-5">
                <h3 className="text-sm font-semibold text-neutral-900 mb-1">No contract yet</h3>
                <p className="text-xs text-neutral-500 mb-4">
                  {summary.thread_id
                    ? 'The intake is in progress. Continue to complete it.'
                    : 'Complete the AI intake to generate a contract.'}
                </p>
                <button
                  onClick={() => router.push(summary.thread_id ? `/chat?thread=${summary.thread_id}` : '/chat')}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-black text-white text-sm font-medium rounded-lg hover:bg-neutral-800 transition-colors"
                >
                  {summary.thread_id ? 'Continue Intake' : 'Start AI Intake'}
                </button>
              </div>
            )}

            {/* Collaborators */}
            <div className="bg-white rounded-xl border border-neutral-200 p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-neutral-900">Collaborators</h3>
                {canManage && (
                  <button
                    onClick={() => { setShowAddForm(!showAddForm); loadJoinCode(); }}
                    className="flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-900 transition-colors"
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    Add
                  </button>
                )}
              </div>

              {/* Add form */}
              {showAddForm && canManage && (
                <form onSubmit={handleAddCollaborator} className="mb-4 space-y-2">
                  <input
                    type="email"
                    required
                    placeholder="colleague@email.com"
                    value={addEmail}
                    onChange={(e) => setAddEmail(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:ring-1 focus:ring-neutral-900 outline-none"
                    disabled={addingCollaborator}
                  />
                  <select
                    value={addRole}
                    onChange={(e) => setAddRole(e.target.value as CollaboratorRole)}
                    className="w-full px-3 py-2 text-sm border border-neutral-200 rounded-lg focus:ring-1 focus:ring-neutral-900 outline-none"
                    disabled={addingCollaborator}
                  >
                    {myRole === 'owner' && <option value="manager">Manager — full control</option>}
                    <option value="collaborator">Collaborator — can message</option>
                    <option value="viewer">Viewer — read only</option>
                  </select>
                  <button
                    type="submit"
                    disabled={addingCollaborator}
                    className="w-full py-2 text-sm bg-black text-white rounded-lg hover:bg-neutral-800 disabled:opacity-50 transition-colors"
                  >
                    {addingCollaborator ? 'Adding…' : 'Add'}
                  </button>
                </form>
              )}

              {/* Invite link */}
              {canManage && (
                <div className="mb-4">
                  <p className="text-xs text-neutral-400 mb-1.5">Invite link</p>
                  {joinUrl ? (
                    <div className="flex items-center gap-2">
                      <span className="flex-1 text-xs bg-neutral-50 border border-neutral-200 px-2.5 py-1.5 rounded-lg truncate text-neutral-600 select-all">
                        {joinUrl}
                      </span>
                      <button onClick={copyCode} className="p-1.5 text-neutral-400 hover:text-neutral-900 shrink-0 transition-colors">
                        {codeCopied ? <Check className="h-3.5 w-3.5 text-neutral-900" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={loadJoinCode}
                      className="text-xs text-neutral-500 hover:text-neutral-900 underline underline-offset-2 transition-colors"
                    >
                      Show invite link
                    </button>
                  )}
                </div>
              )}

              {/* Collaborator list */}
              <div className="space-y-2">
                {collaborators.length === 0 && (
                  <p className="text-xs text-neutral-400">No collaborators yet.</p>
                )}
                {collaborators.map((c) => (
                  <div key={c.user_id} className="flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        {roleIcon(c.role)}
                        <span className="text-sm font-medium text-neutral-900 truncate">
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
                          className="text-xs border border-neutral-200 rounded px-1.5 py-0.5 outline-none"
                        >
                          {myRole === 'owner' && <option value="manager">Manager</option>}
                          <option value="collaborator">Collaborator</option>
                          <option value="viewer">Viewer</option>
                        </select>
                        <button
                          onClick={() => handleRemove(c.user_id, c.email)}
                          className="p-1 text-neutral-300 hover:text-neutral-700 transition-colors"
                          title="Remove"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ) : (
                      <span className={cn('text-xs px-2 py-0.5 rounded-full font-medium shrink-0', ROLE_BADGE[c.role])}>
                        {c.role}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

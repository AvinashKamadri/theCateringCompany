import { apiClient } from './client';

export interface Project {
  id: string;
  name: string;
  event_type: string;
  event_date: string | null;
  event_end_date: string | null;
  guest_count: number | null;
  status: string;
  total_price: number | null;
  venue_name: string | null;
  venue_id: string | null;
  created_at: string;
  updated_at: string;
}

export const projectsApi = {
  // Get all projects for current user
  getAll: async (): Promise<Project[]> => {
    return apiClient.get('/projects');
  },

  // Get single project by ID
  getById: async (id: string): Promise<any> => {
    return apiClient.get(`/projects/${id}`);
  },

  // Create new project
  create: async (data: {
    title: string;
    eventDate?: string;
    eventEndDate?: string;
    guestCount?: number;
  }): Promise<Project> => {
    return apiClient.post('/projects', data);
  },

  // ─── Join code ────────────────────────────────────────────────────────────

  lookupByCode: async (code: string): Promise<{ found: boolean; project?: { id: string; title: string; status: string } }> => {
    return apiClient.get(`/projects/by-code/${encodeURIComponent(code)}`);
  },

  joinByCode: async (code: string): Promise<{ project: { id: string; title: string }; role: string; already_member: boolean }> => {
    return apiClient.post('/projects/join', { code });
  },

  getJoinCode: async (projectId: string): Promise<{ join_code: string }> => {
    return apiClient.get(`/projects/${projectId}/join-code`);
  },

  // ─── Collaborator management ──────────────────────────────────────────────

  listCollaborators: async (projectId: string): Promise<{ collaborators: Collaborator[] }> => {
    return apiClient.get(`/projects/${projectId}/collaborators`);
  },

  addCollaborator: async (
    projectId: string,
    email: string,
    role: CollaboratorRole = 'collaborator',
  ): Promise<{ user_id: string; email: string; role: CollaboratorRole }> => {
    return apiClient.post(`/projects/${projectId}/collaborators`, { email, role });
  },

  updateCollaboratorRole: async (
    projectId: string,
    userId: string,
    role: CollaboratorRole,
  ): Promise<{ user_id: string; role: CollaboratorRole }> => {
    return (apiClient as any).patch(`/projects/${projectId}/collaborators/${userId}`, { role });
  },

  removeCollaborator: async (
    projectId: string,
    userId: string,
  ): Promise<{ removed: boolean; user_id: string }> => {
    return (apiClient as any).delete(`/projects/${projectId}/collaborators/${userId}`);
  },
};

export type CollaboratorRole = 'owner' | 'manager' | 'collaborator' | 'viewer';

export interface Collaborator {
  user_id: string;
  email: string;
  primary_phone: string | null;
  first_name: string | null;
  last_name: string | null;
  role: CollaboratorRole;
  added_at: string;
}

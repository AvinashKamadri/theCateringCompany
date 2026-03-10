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
};

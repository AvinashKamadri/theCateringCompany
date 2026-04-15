import axios, { AxiosError } from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001';

export interface ApiError {
  message: string;
  statusCode: number;
  error?: string;
}

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

// Attach JWT from cookie as Authorization header (needed for cross-origin requests)
apiClient.interceptors.request.use((config) => {
  if (typeof document !== 'undefined') {
    const token = document.cookie.match(/app_jwt=([^;]+)/)?.[1];
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Flag to prevent multiple refresh attempts
let isRefreshing = false;
let failedQueue: any[] = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

/**
 * Clear all auth cookies client-side and wipe Zustand auth state.
 * Called before redirecting to /signin so the middleware doesn't
 * see a stale cookie and bounce the user straight back.
 */
function forceLogout() {
  if (typeof document === 'undefined') return;

  // Clear the JWT cookies for all likely paths/domains
  const cookiesToClear = ['app_jwt', 'app_refresh_token'];
  const paths = ['/', '/api'];
  for (const name of cookiesToClear) {
    for (const path of paths) {
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=${path}; SameSite=Lax`;
      document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=${path}; SameSite=None; Secure`;
    }
  }

  // Clear Zustand persisted auth state from localStorage
  try {
    localStorage.removeItem('auth-storage');
  } catch {}
}

// Response interceptor for error handling with automatic token refresh
apiClient.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as any;
    const isAuthEndpoint = originalRequest.url?.includes('/auth/');

    // If 401 and we haven't tried to refresh yet (skip auth endpoints)
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => apiClient(originalRequest))
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        await apiClient.post('/auth/refresh', {});
        processQueue(null, 'refreshed');
        isRefreshing = false;
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        isRefreshing = false;
        // Clear cookies BEFORE redirecting — prevents middleware bounce loop
        forceLogout();
        if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/signin')) {
          window.location.href = '/signin';
        }
        return Promise.reject(refreshError);
      }
    }

    // Fallback 401 handler (e.g. refresh endpoint itself returned 401)
    if (error.response?.status === 401 && !isAuthEndpoint && !originalRequest._retry) {
      forceLogout();
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/signin')) {
        window.location.href = '/signin';
      }
    }

    return Promise.reject(error.response?.data || error);
  }
);

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
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

// Response interceptor for error handling with automatic token refresh
apiClient.interceptors.response.use(
  (response) => response.data,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as any;

    // If 401 and we haven't tried to refresh yet (skip for auth endpoints themselves)
    const isAuthEndpoint = originalRequest.url?.includes('/auth/');
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => {
            return apiClient(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Try to refresh the token
        await apiClient.post('/auth/refresh', {});
        processQueue(null, 'refreshed');
        isRefreshing = false;
        // Retry the original request
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to signin
        processQueue(refreshError, null);
        isRefreshing = false;
        if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/signin')) {
          window.location.href = '/signin';
        }
        return Promise.reject(refreshError);
      }
    }

    // For other errors or if refresh also failed — but never redirect from auth endpoints
    if (error.response?.status === 401 && !isAuthEndpoint) {
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/signin')) {
        window.location.href = '/signin';
      }
    }

    return Promise.reject(error.response?.data || error);
  }
);

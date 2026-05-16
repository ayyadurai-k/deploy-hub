import axios, { type AxiosError, type AxiosRequestConfig } from "axios";
import { getAccessToken, setAccessToken } from "./authStore";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true, // refresh cookie rides on /auth/refresh
});

// ---- Bearer injector ----
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

// ---- 401 refresh interceptor with single-flight queueing ----
type FailedRequest = {
  resolve: (token: string) => void;
  reject: (err: unknown) => void;
};

let refreshing: Promise<string> | null = null;
const queue: FailedRequest[] = [];

function flushQueue(error: unknown, token: string | null) {
  queue.forEach(({ resolve, reject }) => {
    if (token) resolve(token);
    else reject(error);
  });
  queue.length = 0;
}

async function refreshAccessToken(): Promise<string> {
  // Bare axios call so we don't recurse through our own interceptor.
  const response = await axios.post<{ access: string }>(
    `${API_BASE}/auth/refresh`,
    {},
    { withCredentials: true },
  );
  return response.data.access;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (AxiosRequestConfig & { _retried?: boolean }) | undefined;
    const isUnauthorized = error.response?.status === 401;
    const isRefreshCall = original?.url?.includes("/auth/refresh");

    if (!isUnauthorized || !original || original._retried || isRefreshCall) {
      return Promise.reject(error);
    }

    original._retried = true;

    // If a refresh is already in flight, queue and wait.
    if (refreshing) {
      return new Promise((resolve, reject) => {
        queue.push({
          resolve: (token) => {
            original.headers = {
              ...original.headers,
              Authorization: `Bearer ${token}`,
            };
            resolve(api(original));
          },
          reject,
        });
      });
    }

    refreshing = refreshAccessToken();
    try {
      const newToken = await refreshing;
      setAccessToken(newToken);
      flushQueue(null, newToken);
      original.headers = {
        ...original.headers,
        Authorization: `Bearer ${newToken}`,
      };
      return api(original);
    } catch (refreshErr) {
      setAccessToken(null);
      flushQueue(refreshErr, null);
      // Surface as 401 so route guards redirect to /login.
      return Promise.reject(refreshErr);
    } finally {
      refreshing = null;
    }
  },
);

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, API_BASE } from "./api";
import { getAccessToken, setAccessToken, subscribeToken } from "./authStore";
import type { Paginated, Project, Repository, SyncResponse, User } from "./types";

export function useAccessToken(): string | null {
  const [token, setToken] = useState<string | null>(getAccessToken());
  useEffect(() => subscribeToken(() => setToken(getAccessToken())), []);
  return token;
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: async (): Promise<User> => {
      const { data } = await api.get<User>("/auth/me");
      return data;
    },
  });
}

export function useRepositories() {
  return useQuery({
    queryKey: ["repositories"],
    queryFn: async (): Promise<Paginated<Repository>> => {
      const { data } = await api.get<Paginated<Repository>>("/repositories/", {
        params: { limit: 100 },
      });
      return data;
    },
    // Return a structured failure for 409 so the UI can show the Connect-GitHub CTA.
    retry: false,
  });
}

export function useSyncRepositories() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<SyncResponse> => {
      const { data } = await api.post<SyncResponse>("/repositories/sync");
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["repositories"] });
    },
  });
}

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: async (): Promise<Paginated<Project>> => {
      const { data } = await api.get<Paginated<Project>>("/projects/", {
        params: { limit: 100 },
      });
      return data;
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      try {
        await api.post("/auth/logout");
      } finally {
        setAccessToken(null);
        qc.clear();
      }
    },
  });
}

// URL helpers — the LoginPage uses these to point window.location at the backend
// /start endpoints (browser navigation, not XHR).
export const oauthStartUrl = (provider: "google" | "github") =>
  `${API_BASE}/oauth/${provider}/start`;

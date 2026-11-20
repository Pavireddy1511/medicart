import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from "axios";

import type { ApiErrorBody, FieldError, TokenResponse } from "@/types";
import { session } from "@/utils/storage";

export const http = axios.create({
  baseURL: "/api",
  timeout: 90_000,
  headers: { Accept: "application/json" },
});

export const AUTH_EVENT = "medicart:auth-changed";

function broadcastLogout() {
  session.clear();
  window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: { user: null } }));
}

http.interceptors.request.use((config) => {
  const token = session.getAccessToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = session.getRefreshToken();
  if (!refreshToken) return null;
  try {
    const { data } = await axios.post<TokenResponse>("/api/auth/refresh", { refresh_token: refreshToken });
    session.save(data.access_token, data.refresh_token, data.user);
    return data.access_token;
  } catch {
    return null;
  }
}

const AUTH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh"];

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;
    const status = error.response?.status;
    const url = original?.url ?? "";

    if (status === 401 && original && !original._retried && !AUTH_PATHS.some((p) => url.includes(p))) {
      original._retried = true;
      refreshing = refreshing ?? refreshAccessToken().finally(() => (refreshing = null));
      const token = await refreshing;
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return http.request(original);
      }
      broadcastLogout();
    }
    return Promise.reject(error);
  },
);

export interface ApiError {
  status: number | null;
  code: string;
  message: string;
  details?: unknown;
  fieldErrors: Record<string, string>;
}

export function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const body = error.response?.data as { error?: ApiErrorBody } | undefined;
    const api = body?.error;
    const fieldErrors: Record<string, string> = {};
    if (Array.isArray(api?.details)) {
      for (const item of api.details as FieldError[]) {
        if (item && typeof item === "object" && "field" in item) fieldErrors[item.field] = item.message;
      }
    }
    if (!error.response) {
      return {
        status: null,
        code: "network",
        message: "Cannot reach the server. Check your connection and try again.",
        fieldErrors,
      };
    }
    return {
      status: error.response.status,
      code: api?.code ?? "error",
      message: api?.message ?? `Request failed (${error.response.status})`,
      details: api?.details,
      fieldErrors,
    };
  }
  return { status: null, code: "unknown", message: "Something went wrong", fieldErrors: {} };
}

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await http.request<T>(config);
  return response.data;
}

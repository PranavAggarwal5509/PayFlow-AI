import { getToken, handleUnauthorized } from "@/lib/session";
import type { ApiEnvelope, Paginated } from "@/types/api";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

export function buildQuery(params?: Query): string {
  if (!params) return "";
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function parse<T>(response: Response): Promise<ApiEnvelope<T>> {
  let body: ApiEnvelope<T> | null = null;
  try {
    body = (await response.json()) as ApiEnvelope<T>;
  } catch {
    // non-JSON error (proxy, network) — fall through to the generic message
  }
  if (response.status === 401 && !response.url.includes("/auth/login")) handleUnauthorized();
  if (!response.ok || body?.error) {
    throw new ApiError(
      body?.error?.message ?? "The server could not complete this request.",
      response.status,
      body?.error?.code ?? "unknown",
    );
  }
  return body as ApiEnvelope<T>;
}

function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>> {
  try {
    const response = await fetch(`${API_BASE}/api/v1${path}`, {
      ...init,
      headers: { Accept: "application/json", ...authHeader(), ...(init?.headers ?? {}) },
      cache: "no-store",
    });
    return await parse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Cannot reach the PayFlow API. Check that the backend is running.", 0, "network");
  }
}

export async function get<T>(path: string, params?: Query): Promise<T> {
  return (await request<T>(path + buildQuery(params))).data as T;
}

export async function getPage<T>(path: string, params?: Query): Promise<Paginated<T>> {
  const envelope = await request<T[]>(path + buildQuery(params));
  return {
    items: envelope.data ?? [],
    meta: envelope.meta ?? { page: 1, page_size: 20, total: 0, total_pages: 1 },
  };
}

export async function send<T>(
  method: "POST" | "PATCH",
  path: string,
  body?: unknown,
): Promise<T> {
  return (
    await request<T>(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  ).data as T;
}

export function uploadFile<T>(
  path: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<T> {
  // XMLHttpRequest is used because fetch() cannot report upload progress.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/v1${path}`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () =>
      reject(new ApiError("Cannot reach the PayFlow API. Check that the backend is running.", 0, "network"));
    xhr.onload = () => {
      if (xhr.status === 401) handleUnauthorized();
      try {
        const body = JSON.parse(xhr.responseText) as ApiEnvelope<T>;
        if (xhr.status >= 200 && xhr.status < 300 && !body.error) resolve(body.data as T);
        else reject(new ApiError(body.error?.message ?? "Upload failed.", xhr.status, body.error?.code ?? "unknown"));
      } catch {
        reject(new ApiError("Upload failed.", xhr.status, "unknown"));
      }
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

/** Links that the browser opens directly (PDF tabs, EventSource) cannot send headers: pass the token. */
const withToken = (url: string): string => {
  const token = getToken();
  return token ? `${url}?access_token=${encodeURIComponent(token)}` : url;
};

export const documentUrl = (invoiceId: string): string => withToken(`${API_BASE}/api/v1/invoices/${invoiceId}/document`);
export const runEventsUrl = (runId: string): string => withToken(`${API_BASE}/api/v1/runs/${runId}/events`);


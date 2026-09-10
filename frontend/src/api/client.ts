/**
 * Typed fetch wrapper.
 *
 * Same-origin in every environment (decision B1): the Vite dev server proxies
 * `/api` to FastAPI, and the Render static site rewrites `/api/*` to the API
 * service. So `credentials: "include"` sends the httpOnly refresh cookie
 * without any CORS credentials dance.
 *
 * The access token lives only in the auth store (memory). On a 401 we try the
 * refresh cookie exactly once, transparently retry the original request, and
 * fall back to clearing the session if the cookie is dead too.
 */

import type { User } from "@/features/auth/store";
import { useAuthStore } from "@/features/auth/store";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";

const REFRESH_PATH = "/api/v1/auth/refresh";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** The backend's machine-readable `error_code`, when it sent one. */
    readonly code?: string,
    /** Field-level problems, e.g. every unmet password rule (GU-01 AC-4). */
    readonly problems?: string[],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Attach the bearer token and retry through refresh on 401. Default true. */
  auth?: boolean;
}

let refreshInFlight: Promise<string | null> | null = null;

async function requestRefresh(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${REFRESH_PATH}`, {
      method: "POST",
      headers: { Accept: "application/json" },
      credentials: "include",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { access_token: string; user: User };
    useAuthStore.getState().setSession(body.access_token, body.user);
    return body.access_token;
  } catch {
    return null;
  }
}

/**
 * Single-flight: many components can 401 at once during a token expiry; they
 * should all await one refresh, not stampede the endpoint.
 */
export function refreshSession(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = requestRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function parseBody(res: Response): Promise<unknown> {
  if (res.status === 204 || res.headers.get("content-length") === "0")
    return null;
  const type = res.headers.get("content-type") ?? "";
  if (!type.includes("json")) return null;
  return res.json().catch(() => null);
}

function toApiError(
  status: number,
  method: string,
  path: string,
  payload: unknown,
): ApiError {
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (detail && typeof detail === "object") {
    const d = detail as {
      message?: string;
      error_code?: string;
      problems?: string[];
    };
    return new ApiError(
      status,
      d.message ?? `${method} ${path} failed (${status})`,
      d.error_code,
      d.problems,
    );
  }
  if (typeof detail === "string") return new ApiError(status, detail);
  return new ApiError(status, `${method} ${path} failed (${status})`);
}

async function send(
  path: string,
  opts: RequestOptions,
  useToken: boolean,
): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const token = useToken ? useAuthStore.getState().accessToken : null;
  if (token) headers.Authorization = `Bearer ${token}`;

  return fetch(`${API_BASE_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    credentials: "include",
  });
}

export async function apiRequest<T>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const method = opts.method ?? "GET";
  const withAuth = opts.auth !== false;

  let res = await send(path, opts, withAuth);

  if (res.status === 401 && withAuth) {
    const fresh = await refreshSession();
    if (fresh) {
      res = await send(path, opts, true);
    } else {
      useAuthStore.getState().clear();
    }
  }

  const payload = await parseBody(res);
  if (!res.ok) throw toApiError(res.status, method, path, payload);
  if (res.status === 204) return undefined as T;
  return payload as T;
}

// --- health (kept from M0) ------------------------------------------

export type DependencyState = "up" | "down";

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  environment: string;
  dependencies: Record<string, DependencyState>;
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>("/healthz", { auth: false });
}

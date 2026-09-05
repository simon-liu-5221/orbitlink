/**
 * Minimal typed fetch wrapper for M0.
 *
 * In dev, requests are same-origin and Vite proxies them to FastAPI. In
 * production the deployed API origin is provided via VITE_API_BASE_URL
 * (set at build time on the Render static site).
 */

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new ApiError(res.status, `GET ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export type DependencyState = "up" | "down";

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  environment: string;
  dependencies: Record<string, DependencyState>;
}

export function fetchHealth(): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/healthz");
}

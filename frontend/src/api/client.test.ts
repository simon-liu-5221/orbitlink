import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useAuthStore } from "@/features/auth/store";
import { jsonResponse } from "@/test/utils";

import { apiRequest, ApiError } from "./client";

beforeEach(() => {
  useAuthStore.setState({
    status: "authenticated",
    accessToken: "stale",
    user: null,
  });
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("attaches the bearer token from the store", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(jsonResponse({ ok: true }));
  await apiRequest("/api/v1/projects");
  const [, init] = vi.mocked(fetch).mock.calls[0];
  expect((init?.headers as Record<string, string>).Authorization).toBe(
    "Bearer stale",
  );
  expect(init?.credentials).toBe("include");
});

test("on 401 it refreshes once, adopts the new session, and retries", async () => {
  vi.mocked(fetch)
    .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401)) // original
    .mockResolvedValueOnce(
      jsonResponse({
        access_token: "fresh",
        user: { id: "u1", username: "sam" },
      }), // refresh
    )
    .mockResolvedValueOnce(jsonResponse({ items: [] })); // retry

  const result = await apiRequest<{ items: unknown[] }>("/api/v1/projects");

  expect(result).toEqual({ items: [] });
  expect(useAuthStore.getState().accessToken).toBe("fresh");
  const retryInit = vi.mocked(fetch).mock.calls[2][1];
  expect((retryInit?.headers as Record<string, string>).Authorization).toBe(
    "Bearer fresh",
  );
});

test("when refresh also fails the session is cleared and the error propagates", async () => {
  vi.mocked(fetch)
    .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
    .mockResolvedValueOnce(jsonResponse({ detail: "no cookie" }, 401)); // refresh fails

  await expect(apiRequest("/api/v1/projects")).rejects.toBeInstanceOf(ApiError);
  expect(useAuthStore.getState().status).toBe("anonymous");
  expect(useAuthStore.getState().accessToken).toBeNull();
});

test("structured error detail becomes ApiError.code / .problems", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(
    jsonResponse(
      {
        detail: {
          error_code: "WEAK_PASSWORD",
          message: "password does not meet the requirements",
          problems: [
            "must be at least 12 characters",
            "must contain at least one digit",
          ],
        },
      },
      422,
    ),
  );

  const err = await apiRequest("/api/v1/auth/register", {
    method: "POST",
    body: {},
    auth: false,
  }).catch((e: unknown) => e);

  expect(err).toBeInstanceOf(ApiError);
  expect((err as ApiError).code).toBe("WEAK_PASSWORD");
  expect((err as ApiError).problems).toHaveLength(2);
});

test("204 responses resolve to undefined without parsing a body", async () => {
  vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }));
  await expect(
    apiRequest("/api/v1/auth/logout", { method: "POST" }),
  ).resolves.toBeUndefined();
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ApiError } from "@/api/client";
import { renderWithProviders, resetAuthStore } from "@/test/utils";

import { AdminUsersPage } from "./AdminUsersPage";
import type { AdminUser } from "./api";
import { adminApi } from "./api";

vi.mock("./api", () => ({
  adminApi: { listUsers: vi.fn(), suspend: vi.fn(), unsuspend: vi.fn() },
}));
vi.mock("@/features/auth/session", () => ({ signOut: vi.fn() }));

function user(over: Partial<AdminUser> = {}): AdminUser {
  return {
    id: crypto.randomUUID(),
    email: "a@example.com",
    username: "alice",
    role: "user",
    email_verified: true,
    subscription_plan: "trial",
    suspended_at: null,
    created_at: new Date().toISOString(),
    ...over,
  };
}

beforeEach(() => {
  resetAuthStore();
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

test("renders every user returned, not just the caller's own data", async () => {
  vi.mocked(adminApi.listUsers).mockResolvedValue([
    user({ username: "alice" }),
    user({ username: "bob" }),
  ]);

  renderWithProviders(<AdminUsersPage />);

  expect(await screen.findByText("alice")).toBeInTheDocument();
  expect(screen.getByText("bob")).toBeInTheDocument();
});

test("typing a search term re-queries with it", async () => {
  vi.mocked(adminApi.listUsers).mockResolvedValue([]);
  renderWithProviders(<AdminUsersPage />);
  await screen.findByText(/no users match/i);

  await userEvent.type(
    screen.getByPlaceholderText(/search by email/i),
    "alice",
  );

  await waitFor(() =>
    expect(adminApi.listUsers).toHaveBeenLastCalledWith("alice"),
  );
});

test("suspending a user calls the API and refetches", async () => {
  const target = user({ username: "troublemaker" });
  vi.mocked(adminApi.listUsers).mockResolvedValue([target]);
  vi.mocked(adminApi.suspend).mockResolvedValue({
    ...target,
    suspended_at: new Date().toISOString(),
  });

  renderWithProviders(<AdminUsersPage />);
  const row = (await screen.findByText("troublemaker")).closest("li")!;
  await userEvent.click(within(row).getByRole("button", { name: "Suspend" }));

  await waitFor(() => expect(adminApi.suspend).toHaveBeenCalledWith(target.id));
});

test("a suspended user shows a badge and a Restore button", async () => {
  vi.mocked(adminApi.listUsers).mockResolvedValue([
    user({ username: "suspended-one", suspended_at: new Date().toISOString() }),
  ]);

  renderWithProviders(<AdminUsersPage />);
  const row = (await screen.findByText("suspended-one")).closest("li")!;
  expect(within(row).getByText("suspended")).toBeInTheDocument();
  expect(
    within(row).getByRole("button", { name: "Restore" }),
  ).toBeInTheDocument();
});

test("trying to suspend an admin shows the backend's error message", async () => {
  const target = user({ username: "other-admin", role: "admin" });
  vi.mocked(adminApi.listUsers).mockResolvedValue([target]);
  vi.mocked(adminApi.suspend).mockRejectedValue(
    new ApiError(409, "cannot suspend another admin"),
  );

  renderWithProviders(<AdminUsersPage />);
  const row = (await screen.findByText("other-admin")).closest("li")!;
  await userEvent.click(within(row).getByRole("button", { name: "Suspend" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /cannot suspend another admin/i,
  );
});

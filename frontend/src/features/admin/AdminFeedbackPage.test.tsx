import { screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { renderWithProviders, resetAuthStore } from "@/test/utils";

import { AdminFeedbackPage } from "./AdminFeedbackPage";
import type { AdminFeedback } from "./api";
import { adminApi } from "./api";

vi.mock("./api", () => ({ adminApi: { listFeedback: vi.fn() } }));
vi.mock("@/features/auth/session", () => ({ signOut: vi.fn() }));

function feedback(over: Partial<AdminFeedback> = {}): AdminFeedback {
  return {
    id: crypto.randomUUID(),
    rating: 4,
    comment: "pretty good",
    created_at: new Date().toISOString(),
    user_email: "a@example.com",
    username: "alice",
    ...over,
  };
}

beforeEach(() => {
  resetAuthStore();
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

test("shows every submission with who sent it", async () => {
  vi.mocked(adminApi.listFeedback).mockResolvedValue([
    feedback({ username: "alice", comment: "love it" }),
    feedback({ username: "bob", comment: null, rating: 2 }),
  ]);

  renderWithProviders(<AdminFeedbackPage />);

  expect(await screen.findByText("love it")).toBeInTheDocument();
  expect(screen.getByText(/alice/)).toBeInTheDocument();
  expect(screen.getByText(/bob/)).toBeInTheDocument();
});

test("an empty inbox says so instead of showing a blank list", async () => {
  vi.mocked(adminApi.listFeedback).mockResolvedValue([]);
  renderWithProviders(<AdminFeedbackPage />);
  expect(await screen.findByText(/no feedback yet/i)).toBeInTheDocument();
});

test("a submission with no comment doesn't render an empty paragraph", async () => {
  vi.mocked(adminApi.listFeedback).mockResolvedValue([
    feedback({ comment: null }),
  ]);
  renderWithProviders(<AdminFeedbackPage />);
  await screen.findByText(/alice/);
  // 5 stars rendered, no stray empty comment text
  expect(screen.getByLabelText("4 out of 5 stars")).toBeInTheDocument();
});

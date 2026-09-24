import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ApiError } from "@/api/client";

import { ErrorBoundary } from "./ErrorBoundary";

function Bomb({ error }: { error: Error }): never {
  throw error;
}

test("renders children normally when nothing throws", () => {
  render(
    <ErrorBoundary>
      <p>all good</p>
    </ErrorBoundary>,
  );
  expect(screen.getByText("all good")).toBeInTheDocument();
});

test("catches a render error and shows a fallback instead of a blank page", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <ErrorBoundary>
      <Bomb error={new Error("boom")} />
    </ErrorBoundary>,
  );
  expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /reload/i }),
  ).toBeInTheDocument();
});

test("shows the request id when the thrown error is an ApiError that has one", () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  render(
    <ErrorBoundary>
      <Bomb
        error={new ApiError(500, "boom", "INTERNAL_ERROR", undefined, "req-1")}
      />
    </ErrorBoundary>,
  );
  expect(screen.getByText("req-1")).toBeInTheDocument();
});

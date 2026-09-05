import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { HealthStatus } from "./HealthStatus";

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

test("renders backend status and dependency dots when healthy", async () => {
  vi.mocked(fetch).mockResolvedValue(
    new Response(
      JSON.stringify({
        status: "ok",
        version: "0.1.0",
        environment: "development",
        dependencies: { database: "up", redis: "up" },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  render(<HealthStatus />, { wrapper });

  expect(await screen.findByTestId("health-status")).toBeInTheDocument();
  expect(screen.getByText("ok")).toBeInTheDocument();
  expect(screen.getByText("database")).toBeInTheDocument();
  expect(screen.getByText("redis")).toBeInTheDocument();
});

test("shows an error message when the backend is unreachable", async () => {
  vi.mocked(fetch).mockRejectedValue(new Error("network down"));

  render(<HealthStatus />, { wrapper });

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Backend unreachable",
  );
});

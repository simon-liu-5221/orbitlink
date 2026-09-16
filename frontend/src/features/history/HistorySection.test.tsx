import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { HistorySection } from "./HistorySection";

const analysisHistory = vi.fn();
const analysisForecast = vi.fn().mockResolvedValue({
  required_history: 5,
  sentiment: {
    available: false,
    predicted_next: null,
    mae: null,
    points_used: 0,
  },
  participants: {
    available: false,
    predicted_next: null,
    mae: null,
    points_used: 0,
  },
  communities: {
    available: false,
    predicted_next: null,
    mae: null,
    points_used: 0,
  },
});

vi.mock("@/features/projects/api", () => ({
  projectsApi: {
    analysisHistory: (id: string) => analysisHistory(id),
    analysisForecast: (id: string) => analysisForecast(id),
  },
}));

function renderWithClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <HistorySection projectId="p1" />
    </QueryClientProvider>,
  );
}

test("no analyses yet shows the empty state (spec: 專案沒有任何分析)", async () => {
  analysisHistory.mockResolvedValueOnce([]);
  renderWithClient();
  await waitFor(() =>
    expect(screen.getByText(/nothing to compare/i)).toBeInTheDocument(),
  );
});

test("fewer than 2 analyses shows the need-more-history message (AC-6)", async () => {
  analysisHistory.mockResolvedValueOnce([
    {
      id: "a1",
      created_at: "2026-01-01T00:00:00Z",
      node_count: 5,
      community_count: 1,
      insufficient_data: false,
      sentiment_index: 0.1,
    },
  ]);
  renderWithClient();
  await waitFor(() =>
    expect(screen.getByText(/need more history/i)).toBeInTheDocument(),
  );
});

test("2+ analyses renders the three trend charts and the comparison table", async () => {
  analysisHistory.mockResolvedValueOnce([
    {
      id: "a1",
      created_at: "2026-01-01T00:00:00Z",
      node_count: 5,
      community_count: 1,
      insufficient_data: false,
      sentiment_index: 0.1,
    },
    {
      id: "a2",
      created_at: "2026-01-08T00:00:00Z",
      node_count: 8,
      community_count: 2,
      insufficient_data: false,
      sentiment_index: 0.3,
    },
  ]);
  renderWithClient();

  await waitFor(() =>
    expect(screen.getByTestId("history-trend-Sentiment")).toBeInTheDocument(),
  );
  expect(screen.getByTestId("history-trend-Participants")).toBeInTheDocument();
  expect(screen.getByTestId("history-trend-Communities")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(3);
  await waitFor(() =>
    expect(screen.getByTestId("forecast-sentiment")).toBeInTheDocument(),
  );
});

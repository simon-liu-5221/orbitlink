import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { AnalysisChartsSection } from "./AnalysisChartsSection";

vi.mock("@/features/projects/api", () => ({
  projectsApi: { analysisGraph: vi.fn().mockResolvedValue({ nodes: [], edges: [] }) },
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

test("insufficient_data shows one empty state and renders none of the three charts (AC-7)", () => {
  renderWithClient(
    <AnalysisChartsSection
      analysisId="a1"
      sentimentSummary={{ distribution: { positive: 50, neutral: 30, negative: 20 } }}
      insufficientData
    />,
  );

  expect(screen.getByText(/not enough data for charts/i)).toBeInTheDocument();
  expect(screen.queryByTestId("sentiment-distribution-chart")).not.toBeInTheDocument();
  expect(screen.queryByTestId("sentiment-trend-chart")).not.toBeInTheDocument();
  expect(screen.queryByTestId("engagement-scatter-chart")).not.toBeInTheDocument();
});

test("with enough data, the distribution and trend sections render", () => {
  renderWithClient(
    <AnalysisChartsSection
      analysisId="a1"
      sentimentSummary={{ distribution: { positive: 50, neutral: 30, negative: 20 } }}
      insufficientData={false}
    />,
  );

  expect(screen.getByText("Sentiment distribution")).toBeInTheDocument();
  expect(screen.getByTestId("sentiment-distribution-chart")).toBeInTheDocument();
});

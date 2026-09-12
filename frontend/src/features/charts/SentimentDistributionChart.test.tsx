import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import { SentimentDistributionChart } from "./SentimentDistributionChart";

test("renders all three category labels (AC-1)", () => {
  render(
    <SentimentDistributionChart
      distribution={{ positive: 60, neutral: 30, negative: 10 }}
    />,
  );
  // scoped to the chart itself — Recharts also renders an off-screen span it
  // uses to measure tick-label width, which would otherwise double-match
  const chart = within(screen.getByTestId("sentiment-distribution-chart"));
  expect(chart.getByText("Positive")).toBeInTheDocument();
  expect(chart.getByText("Neutral")).toBeInTheDocument();
  expect(chart.getByText("Negative")).toBeInTheDocument();
});

test("shows an empty state instead of a blank chart when everything is zero", () => {
  render(
    <SentimentDistributionChart
      distribution={{ positive: 0, neutral: 0, negative: 0 }}
    />,
  );
  expect(screen.getByText(/no sentiment data/i)).toBeInTheDocument();
  expect(
    screen.queryByTestId("sentiment-distribution-chart"),
  ).not.toBeInTheDocument();
});

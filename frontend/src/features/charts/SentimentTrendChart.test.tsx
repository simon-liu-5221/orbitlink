import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { SentimentTrendChart } from "./SentimentTrendChart";

test("shows an empty state for no trend data instead of a blank chart (AC-4)", () => {
  render(<SentimentTrendChart trend={[]} trendBucket="day" />);
  expect(screen.getByText(/not enough time-spread data/i)).toBeInTheDocument();
  expect(screen.queryByTestId("sentiment-trend-chart")).not.toBeInTheDocument();
});

test("renders the chart when there is trend data", () => {
  render(
    <SentimentTrendChart
      trend={[
        { bucketStart: "2026-01-01T00:00:00Z", meanScore: 0.4, count: 3 },
      ]}
      trendBucket="day"
    />,
  );
  expect(screen.getByTestId("sentiment-trend-chart")).toBeInTheDocument();
});

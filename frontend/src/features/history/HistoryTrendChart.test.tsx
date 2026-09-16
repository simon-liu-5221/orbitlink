import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { HistoryTrendChart } from "./HistoryTrendChart";

test("renders a labeled chart for the given points", () => {
  render(
    <HistoryTrendChart
      title="Participants"
      points={[
        { label: "Jan 1", value: 5 },
        { label: "Jan 8", value: 12 },
      ]}
      color="#16a34a"
    />,
  );
  expect(screen.getByText("Participants")).toBeInTheDocument();
  expect(screen.getByTestId("history-trend-Participants")).toBeInTheDocument();
});

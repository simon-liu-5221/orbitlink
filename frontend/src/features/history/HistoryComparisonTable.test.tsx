import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import { HistoryComparisonTable } from "./HistoryComparisonTable";

test("renders one row per analysis with all AC-8 columns", () => {
  render(
    <HistoryComparisonTable
      rows={[
        {
          id: "a1",
          label: "Jan 1",
          nodeCount: 5,
          communityCount: 1,
          sentimentIndex: 0.42,
          insufficientData: false,
        },
        {
          id: "a2",
          label: "Jan 8",
          nodeCount: 8,
          communityCount: 2,
          sentimentIndex: null,
          insufficientData: true,
        },
      ]}
    />,
  );

  const rows = screen.getAllByRole("row");
  expect(rows).toHaveLength(3); // header + 2 data rows

  const row1 = within(rows[1]);
  expect(row1.getByText("Jan 1")).toBeInTheDocument();
  expect(row1.getByText("5")).toBeInTheDocument();
  expect(row1.getByText("0.42")).toBeInTheDocument();
  expect(row1.getByText("OK")).toBeInTheDocument();

  const row2 = within(rows[2]);
  expect(row2.getByText("—")).toBeInTheDocument();
  expect(row2.getByText(/insufficient/i)).toBeInTheDocument();
});

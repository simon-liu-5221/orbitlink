import { screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { Job } from "./api";
import { renderWithProviders } from "@/test/utils";

import { JobProgress } from "./JobProgress";

function job(overrides: Partial<Job>): Job {
  return {
    id: "j1",
    project_id: "p1",
    status: "queued",
    progress: 0,
    error_code: null,
    error_message: null,
    analysis_id: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    started_at: null,
    finished_at: null,
    ...overrides,
  };
}

test("a running job shows the named stage and a progress bar", () => {
  renderWithProviders(
    <JobProgress job={job({ status: "analyzing", progress: 62 })} />,
  );
  expect(screen.getByText("Analyzing")).toBeInTheDocument();
  const bar = screen.getByRole("progressbar");
  expect(bar).toHaveAttribute("aria-valuenow", "62");
});

test("a failed job explains a known error code in plain language", () => {
  renderWithProviders(
    <JobProgress
      job={job({ status: "failed", error_code: "COMMENTS_DISABLED" })}
    />,
  );
  expect(screen.getByText(/comments are turned off/i)).toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
});

test("a completed job links to its results", () => {
  renderWithProviders(
    <JobProgress
      job={job({ status: "completed", progress: 100, analysis_id: "a9" })}
    />,
  );
  expect(screen.getByRole("link", { name: /view results/i })).toHaveAttribute(
    "href",
    "/analyses/a9",
  );
});

test("cancel is offered only while the job is live", () => {
  const { rerender } = renderWithProviders(
    <JobProgress job={job({ status: "fetching" })} onCancel={() => {}} />,
  );
  expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();

  rerender(
    <JobProgress
      job={job({ status: "completed", analysis_id: "a1" })}
      onCancel={() => {}}
    />,
  );
  expect(
    screen.queryByRole("button", { name: "Cancel" }),
  ).not.toBeInTheDocument();
});

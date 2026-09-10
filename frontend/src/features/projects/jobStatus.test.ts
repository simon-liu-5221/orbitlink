import { expect, test } from "vitest";

import { isLive, isTerminal, jobStageLabel, LIVE_STATUSES } from "./jobStatus";

test("every live status has a human label and the ADR-0002 order", () => {
  expect(LIVE_STATUSES).toEqual([
    "queued",
    "fetching",
    "building_graph",
    "analyzing",
    "persisting",
  ]);
  expect(jobStageLabel("building_graph")).toBe("Building the network");
  expect(jobStageLabel("fetching")).toBe("Fetching comments");
});

test("terminal vs live classification", () => {
  expect(isTerminal("completed")).toBe(true);
  expect(isTerminal("failed")).toBe(true);
  expect(isTerminal("cancelled")).toBe(true);
  expect(isTerminal("analyzing")).toBe(false);

  expect(isLive("analyzing")).toBe(true);
  expect(isLive("completed")).toBe(false);
});

test("an unknown status falls back to itself", () => {
  expect(jobStageLabel("weird_new_state")).toBe("weird_new_state");
});

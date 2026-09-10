/**
 * Job status presentation — the named stages from ADR-0002:
 *   queued -> fetching -> building_graph -> analyzing -> persisting -> completed
 * with failed / cancelled as the other terminals. The progress bar shows a
 * real number the worker reports; the label makes it legible (PR-01 step 6:
 * "具名階段, 不是單純轉圈").
 */

export const LIVE_STATUSES = [
  "queued",
  "fetching",
  "building_graph",
  "analyzing",
  "persisting",
] as const;

export const TERMINAL_STATUSES = ["completed", "failed", "cancelled"] as const;

export type JobStatusValue =
  (typeof LIVE_STATUSES)[number] | (typeof TERMINAL_STATUSES)[number];

const LABELS: Record<string, string> = {
  queued: "Queued",
  fetching: "Fetching comments",
  building_graph: "Building the network",
  analyzing: "Analyzing",
  persisting: "Saving results",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function jobStageLabel(status: string): string {
  return LABELS[status] ?? status;
}

export function isTerminal(status: string): boolean {
  return (TERMINAL_STATUSES as readonly string[]).includes(status);
}

export function isLive(status: string): boolean {
  return (LIVE_STATUSES as readonly string[]).includes(status);
}

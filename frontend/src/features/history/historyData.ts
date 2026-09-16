import type { AnalysisHistoryEntry } from "@/features/projects/api";

/**
 * AN-06 phase 1 — pure trend/comparison-table builders. No Recharts, no DOM,
 * so these can be unit-tested without a browser (spec AC-6/AC-7/AC-8).
 */

//: AC-6 — a single point (or none) can't show a trend; the UI shows a
//: "need more history" message instead of a misleading one-point line.
export function hasEnoughHistory(analyses: AnalysisHistoryEntry[]): boolean {
  return analyses.length >= 2;
}

export interface TrendPoint {
  label: string;
  value: number;
}

function formatLabel(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

//: AC-2/AC-7 — sentiment index is included for every analysis that has one;
//: rows with no computable index (missing/malformed distribution) are simply
//: not plottable points, not zeros.
export function buildSentimentTrend(
  analyses: AnalysisHistoryEntry[],
): TrendPoint[] {
  return analyses
    .filter((a) => a.sentiment_index !== null)
    .map((a) => ({
      label: formatLabel(a.created_at),
      value: a.sentiment_index as number,
    }));
}

//: AC-7 — participant count stays meaningful even on an insufficient-data
//: analysis, so nothing is excluded here.
export function buildParticipantsTrend(
  analyses: AnalysisHistoryEntry[],
): TrendPoint[] {
  return analyses.map((a) => ({
    label: formatLabel(a.created_at),
    value: a.node_count,
  }));
}

//: AC-7 — community count is meaningless when the analysis didn't have
//: enough data to build a real graph, so those rows are dropped here (and
//: only here).
export function buildCommunityTrend(
  analyses: AnalysisHistoryEntry[],
): TrendPoint[] {
  return analyses
    .filter((a) => !a.insufficient_data)
    .map((a) => ({
      label: formatLabel(a.created_at),
      value: a.community_count,
    }));
}

export interface ComparisonRow {
  id: string;
  label: string;
  nodeCount: number;
  communityCount: number;
  sentimentIndex: number | null;
  insufficientData: boolean;
}

//: AC-8 — every analysis gets one row, regardless of insufficient_data; the
//: flag itself is a column so the table can flag it, not hide it.
export function buildComparisonRows(
  analyses: AnalysisHistoryEntry[],
): ComparisonRow[] {
  return analyses.map((a) => ({
    id: a.id,
    label: formatLabel(a.created_at),
    nodeCount: a.node_count,
    communityCount: a.community_count,
    sentimentIndex: a.sentiment_index,
    insufficientData: a.insufficient_data,
  }));
}

import { useQuery } from "@tanstack/react-query";

import { Spinner } from "@/components/ui";
import { projectsApi } from "@/features/projects/api";

import { ForecastSection } from "./ForecastSection";
import { HistoryComparisonTable } from "./HistoryComparisonTable";
import {
  buildCommunityTrend,
  buildComparisonRows,
  buildParticipantsTrend,
  buildSentimentTrend,
  hasEnoughHistory,
} from "./historyData";
import { HistoryTrendChart } from "./HistoryTrendChart";

/**
 * AN-06 phase 1 — trend charts + comparison table for a project's own
 * analysis history. Lives on the project detail page (comparisons never
 * cross projects — out of scope per the spec).
 */
export function HistorySection({ projectId }: { projectId: string }) {
  const history = useQuery({
    queryKey: ["projects", projectId, "analyses"],
    queryFn: () => projectsApi.analysisHistory(projectId),
  });

  if (history.isLoading) {
    return (
      <div className="flex justify-center p-8 text-slate-400">
        <Spinner />
      </div>
    );
  }

  const analyses = history.data ?? [];

  if (analyses.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No analyses yet — nothing to compare.
      </p>
    );
  }

  if (!hasEnoughHistory(analyses)) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
        Need more history to show a trend — run another analysis on this
        project.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <HistoryTrendChart
          title="Sentiment"
          points={buildSentimentTrend(analyses)}
          color="#2563eb"
          yDomain={[-1, 1]}
          valueFormatter={(v) => v.toFixed(2)}
        />
        <HistoryTrendChart
          title="Participants"
          points={buildParticipantsTrend(analyses)}
          color="#16a34a"
        />
        <HistoryTrendChart
          title="Communities"
          points={buildCommunityTrend(analyses)}
          color="#7c3aed"
        />
      </div>
      <HistoryComparisonTable rows={buildComparisonRows(analyses)} />
      <ForecastSection projectId={projectId} />
    </div>
  );
}

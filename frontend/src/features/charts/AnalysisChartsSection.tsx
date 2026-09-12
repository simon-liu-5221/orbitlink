import { useQuery } from "@tanstack/react-query";

import { Spinner } from "@/components/ui";
import { projectsApi } from "@/features/projects/api";

import { EngagementScatterChart } from "./EngagementScatterChart";
import { parseSentimentSummary } from "./sentimentSummary";
import { SentimentDistributionChart } from "./SentimentDistributionChart";
import { SentimentTrendChart } from "./SentimentTrendChart";

/**
 * The three PR-13 charts. Distribution and trend need nothing beyond the
 * sentiment_summary the result page already has; the scatter plot shares the
 * same ["analyses", id, "graph"] query PR-10's network graph uses, so opening
 * both sections costs one fetch, not two.
 */
export function AnalysisChartsSection({
  analysisId,
  sentimentSummary,
  insufficientData,
}: {
  analysisId: string;
  sentimentSummary: unknown;
  insufficientData: boolean;
}) {
  const graph = useQuery({
    queryKey: ["analyses", analysisId, "graph"],
    queryFn: () => projectsApi.analysisGraph(analysisId),
  });

  if (insufficientData) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
        Not enough data for charts.
      </p>
    );
  }

  const summary = parseSentimentSummary(sentimentSummary);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="rounded-lg border border-slate-200 p-3">
        <h3 className="mb-2 text-xs font-medium text-slate-500">
          Sentiment distribution
        </h3>
        <SentimentDistributionChart distribution={summary.distribution} />
      </div>
      <div className="rounded-lg border border-slate-200 p-3">
        <h3 className="mb-2 text-xs font-medium text-slate-500">
          Sentiment over time
        </h3>
        <SentimentTrendChart
          trend={summary.trend}
          trendBucket={summary.trendBucket}
        />
      </div>
      <div className="rounded-lg border border-slate-200 p-3 sm:col-span-2">
        <h3 className="mb-2 text-xs font-medium text-slate-500">
          Comments vs. engagement
        </h3>
        {graph.isLoading ? (
          <div className="flex h-56 items-center justify-center text-slate-400">
            <Spinner />
          </div>
        ) : (
          <EngagementScatterChart nodes={graph.data?.nodes ?? []} />
        )}
      </div>
    </div>
  );
}

import { lazy, Suspense } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { FormError, Spinner } from "@/components/ui";

import { projectsApi } from "./api";

// Cytoscape is a heavy dependency (PERF-05: LCP < 2.5s) — keep it out of the
// initial bundle and only fetch it when someone actually opens a result page.
const NetworkGraphSection = lazy(() =>
  import("@/features/graph/NetworkGraphSection").then((m) => ({
    default: m.NetworkGraphSection,
  })),
);

/**
 * The analysis result page: summary stats, the interactive network graph
 * (PR-10), and the top-participant lists. Charts (sentiment distribution /
 * trend / engagement scatter) are a separate, smaller M4 PR.
 */
export function AnalysisResultPage() {
  const { analysisId = "" } = useParams();
  const analysis = useQuery({
    queryKey: ["analyses", analysisId],
    queryFn: () => projectsApi.analysis(analysisId),
    retry: (count, err) =>
      !(err instanceof ApiError && err.status === 404) && count < 2,
  });

  if (analysis.isLoading) {
    return (
      <AppShell>
        <div className="flex justify-center p-12 text-slate-400">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  if (analysis.isError || !analysis.data) {
    return (
      <AppShell>
        <div className="mx-auto max-w-3xl p-6">
          <FormError>That analysis isn't available.</FormError>
        </div>
      </AppShell>
    );
  }

  const a = analysis.data;
  const stats: [string, string | number][] = [
    ["Participants", a.node_count],
    ["Connections", a.edge_count],
    ["Communities", a.community_count],
    ["Comments analysed", a.fetched_comment_count],
    ["Modularity", a.modularity?.toFixed(3) ?? "—"],
  ];

  return (
    <AppShell>
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <Link
          to={`/projects/${a.project_id}`}
          className="text-sm text-slate-500 underline"
        >
          ← Back to project
        </Link>

        <h1 className="text-xl font-semibold text-slate-900">
          Analysis result
        </h1>

        {(a.insufficient_data || a.weak_structure || a.approximated) && (
          <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {a.insufficient_data && (
              <p>Not enough data for a reliable network.</p>
            )}
            {a.weak_structure && <p>The community structure is weak.</p>}
            {a.approximated && (
              <p>Some centrality measures were approximated for size.</p>
            )}
          </div>
        )}

        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {stats.map(([label, value]) => (
            <div key={label} className="rounded-lg border border-slate-200 p-3">
              <dt className="text-xs text-slate-500">{label}</dt>
              <dd className="text-lg font-semibold text-slate-900">{value}</dd>
            </div>
          ))}
        </dl>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Network graph
          </h2>
          <Suspense
            fallback={
              <div className="flex justify-center p-8 text-slate-400">
                <Spinner />
              </div>
            }
          >
            <NetworkGraphSection analysisId={a.id} />
          </Suspense>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Top influencers
          </h2>
          <ol className="space-y-1 text-sm">
            {a.top_influencers.map((node) => (
              <li key={node.pseudonym} className="flex justify-between">
                <span className="font-mono text-slate-700">
                  {node.pseudonym}
                </span>
                <span className="text-slate-400">
                  rank {node.influence_rank} · PR {node.pagerank.toFixed(3)}
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Most engaged
          </h2>
          <ol className="space-y-1 text-sm">
            {a.top_engaged.map((node) => (
              <li key={node.pseudonym} className="flex justify-between">
                <span className="font-mono text-slate-700">
                  {node.pseudonym}
                </span>
                <span className="text-slate-400">
                  {node.comment_count} comments · {node.like_count} likes
                </span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </AppShell>
  );
}

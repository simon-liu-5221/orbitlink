import type { Core } from "cytoscape";
import { useCallback, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button, Spinner } from "@/components/ui";
import { nodesToCsv } from "@/features/export/csv";
import { downloadBlob, downloadText } from "@/features/export/downloadFile";
import { projectsApi } from "@/features/projects/api";

import { GraphControls } from "./GraphControls";
import {
  computeDegrees,
  DEFAULT_FILTERS,
  filterGraph,
  sampleTopByPagerank,
} from "./graphData";
import type { GraphFilters } from "./graphData";
import { NetworkGraph } from "./NetworkGraph";
import { NodeDetailPanel } from "./NodeDetailPanel";

/** Everything needed to view an analysis' network graph (spec PR-10). */
export function NetworkGraphSection({ analysisId }: { analysisId: string }) {
  const graph = useQuery({
    queryKey: ["analyses", analysisId, "graph"],
    queryFn: () => projectsApi.analysisGraph(analysisId),
  });

  const [filters, setFilters] = useState<GraphFilters>(DEFAULT_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const cyRef = useRef<Core | null>(null);
  const onCyReady = useCallback((cy: Core | null) => {
    cyRef.current = cy;
  }, []);

  const sampled = useMemo(() => {
    if (!graph.data) return null;
    return sampleTopByPagerank(graph.data.nodes, graph.data.edges);
  }, [graph.data]);

  const degrees = useMemo(
    () => computeDegrees(sampled?.edges ?? []),
    [sampled],
  );

  const filtered = useMemo(() => {
    if (!sampled) return null;
    return filterGraph(sampled.nodes, sampled.edges, filters, degrees);
  }, [sampled, filters, degrees]);

  const communities = useMemo(() => {
    if (!sampled) return [];
    const seen = new Set<number>();
    for (const node of sampled.nodes) {
      if (node.community_index !== null) seen.add(node.community_index);
    }
    return [...seen].sort((a, b) => a - b);
  }, [sampled]);

  const maxDegree = useMemo(
    () => Math.max(0, ...[...degrees.values()]),
    [degrees],
  );

  const selectedNode =
    filtered?.nodes.find((n) => n.pseudonym === selected) ?? null;

  const onSelectNode = useCallback(
    (pseudonym: string) => setSelected(pseudonym),
    [],
  );

  const analysisIdShort = analysisId.slice(0, 8);

  function exportImage() {
    const cy = cyRef.current;
    if (!cy) return;
    cy.png({
      output: "blob-promise",
      full: true,
      scale: 2,
      bg: "#ffffff",
    }).then((blob) =>
      downloadBlob(blob, `orbitlink-graph-${analysisIdShort}.png`),
    );
  }

  function exportCsv() {
    if (!filtered) return;
    downloadText(
      nodesToCsv(filtered.nodes),
      `orbitlink-nodes-${analysisIdShort}.csv`,
      "text/csv;charset=utf-8",
    );
  }

  if (graph.isLoading) {
    return (
      <div className="flex justify-center p-8 text-slate-400">
        <Spinner />
      </div>
    );
  }

  if (graph.isError || !graph.data) {
    return (
      <p className="text-sm text-slate-500">Couldn't load the network graph.</p>
    );
  }

  if (graph.data.node_count === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
        Not enough data to build a network graph.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {sampled?.sampled ? (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Showing the top {sampled.nodes.length.toLocaleString()} of{" "}
            {sampled.totalNodeCount.toLocaleString()} participants by influence,
            to keep the graph responsive.
          </p>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={exportImage}
            disabled={!filtered || filtered.nodes.length === 0}
          >
            Export image
          </Button>
          <Button
            variant="secondary"
            onClick={exportCsv}
            disabled={!filtered || filtered.nodes.length === 0}
          >
            Export data (CSV)
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_16rem]">
        <div>
          {filtered && filtered.nodes.length > 0 ? (
            <NetworkGraph
              nodes={filtered.nodes}
              edges={filtered.edges}
              onSelectNode={onSelectNode}
              onCyReady={onCyReady}
            />
          ) : (
            <div className="flex h-[32rem] items-center justify-center rounded-lg border border-dashed border-slate-300 text-sm text-slate-500">
              No nodes match the current filters.
            </div>
          )}
        </div>
        <div className="space-y-3">
          <GraphControls
            filters={filters}
            onChange={setFilters}
            communities={communities}
            maxDegree={maxDegree}
          />
          <NodeDetailPanel
            node={selectedNode}
            degree={
              selectedNode ? (degrees.get(selectedNode.pseudonym) ?? 0) : 0
            }
            onClose={() => setSelected(null)}
          />
        </div>
      </div>
    </div>
  );
}

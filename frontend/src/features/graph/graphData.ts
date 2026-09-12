/**
 * Pure data-prep for the network graph (spec PR-10). No Cytoscape, no DOM — so
 * the CAP-03 degradation, the filters, and the visual encodings are all
 * testable without a canvas.
 */

import type { components } from "@/api/schema";

export type GraphNode = components["schemas"]["NodeOut"];
export type GraphEdge = components["schemas"]["GraphEdgeOut"];

/** Nodes past this count are sampled for rendering (PERF-04 / CAP-03). */
export const MAX_RENDERED_NODES = 2000;

export interface SampledGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** True when the graph was too big and got cut down. */
  sampled: boolean;
  /** The node count before sampling — for the "top X of Y" banner. */
  totalNodeCount: number;
}

/**
 * Keep only the strongest `maxNodes` participants (by PageRank) and the edges
 * between them. `nodes` is assumed already sorted by pagerank descending (the
 * API returns it that way), but this doesn't rely on that.
 */
export function sampleTopByPagerank(
  nodes: GraphNode[],
  edges: GraphEdge[],
  maxNodes: number = MAX_RENDERED_NODES,
): SampledGraph {
  if (nodes.length <= maxNodes) {
    return { nodes, edges, sampled: false, totalNodeCount: nodes.length };
  }
  const kept = [...nodes]
    .sort((a, b) => b.pagerank - a.pagerank)
    .slice(0, maxNodes);
  const keptIds = new Set(kept.map((n) => n.pseudonym));
  const keptEdges = edges.filter(
    (e) => keptIds.has(e.source) && keptIds.has(e.target),
  );
  return {
    nodes: kept,
    edges: keptEdges,
    sampled: true,
    totalNodeCount: nodes.length,
  };
}

/** Each edge counts once toward each endpoint it touches (direction ignored). */
export function computeDegrees(edges: GraphEdge[]): Map<string, number> {
  const degrees = new Map<string, number>();
  for (const edge of edges) {
    degrees.set(edge.source, (degrees.get(edge.source) ?? 0) + 1);
    degrees.set(edge.target, (degrees.get(edge.target) ?? 0) + 1);
  }
  return degrees;
}

export interface GraphFilters {
  minDegree: number;
  /** Communities to hide. Empty = show every community. */
  excludedCommunities: ReadonlySet<number>;
  /**
   * `null` = the sentiment filter hasn't been touched — show everything,
   * including nodes with no sentiment score. A concrete [min, max] excludes
   * anything outside it, including null-sentiment nodes (PR-10 AC-12).
   */
  sentimentRange: readonly [number, number] | null;
}

export const DEFAULT_FILTERS: GraphFilters = {
  minDegree: 0,
  excludedCommunities: new Set(),
  sentimentRange: null,
};

/** Applies the degree / community / sentiment filters and drops orphaned edges. */
export function filterGraph(
  nodes: GraphNode[],
  edges: GraphEdge[],
  filters: GraphFilters,
  degrees: Map<string, number>,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const kept = nodes.filter((node) => {
    if ((degrees.get(node.pseudonym) ?? 0) < filters.minDegree) return false;
    if (
      node.community_index !== null &&
      filters.excludedCommunities.has(node.community_index)
    ) {
      return false;
    }
    if (filters.sentimentRange) {
      if (node.avg_sentiment === null) return false;
      const [min, max] = filters.sentimentRange;
      if (node.avg_sentiment < min || node.avg_sentiment > max) return false;
    }
    return true;
  });
  const keptIds = new Set(kept.map((n) => n.pseudonym));
  const keptEdges = edges.filter(
    (e) => keptIds.has(e.source) && keptIds.has(e.target),
  );
  return { nodes: kept, edges: keptEdges };
}

/** A palette distinct enough at a glance; stable because it's indexed, not random. */
const COMMUNITY_PALETTE = [
  "#2563eb", // blue
  "#dc2626", // red
  "#16a34a", // green
  "#d97706", // amber
  "#7c3aed", // violet
  "#0891b2", // cyan
  "#db2777", // pink
  "#65a30d", // lime
];
const NO_COMMUNITY_COLOR = "#94a3b8"; // slate — for nodes with no community assigned

export function communityColor(communityIndex: number | null): string {
  if (communityIndex === null) return NO_COMMUNITY_COLOR;
  return COMMUNITY_PALETTE[communityIndex % COMMUNITY_PALETTE.length];
}

const MIN_RADIUS = 8;
const MAX_RADIUS = 40;

/**
 * Area-proportional sizing (sqrt of the pagerank ratio) so visual weight
 * tracks influence without the biggest node swallowing the canvas.
 */
export function nodeRadius(pagerank: number, maxPagerank: number): number {
  if (maxPagerank <= 0) return MIN_RADIUS;
  const ratio = Math.max(0, Math.min(1, pagerank / maxPagerank));
  return MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * Math.sqrt(ratio);
}

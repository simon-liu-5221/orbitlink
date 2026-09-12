/**
 * Node data as CSV (spec PR-11). Pure — no DOM, no download mechanics — so the
 * escaping rules are testable without touching a file.
 */

import type { GraphNode } from "@/features/graph/graphData";

const HEADERS = [
  "pseudonym",
  "community_index",
  "pagerank",
  "betweenness",
  "engagement_score",
  "comment_count",
  "like_count",
  "avg_sentiment",
  "influence_rank",
] as const;

/** RFC 4180: quote a field that contains a comma, quote, or newline; double up quotes inside it. */
function escapeCsvField(value: string): string {
  if (/[",\r\n]/.test(value)) {
    return `"${value.replace(/"/g, '""')}"`;
  }
  return value;
}

function cellText(value: string | number | null): string {
  return value === null ? "" : String(value);
}

function rowFor(node: GraphNode): string {
  return [
    node.pseudonym,
    node.community_index,
    node.pagerank,
    node.betweenness,
    node.engagement_score,
    node.comment_count,
    node.like_count,
    node.avg_sentiment,
    node.influence_rank,
  ]
    .map((value) => escapeCsvField(cellText(value)))
    .join(",");
}

/**
 * `nodes` should already reflect whatever the user is currently looking at —
 * post CAP-03 sampling and post-filter (PR-11 AC-2) — the caller decides that,
 * this just formats whatever list it's given.
 */
export function nodesToCsv(nodes: GraphNode[]): string {
  return [HEADERS.join(","), ...nodes.map(rowFor)].join("\r\n");
}

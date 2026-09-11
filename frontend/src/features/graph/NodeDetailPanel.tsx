import { communityColor } from "./graphData";
import type { GraphNode } from "./graphData";

/** The click-through detail sidebar (PR-10 AC-9). Pure presentation — the
 * caller owns which node (if any) is selected. */
export function NodeDetailPanel({
  node,
  degree,
  onClose,
}: {
  node: GraphNode | null;
  degree: number;
  onClose: () => void;
}) {
  if (!node) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-400">
        Click a node to see its details.
      </div>
    );
  }

  const rows: [string, string][] = [
    [
      "Community",
      node.community_index !== null ? `#${node.community_index}` : "none",
    ],
    ["Connections", String(degree)],
    ["Engagement score", node.engagement_score.toFixed(2)],
    [
      "Average sentiment",
      node.avg_sentiment === null ? "—" : node.avg_sentiment.toFixed(2),
    ],
    ["Comments", String(node.comment_count)],
    ["Likes received", String(node.like_count)],
    ["PageRank", node.pagerank.toFixed(4)],
  ];

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: communityColor(node.community_index) }}
            aria-hidden
          />
          <span className="font-mono text-sm font-medium text-slate-900">
            {node.pseudonym}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-slate-400 hover:text-slate-600"
          aria-label="Close details"
        >
          ✕
        </button>
      </div>
      <dl className="space-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4">
            <dt className="text-slate-500">{label}</dt>
            <dd className="font-medium text-slate-800">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

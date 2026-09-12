import { communityColor } from "@/features/graph/graphData";
import type { GraphNode } from "@/features/graph/graphData";

export interface ScatterPoint {
  pseudonym: string;
  comments: number;
  engagement: number;
  color: string;
}

/**
 * One point per participant: comment volume (x) vs computed engagement score
 * (y), colored by the same community palette as the network graph — reusing
 * `communityColor` keeps the two views visually consistent.
 */
export function buildEngagementScatterData(nodes: GraphNode[]): ScatterPoint[] {
  return nodes.map((node) => ({
    pseudonym: node.pseudonym,
    comments: node.comment_count,
    engagement: node.engagement_score,
    color: communityColor(node.community_index),
  }));
}

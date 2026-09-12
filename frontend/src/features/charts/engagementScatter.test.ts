import { expect, test } from "vitest";

import type { GraphNode } from "@/features/graph/graphData";

import { buildEngagementScatterData } from "./engagementScatter";

function node(pseudonym: string, over: Partial<GraphNode> = {}): GraphNode {
  return {
    pseudonym,
    community_index: null,
    comment_count: 0,
    like_count: 0,
    replies_received: 0,
    engagement_score: 0,
    engagement_breakdown: {},
    pagerank: 0,
    betweenness: 0,
    influence_rank: null,
    avg_sentiment: null,
    ...over,
  };
}

test("maps comment count and engagement score onto x/y (AC-5)", () => {
  const points = buildEngagementScatterData([
    node("a", { comment_count: 3, engagement_score: 7.5 }),
  ]);
  expect(points).toEqual([
    { pseudonym: "a", comments: 3, engagement: 7.5, color: expect.any(String) },
  ]);
});

test("uses the same community palette as the network graph", () => {
  const points = buildEngagementScatterData([
    node("a", { community_index: 2 }),
    node("b", { community_index: 2 }),
    node("c", { community_index: 5 }),
  ]);
  expect(points[0].color).toBe(points[1].color); // same community, same color
  expect(points[0].color).not.toBe(points[2].color);
});

test("an empty node list produces an empty scatter (AC-6)", () => {
  expect(buildEngagementScatterData([])).toEqual([]);
});

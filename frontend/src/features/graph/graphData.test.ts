import { expect, test } from "vitest";

import {
  communityColor,
  computeDegrees,
  DEFAULT_FILTERS,
  filterGraph,
  type GraphEdge,
  type GraphFilters,
  type GraphNode,
  nodeRadius,
  sampleTopByPagerank,
} from "./graphData";

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

function edge(source: string, target: string, weight = 1): GraphEdge {
  return { source, target, weight };
}

// --- AC-5 / AC-6 : sampling --------------------------------------------

test("a graph at or under the cap is returned untouched", () => {
  const nodes = [node("a", { pagerank: 0.5 }), node("b", { pagerank: 0.3 })];
  const edges = [edge("a", "b")];

  const result = sampleTopByPagerank(nodes, edges, 2);

  expect(result).toEqual({ nodes, edges, sampled: false, totalNodeCount: 2 });
});

test("a graph over the cap keeps only the top-N by pagerank, and only edges between kept nodes", () => {
  const nodes = [
    node("low", { pagerank: 0.1 }),
    node("high", { pagerank: 0.9 }),
    node("mid", { pagerank: 0.5 }),
  ];
  const edges = [edge("high", "mid"), edge("high", "low"), edge("mid", "low")];

  const result = sampleTopByPagerank(nodes, edges, 2);

  expect(result.sampled).toBe(true);
  expect(result.totalNodeCount).toBe(3);
  expect(result.nodes.map((n) => n.pseudonym)).toEqual(["high", "mid"]);
  expect(result.edges).toEqual([edge("high", "mid")]); // both endpoints kept
});

// --- degree ------------------------------------------------------------

test("degree counts every edge touching a node, either direction", () => {
  const degrees = computeDegrees([
    edge("a", "b"),
    edge("c", "a"),
    edge("b", "c"),
  ]);
  expect(degrees.get("a")).toBe(2);
  expect(degrees.get("b")).toBe(2);
  expect(degrees.get("c")).toBe(2);
});

test("a node with no edges has no entry", () => {
  const degrees = computeDegrees([edge("a", "b")]);
  expect(degrees.has("isolated")).toBe(false);
});

// --- AC-10 / AC-11 / AC-12 : filters ------------------------------------

test("default filters keep everything", () => {
  const nodes = [node("a"), node("b", { community_index: 2 })];
  const { nodes: kept } = filterGraph(nodes, [], DEFAULT_FILTERS, new Map());
  expect(kept).toHaveLength(2);
});

test("min degree excludes low-connection nodes (AC-10)", () => {
  const nodes = [node("hub"), node("leaf")];
  const edges = [edge("hub", "leaf"), edge("hub", "other")];
  const degrees = computeDegrees(edges);
  const filters: GraphFilters = { ...DEFAULT_FILTERS, minDegree: 2 };

  const { nodes: kept } = filterGraph(nodes, edges, filters, degrees);

  expect(kept.map((n) => n.pseudonym)).toEqual(["hub"]);
});

test("excluded communities are filtered out; nodes with no community are unaffected (AC-11)", () => {
  const nodes = [
    node("in-a", { community_index: 0 }),
    node("in-b", { community_index: 1 }),
    node("unassigned", { community_index: null }),
  ];
  const filters: GraphFilters = {
    ...DEFAULT_FILTERS,
    excludedCommunities: new Set([0]),
  };

  const { nodes: kept } = filterGraph(nodes, [], filters, new Map());

  expect(kept.map((n) => n.pseudonym)).toEqual(["in-b", "unassigned"]);
});

test("a sentiment range excludes out-of-range AND null-sentiment nodes (AC-12)", () => {
  const nodes = [
    node("happy", { avg_sentiment: 0.8 }),
    node("sad", { avg_sentiment: -0.8 }),
    node("unscored", { avg_sentiment: null }),
  ];
  const filters: GraphFilters = { ...DEFAULT_FILTERS, sentimentRange: [0, 1] };

  const { nodes: kept } = filterGraph(nodes, [], filters, new Map());

  expect(kept.map((n) => n.pseudonym)).toEqual(["happy"]);
});

test("null-sentiment nodes still show when the sentiment filter is untouched (AC-12)", () => {
  const nodes = [node("unscored", { avg_sentiment: null })];
  const { nodes: kept } = filterGraph(nodes, [], DEFAULT_FILTERS, new Map());
  expect(kept).toHaveLength(1);
});

test("filtering drops edges whose endpoint got filtered out", () => {
  const nodes = [node("hub"), node("leaf")];
  const edges = [edge("hub", "leaf")];
  const filters: GraphFilters = { ...DEFAULT_FILTERS, minDegree: 5 };

  const { edges: keptEdges } = filterGraph(
    nodes,
    edges,
    filters,
    computeDegrees(edges),
  );

  expect(keptEdges).toEqual([]);
});

// --- AC-7 / AC-8 : visual encoding --------------------------------------

test("the same community always gets the same color across calls", () => {
  expect(communityColor(3)).toBe(communityColor(3));
});

test("different communities get different colors, and null gets a neutral one", () => {
  expect(communityColor(0)).not.toBe(communityColor(1));
  expect(communityColor(null)).not.toBe(communityColor(0));
});

test("higher pagerank means a larger radius", () => {
  const small = nodeRadius(0.1, 1.0);
  const large = nodeRadius(0.9, 1.0);
  expect(large).toBeGreaterThan(small);
});

test("radius never falls below the floor even at zero pagerank", () => {
  expect(nodeRadius(0, 1.0)).toBeGreaterThan(0);
});

test("a graph with everyone at pagerank 0 doesn't divide by zero", () => {
  expect(() => nodeRadius(0, 0)).not.toThrow();
  expect(Number.isFinite(nodeRadius(0, 0))).toBe(true);
});

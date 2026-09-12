import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";

import type { GraphNode } from "@/features/graph/graphData";

import { EngagementScatterChart } from "./EngagementScatterChart";

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

test("shows an empty state when there are no participants (AC-6)", () => {
  render(<EngagementScatterChart nodes={[]} />);
  expect(screen.getByText(/no participant data/i)).toBeInTheDocument();
  expect(
    screen.queryByTestId("engagement-scatter-chart"),
  ).not.toBeInTheDocument();
});

test("renders the chart with axis labels when there is data (AC-5)", () => {
  render(<EngagementScatterChart nodes={[node("a", { comment_count: 3 })]} />);
  const chart = within(screen.getByTestId("engagement-scatter-chart"));
  expect(chart.getByText("Comments")).toBeInTheDocument();
  expect(chart.getByText("Engagement")).toBeInTheDocument();
});

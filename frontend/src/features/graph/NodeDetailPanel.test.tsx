import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import type { GraphNode } from "./graphData";
import { NodeDetailPanel } from "./NodeDetailPanel";

const node: GraphNode = {
  pseudonym: "a1b2c3d4",
  community_index: 2,
  comment_count: 5,
  like_count: 12,
  replies_received: 3,
  engagement_score: 7.25,
  engagement_breakdown: {},
  pagerank: 0.0421,
  betweenness: 0.1,
  influence_rank: 1,
  avg_sentiment: 0.6,
};

test("prompts to click a node when nothing is selected", () => {
  render(<NodeDetailPanel node={null} degree={0} onClose={() => {}} />);
  expect(screen.getByText(/click a node/i)).toBeInTheDocument();
});

test("shows the selected node's details (AC-9)", () => {
  render(<NodeDetailPanel node={node} degree={4} onClose={() => {}} />);

  expect(screen.getByText("a1b2c3d4")).toBeInTheDocument();
  expect(screen.getByText("#2")).toBeInTheDocument(); // community
  expect(screen.getByText("4")).toBeInTheDocument(); // degree
  expect(screen.getByText("7.25")).toBeInTheDocument(); // engagement
  expect(screen.getByText("0.60")).toBeInTheDocument(); // sentiment
  expect(screen.getByText("5")).toBeInTheDocument(); // comments
  expect(screen.getByText("12")).toBeInTheDocument(); // likes
});

test("a node with no sentiment score shows a placeholder, not a crash", () => {
  render(
    <NodeDetailPanel
      node={{ ...node, avg_sentiment: null }}
      degree={0}
      onClose={() => {}}
    />,
  );
  expect(screen.getByText("—")).toBeInTheDocument();
});

test("close calls the handler", async () => {
  const onClose = vi.fn();
  render(<NodeDetailPanel node={node} degree={1} onClose={onClose} />);
  await userEvent.click(screen.getByRole("button", { name: /close/i }));
  expect(onClose).toHaveBeenCalled();
});

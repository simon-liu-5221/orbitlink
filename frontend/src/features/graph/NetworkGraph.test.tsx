import { render } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import type { GraphEdge, GraphNode } from "./graphData";
import { NetworkGraph } from "./NetworkGraph";

/**
 * jsdom has no real canvas, so Cytoscape's renderer can't run here. Instead we
 * mock the library entirely and assert the wiring: the right elements go in,
 * and a tap on a node reaches our callback with its id. The visual encoding
 * itself (color/size formulas) is covered without any of this in
 * graphData.test.ts.
 */
const handlers: Record<
  string,
  (evt: { target: { id: () => string } }) => void
> = {};
const fakeCore = {
  on: vi.fn(
    (event: string, _selector: string, handler: (evt: unknown) => void) => {
      handlers[event] = handler as never;
    },
  ),
  destroy: vi.fn(),
};
const cytoscapeMock = vi.fn((_config: unknown) => fakeCore);

vi.mock("cytoscape", () => ({
  default: (config: unknown) => cytoscapeMock(config),
}));

function node(pseudonym: string, over: Partial<GraphNode> = {}): GraphNode {
  return {
    pseudonym,
    community_index: 0,
    comment_count: 0,
    like_count: 0,
    replies_received: 0,
    engagement_score: 0,
    engagement_breakdown: {},
    pagerank: 0.1,
    betweenness: 0,
    influence_rank: null,
    avg_sentiment: null,
    ...over,
  };
}

beforeEach(() => {
  cytoscapeMock.mockClear();
  fakeCore.on.mockClear();
  fakeCore.destroy.mockClear();
});
afterEach(() => vi.restoreAllMocks());

test("builds one Cytoscape element per node and per edge", () => {
  const nodes = [node("a"), node("b")];
  const edges: GraphEdge[] = [{ source: "a", target: "b", weight: 2 }];

  render(<NetworkGraph nodes={nodes} edges={edges} onSelectNode={() => {}} />);

  const call = cytoscapeMock.mock.calls[0][0] as {
    elements: { data: Record<string, unknown> }[];
  };
  const ids = call.elements.map((el) => el.data.id);
  expect(ids).toEqual(["a", "b", "a->b"]);
});

test("a tap on a node calls onSelectNode with that node's pseudonym", () => {
  const onSelectNode = vi.fn();
  render(
    <NetworkGraph
      nodes={[node("clicked-one")]}
      edges={[]}
      onSelectNode={onSelectNode}
    />,
  );

  handlers.tap({ target: { id: () => "clicked-one" } });

  expect(onSelectNode).toHaveBeenCalledWith("clicked-one");
});

test("unmounting destroys the Cytoscape instance", () => {
  const { unmount } = render(
    <NetworkGraph nodes={[node("a")]} edges={[]} onSelectNode={() => {}} />,
  );
  unmount();
  expect(fakeCore.destroy).toHaveBeenCalled();
});

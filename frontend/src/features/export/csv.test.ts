import { expect, test } from "vitest";

import type { GraphNode } from "@/features/graph/graphData";

import { nodesToCsv } from "./csv";

function node(pseudonym: string, over: Partial<GraphNode> = {}): GraphNode {
  return {
    pseudonym,
    community_index: 0,
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

test("header row is fixed and in order (AC-3)", () => {
  const [header] = nodesToCsv([]).split("\r\n");
  expect(header).toBe(
    "pseudonym,community_index,pagerank,betweenness,engagement_score,comment_count,like_count,avg_sentiment,influence_rank",
  );
});

test("one row per node, in the given order (AC-2 — caller decides which nodes)", () => {
  const csv = nodesToCsv([node("aaa"), node("bbb")]);
  const rows = csv.split("\r\n").slice(1);
  expect(rows).toHaveLength(2);
  expect(rows[0]).toMatch(/^aaa,/);
  expect(rows[1]).toMatch(/^bbb,/);
});

test("null fields become empty, not the literal string 'null' (AC-3)", () => {
  const csv = nodesToCsv([
    node("a", { community_index: null, avg_sentiment: null }),
  ]);
  const [, row] = csv.split("\r\n");
  const fields = row.split(",");
  expect(fields[1]).toBe(""); // community_index
  expect(fields[7]).toBe(""); // avg_sentiment
});

test("a field containing a comma is quoted (AC-4)", () => {
  // pseudonyms are hex and never contain commas in practice, but the
  // escaper itself must be correct for any string field
  const csv = nodesToCsv([node("has,comma")]);
  expect(csv).toContain('"has,comma"');
});

test("a field containing a double quote is quoted and the quote is doubled (AC-4)", () => {
  const csv = nodesToCsv([node('has"quote')]);
  expect(csv).toContain('"has""quote"');
});

test("a field containing a newline is quoted (AC-4)", () => {
  const csv = nodesToCsv([node("has\nnewline")]);
  expect(csv).toContain('"has\nnewline"');
});

test("an empty node list produces just the header", () => {
  expect(nodesToCsv([])).toBe(
    "pseudonym,community_index,pagerank,betweenness,engagement_score,comment_count,like_count,avg_sentiment,influence_rank",
  );
});

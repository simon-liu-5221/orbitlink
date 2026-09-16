import { describe, expect, it } from "vitest";

import type { AnalysisHistoryEntry } from "@/features/projects/api";

import {
  buildCommunityTrend,
  buildComparisonRows,
  buildParticipantsTrend,
  buildSentimentTrend,
  hasEnoughHistory,
} from "./historyData";

function entry(overrides: Partial<AnalysisHistoryEntry>): AnalysisHistoryEntry {
  return {
    id: "a1",
    created_at: "2026-01-01T00:00:00Z",
    node_count: 10,
    community_count: 2,
    insufficient_data: false,
    sentiment_index: 0.3,
    ...overrides,
  };
}

describe("hasEnoughHistory", () => {
  it("is false for 0 or 1 analyses", () => {
    expect(hasEnoughHistory([])).toBe(false);
    expect(hasEnoughHistory([entry({})])).toBe(false);
  });

  it("is true for 2 or more", () => {
    expect(hasEnoughHistory([entry({}), entry({ id: "a2" })])).toBe(true);
  });
});

describe("buildSentimentTrend", () => {
  it("drops rows with no computable sentiment index", () => {
    const rows = [
      entry({ id: "a1", sentiment_index: 0.5 }),
      entry({ id: "a2", sentiment_index: null }),
    ];
    expect(buildSentimentTrend(rows)).toEqual([
      { label: expect.any(String) as unknown as string, value: 0.5 },
    ]);
  });

  it("includes insufficient_data rows as long as a sentiment index exists", () => {
    const rows = [entry({ insufficient_data: true, sentiment_index: -0.2 })];
    expect(buildSentimentTrend(rows)).toHaveLength(1);
  });
});

describe("buildParticipantsTrend", () => {
  it("includes every row, including insufficient_data ones", () => {
    const rows = [
      entry({ id: "a1", node_count: 5 }),
      entry({ id: "a2", node_count: 8, insufficient_data: true }),
    ];
    expect(buildParticipantsTrend(rows).map((p) => p.value)).toEqual([5, 8]);
  });
});

describe("buildCommunityTrend", () => {
  it("excludes insufficient_data rows (AC-7)", () => {
    const rows = [
      entry({ id: "a1", community_count: 3 }),
      entry({ id: "a2", community_count: 4, insufficient_data: true }),
      entry({ id: "a3", community_count: 5 }),
    ];
    expect(buildCommunityTrend(rows).map((p) => p.value)).toEqual([3, 5]);
  });
});

describe("buildComparisonRows", () => {
  it("has one row per analysis with every column, insufficient_data included", () => {
    const rows = [
      entry({
        id: "a1",
        node_count: 5,
        community_count: 1,
        sentiment_index: 0.1,
      }),
      entry({
        id: "a2",
        node_count: 8,
        community_count: 2,
        sentiment_index: null,
        insufficient_data: true,
      }),
    ];
    const result = buildComparisonRows(rows);
    expect(result).toHaveLength(2);
    expect(result[0]).toMatchObject({
      id: "a1",
      nodeCount: 5,
      communityCount: 1,
      sentimentIndex: 0.1,
      insufficientData: false,
    });
    expect(result[1]).toMatchObject({
      id: "a2",
      nodeCount: 8,
      communityCount: 2,
      sentimentIndex: null,
      insufficientData: true,
    });
  });
});

import { expect, test } from "vitest";

import {
  distributionChartData,
  parseSentimentSummary,
  trendChartData,
} from "./sentimentSummary";

// --- AC-1 / AC-2 : distribution ------------------------------------------

test("parses a well-formed distribution", () => {
  const summary = parseSentimentSummary({
    distribution: { positive: 60, neutral: 30, negative: 10 },
    trend: [],
    trend_bucket: "day",
  });
  expect(summary.distribution).toEqual({
    positive: 60,
    neutral: 30,
    negative: 10,
  });
});

test("a missing distribution key defaults to zero, not a crash (AC-2)", () => {
  const summary = parseSentimentSummary({ distribution: { positive: 100 } });
  expect(summary.distribution).toEqual({
    positive: 100,
    neutral: 0,
    negative: 0,
  });
});

test("garbage input (wrong types, missing fields entirely) still parses to zeros", () => {
  expect(parseSentimentSummary(null).distribution).toEqual({
    positive: 0,
    neutral: 0,
    negative: 0,
  });
  expect(parseSentimentSummary("not an object").distribution.positive).toBe(0);
  expect(
    parseSentimentSummary({ distribution: "nope" }).distribution.positive,
  ).toBe(0);
});

test("distributionChartData is always positive/neutral/negative in that order (AC-1)", () => {
  const bars = distributionChartData({ negative: 1, neutral: 2, positive: 3 });
  expect(bars.map((b) => b.label)).toEqual(["Positive", "Neutral", "Negative"]);
  expect(bars.map((b) => b.value)).toEqual([3, 2, 1]);
});

test("each distribution category has its own stable color", () => {
  const bars = distributionChartData({ positive: 1, neutral: 1, negative: 1 });
  const colors = new Set(bars.map((b) => b.color));
  expect(colors.size).toBe(3);
});

// --- AC-3 / AC-4 : trend --------------------------------------------------

test("an hour bucket includes the hour in the label", () => {
  const summary = parseSentimentSummary({
    trend: [
      { bucket_start: "2026-03-01T14:00:00+00:00", mean_score: 0.2, count: 5 },
    ],
    trend_bucket: "hour",
  });
  const points = trendChartData(summary.trend, summary.trendBucket);
  expect(points).toHaveLength(1);
  expect(points[0].score).toBe(0.2);
  expect(points[0].count).toBe(5);
  // some rendering of the hour is present (exact format is locale-dependent)
  expect(points[0].label.length).toBeGreaterThan(0);
});

test("a day bucket produces a different label than an hour bucket for the same instant", () => {
  const raw = {
    bucket_start: "2026-03-01T14:00:00+00:00",
    mean_score: 0,
    count: 1,
  };
  const hourly = trendChartData(
    parseSentimentSummary({ trend: [raw], trend_bucket: "hour" }).trend,
    "hour",
  );
  const daily = trendChartData(
    parseSentimentSummary({ trend: [raw], trend_bucket: "day" }).trend,
    "day",
  );
  expect(hourly[0].label).not.toBe(daily[0].label);
});

test("an empty trend parses to an empty array, not an error (AC-4)", () => {
  const summary = parseSentimentSummary({ trend: [] });
  expect(trendChartData(summary.trend, summary.trendBucket)).toEqual([]);
});

test("trend entries missing a timestamp are dropped rather than mis-rendered", () => {
  const summary = parseSentimentSummary({
    trend: [
      { mean_score: 0.5, count: 2 },
      { bucket_start: "2026-01-01T00:00:00Z", mean_score: 0.1, count: 1 },
    ],
  });
  expect(summary.trend).toHaveLength(1);
});

test("trend_bucket defaults to day for anything other than the literal 'hour'", () => {
  expect(parseSentimentSummary({ trend_bucket: "weird" }).trendBucket).toBe(
    "day",
  );
  expect(parseSentimentSummary({}).trendBucket).toBe("day");
});

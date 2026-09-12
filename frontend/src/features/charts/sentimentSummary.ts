/**
 * The backend's `sentiment_summary` is `dict[str, Any]` (AN-03) — no strict
 * schema, so this is where we defensively turn it into something typed before
 * any chart touches it. Pure: no Recharts, no DOM.
 */

export interface SentimentDistribution {
  positive: number;
  neutral: number;
  negative: number;
}

export interface SentimentTrendPoint {
  bucketStart: string;
  meanScore: number;
  count: number;
}

export type TrendBucket = "hour" | "day";

export interface SentimentSummary {
  distribution: SentimentDistribution;
  trend: SentimentTrendPoint[];
  trendBucket: TrendBucket;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

/** Never throws — a malformed or missing field just falls back to empty/zero. */
export function parseSentimentSummary(raw: unknown): SentimentSummary {
  const obj =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  const dist =
    obj.distribution && typeof obj.distribution === "object"
      ? (obj.distribution as Record<string, unknown>)
      : {};

  const trendRaw = Array.isArray(obj.trend) ? obj.trend : [];
  const trend: SentimentTrendPoint[] = trendRaw
    .filter((p): p is Record<string, unknown> => !!p && typeof p === "object")
    .map((p) => ({
      bucketStart: typeof p.bucket_start === "string" ? p.bucket_start : "",
      meanScore: asNumber(p.mean_score),
      count: asNumber(p.count),
    }))
    .filter((p) => p.bucketStart !== "");

  return {
    distribution: {
      positive: asNumber(dist.positive),
      neutral: asNumber(dist.neutral),
      negative: asNumber(dist.negative),
    },
    trend,
    trendBucket: obj.trend_bucket === "hour" ? "hour" : "day",
  };
}

// --- chart-ready shapes -------------------------------------------------

export interface DistributionBar {
  label: string;
  value: number;
  color: string;
}

const DISTRIBUTION_COLORS = {
  positive: "#16a34a",
  neutral: "#94a3b8",
  negative: "#dc2626",
} as const;

/** Fixed positive/neutral/negative order regardless of object key order. */
export function distributionChartData(
  distribution: SentimentDistribution,
): DistributionBar[] {
  return [
    {
      label: "Positive",
      value: distribution.positive,
      color: DISTRIBUTION_COLORS.positive,
    },
    {
      label: "Neutral",
      value: distribution.neutral,
      color: DISTRIBUTION_COLORS.neutral,
    },
    {
      label: "Negative",
      value: distribution.negative,
      color: DISTRIBUTION_COLORS.negative,
    },
  ];
}

export interface TrendPoint {
  label: string;
  score: number;
  count: number;
}

function formatBucket(iso: string, bucket: TrendBucket): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return bucket === "hour"
    ? date.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
      })
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function trendChartData(
  trend: SentimentTrendPoint[],
  bucket: TrendBucket,
): TrendPoint[] {
  return trend.map((p) => ({
    label: formatBucket(p.bucketStart, bucket),
    score: p.meanScore,
    count: p.count,
  }));
}

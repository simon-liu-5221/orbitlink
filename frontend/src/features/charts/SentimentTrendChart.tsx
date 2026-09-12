import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { trendChartData } from "./sentimentSummary";
import type { SentimentTrendPoint, TrendBucket } from "./sentimentSummary";

export function SentimentTrendChart({
  trend,
  trendBucket,
}: {
  trend: SentimentTrendPoint[];
  trendBucket: TrendBucket;
}) {
  if (trend.length === 0) {
    return (
      <p className="flex h-48 items-center justify-center text-sm text-slate-500">
        Not enough time-spread data.
      </p>
    );
  }

  const data = trendChartData(trend, trendBucket);

  return (
    <div className="h-48 w-full" data-testid="sentiment-trend-chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ left: 8, right: 16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={20} />
          <YAxis domain={[-1, 1]} tick={{ fontSize: 12 }} width={36} />
          <Tooltip
            formatter={(value: number, name: string) =>
              name === "score" ? value.toFixed(2) : value
            }
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

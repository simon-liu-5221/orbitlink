import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { distributionChartData } from "./sentimentSummary";
import type { SentimentDistribution } from "./sentimentSummary";

export function SentimentDistributionChart({
  distribution,
}: {
  distribution: SentimentDistribution;
}) {
  const data = distributionChartData(distribution);
  const hasData = data.some((bar) => bar.value > 0);

  if (!hasData) {
    return (
      <p className="flex h-48 items-center justify-center text-sm text-slate-500">
        No sentiment data.
      </p>
    );
  }

  return (
    <div className="h-48 w-full" data-testid="sentiment-distribution-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <XAxis
            type="number"
            domain={[0, 100]}
            unit="%"
            tick={{ fontSize: 12 }}
          />
          <YAxis
            type="category"
            dataKey="label"
            tick={{ fontSize: 12 }}
            width={70}
            interval={0} // always show all three categories, never collapse one
          />
          <Tooltip formatter={(value: number) => `${value.toFixed(1)}%`} />
          <Bar dataKey="value">
            {data.map((bar) => (
              <Cell key={bar.label} fill={bar.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TrendPoint } from "./historyData";

/** One line chart, reused for the three AN-06 headline metrics. */
export function HistoryTrendChart({
  title,
  points,
  color,
  yDomain,
  valueFormatter,
}: {
  title: string;
  points: TrendPoint[];
  color: string;
  yDomain?: [number, number];
  valueFormatter?: (value: number) => string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <h3 className="mb-2 text-xs font-medium text-slate-500">{title}</h3>
      <div className="h-40 w-full" data-testid={`history-trend-${title}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={20} />
            <YAxis
              domain={yDomain ?? ["auto", "auto"]}
              tick={{ fontSize: 12 }}
              width={36}
            />
            <Tooltip
              formatter={(value: number) =>
                valueFormatter ? valueFormatter(value) : value
              }
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={color}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

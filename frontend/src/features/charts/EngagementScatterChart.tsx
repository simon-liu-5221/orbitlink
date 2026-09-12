import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { GraphNode } from "@/features/graph/graphData";

import { buildEngagementScatterData } from "./engagementScatter";

export function EngagementScatterChart({ nodes }: { nodes: GraphNode[] }) {
  if (nodes.length === 0) {
    return (
      <p className="flex h-56 items-center justify-center text-sm text-slate-500">
        No participant data.
      </p>
    );
  }

  const data = buildEngagementScatterData(nodes);

  return (
    <div className="h-56 w-full" data-testid="engagement-scatter-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ left: 8, right: 16, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            type="number"
            dataKey="comments"
            name="Comments"
            tick={{ fontSize: 12 }}
            label={{
              value: "Comments",
              position: "insideBottom",
              offset: -4,
              fontSize: 12,
            }}
          />
          <YAxis
            type="number"
            dataKey="engagement"
            name="Engagement"
            tick={{ fontSize: 12 }}
            label={{
              value: "Engagement",
              angle: -90,
              position: "insideLeft",
              fontSize: 12,
            }}
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data}>
            {data.map((point) => (
              <Cell key={point.pseudonym} fill={point.color} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

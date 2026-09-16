import type { AnalysisForecast } from "@/features/projects/api";

/**
 * AN-06 phase 2 — pure view-model builder for the forecast cards. No
 * component, no fetch: just turns the API shape into display-ready strings
 * so the "how many decimals" decision lives in one tested place.
 */

type MetricKey = "sentiment" | "participants" | "communities";

const METRICS: {
  key: MetricKey;
  label: string;
  format: (n: number) => string;
}[] = [
  { key: "sentiment", label: "Sentiment", format: (n) => n.toFixed(2) },
  {
    key: "participants",
    label: "Participants",
    format: (n) => Math.round(n).toString(),
  },
  {
    key: "communities",
    label: "Communities",
    format: (n) => Math.round(n).toString(),
  },
];

export interface ForecastMetricView {
  key: MetricKey;
  label: string;
  available: boolean;
  predictedNextLabel: string | null;
  maeLabel: string | null;
  //: AC-11 — how many more analyses this metric needs before a forecast
  //: becomes available; 0 when it already is.
  moreNeeded: number;
}

export function buildForecastViews(
  forecast: AnalysisForecast,
): ForecastMetricView[] {
  return METRICS.map(({ key, label, format }) => {
    const metric = forecast[key];
    return {
      key,
      label,
      available: metric.available,
      predictedNextLabel:
        metric.predicted_next === null ? null : format(metric.predicted_next),
      maeLabel: metric.mae === null ? null : format(metric.mae),
      moreNeeded: Math.max(0, forecast.required_history - metric.points_used),
    };
  });
}

import { useQuery } from "@tanstack/react-query";

import { Spinner } from "@/components/ui";
import { projectsApi } from "@/features/projects/api";

import { buildForecastViews } from "./forecastData";

/**
 * AN-06 phase 2 — one card per headline metric: a linear-regression
 * extrapolation plus its leave-one-out MAE, or a "need N more" message when
 * a metric doesn't have enough usable points yet (AC-11). AC-12: the
 * disclaimer is not optional copy, it's the whole point of this feature.
 */
export function ForecastSection({ projectId }: { projectId: string }) {
  const forecast = useQuery({
    queryKey: ["projects", projectId, "analyses", "forecast"],
    queryFn: () => projectsApi.analysisForecast(projectId),
  });

  if (forecast.isLoading) {
    return (
      <div className="flex justify-center p-4 text-slate-400">
        <Spinner />
      </div>
    );
  }

  if (!forecast.data) return null;

  const views = buildForecastViews(forecast.data);

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 p-4">
      <div>
        <h3 className="text-xs font-medium text-slate-500">Forecast</h3>
        <p className="text-xs text-slate-400">
          A simple extrapolated trend line, not a machine-learning model.
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {views.map((view) => (
          <div
            key={view.key}
            className="rounded-md border border-slate-100 p-3"
            data-testid={`forecast-${view.key}`}
          >
            <p className="text-xs text-slate-500">{view.label}</p>
            {view.available ? (
              <>
                <p className="text-lg font-semibold text-slate-900">
                  {view.predictedNextLabel}
                </p>
                <p className="text-xs text-slate-400">MAE {view.maeLabel}</p>
              </>
            ) : (
              <p className="text-sm text-slate-500">
                Need {view.moreNeeded} more{" "}
                {view.moreNeeded === 1 ? "analysis" : "analyses"}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

import { describe, expect, it } from "vitest";

import type { AnalysisForecast } from "@/features/projects/api";

import { buildForecastViews } from "./forecastData";

function forecast(overrides: Partial<AnalysisForecast> = {}): AnalysisForecast {
  return {
    required_history: 5,
    sentiment: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 0,
    },
    participants: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 0,
    },
    communities: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 0,
    },
    ...overrides,
  };
}

describe("buildForecastViews", () => {
  it("AC-11: unavailable metrics report exactly how many more analyses are needed", () => {
    const views = buildForecastViews(
      forecast({
        sentiment: {
          available: false,
          predicted_next: null,
          mae: null,
          points_used: 3,
        },
      }),
    );
    const sentiment = views.find((v) => v.key === "sentiment")!;
    expect(sentiment.available).toBe(false);
    expect(sentiment.moreNeeded).toBe(2);
    expect(sentiment.predictedNextLabel).toBeNull();
    expect(sentiment.maeLabel).toBeNull();
  });

  it("never reports a negative moreNeeded once past the threshold", () => {
    const views = buildForecastViews(
      forecast({
        sentiment: {
          available: true,
          predicted_next: 0.4,
          mae: 0.05,
          points_used: 8,
        },
      }),
    );
    expect(views.find((v) => v.key === "sentiment")!.moreNeeded).toBe(0);
  });

  it("formats sentiment to 2 decimals and counts as whole numbers", () => {
    const views = buildForecastViews(
      forecast({
        sentiment: {
          available: true,
          predicted_next: 0.4321,
          mae: 0.019,
          points_used: 5,
        },
        participants: {
          available: true,
          predicted_next: 12.6,
          mae: 1.2,
          points_used: 5,
        },
        communities: {
          available: true,
          predicted_next: 3.4,
          mae: 0.5,
          points_used: 5,
        },
      }),
    );
    const byKey = Object.fromEntries(views.map((v) => [v.key, v]));
    expect(byKey.sentiment.predictedNextLabel).toBe("0.43");
    expect(byKey.sentiment.maeLabel).toBe("0.02");
    expect(byKey.participants.predictedNextLabel).toBe("13");
    expect(byKey.communities.predictedNextLabel).toBe("3");
  });
});

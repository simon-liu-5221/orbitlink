import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { ForecastSection } from "./ForecastSection";

const analysisForecast = vi.fn();

vi.mock("@/features/projects/api", () => ({
  projectsApi: { analysisForecast: (id: string) => analysisForecast(id) },
}));

function renderWithClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ForecastSection projectId="p1" />
    </QueryClientProvider>,
  );
}

test("AC-12: always shows the not-a-model disclaimer", async () => {
  analysisForecast.mockResolvedValueOnce({
    required_history: 5,
    sentiment: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 2,
    },
    participants: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 2,
    },
    communities: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 2,
    },
  });
  renderWithClient();
  expect(
    await screen.findByText(/not a machine-learning model/i),
  ).toBeInTheDocument();
});

test("AC-11: an unavailable metric shows how many more analyses are needed", async () => {
  analysisForecast.mockResolvedValueOnce({
    required_history: 5,
    sentiment: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 3,
    },
    participants: {
      available: true,
      predicted_next: 12,
      mae: 1,
      points_used: 5,
    },
    communities: {
      available: false,
      predicted_next: null,
      mae: null,
      points_used: 5,
    },
  });
  renderWithClient();

  const sentimentCard = within(await screen.findByTestId("forecast-sentiment"));
  expect(sentimentCard.getByText(/need 2 more analyses/i)).toBeInTheDocument();

  const participantsCard = within(screen.getByTestId("forecast-participants"));
  expect(participantsCard.getByText("12")).toBeInTheDocument();
  expect(participantsCard.getByText(/mae 1/i)).toBeInTheDocument();
});

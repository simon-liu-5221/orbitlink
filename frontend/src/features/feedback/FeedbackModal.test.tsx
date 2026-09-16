import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { FeedbackModal } from "./FeedbackModal";
import { feedbackApi } from "./api";

vi.mock("./api", () => ({ feedbackApi: { submit: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.restoreAllMocks());

test("submit is disabled until a star is picked (AC-9)", () => {
  render(<FeedbackModal onClose={() => {}} />);
  expect(screen.getByRole("button", { name: "Send feedback" })).toBeDisabled();
});

test("picking a star enables submit, and it sends the rating and trimmed comment", async () => {
  vi.mocked(feedbackApi.submit).mockResolvedValue({
    id: "f1",
    rating: 4,
    comment: "nice",
    created_at: new Date().toISOString(),
  });

  render(<FeedbackModal onClose={() => {}} />);
  await userEvent.click(screen.getByRole("radio", { name: "4 stars" }));
  expect(screen.getByRole("button", { name: "Send feedback" })).toBeEnabled();

  await userEvent.type(screen.getByLabelText(/comments/i), "  nice  ");
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(feedbackApi.submit).toHaveBeenCalledWith({
    rating: 4,
    comment: "nice",
  });
});

test("an empty comment is sent as null, not an empty string", async () => {
  vi.mocked(feedbackApi.submit).mockResolvedValue({
    id: "f1",
    rating: 5,
    comment: null,
    created_at: new Date().toISOString(),
  });

  render(<FeedbackModal onClose={() => {}} />);
  await userEvent.click(screen.getByRole("radio", { name: "5 stars" }));
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(feedbackApi.submit).toHaveBeenCalledWith({ rating: 5, comment: null });
});

test("shows a thank-you message and lets the user send another (AC-10)", async () => {
  vi.mocked(feedbackApi.submit).mockResolvedValue({
    id: "f1",
    rating: 5,
    comment: null,
    created_at: new Date().toISOString(),
  });

  render(<FeedbackModal onClose={() => {}} />);
  await userEvent.click(screen.getByRole("radio", { name: "5 stars" }));
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(
    await screen.findByText(/thanks for letting us know/i),
  ).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Send more" }));
  // form is reset — submit disabled again, no rating selected
  expect(screen.getByRole("button", { name: "Send feedback" })).toBeDisabled();
  expect(screen.getByRole("radio", { name: "5 stars" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
});

test("a failed submit shows an error and keeps the form open", async () => {
  vi.mocked(feedbackApi.submit).mockRejectedValue(new Error("network down"));

  render(<FeedbackModal onClose={() => {}} />);
  await userEvent.click(screen.getByRole("radio", { name: "2 stars" }));
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't send/i);
  expect(
    screen.getByRole("button", { name: "Send feedback" }),
  ).toBeInTheDocument();
});

test("clicking cancel or the backdrop closes without submitting", async () => {
  const onClose = vi.fn();
  render(<FeedbackModal onClose={onClose} />);
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onClose).toHaveBeenCalled();
  expect(feedbackApi.submit).not.toHaveBeenCalled();
});

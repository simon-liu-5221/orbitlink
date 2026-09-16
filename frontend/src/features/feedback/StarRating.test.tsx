import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { StarRating } from "./StarRating";

test("no star is checked when value is null", () => {
  render(<StarRating value={null} onChange={() => {}} />);
  const stars = screen.getAllByRole("radio");
  expect(stars.every((s) => s.getAttribute("aria-checked") === "false")).toBe(
    true,
  );
});

test("clicking a star reports its number", async () => {
  const onChange = vi.fn();
  render(<StarRating value={null} onChange={onChange} />);
  await userEvent.click(screen.getByRole("radio", { name: "3 stars" }));
  expect(onChange).toHaveBeenCalledWith(3);
});

test("only the selected star (and not higher ones) is checked", () => {
  render(<StarRating value={3} onChange={() => {}} />);
  expect(screen.getByRole("radio", { name: "3 stars" })).toHaveAttribute(
    "aria-checked",
    "true",
  );
  expect(screen.getByRole("radio", { name: "4 stars" })).toHaveAttribute(
    "aria-checked",
    "false",
  );
});

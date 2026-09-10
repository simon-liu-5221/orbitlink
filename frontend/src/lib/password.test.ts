import { expect, test } from "vitest";

import { isPasswordAcceptable, passwordProblems } from "./password";

test("lists every unmet rule, not just the first (mirrors GU-01 AC-4)", () => {
  expect(passwordProblems("short")).toEqual([
    "must be at least 12 characters",
    "must contain at least one digit",
  ]);
});

test("a long all-letters password is only missing a digit", () => {
  expect(passwordProblems("abcdefghijklmno")).toEqual([
    "must contain at least one digit",
  ]);
});

test("digits with no letters is flagged", () => {
  expect(passwordProblems("1234567890123")).toEqual([
    "must contain at least one letter",
  ]);
});

test("12+ chars with a digit and a letter passes", () => {
  expect(passwordProblems("correct-horse-7")).toEqual([]);
  expect(isPasswordAcceptable("correct-horse-7")).toBe(true);
});

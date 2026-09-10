import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { ApiError } from "@/api/client";
import { renderWithProviders, resetAuthStore } from "@/test/utils";

import { LoginPage } from "./LoginPage";
import { authApi } from "./api";
import { useAuthStore } from "./store";

vi.mock("./api", () => ({ authApi: { login: vi.fn() } }));

beforeEach(() => {
  resetAuthStore();
  vi.clearAllMocks();
});

afterEach(() => vi.restoreAllMocks());

function setup(route = "/login") {
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<div>Projects home</div>} />
      <Route path="/secret" element={<div>Secret page</div>} />
    </Routes>,
    { route },
  );
}

test("a good sign-in stores the session and lands on the app", async () => {
  vi.mocked(authApi.login).mockResolvedValue({
    access_token: "tok",
    token_type: "bearer",
    expires_in: 900,
    user: { id: "u1", username: "sam", email: "s@e.com" } as never,
  });

  setup();
  await userEvent.type(screen.getByLabelText("Email"), "s@e.com");
  await userEvent.type(screen.getByLabelText("Password"), "correct-horse-7");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() =>
    expect(screen.getByText("Projects home")).toBeInTheDocument(),
  );
  expect(useAuthStore.getState().accessToken).toBe("tok");
});

test("wrong credentials show an inline error, no navigation", async () => {
  vi.mocked(authApi.login).mockRejectedValue(new ApiError(401, "nope"));

  setup();
  await userEvent.type(screen.getByLabelText("Email"), "s@e.com");
  await userEvent.type(screen.getByLabelText("Password"), "whatever12345");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("don't match");
  expect(screen.queryByText("Projects home")).not.toBeInTheDocument();
});

test("an unverified account is told to resend the confirmation", async () => {
  vi.mocked(authApi.login).mockRejectedValue(
    new ApiError(403, "confirm your email", "EMAIL_NOT_VERIFIED"),
  );

  setup();
  await userEvent.type(screen.getByLabelText("Email"), "s@e.com");
  await userEvent.type(screen.getByLabelText("Password"), "correct-horse-7");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Confirm your email",
  );
  expect(screen.getByRole("link", { name: /resend/i })).toHaveAttribute(
    "href",
    "/verify",
  );
});

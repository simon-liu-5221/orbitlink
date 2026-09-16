import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { beforeEach, expect, test } from "vitest";

import { renderWithProviders } from "@/test/utils";

import { RequireAdmin } from "./RequireAuth";
import { useAuthStore } from "./store";
import type { User } from "./store";

function asUser(role: string): User {
  return { id: "u1", username: "someone", email: "s@e.com", role } as User;
}

function setup() {
  return renderWithProviders(
    <Routes>
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <div>Admin area</div>
          </RequireAdmin>
        }
      />
      <Route path="/" element={<div>Home</div>} />
    </Routes>,
    { route: "/admin" },
  );
}

beforeEach(() => {
  useAuthStore.setState({ status: "anonymous", accessToken: null, user: null });
});

test("an admin sees the protected content", () => {
  useAuthStore.setState({
    status: "authenticated",
    accessToken: "t",
    user: asUser("admin"),
  });
  setup();
  expect(screen.getByText("Admin area")).toBeInTheDocument();
});

test("a non-admin is redirected home without ever seeing it", () => {
  useAuthStore.setState({
    status: "authenticated",
    accessToken: "t",
    user: asUser("user"),
  });
  setup();
  expect(screen.queryByText("Admin area")).not.toBeInTheDocument();
  expect(screen.getByText("Home")).toBeInTheDocument();
});

test("no user at all is also redirected, not crashed", () => {
  setup();
  expect(screen.getByText("Home")).toBeInTheDocument();
});

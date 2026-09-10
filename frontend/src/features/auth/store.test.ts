import { beforeEach, expect, test } from "vitest";

import type { User } from "./store";
import { useAuthStore } from "./store";

const user = { id: "u1", username: "sam", email: "sam@example.com" } as User;

beforeEach(() => {
  useAuthStore.setState({ status: "loading", accessToken: null, user: null });
});

test("setSession makes the store authenticated", () => {
  useAuthStore.getState().setSession("token-abc", user);
  const s = useAuthStore.getState();
  expect(s.status).toBe("authenticated");
  expect(s.accessToken).toBe("token-abc");
  expect(s.user?.username).toBe("sam");
});

test("clear wipes the token and marks anonymous", () => {
  useAuthStore.getState().setSession("token-abc", user);
  useAuthStore.getState().clear();
  expect(useAuthStore.getState()).toMatchObject({
    status: "anonymous",
    accessToken: null,
    user: null,
  });
});

test("markAnonymous only moves out of the loading state", () => {
  useAuthStore.getState().markAnonymous();
  expect(useAuthStore.getState().status).toBe("anonymous");

  useAuthStore.getState().setSession("token-abc", user);
  useAuthStore.getState().markAnonymous(); // must not log an authenticated user out
  expect(useAuthStore.getState().status).toBe("authenticated");
});

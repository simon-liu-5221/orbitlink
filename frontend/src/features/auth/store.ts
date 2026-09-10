import { create } from "zustand";

import type { components } from "@/api/schema";

export type User = components["schemas"]["UserOut"];

/**
 * "loading"       — a session restore is in flight; render nothing decisive yet
 * "authenticated" — we hold a live access token in memory
 * "anonymous"     — no session; the access token never survives a reload, only
 *                   the httpOnly refresh cookie does (decision B1)
 */
export type AuthStatus = "loading" | "authenticated" | "anonymous";

interface AuthState {
  status: AuthStatus;
  accessToken: string | null;
  user: User | null;
  /** A successful login / register / refresh landed a new token + user. */
  setSession: (accessToken: string, user: User) => void;
  /** Refresh failed or the user signed out. */
  clear: () => void;
  /** Bootstrap finished and found no session — distinct from an active sign-out. */
  markAnonymous: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  status: "loading",
  accessToken: null,
  user: null,
  setSession: (accessToken, user) =>
    set({ status: "authenticated", accessToken, user }),
  clear: () => set({ status: "anonymous", accessToken: null, user: null }),
  markAnonymous: () =>
    set((s) => (s.status === "loading" ? { status: "anonymous" } : s)),
}));

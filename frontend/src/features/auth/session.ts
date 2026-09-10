import { useEffect } from "react";

import { refreshSession } from "@/api/client";

import { authApi } from "./api";
import { useAuthStore } from "./store";

/**
 * On first mount, try to turn the httpOnly refresh cookie into a live session.
 * Until this resolves the store sits in "loading" and route guards wait.
 */
export function useSessionBootstrap(): void {
  useEffect(() => {
    let cancelled = false;
    refreshSession().then((token) => {
      if (cancelled) return;
      if (!token) useAuthStore.getState().markAnonymous();
    });
    return () => {
      cancelled = true;
    };
  }, []);
}

/** Revoke the refresh token server-side, then drop the in-memory session. */
export async function signOut(): Promise<void> {
  try {
    await authApi.logout();
  } finally {
    useAuthStore.getState().clear();
  }
}

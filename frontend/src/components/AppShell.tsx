import type { ReactNode } from "react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { signOut } from "@/features/auth/session";
import { useAuthStore } from "@/features/auth/store";

import { Button } from "./ui";

export function AppShell({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const [signingOut, setSigningOut] = useState(false);

  async function onSignOut() {
    setSigningOut(true);
    await signOut();
    navigate("/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-3">
          <Link to="/" className="font-bold tracking-tight text-slate-900">
            OrbitLink
          </Link>
          <div className="flex items-center gap-3 text-sm text-slate-500">
            {user && <span className="hidden sm:inline">{user.username}</span>}
            <Button variant="ghost" onClick={onSignOut} loading={signingOut}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}

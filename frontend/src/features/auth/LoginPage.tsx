import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Button, FormError, TextField } from "@/components/ui";

import { AuthLayout } from "./AuthLayout";
import { authApi } from "./api";
import { useAuthStore } from "./store";

interface LocationState {
  from?: { pathname: string };
}

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsVerification, setNeedsVerification] = useState(false);

  const destination =
    (location.state as LocationState | null)?.from?.pathname ?? "/";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNeedsVerification(false);
    try {
      const { access_token, user } = await authApi.login({
        email,
        password,
        remember_me: rememberMe,
      });
      setSession(access_token, user);
      navigate(destination, { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.code === "EMAIL_NOT_VERIFIED") {
        setNeedsVerification(true);
        setError("Confirm your email address before signing in.");
      } else if (err instanceof ApiError && err.status === 401) {
        setError("That email and password don't match.");
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Sign in to your account"
      footer={
        <>
          New here?{" "}
          <Link className="font-medium text-slate-900 underline" to="/register">
            Create an account
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <FormError>{error}</FormError>
        {needsVerification && (
          <p className="text-sm text-slate-600">
            <Link className="font-medium underline" to="/verify">
              Resend the confirmation link
            </Link>
          </p>
        )}
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(e) => setRememberMe(e.target.checked)}
          />
          Keep me signed in
        </label>
        <Button type="submit" className="w-full" loading={submitting}>
          Sign in
        </Button>
        <p className="text-center text-sm">
          <Link className="text-slate-500 underline" to="/forgot-password">
            Forgot your password?
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Button, FormError, TextField } from "@/components/ui";
import { MIN_PASSWORD_LENGTH, passwordProblems } from "@/lib/password";

import { AuthLayout } from "./AuthLayout";
import { authApi } from "./api";

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [serverProblems, setServerProblems] = useState<string[]>([]);

  const localProblems = useMemo(() => passwordProblems(password), [password]);
  const mismatch = touched && confirm.length > 0 && confirm !== password;

  if (!token) {
    return (
      <AuthLayout
        title="Reset your password"
        footer={
          <Link
            className="font-medium text-slate-900 underline"
            to="/forgot-password"
          >
            Request a link
          </Link>
        }
      >
        <FormError>
          This link is missing its token. Request a new one.
        </FormError>
      </AuthLayout>
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (localProblems.length > 0 || password !== confirm) return;

    setSubmitting(true);
    setError(null);
    setServerProblems([]);
    try {
      await authApi.resetPassword({ token, password });
      navigate("/login", {
        replace: true,
        state: { notice: "Password changed. Sign in with your new one." },
      });
    } catch (err) {
      if (err instanceof ApiError && err.code === "WEAK_PASSWORD") {
        setServerProblems(err.problems ?? []);
      } else if (err instanceof ApiError && err.status === 410) {
        setError("This link has expired. Request a new one.");
      } else if (err instanceof ApiError && err.status === 400) {
        setError("This link is not valid. Request a new one.");
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout
      title="Choose a new password"
      footer={
        <Link className="font-medium text-slate-900 underline" to="/login">
          Back to sign in
        </Link>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <FormError>{error}</FormError>
        {serverProblems.length > 0 && (
          <FormError>Password: {serverProblems.join("; ")}</FormError>
        )}
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setTouched(true)}
          hint={`At least ${MIN_PASSWORD_LENGTH} characters, one digit, one letter.`}
          error={
            touched && localProblems.length > 0
              ? localProblems.join("; ")
              : undefined
          }
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          onBlur={() => setTouched(true)}
          error={mismatch ? "The two passwords don't match." : undefined}
        />
        <Button type="submit" className="w-full" loading={submitting}>
          Set new password
        </Button>
      </form>
    </AuthLayout>
  );
}

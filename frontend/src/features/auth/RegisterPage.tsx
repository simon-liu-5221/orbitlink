import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Button, FormError, FormNotice, TextField } from "@/components/ui";
import { MIN_PASSWORD_LENGTH, passwordProblems } from "@/lib/password";

import { AuthLayout } from "./AuthLayout";
import { authApi } from "./api";

const USERNAME_PATTERN = /^[A-Za-z0-9_.-]+$/;

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [serverProblems, setServerProblems] = useState<string[]>([]);
  const [done, setDone] = useState(false);

  const localProblems = useMemo(() => passwordProblems(password), [password]);
  const rules = useMemo(
    () => [
      {
        label: `At least ${MIN_PASSWORD_LENGTH} characters`,
        ok: password.length >= MIN_PASSWORD_LENGTH,
      },
      { label: "At least one digit", ok: /\d/.test(password) },
      { label: "At least one letter", ok: /[a-zA-Z]/.test(password) },
    ],
    [password],
  );
  const usernameError =
    touched && username.length > 0 && !USERNAME_PATTERN.test(username)
      ? "Letters, digits, dot, dash and underscore only."
      : undefined;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (localProblems.length > 0 || usernameError || username.length < 3)
      return;

    setSubmitting(true);
    setError(null);
    setServerProblems([]);
    try {
      await authApi.register({ email, username, password });
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === "WEAK_PASSWORD") {
        setServerProblems(err.problems ?? []);
      } else if (err instanceof ApiError && err.code === "USERNAME_TAKEN") {
        setError("That username is taken. Pick another.");
      } else if (err instanceof ApiError && err.status === 422) {
        setError("Check your details and try again.");
      } else {
        setError("Something went wrong. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <AuthLayout
        title="Almost there"
        footer={
          <Link className="font-medium text-slate-900 underline" to="/login">
            Back to sign in
          </Link>
        }
      >
        <FormNotice>
          Check your inbox — we sent a link to confirm your email address. It
          works for 24 hours.
        </FormNotice>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Create your account"
      footer={
        <>
          Already have one?{" "}
          <Link className="font-medium text-slate-900 underline" to="/login">
            Sign in
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={onSubmit} noValidate>
        <FormError>{error}</FormError>
        {serverProblems.length > 0 && (
          <FormError>
            <span>Password: {serverProblems.join("; ")}</span>
          </FormError>
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
          label="Username"
          autoComplete="username"
          required
          minLength={3}
          maxLength={30}
          value={username}
          error={usernameError}
          onChange={(e) => setUsername(e.target.value)}
          onBlur={() => setTouched(true)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setTouched(true)}
          hint={
            <ul className="space-y-0.5">
              {rules.map((rule) => {
                const show = touched || password.length > 0;
                return (
                  <li
                    key={rule.label}
                    className={
                      !show ? "" : rule.ok ? "text-emerald-600" : "text-red-600"
                    }
                  >
                    {show ? (rule.ok ? "✓" : "✗") : "•"} {rule.label}
                  </li>
                );
              })}
            </ul>
          }
        />
        <Button type="submit" className="w-full" loading={submitting}>
          Create account
        </Button>
      </form>
    </AuthLayout>
  );
}

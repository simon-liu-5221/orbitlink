import type { FormEvent } from "react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Button, FormNotice, TextField } from "@/components/ui";

import { AuthLayout } from "./AuthLayout";
import { authApi } from "./api";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await authApi.forgotPassword(email);
    } finally {
      setSubmitting(false);
      setSent(true); // identical outcome whether or not the address has an account
    }
  }

  return (
    <AuthLayout
      title="Reset your password"
      footer={
        <Link className="font-medium text-slate-900 underline" to="/login">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <FormNotice>
          If that address has an account, a reset link is on its way. It works
          for one hour.
        </FormNotice>
      ) : (
        <form className="space-y-4" onSubmit={onSubmit} noValidate>
          <p className="text-sm text-slate-600">
            Enter your email and we'll send a link to choose a new password.
          </p>
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Button type="submit" className="w-full" loading={submitting}>
            Send reset link
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}

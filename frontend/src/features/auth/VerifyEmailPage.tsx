import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  Button,
  FormError,
  FormNotice,
  Spinner,
  TextField,
} from "@/components/ui";

import { AuthLayout } from "./AuthLayout";
import { authApi } from "./api";

type Phase = "checking" | "ok" | "expired" | "invalid" | "no-token";

export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [phase, setPhase] = useState<Phase>(token ? "checking" : "no-token");
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;
    authApi
      .verifyEmail(token)
      .then(() => setPhase("ok"))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 410) setPhase("expired");
        else setPhase("invalid");
      });
  }, [token]);

  return (
    <AuthLayout
      title="Confirm your email"
      footer={
        <Link className="font-medium text-slate-900 underline" to="/login">
          Go to sign in
        </Link>
      }
    >
      {phase === "checking" && (
        <p className="flex items-center gap-2 text-sm text-slate-600">
          <Spinner className="h-4 w-4" /> Confirming your address…
        </p>
      )}
      {phase === "ok" && (
        <FormNotice>Your email is confirmed. You can sign in now.</FormNotice>
      )}
      {phase === "invalid" && (
        <FormError>This confirmation link is not valid.</FormError>
      )}
      {(phase === "expired" || phase === "no-token") && (
        <ResendForm
          intro={
            phase === "expired"
              ? "That link has expired. Enter your email and we'll send a new one."
              : "Enter your email and we'll send a fresh confirmation link."
          }
        />
      )}
    </AuthLayout>
  );
}

function ResendForm({ intro }: { intro: string }) {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      await authApi.resendVerification(email);
    } finally {
      setSubmitting(false);
      setSent(true); // the endpoint is deliberately silent about whether it did anything
    }
  }

  if (sent) {
    return (
      <FormNotice>
        If that address needs confirming, a new link is on its way.
      </FormNotice>
    );
  }

  return (
    <form className="space-y-4" onSubmit={onSubmit} noValidate>
      <p className="text-sm text-slate-600">{intro}</p>
      <TextField
        label="Email"
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Button type="submit" className="w-full" loading={submitting}>
        Send a new link
      </Button>
    </form>
  );
}

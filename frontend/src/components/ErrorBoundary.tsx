import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

import { ApiError } from "@/api/client";

import { Button } from "./ui";

/**
 * M7 / UX-02 — a top-level backstop against a blank white screen. Every page
 * already handles its own known error states (`.isError` on a query), so
 * this only fires for genuinely unexpected render bugs. React error
 * boundaries must be class components — there is no hooks equivalent.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error): { error: Error } {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // eslint-disable-next-line no-console
    console.error("Unhandled render error", error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    const requestId = error instanceof ApiError ? error.requestId : undefined;

    return (
      <div className="mx-auto max-w-md space-y-4 p-8 text-center">
        <h1 className="text-lg font-semibold text-slate-900">
          Something went wrong
        </h1>
        <p className="text-sm text-slate-600">
          This page hit an unexpected error. Reloading usually fixes it.
        </p>
        {requestId && (
          <p className="text-xs text-slate-400">
            If this keeps happening, mention this id to support:{" "}
            <span className="font-mono">{requestId}</span>
          </p>
        )}
        <Button onClick={() => window.location.reload()}>Reload</Button>
      </div>
    );
  }
}

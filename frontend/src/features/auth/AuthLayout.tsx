import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function AuthLayout({
  title,
  children,
  footer,
}: {
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <Link
            to="/"
            className="text-2xl font-bold tracking-tight text-slate-900"
          >
            OrbitLink
          </Link>
          <h1 className="mt-2 text-sm font-medium text-slate-500">{title}</h1>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {children}
        </div>
        {footer ? (
          <p className="text-center text-sm text-slate-500">{footer}</p>
        ) : null}
      </div>
    </div>
  );
}

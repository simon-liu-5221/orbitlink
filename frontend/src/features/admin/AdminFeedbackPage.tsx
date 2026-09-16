import { useQuery } from "@tanstack/react-query";

import { AppShell } from "@/components/AppShell";
import { FormError, Spinner } from "@/components/ui";

import { AdminNav } from "./AdminNav";
import { adminApi } from "./api";

function Stars({ rating }: { rating: number }) {
  return (
    <span aria-label={`${rating} out of 5 stars`} className="text-amber-400">
      {"★".repeat(rating)}
      <span className="text-slate-300">{"★".repeat(5 - rating)}</span>
    </span>
  );
}

export function AdminFeedbackPage() {
  const feedback = useQuery({
    queryKey: ["admin", "feedback"],
    queryFn: () => adminApi.listFeedback(),
  });

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-4 p-6">
        <AdminNav active="feedback" />

        {feedback.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="h-4 w-4" /> Loading…
          </p>
        ) : feedback.isError ? (
          <FormError>Couldn't load feedback.</FormError>
        ) : feedback.data && feedback.data.length > 0 ? (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {feedback.data.map((f) => (
              <li key={f.id} className="space-y-1 px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <Stars rating={f.rating} />
                  <span className="text-xs text-slate-400">
                    {new Date(f.created_at).toLocaleString()}
                  </span>
                </div>
                {f.comment && (
                  <p className="text-sm text-slate-700">{f.comment}</p>
                )}
                <p className="text-xs text-slate-400">
                  {f.username} · {f.user_email}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
            No feedback yet.
          </p>
        )}
      </div>
    </AppShell>
  );
}

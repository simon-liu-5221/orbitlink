import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { Button, FormError, Spinner } from "@/components/ui";

import { AdminNav } from "./AdminNav";
import { adminApi } from "./api";

export function AdminUsersPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const users = useQuery({
    queryKey: ["admin", "users", search],
    queryFn: () => adminApi.listUsers(search),
  });

  const toggleSuspend = useMutation({
    mutationFn: ({ id, suspended }: { id: string; suspended: boolean }) =>
      suspended ? adminApi.unsuspend(id) : adminApi.suspend(id),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (err) => {
      setError(
        err instanceof ApiError && err.status === 409
          ? err.message
          : "Couldn't update that account.",
      );
    },
  });

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-4 p-6">
        <AdminNav active="users" />

        <input
          type="search"
          placeholder="Search by email or username"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
        />
        <FormError>{error}</FormError>

        {users.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="h-4 w-4" /> Loading…
          </p>
        ) : users.isError ? (
          <FormError>Couldn't load users.</FormError>
        ) : users.data && users.data.length > 0 ? (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {users.data.map((u) => {
              const suspended = u.suspended_at !== null;
              return (
                <li
                  key={u.id}
                  className="flex items-center justify-between gap-3 px-4 py-3"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {u.username}{" "}
                      {u.role === "admin" && (
                        <span className="ml-1 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                          admin
                        </span>
                      )}
                      {suspended && (
                        <span className="ml-1 rounded bg-red-100 px-1.5 py-0.5 text-xs text-red-700">
                          suspended
                        </span>
                      )}
                    </p>
                    <p className="truncate text-xs text-slate-400">
                      {u.email} · {u.email_verified ? "verified" : "unverified"}{" "}
                      · {u.subscription_plan}
                    </p>
                  </div>
                  <Button
                    variant={suspended ? "secondary" : "danger"}
                    onClick={() =>
                      toggleSuspend.mutate({ id: u.id, suspended })
                    }
                    loading={
                      toggleSuspend.isPending &&
                      toggleSuspend.variables?.id === u.id
                    }
                  >
                    {suspended ? "Restore" : "Suspend"}
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
            No users match that search.
          </p>
        )}
      </div>
    </AppShell>
  );
}

import { useQuery } from "@tanstack/react-query";

import { fetchHealth } from "@/api/client";

const DOT: Record<string, string> = {
  up: "bg-green-500",
  down: "bg-red-500",
};

export function HealthStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 10_000,
  });

  if (isLoading) {
    return <p className="text-sm text-slate-500">Checking backend…</p>;
  }

  if (isError || !data) {
    return (
      <p className="text-sm font-medium text-red-600" role="alert">
        Backend unreachable
      </p>
    );
  }

  return (
    <div className="space-y-2" data-testid="health-status">
      <p className="text-sm">
        Backend:{" "}
        <span
          className={
            data.status === "ok"
              ? "font-semibold text-green-600"
              : "font-semibold text-amber-600"
          }
        >
          {data.status}
        </span>{" "}
        <span className="text-slate-400">
          ({data.environment} · v{data.version})
        </span>
      </p>
      <ul className="space-y-1">
        {Object.entries(data.dependencies).map(([name, state]) => (
          <li key={name} className="flex items-center gap-2 text-sm">
            <span
              className={`inline-block h-2 w-2 rounded-full ${DOT[state] ?? "bg-slate-300"}`}
              aria-hidden
            />
            <span className="capitalize">{name}</span>
            <span className="text-slate-400">{state}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

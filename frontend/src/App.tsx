import { HealthStatus } from "@/features/health/HealthStatus";

export default function App() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-8 p-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">OrbitLink</h1>
        <p className="text-slate-600">
          YouTube comment network analysis. This is the M0 skeleton — deploy
          pipeline and health wiring only.
        </p>
      </header>

      <section className="rounded-lg border border-slate-200 p-4">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
          System status
        </h2>
        <HealthStatus />
      </section>
    </main>
  );
}

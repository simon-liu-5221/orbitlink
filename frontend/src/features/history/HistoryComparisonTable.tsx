import type { ComparisonRow } from "./historyData";

/** AC-8 — one row per analysis, time/participants/communities/sentiment/flag. */
export function HistoryComparisonTable({ rows }: { rows: ComparisonRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wide text-slate-500">
            <th className="py-1 pr-4">Date</th>
            <th className="py-1 pr-4">Participants</th>
            <th className="py-1 pr-4">Communities</th>
            <th className="py-1 pr-4">Sentiment</th>
            <th className="py-1 pr-4">Data</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-slate-100">
              <td className="py-1 pr-4">{row.label}</td>
              <td className="py-1 pr-4">{row.nodeCount}</td>
              <td className="py-1 pr-4">{row.communityCount}</td>
              <td className="py-1 pr-4">
                {row.sentimentIndex === null
                  ? "—"
                  : row.sentimentIndex.toFixed(2)}
              </td>
              <td className="py-1 pr-4">
                {row.insufficientData ? (
                  <span className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                    Insufficient
                  </span>
                ) : (
                  "OK"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

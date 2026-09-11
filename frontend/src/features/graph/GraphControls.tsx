import type { GraphFilters } from "./graphData";
import { communityColor } from "./graphData";

export function GraphControls({
  filters,
  onChange,
  communities,
  maxDegree,
}: {
  filters: GraphFilters;
  onChange: (filters: GraphFilters) => void;
  communities: number[];
  maxDegree: number;
}) {
  function toggleCommunity(index: number) {
    const next = new Set(filters.excludedCommunities);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    onChange({ ...filters, excludedCommunities: next });
  }

  return (
    <div className="space-y-4 rounded-lg border border-slate-200 p-4 text-sm">
      <div>
        <label
          htmlFor="min-degree"
          className="block font-medium text-slate-700"
        >
          Minimum connections: {filters.minDegree}
        </label>
        <input
          id="min-degree"
          type="range"
          min={0}
          max={Math.max(maxDegree, 1)}
          value={filters.minDegree}
          onChange={(e) =>
            onChange({ ...filters, minDegree: Number(e.target.value) })
          }
          className="w-full"
        />
      </div>

      {communities.length > 0 && (
        <div>
          <p className="mb-1 font-medium text-slate-700">Communities</p>
          <div className="flex flex-wrap gap-2">
            {communities.map((index) => {
              const active = !filters.excludedCommunities.has(index);
              return (
                <button
                  key={index}
                  type="button"
                  onClick={() => toggleCommunity(index)}
                  aria-pressed={active}
                  className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
                    active
                      ? "border-slate-300 bg-white"
                      : "border-slate-200 bg-slate-50 opacity-50"
                  }`}
                >
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: communityColor(index) }}
                    aria-hidden
                  />
                  #{index}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div>
        <label className="flex items-center gap-2 font-medium text-slate-700">
          <input
            type="checkbox"
            checked={filters.sentimentRange !== null}
            onChange={(e) =>
              onChange({
                ...filters,
                sentimentRange: e.target.checked ? [-1, 1] : null,
              })
            }
          />
          Filter by sentiment
        </label>
        {filters.sentimentRange && (
          <div className="mt-2 flex items-center gap-2">
            <input
              type="range"
              min={-1}
              max={1}
              step={0.1}
              value={filters.sentimentRange[0]}
              onChange={(e) => {
                const min = Number(e.target.value);
                const max = filters.sentimentRange![1];
                onChange({
                  ...filters,
                  sentimentRange: [Math.min(min, max), max],
                });
              }}
              aria-label="Minimum sentiment"
              className="w-full"
            />
            <input
              type="range"
              min={-1}
              max={1}
              step={0.1}
              value={filters.sentimentRange[1]}
              onChange={(e) => {
                const max = Number(e.target.value);
                const min = filters.sentimentRange![0];
                onChange({
                  ...filters,
                  sentimentRange: [min, Math.max(min, max)],
                });
              }}
              aria-label="Maximum sentiment"
              className="w-full"
            />
          </div>
        )}
      </div>
    </div>
  );
}

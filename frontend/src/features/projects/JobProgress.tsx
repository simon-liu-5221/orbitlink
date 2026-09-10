import { Link } from "react-router-dom";

import type { Job } from "./api";
import { isLive, isTerminal, jobStageLabel, LIVE_STATUSES } from "./jobStatus";

const ERROR_HELP: Record<string, string> = {
  RESOURCE_NOT_FOUND: "That video or channel doesn't exist or is private.",
  COMMENTS_DISABLED: "Comments are turned off on that video.",
  QUOTA_EXCEEDED:
    "The YouTube API quota is used up. Try again after midnight Pacific.",
  INVALID_URL: "That link isn't a YouTube video or channel.",
};

export function JobProgress({
  job,
  onCancel,
}: {
  job: Job;
  onCancel?: () => void;
}) {
  const live = isLive(job.status);
  const failed = job.status === "failed";
  const stageIndex = LIVE_STATUSES.indexOf(
    job.status as (typeof LIVE_STATUSES)[number],
  );

  return (
    <div className="space-y-2 rounded-lg border border-slate-200 p-4">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-slate-800">
          {jobStageLabel(job.status)}
        </span>
        <span className="text-slate-400">
          {new Date(job.created_at).toLocaleString()}
        </span>
      </div>

      {live && (
        <>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-slate-900 transition-all"
              style={{ width: `${Math.max(job.progress, 4)}%` }}
              role="progressbar"
              aria-valuenow={job.progress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          <ol className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-400">
            {LIVE_STATUSES.map((stage, i) => (
              <li
                key={stage}
                className={i <= stageIndex ? "text-slate-700" : ""}
              >
                {i <= stageIndex ? "●" : "○"} {jobStageLabel(stage)}
              </li>
            ))}
          </ol>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-xs text-slate-500 underline"
            >
              Cancel
            </button>
          )}
        </>
      )}

      {failed && (
        <p className="text-sm text-red-600">
          {job.error_code && ERROR_HELP[job.error_code]
            ? ERROR_HELP[job.error_code]
            : (job.error_message ?? "The analysis failed.")}
        </p>
      )}

      {job.status === "cancelled" && (
        <p className="text-sm text-slate-500">Cancelled.</p>
      )}

      {job.status === "completed" && job.analysis_id && (
        <Link
          to={`/analyses/${job.analysis_id}`}
          className="inline-block text-sm font-medium text-slate-900 underline"
        >
          View results
        </Link>
      )}

      {isTerminal(job.status) &&
        job.status === "completed" &&
        !job.analysis_id && (
          <p className="text-sm text-slate-500">
            Finished, but no results were saved.
          </p>
        )}
    </div>
  );
}

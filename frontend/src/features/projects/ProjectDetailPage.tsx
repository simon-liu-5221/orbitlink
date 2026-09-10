import type { FormEvent } from "react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { Button, FormError, Spinner, TextField } from "@/components/ui";

import { projectsApi } from "./api";
import { JobProgress } from "./JobProgress";
import { isLive } from "./jobStatus";

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const project = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => projectsApi.get(projectId),
    retry: (count, err) =>
      !(err instanceof ApiError && err.status === 403) && count < 2,
  });

  const jobs = useQuery({
    queryKey: ["projects", projectId, "jobs"],
    queryFn: () => projectsApi.jobs(projectId),
    enabled: project.isSuccess,
    refetchInterval: (query) =>
      (query.state.data ?? []).some((job) => isLive(job.status)) ? 2000 : false,
  });

  const anyLive = (jobs.data ?? []).some((job) => isLive(job.status));

  const startAnalysis = useMutation({
    mutationFn: (sourceUrl: string) =>
      projectsApi.startAnalysis(projectId, { source_url: sourceUrl }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "jobs"],
      });
    },
  });

  const cancelJob = useMutation({
    mutationFn: (jobId: string) => projectsApi.cancelJob(jobId),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["projects", projectId, "jobs"],
      }),
  });

  const remove = useMutation({
    mutationFn: () => projectsApi.remove(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate("/", { replace: true });
    },
  });

  if (project.isLoading) {
    return (
      <AppShell>
        <div className="flex justify-center p-12 text-slate-400">
          <Spinner />
        </div>
      </AppShell>
    );
  }

  if (project.isError || !project.data) {
    const forbidden =
      project.error instanceof ApiError && project.error.status === 403;
    return (
      <AppShell>
        <div className="mx-auto max-w-3xl p-6">
          <FormError>
            {forbidden
              ? "That project doesn't exist, or it isn't yours."
              : "Couldn't load that project."}
          </FormError>
          <Link to="/" className="mt-3 inline-block text-sm underline">
            Back to projects
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-8 p-6">
        <Link to="/" className="text-sm text-slate-500 underline">
          ← All projects
        </Link>

        <ProjectHeader
          name={project.data.name}
          archived={project.data.archived_at !== null}
          busy={anyLive}
          onRename={(name) => projectsApi.rename(projectId, name)}
          onRenamed={() =>
            queryClient.invalidateQueries({ queryKey: ["projects", projectId] })
          }
          onDelete={() => remove.mutate()}
          deleting={remove.isPending}
          deleteError={
            remove.error instanceof ApiError && remove.error.status === 409
              ? "Wait for the running analysis to finish, or cancel it first."
              : remove.isError
                ? "Couldn't delete the project."
                : null
          }
        />

        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Start an analysis
          </h2>
          <StartAnalysisForm
            disabled={anyLive}
            pending={startAnalysis.isPending}
            error={
              startAnalysis.error instanceof ApiError
                ? startAnalysis.error.status === 409
                  ? "This project already has an analysis running."
                  : startAnalysis.error.status === 422
                    ? "That doesn't look like a YouTube video or channel link."
                    : "Couldn't start the analysis."
                : null
            }
            onSubmit={(url) => startAnalysis.mutate(url)}
          />
        </section>

        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Analyses
          </h2>
          {jobs.isLoading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : jobs.data && jobs.data.length > 0 ? (
            <div className="space-y-3">
              {jobs.data.map((job) => (
                <JobProgress
                  key={job.id}
                  job={job}
                  onCancel={
                    isLive(job.status)
                      ? () => cancelJob.mutate(job.id)
                      : undefined
                  }
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">
              No analyses yet. Paste a link above to run the first one.
            </p>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function ProjectHeader({
  name,
  archived,
  onRename,
  onRenamed,
  onDelete,
  deleting,
  deleteError,
}: {
  name: string;
  archived: boolean;
  busy: boolean;
  onRename: (name: string) => Promise<unknown>;
  onRenamed: () => void;
  onDelete: () => void;
  deleting: boolean;
  deleteError: string | null;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const rename = useMutation({
    mutationFn: () => onRename(draft.trim()),
    onSuccess: () => {
      setEditing(false);
      onRenamed();
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (draft.trim() && draft.trim() !== name) rename.mutate();
    else setEditing(false);
  }

  return (
    <div className="space-y-2">
      {editing ? (
        <form onSubmit={submit} className="flex items-end gap-2">
          <div className="flex-1">
            <TextField
              label="Project name"
              value={draft}
              maxLength={200}
              autoFocus
              onChange={(e) => setDraft(e.target.value)}
            />
          </div>
          <Button type="submit" loading={rename.isPending}>
            Save
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setDraft(name);
              setEditing(false);
            }}
          >
            Cancel
          </Button>
        </form>
      ) : (
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-slate-900">{name}</h1>
          {archived && (
            <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
              Archived
            </span>
          )}
          <Button variant="ghost" onClick={() => setEditing(true)}>
            Rename
          </Button>
        </div>
      )}

      {rename.isError && <FormError>Couldn't rename the project.</FormError>}

      <div>
        {confirmingDelete ? (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-slate-600">
              Delete this project and all its analyses?
            </span>
            <Button variant="danger" onClick={onDelete} loading={deleting}>
              Delete
            </Button>
            <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
              Keep
            </Button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className="text-xs text-red-600 underline"
          >
            Delete project
          </button>
        )}
        {deleteError && <FormError>{deleteError}</FormError>}
      </div>
    </div>
  );
}

function StartAnalysisForm({
  disabled,
  pending,
  error,
  onSubmit,
}: {
  disabled: boolean;
  pending: boolean;
  error: string | null;
  onSubmit: (url: string) => void;
}) {
  const [url, setUrl] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (url.trim()) onSubmit(url.trim());
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex items-end gap-2">
        <div className="flex-1">
          <TextField
            label="YouTube video or channel link"
            placeholder="https://youtube.com/watch?v=…  or  https://youtube.com/@channel"
            value={url}
            disabled={disabled}
            onChange={(e) => setUrl(e.target.value)}
          />
        </div>
        <Button
          type="submit"
          loading={pending}
          disabled={disabled || !url.trim()}
        >
          Start
        </Button>
      </div>
      {disabled && (
        <p className="text-xs text-slate-500">
          An analysis is already running for this project.
        </p>
      )}
      <FormError>{error}</FormError>
    </form>
  );
}

import type { FormEvent } from "react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { AppShell } from "@/components/AppShell";
import { Button, FormError, Spinner, TextField } from "@/components/ui";

import { projectsApi } from "./api";

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const projects = useQuery({
    queryKey: ["projects", { q: search, includeArchived }],
    queryFn: () => projectsApi.list({ q: search, includeArchived }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["projects"] });

  const create = useMutation({
    mutationFn: () => projectsApi.create(newName),
    onSuccess: () => {
      setNewName("");
      setCreateError(null);
      invalidate();
    },
    onError: (err) => {
      setCreateError(
        err instanceof ApiError && err.status === 422
          ? "Give the project a name (up to 200 characters)."
          : "Couldn't create the project. Try again.",
      );
    },
  });

  const archive = useMutation({
    mutationFn: ({ id, archived }: { id: string; archived: boolean }) =>
      archived ? projectsApi.unarchive(id) : projectsApi.archive(id),
    onSuccess: invalidate,
  });

  function onCreate(event: FormEvent) {
    event.preventDefault();
    if (newName.trim()) create.mutate();
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-6 p-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-slate-900">Projects</h1>
        </div>

        <form onSubmit={onCreate} className="flex items-end gap-2">
          <div className="flex-1">
            <TextField
              label="New project"
              placeholder="e.g. Climate discourse on YouTube"
              value={newName}
              maxLength={200}
              onChange={(e) => setNewName(e.target.value)}
            />
          </div>
          <Button
            type="submit"
            loading={create.isPending}
            disabled={!newName.trim()}
          >
            Create
          </Button>
        </form>
        <FormError>{createError}</FormError>

        <div className="flex items-center gap-3">
          <input
            type="search"
            placeholder="Search projects"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
          />
          <label className="flex shrink-0 items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(e) => setIncludeArchived(e.target.checked)}
            />
            Show archived
          </label>
        </div>

        {projects.isLoading ? (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <Spinner className="h-4 w-4" /> Loading…
          </p>
        ) : projects.isError ? (
          <FormError>Couldn't load your projects.</FormError>
        ) : projects.data && projects.data.length > 0 ? (
          <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
            {projects.data.map((project) => (
              <li
                key={project.id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0">
                  <Link
                    to={`/projects/${project.id}`}
                    className="block truncate font-medium text-slate-900 hover:underline"
                  >
                    {project.name}
                  </Link>
                  <p className="text-xs text-slate-400">
                    {project.archived_at ? "Archived · " : ""}
                    created {new Date(project.created_at).toLocaleDateString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  onClick={() =>
                    archive.mutate({
                      id: project.id,
                      archived: project.archived_at !== null,
                    })
                  }
                >
                  {project.archived_at ? "Restore" : "Archive"}
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
            {search
              ? "No projects match that search."
              : "No projects yet. Create one above to start analysing."}
          </p>
        )}
      </div>
    </AppShell>
  );
}

import { apiRequest } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type Project = Schemas["ProjectOut"];
export type Job = Schemas["JobStatusOut"];
export type Analysis = Schemas["AnalysisOut"];
export type AnalysisGraph = Schemas["AnalysisGraphOut"];

export interface ListProjectsParams {
  q?: string;
  includeArchived?: boolean;
}

export const projectsApi = {
  list: ({ q, includeArchived }: ListProjectsParams = {}) => {
    const params = new URLSearchParams();
    if (q?.trim()) params.set("q", q.trim());
    if (includeArchived) params.set("include_archived", "true");
    const suffix = params.toString() ? `?${params}` : "";
    return apiRequest<Project[]>(`/api/v1/projects${suffix}`);
  },

  get: (id: string) => apiRequest<Project>(`/api/v1/projects/${id}`),

  create: (name: string) =>
    apiRequest<Project>("/api/v1/projects", { method: "POST", body: { name } }),

  rename: (id: string, name: string) =>
    apiRequest<Project>(`/api/v1/projects/${id}`, {
      method: "PATCH",
      body: { name },
    }),

  archive: (id: string) =>
    apiRequest<Project>(`/api/v1/projects/${id}/archive`, { method: "POST" }),

  unarchive: (id: string) =>
    apiRequest<Project>(`/api/v1/projects/${id}/unarchive`, { method: "POST" }),

  remove: (id: string) =>
    apiRequest<void>(`/api/v1/projects/${id}`, { method: "DELETE" }),

  jobs: (id: string) => apiRequest<Job[]>(`/api/v1/projects/${id}/jobs`),

  startAnalysis: (projectId: string, body: Schemas["AnalysisCreate"]) =>
    apiRequest<Schemas["JobAccepted"]>(
      `/api/v1/projects/${projectId}/analyses`,
      {
        method: "POST",
        body,
      },
    ),

  job: (jobId: string) => apiRequest<Job>(`/api/v1/jobs/${jobId}`),

  cancelJob: (jobId: string) =>
    apiRequest<Job>(`/api/v1/jobs/${jobId}/cancel`, { method: "POST" }),

  analysis: (analysisId: string) =>
    apiRequest<Analysis>(`/api/v1/analyses/${analysisId}`),

  analysisGraph: (analysisId: string) =>
    apiRequest<AnalysisGraph>(`/api/v1/analyses/${analysisId}/graph`),
};

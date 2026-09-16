import { apiRequest } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];
export type AdminUser = Schemas["AdminUserOut"];
export type AdminFeedback = Schemas["AdminFeedbackOut"];

export const adminApi = {
  listUsers: (q?: string) => {
    const params = new URLSearchParams();
    if (q?.trim()) params.set("q", q.trim());
    const suffix = params.toString() ? `?${params}` : "";
    return apiRequest<AdminUser[]>(`/api/v1/admin/users${suffix}`);
  },

  suspend: (userId: string) =>
    apiRequest<AdminUser>(`/api/v1/admin/users/${userId}/suspend`, {
      method: "POST",
    }),

  unsuspend: (userId: string) =>
    apiRequest<AdminUser>(`/api/v1/admin/users/${userId}/unsuspend`, {
      method: "POST",
    }),

  listFeedback: () => apiRequest<AdminFeedback[]>("/api/v1/admin/feedback"),
};

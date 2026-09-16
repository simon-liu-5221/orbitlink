import { apiRequest } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];

export const feedbackApi = {
  submit: (body: Schemas["FeedbackCreate"]) =>
    apiRequest<Schemas["FeedbackOut"]>("/api/v1/feedback", {
      method: "POST",
      body,
    }),
};

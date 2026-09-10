import { apiRequest } from "@/api/client";
import type { components } from "@/api/schema";

type Schemas = components["schemas"];

const NO_AUTH = { auth: false } as const;

export const authApi = {
  register: (body: Schemas["RegisterRequest"]) =>
    apiRequest<Schemas["MessageResponse"]>("/api/v1/auth/register", {
      method: "POST",
      body,
      ...NO_AUTH,
    }),

  login: (body: Schemas["LoginRequest"]) =>
    apiRequest<Schemas["TokenResponse"]>("/api/v1/auth/login", {
      method: "POST",
      body,
      ...NO_AUTH,
    }),

  logout: () =>
    apiRequest<void>("/api/v1/auth/logout", { method: "POST", ...NO_AUTH }),

  verifyEmail: (token: string) =>
    apiRequest<Schemas["MessageResponse"]>(
      `/api/v1/auth/verify?token=${encodeURIComponent(token)}`,
      NO_AUTH,
    ),

  resendVerification: (email: string) =>
    apiRequest<Schemas["MessageResponse"]>("/api/v1/auth/resend-verification", {
      method: "POST",
      body: { email },
      ...NO_AUTH,
    }),

  forgotPassword: (email: string) =>
    apiRequest<Schemas["MessageResponse"]>("/api/v1/auth/forgot-password", {
      method: "POST",
      body: { email },
      ...NO_AUTH,
    }),

  resetPassword: (body: Schemas["ResetPasswordRequest"]) =>
    apiRequest<Schemas["MessageResponse"]>("/api/v1/auth/reset-password", {
      method: "POST",
      body,
      ...NO_AUTH,
    }),

  me: () => apiRequest<Schemas["UserOut"]>("/api/v1/auth/me"),
};

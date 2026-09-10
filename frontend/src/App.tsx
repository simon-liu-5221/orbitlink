import { Navigate, Route, Routes } from "react-router-dom";

import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { RedirectIfAuthed, RequireAuth } from "@/features/auth/RequireAuth";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { useSessionBootstrap } from "@/features/auth/session";
import { VerifyEmailPage } from "@/features/auth/VerifyEmailPage";
import { HealthStatus } from "@/features/health/HealthStatus";
import { AnalysisResultPage } from "@/features/projects/AnalysisResultPage";
import { ProjectDetailPage } from "@/features/projects/ProjectDetailPage";
import { ProjectsPage } from "@/features/projects/ProjectsPage";

export default function App() {
  useSessionBootstrap();

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <LoginPage />
          </RedirectIfAuthed>
        }
      />
      <Route
        path="/register"
        element={
          <RedirectIfAuthed>
            <RegisterPage />
          </RedirectIfAuthed>
        }
      />
      <Route path="/verify" element={<VerifyEmailPage />} />
      <Route
        path="/status"
        element={
          <div className="mx-auto max-w-lg space-y-4 p-8">
            <h1 className="text-lg font-semibold text-slate-900">
              System status
            </h1>
            <HealthStatus />
          </div>
        }
      />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route
        path="/"
        element={
          <RequireAuth>
            <ProjectsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/projects/:projectId"
        element={
          <RequireAuth>
            <ProjectDetailPage />
          </RequireAuth>
        }
      />
      <Route
        path="/analyses/:analysisId"
        element={
          <RequireAuth>
            <AnalysisResultPage />
          </RequireAuth>
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

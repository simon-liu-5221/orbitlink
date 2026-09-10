import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { renderWithProviders, resetAuthStore } from "@/test/utils";

import { ProjectsPage } from "./ProjectsPage";
import type { Project } from "./api";
import { projectsApi } from "./api";

vi.mock("./api", () => ({
  projectsApi: {
    list: vi.fn(),
    create: vi.fn(),
    archive: vi.fn(),
    unarchive: vi.fn(),
  },
}));
vi.mock("@/features/auth/session", () => ({ signOut: vi.fn() }));

function project(name: string, over: Partial<Project> = {}): Project {
  return {
    id: crypto.randomUUID(),
    name,
    archived_at: null,
    created_at: new Date().toISOString(),
    ...over,
  };
}

beforeEach(() => {
  resetAuthStore();
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

test("renders the caller's projects", async () => {
  vi.mocked(projectsApi.list).mockResolvedValue([
    project("Climate discourse"),
    project("Gaming channel"),
  ]);

  renderWithProviders(<ProjectsPage />);

  expect(await screen.findByText("Climate discourse")).toBeInTheDocument();
  expect(screen.getByText("Gaming channel")).toBeInTheDocument();
});

test("shows the empty state when there are none", async () => {
  vi.mocked(projectsApi.list).mockResolvedValue([]);
  renderWithProviders(<ProjectsPage />);
  expect(await screen.findByText(/no projects yet/i)).toBeInTheDocument();
});

test("creating a project calls the API and refetches", async () => {
  vi.mocked(projectsApi.list).mockResolvedValue([]);
  vi.mocked(projectsApi.create).mockResolvedValue(project("My study"));

  renderWithProviders(<ProjectsPage />);
  await screen.findByText(/no projects yet/i);

  await userEvent.type(screen.getByLabelText("New project"), "My study");
  vi.mocked(projectsApi.list).mockResolvedValue([project("My study")]);
  await userEvent.click(screen.getByRole("button", { name: "Create" }));

  await waitFor(() =>
    expect(projectsApi.create).toHaveBeenCalledWith("My study"),
  );
  expect(await screen.findByText("My study")).toBeInTheDocument();
});

test("archived projects can be restored from the row action", async () => {
  vi.mocked(projectsApi.list).mockResolvedValue([
    project("Old one", { archived_at: new Date().toISOString() }),
  ]);
  vi.mocked(projectsApi.unarchive).mockResolvedValue(project("Old one"));

  renderWithProviders(<ProjectsPage />);
  const row = (await screen.findByText("Old one")).closest("li")!;
  await userEvent.click(within(row).getByRole("button", { name: "Restore" }));

  await waitFor(() => expect(projectsApi.unarchive).toHaveBeenCalled());
});

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { NewProject } from "../../pages/NewProject";
import { projectsApi } from "../../api/client";
import { renderWithProviders } from "../test-utils";

const navigate = vi.fn();

vi.mock("react-router-dom", async (orig) => {
  const m = await orig<typeof import("react-router-dom")>();
  return { ...m, useNavigate: () => navigate };
});

vi.mock("../../api/client", async (orig) => {
  const mod = await orig<typeof import("../../api/client")>();
  return {
    ...mod,
    projectsApi: {
      ...mod.projectsApi,
      create: vi.fn(),
      startRun: vi.fn(),
    },
  };
});

const validForm = {
  name: "My App",
  description: "A short but valid description.",
  requirements: "x".repeat(50),
};

describe("NewProject", () => {
  const create = vi.mocked(projectsApi.create);
  const startRun = vi.mocked(projectsApi.startRun);

  beforeEach(() => {
    vi.clearAllMocks();
    navigate.mockReset();
    create.mockResolvedValue({
      id: "proj-new",
      name: validForm.name,
      description: validForm.description,
      requirements: validForm.requirements,
      status: "pending",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    } as Awaited<ReturnType<typeof projectsApi.create>>);
    startRun.mockResolvedValue({} as Awaited<ReturnType<typeof projectsApi.startRun>>);
  });

  it("submits and navigates to project detail", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MemoryRouter>
        <NewProject />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: /load example/i }));
    await user.type(screen.getByPlaceholderText(/e\.g\., task management api/i), validForm.name);
    await user.type(
      screen.getByPlaceholderText(/one-line description/i),
      validForm.description
    );

    await user.click(screen.getByRole("button", { name: /create project & start build/i }));

    await waitFor(() => {
      expect(create).toHaveBeenCalled();
      expect(startRun).toHaveBeenCalledWith("proj-new");
    });
    expect(navigate).toHaveBeenCalledWith("/projects/proj-new");
  });

  it("loads example requirements when clicking load example", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MemoryRouter>
        <NewProject />
      </MemoryRouter>
    );
    await user.click(screen.getByRole("button", { name: /load example/i }));
    const req = screen.getByPlaceholderText(/describe what you need/i) as HTMLTextAreaElement;
    expect(req.value).toContain("task management");
  });
});

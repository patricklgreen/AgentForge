import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Dashboard } from "../../pages/Dashboard";
import { projectsApi } from "../../api/client";
import { useAppStore } from "../../store";
import { renderWithProviders } from "../test-utils";

vi.mock("../../store", () => ({
  useAppStore: vi.fn(),
}));

vi.mock("../../api/client", async (orig) => {
  const mod = await orig<typeof import("../../api/client")>();
  return {
    ...mod,
    projectsApi: {
      ...mod.projectsApi,
      list: vi.fn(),
      delete: vi.fn(),
    },
  };
});

describe("Dashboard Page", () => {
  const list = vi.mocked(projectsApi.list);
  const del = vi.mocked(projectsApi.delete);

  beforeEach(() => {
    vi.clearAllMocks();
    (useAppStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      user: {
        id: "u1",
        email: "a@b.com",
        username: "ab",
        is_verified: true,
      },
    });
    list.mockResolvedValue([
      {
        id: "p1",
        name: "Alpha",
        description: "d",
        requirements: "r",
        status: "completed",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    ]);
    del.mockResolvedValue(undefined);
  });

  it("lists projects and shows stats", async () => {
    renderWithProviders(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    expect(await screen.findByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getByText("Total")).toBeInTheDocument();
  });

  it("opens delete confirmation and deletes a project", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    await screen.findByText("Alpha");
    await user.click(screen.getByTitle("Delete project"));
    const confirmButtons = screen.getAllByRole("button", { name: /^delete project$/i });
    await user.click(confirmButtons[confirmButtons.length - 1]!);
    await waitFor(() => {
      expect(del).toHaveBeenCalledWith("p1");
    });
  });
});

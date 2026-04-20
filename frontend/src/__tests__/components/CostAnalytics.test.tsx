import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import CostAnalytics from "../../components/CostAnalytics";
import { projectsApi } from "../../api/client";
import { renderWithProviders } from "../test-utils";

vi.mock("../../api/client", async (orig) => {
  const m = await orig<typeof import("../../api/client")>();
  return {
    ...m,
    projectsApi: {
      ...m.projectsApi,
      getCostAnalytics: vi.fn(),
    },
  };
});

const baseAnalytics = {
  project_id: "p1",
  project_name: "Test",
  total_runs: 3,
  total_cost_usd: 2.5,
  total_tokens: 1000,
  average_cost_per_run: 0.83,
  cost_by_agent: { AgentA: 1.5, AgentB: 1.0 },
  recent_runs: [
    {
      run_id: "r1",
      created_at: new Date().toISOString(),
      status: "completed",
      cost_usd: 1,
      tokens: 400,
    },
  ],
  cost_trend: [
    { run_id: "a", created_at: new Date().toISOString(), status: "completed", cost_usd: 2, tokens: 100 },
    { run_id: "b", created_at: new Date().toISOString(), status: "completed", cost_usd: 1, tokens: 100 },
    { run_id: "c", created_at: new Date().toISOString(), status: "failed", cost_usd: 0.5, tokens: 50 },
    { run_id: "d", created_at: new Date().toISOString(), status: "running", cost_usd: 0.1, tokens: 10 },
    { run_id: "e", created_at: new Date().toISOString(), status: "completed", cost_usd: 1, tokens: 100 },
    { run_id: "f", created_at: new Date().toISOString(), status: "completed", cost_usd: 1, tokens: 100 },
    { run_id: "g", created_at: new Date().toISOString(), status: "completed", cost_usd: 1, tokens: 100 },
    { run_id: "h", created_at: new Date().toISOString(), status: "completed", cost_usd: 1, tokens: 100 },
    { run_id: "i", created_at: new Date().toISOString(), status: "completed", cost_usd: 1, tokens: 100 },
    { run_id: "j", created_at: new Date().toISOString(), status: "completed", cost_usd: 1, tokens: 100 },
  ],
};

describe("CostAnalytics", () => {
  const getCostAnalytics = vi.mocked(projectsApi.getCostAnalytics);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading skeleton", () => {
    getCostAnalytics.mockImplementation(() => new Promise(() => {}));
    renderWithProviders(
      <CostAnalytics projectId="p1" projectStatus="pending" />
    );
    expect(screen.getByText("Cost Analytics")).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).toBeTruthy();
  });

  it("shows auth error messaging for 401", async () => {
    getCostAnalytics.mockRejectedValue({ response: { status: 401 } });
    renderWithProviders(
      <CostAnalytics projectId="p1" projectStatus="pending" />
    );
    await waitFor(() => {
      expect(
        screen.getByText("Authentication required to view cost analytics")
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole("button", { name: /refresh page to re-authenticate/i })
    ).toBeInTheDocument();
  });

  it("shows not found for 404 (no query retries)", async () => {
    getCostAnalytics.mockRejectedValue({ response: { status: 404 } });
    renderWithProviders(
      <CostAnalytics projectId="p1" projectStatus="pending" />
    );
    await waitFor(() => {
      expect(screen.getByText("Project not found")).toBeInTheDocument();
    });
  });

  it("renders summary and agent breakdown", async () => {
    getCostAnalytics.mockResolvedValue(baseAnalytics);
    renderWithProviders(
      <CostAnalytics projectId="p1" projectStatus="completed" />
    );
    await waitFor(() => {
      expect(screen.getByText("Total Cost")).toBeInTheDocument();
    });
    expect(screen.getByText("Cost by Agent")).toBeInTheDocument();
    expect(screen.getByText("AgentA")).toBeInTheDocument();
    expect(screen.getByText("Recent Runs")).toBeInTheDocument();
  });
});

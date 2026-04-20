import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import CostTracker from "../../components/CostTracker";
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

describe("CostTracker", () => {
  const getCostAnalytics = vi.mocked(projectsApi.getCostAnalytics);

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns null while loading with no cached data", async () => {
    getCostAnalytics.mockImplementation(
      () => new Promise(() => {})
    );
    const { container } = renderWithProviders(
      <CostTracker projectId="p1" projectStatus="pending" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("returns null on error", async () => {
    getCostAnalytics.mockRejectedValue(new Error("network"));
    const { container } = renderWithProviders(
      <CostTracker projectId="p1" projectStatus="pending" />
    );
    await waitFor(() => {
      expect(getCostAnalytics).toHaveBeenCalled();
    });
    expect(container.firstChild).toBeNull();
  });

  it("returns null when there are no runs", async () => {
    getCostAnalytics.mockResolvedValue({
      total_runs: 0,
      total_cost_usd: 0,
      total_tokens: 0,
    });
    const { container } = renderWithProviders(
      <CostTracker projectId="p1" projectStatus="completed" />
    );
    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("renders cost, tokens, and runs when analytics exist", async () => {
    getCostAnalytics.mockResolvedValue({
      total_runs: 2,
      total_cost_usd: 1.2345,
      total_tokens: 9999,
    });
    renderWithProviders(<CostTracker projectId="p1" projectStatus="completed" />);
    await waitFor(() => {
      expect(screen.getByText(/\$1\.2345/)).toBeInTheDocument();
    });
    expect(screen.getByText(/9,999/)).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });
});

import { describe, it, expect, vi, beforeEach } from "vitest";

const mockInstance = {
  get:    vi.fn(() => Promise.resolve({ data: { ok: true } })),
  post:   vi.fn(() => Promise.resolve({ data: { ok: true } })),
  put:    vi.fn(() => Promise.resolve({ data: { ok: true } })),
  delete: vi.fn(() => Promise.resolve({ data: {} })),
  interceptors: {
    request:  { use: vi.fn(), eject: vi.fn() },
    response: { use: vi.fn(), eject: vi.fn() },
  },
};

vi.mock("axios", () => ({
  default: {
    create: () => mockInstance,
    post: vi.fn(() => Promise.resolve({ data: { access_token: "a", refresh_token: "r" } })),
  },
}));

describe("API client method invocations", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("calls projects, artifacts, and email verification endpoints", async () => {
    const {
      projectsApi,
      artifactsApi,
      emailVerificationApi,
      authApi,
      tokenService,
    } = await import("../../api/client");

    const file = new File(["x"], "f.png", { type: "image/png" });

    await projectsApi.create({
      name: "n",
      description: "d".repeat(25),
      requirements: "r".repeat(50),
      target_language: "Python",
    });
    await projectsApi.list(0, 10);
    await projectsApi.get("pid");
    await projectsApi.startRun("pid");
    await projectsApi.listRuns("pid");
    await projectsApi.getRun("pid", "rid");
    await projectsApi.submitFeedback("pid", "rid", {
      action: "approve",
      feedback: "",
    });
    await projectsApi.updateRequirements("pid", "rid", { spec: {} });
    await projectsApi.getRequirements("pid");
    await projectsApi.cancelRun("pid", "rid");
    await projectsApi.getRunState("pid", "rid");
    await projectsApi.delete("pid");
    await projectsApi.getRunCost("pid", "rid");
    await projectsApi.getCostAnalytics("pid");
    await projectsApi.uploadVisualReference(file, "desc");

    await artifactsApi.list("pid");
    await artifactsApi.getContent("aid");
    await artifactsApi.getDownloadUrl("aid");

    await emailVerificationApi.sendVerificationEmail("a@b.com");
    await emailVerificationApi.confirmEmailVerification("tok");
    await emailVerificationApi.getVerificationStatus();

    await authApi.login({ email: "a@b.com", password: "secret" });
    await authApi.register({
      email: "a@b.com",
      username: "u",
      password: "secret",
    });
    await authApi.me();
    await authApi.refresh("refresh-token");
    tokenService.setTokens("access", "refresh");
    await authApi.logout();
    tokenService.clearTokens();
    await authApi.logout();

    expect(mockInstance.post).toHaveBeenCalled();
    expect(mockInstance.get).toHaveBeenCalled();
  });
});

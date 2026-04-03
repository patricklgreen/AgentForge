import { describe, it, expect } from "vitest";

describe("Dashboard Page", () => {
  it("should export Dashboard component", async () => {
    const { Dashboard } = await import("../../pages/Dashboard");
    expect(typeof Dashboard).toBe("function");
  });

  it("should be a valid React component", async () => {
    const { Dashboard } = await import("../../pages/Dashboard");
    expect(Dashboard.name).toBe("Dashboard");
  });
});
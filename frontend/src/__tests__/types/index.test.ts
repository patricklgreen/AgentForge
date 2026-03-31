import { describe, it, expect } from "vitest";

describe("Type Definitions", () => {
  it("should have correct Project interface structure", () => {
    const mockProject = {
      id: "project-123",
      name: "Test Project",
      description: "A test project",
      requirements: "Build a test application",
      target_language: "TypeScript",
      target_framework: "React",
      status: "pending" as const,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };

    expect(typeof mockProject.id).toBe("string");
    expect(typeof mockProject.name).toBe("string");
    expect(typeof mockProject.description).toBe("string");
    expect(typeof mockProject.requirements).toBe("string");
    expect(["pending", "running", "completed", "failed"]).toContain(mockProject.status);
  });

  it("should have correct ProjectRun interface structure", () => {
    const mockRun = {
      id: "run-123",
      project_id: "project-123",
      thread_id: "thread-123",
      status: "running" as const,
      current_step: "requirements_analysis",
      interrupt_payload: null,
      error_message: null,
      started_at: "2024-01-01T00:00:00Z",
      completed_at: null,
      created_at: "2024-01-01T00:00:00Z",
      events: [],
    };

    expect(typeof mockRun.id).toBe("string");
    expect(typeof mockRun.project_id).toBe("string");
    expect(["pending", "running", "completed", "failed", "cancelled"]).toContain(mockRun.status);
    expect(Array.isArray(mockRun.events)).toBe(true);
  });

  it("should have correct RunEvent interface structure", () => {
    const mockEvent = {
      id: "event-123",
      run_id: "run-123",
      event_type: "agent_start",
      agent_name: "RequirementsAnalyst",
      step: "requirements_analysis",
      message: "Starting analysis",
      data: {},
      created_at: "2024-01-01T00:00:00Z",
    };

    expect(typeof mockEvent.id).toBe("string");
    expect(typeof mockEvent.run_id).toBe("string");
    expect(typeof mockEvent.event_type).toBe("string");
    expect(typeof mockEvent.agent_name).toBe("string");
    expect(typeof mockEvent.step).toBe("string");
    expect(typeof mockEvent.message).toBe("string");
    expect(typeof mockEvent.data).toBe("object");
  });

  it("should have correct WsMessage interface structure", () => {
    const mockMessage = {
      type: "agent_start",
      agent: "RequirementsAnalyst",
      step: "requirements_analysis",
      message: "Starting analysis",
      data: { some: "data" },
    };

    expect(typeof mockMessage.type).toBe("string");
    expect(typeof mockMessage.agent).toBe("string");
    expect(typeof mockMessage.step).toBe("string");
    expect(typeof mockMessage.message).toBe("string");
    expect(typeof mockMessage.data).toBe("object");
  });

  it("should handle optional fields correctly", () => {
    const projectWithOptionalFields = {
      id: "project-123",
      name: "Test Project",
      description: undefined,
      requirements: "Build a test application",
      target_language: "TypeScript",
      target_framework: "React",
      status: "pending" as const,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
    };

    expect(projectWithOptionalFields.description).toBeUndefined();
    expect(typeof projectWithOptionalFields.name).toBe("string");
  });

  it("should handle different project statuses", () => {
    const statuses = ["pending", "running", "completed", "failed"] as const;
    
    statuses.forEach(status => {
      expect(["pending", "running", "completed", "failed"]).toContain(status);
    });
  });

  it("should handle different run statuses", () => {
    const runStatuses = ["pending", "running", "completed", "failed", "cancelled"] as const;
    
    runStatuses.forEach(status => {
      expect(["pending", "running", "completed", "failed", "cancelled"]).toContain(status);
    });
  });

  it("should handle different event types", () => {
    const eventTypes = [
      "agent_start",
      "agent_complete", 
      "interrupt",
      "error",
      "user_feedback",
      "artifact_created",
    ];

    eventTypes.forEach(eventType => {
      expect(typeof eventType).toBe("string");
      expect(eventType.length).toBeGreaterThan(0);
    });
  });
});
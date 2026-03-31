import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAppStore } from "../../store";
import type { Project, ProjectRun, WsMessage, RunEvent } from "../../types";

const mockProject: Project = {
  id: "project-123",
  name: "Test Project",
  description: "A test project",
  requirements: "Build a test application",
  target_language: "TypeScript",
  target_framework: "React",
  status: "pending",
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockProjectRun: ProjectRun = {
  id: "run-123",
  project_id: "project-123",
  thread_id: "thread-123",
  status: "running",
  current_step: "requirements_analysis",
  interrupt_payload: null,
  error_message: null,
  started_at: "2024-01-01T00:00:00Z",
  completed_at: null,
  created_at: "2024-01-01T00:00:00Z",
  events: [],
};

const mockWsMessage: WsMessage = {
  type: "agent_start",
  agent: "RequirementsAnalyst",
  step: "requirements_analysis",
  message: "Starting requirements analysis",
  data: {},
};

describe("useAppStore Projects", () => {
  beforeEach(() => {
    // Reset store before each test
    const { getState } = useAppStore;
    act(() => {
      getState().setProjects([]);
    });
  });

  it("should initialize with empty projects array", () => {
    const { result } = renderHook(() => useAppStore());
    
    expect(result.current.projects).toEqual([]);
  });

  it("should set projects", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setProjects([mockProject]);
    });
    
    expect(result.current.projects).toEqual([mockProject]);
  });

  it("should add project to beginning of array", () => {
    const { result } = renderHook(() => useAppStore());
    
    const existingProject = { ...mockProject, id: "existing-project" };
    const newProject = { ...mockProject, id: "new-project" };
    
    act(() => {
      result.current.setProjects([existingProject]);
    });
    
    act(() => {
      result.current.addProject(newProject);
    });
    
    expect(result.current.projects).toEqual([newProject, existingProject]);
  });

  it("should update project by id", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setProjects([mockProject]);
    });
    
    act(() => {
      result.current.updateProject("project-123", {
        name: "Updated Project Name",
        status: "completed",
      });
    });
    
    expect(result.current.projects[0]).toEqual({
      ...mockProject,
      name: "Updated Project Name",
      status: "completed",
    });
  });

  it("should not update non-existent project", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setProjects([mockProject]);
    });
    
    act(() => {
      result.current.updateProject("non-existent", { name: "Updated" });
    });
    
    expect(result.current.projects).toEqual([mockProject]);
  });
});

describe("useAppStore Active Run", () => {
  beforeEach(() => {
    // Reset store before each test
    const { getState } = useAppStore;
    act(() => {
      getState().setActiveRun(null);
    });
  });

  it("should initialize with null active run", () => {
    const { result } = renderHook(() => useAppStore());
    
    expect(result.current.activeRun).toBeNull();
  });

  it("should set active run", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setActiveRun(mockProjectRun);
    });
    
    expect(result.current.activeRun).toEqual(mockProjectRun);
  });

  it("should clear active run", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setActiveRun(mockProjectRun);
    });
    
    act(() => {
      result.current.setActiveRun(null);
    });
    
    expect(result.current.activeRun).toBeNull();
  });

  it("should update active run", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setActiveRun(mockProjectRun);
    });
    
    act(() => {
      result.current.updateActiveRun({
        status: "completed",
        current_step: "completed",
      });
    });
    
    expect(result.current.activeRun).toEqual({
      ...mockProjectRun,
      status: "completed",
      current_step: "completed",
    });
  });

  it("should not update null active run", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.updateActiveRun({ status: "completed" });
    });
    
    expect(result.current.activeRun).toBeNull();
  });
});

describe("useAppStore Live Events", () => {
  beforeEach(() => {
    // Reset store before each test
    const { getState } = useAppStore;
    act(() => {
      getState().clearLiveEvents();
    });
  });

  it("should initialize with empty live events array", () => {
    const { result } = renderHook(() => useAppStore());
    
    expect(result.current.liveEvents).toEqual([]);
  });

  it("should add live event", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.addLiveEvent(mockWsMessage);
    });
    
    expect(result.current.liveEvents).toHaveLength(1);
    expect(result.current.liveEvents[0]).toMatchObject({
      event_type: "agent_start",
      agent_name: "RequirementsAnalyst",
      step: "requirements_analysis",
      message: "Starting requirements analysis",
      data: {},
    });
    expect(result.current.liveEvents[0]).toHaveProperty("id");
    expect(result.current.liveEvents[0]).toHaveProperty("created_at");
  });

  it("should clear live events", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.addLiveEvent(mockWsMessage);
    });
    
    expect(result.current.liveEvents).toHaveLength(1);
    
    act(() => {
      result.current.clearLiveEvents();
    });
    
    expect(result.current.liveEvents).toEqual([]);
  });

  it("should cap live events at 500", () => {
    const { result } = renderHook(() => useAppStore());
    
    // Add 502 events
    act(() => {
      for (let i = 0; i < 502; i++) {
        result.current.addLiveEvent({
          ...mockWsMessage,
          message: `Event ${i}`,
        });
      }
    });
    
    // Should only keep the last 500
    expect(result.current.liveEvents).toHaveLength(500);
    expect(result.current.liveEvents[0].message).toBe("Event 2");
    expect(result.current.liveEvents[499].message).toBe("Event 501");
  });

  it("should add events to the end of array", () => {
    const { result } = renderHook(() => useAppStore());
    
    const firstEvent = { ...mockWsMessage, message: "First event" };
    const secondEvent = { ...mockWsMessage, message: "Second event" };
    
    act(() => {
      result.current.addLiveEvent(firstEvent);
    });
    
    act(() => {
      result.current.addLiveEvent(secondEvent);
    });
    
    expect(result.current.liveEvents).toHaveLength(2);
    expect(result.current.liveEvents[0].message).toBe("First event");
    expect(result.current.liveEvents[1].message).toBe("Second event");
  });
});

describe("useAppStore UI State", () => {
  beforeEach(() => {
    // Reset store before each test
    const { getState } = useAppStore;
    act(() => {
      getState().setSelectedProjectId(null);
      getState().setReviewModalOpen(false);
    });
  });

  it("should initialize with null selected project id", () => {
    const { result } = renderHook(() => useAppStore());
    
    expect(result.current.selectedProjectId).toBeNull();
  });

  it("should set selected project id", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setSelectedProjectId("project-123");
    });
    
    expect(result.current.selectedProjectId).toBe("project-123");
  });

  it("should clear selected project id", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setSelectedProjectId("project-123");
    });
    
    act(() => {
      result.current.setSelectedProjectId(null);
    });
    
    expect(result.current.selectedProjectId).toBeNull();
  });

  it("should initialize with review modal closed", () => {
    const { result } = renderHook(() => useAppStore());
    
    expect(result.current.isReviewModalOpen).toBe(false);
  });

  it("should open review modal", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setReviewModalOpen(true);
    });
    
    expect(result.current.isReviewModalOpen).toBe(true);
  });

  it("should close review modal", () => {
    const { result } = renderHook(() => useAppStore());
    
    act(() => {
      result.current.setReviewModalOpen(true);
    });
    
    act(() => {
      result.current.setReviewModalOpen(false);
    });
    
    expect(result.current.isReviewModalOpen).toBe(false);
  });
});

describe("useAppStore State Isolation", () => {
  it("should maintain separate state between different hook instances", () => {
    const { result: result1 } = renderHook(() => useAppStore());
    const { result: result2 } = renderHook(() => useAppStore());
    
    // Both should have the same initial state
    expect(result1.current.projects).toEqual(result2.current.projects);
    expect(result1.current.selectedProjectId).toBe(result2.current.selectedProjectId);
    
    // Changes in one should reflect in the other (shared state)
    act(() => {
      result1.current.setSelectedProjectId("project-123");
    });
    
    expect(result1.current.selectedProjectId).toBe("project-123");
    expect(result2.current.selectedProjectId).toBe("project-123");
  });
});
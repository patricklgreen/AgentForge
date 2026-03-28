import { create } from "zustand";
import type { Project, ProjectRun, WsMessage, RunEvent } from "../types";

interface AppState {
  // Projects
  projects: Project[];
  setProjects: (projects: Project[]) => void;
  addProject: (project: Project) => void;
  updateProject: (id: string, updates: Partial) => void;

  // Active run
  activeRun: ProjectRun | null;
  setActiveRun: (run: ProjectRun | null) => void;
  updateActiveRun: (updates: Partial) => void;

  // Live events from WebSocket (capped at 500)
  liveEvents: RunEvent[];
  addLiveEvent: (event: WsMessage) => void;
  clearLiveEvents: () => void;

  // UI state
  selectedProjectId: string | null;
  setSelectedProjectId: (id: string | null) => void;

  isReviewModalOpen: boolean;
  setReviewModalOpen: (open: boolean) => void;
}

export const useAppStore = create((set) => ({
  // ── Projects ────────────────────────────────────────────────────────────────
  projects: [],

  setProjects: (projects) => set({ projects }),

  addProject: (project) =>
    set((state) => ({ projects: [project, ...state.projects] })),

  updateProject: (id, updates) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === id ? { ...p, ...updates } : p
      ),
    })),

  // ── Active Run ───────────────────────────────────────────────────────────────
  activeRun: null,

  setActiveRun: (run) => set({ activeRun: run }),

  updateActiveRun: (updates) =>
    set((state) => ({
      activeRun: state.activeRun ? { ...state.activeRun, ...updates } : null,
    })),

  // ── Live Events ──────────────────────────────────────────────────────────────
  liveEvents: [],

  addLiveEvent: (event) =>
    set((state) => ({
      liveEvents: [
        ...state.liveEvents,
        {
          id: crypto.randomUUID(),
          run_id: "",
          event_type: event.type,
          agent_name: event.agent,
          step: event.step,
          message: event.message,
          data: event.data,
          created_at: new Date().toISOString(),
        } satisfies RunEvent,
      ].slice(-500),
    })),

  clearLiveEvents: () => set({ liveEvents: [] }),

  // ── UI State ─────────────────────────────────────────────────────────────────
  selectedProjectId: null,
  setSelectedProjectId: (id) => set({ selectedProjectId: id }),

  isReviewModalOpen: false,
  setReviewModalOpen: (open) => set({ isReviewModalOpen: open }),
}));

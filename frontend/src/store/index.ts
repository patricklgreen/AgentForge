import { create } from "zustand";
import type { Project, ProjectRun, WsMessage, RunEvent } from "../types";
import type { User, LoginRequest, RegisterRequest } from "../api/client";
import { authApi, tokenService } from "../api/client";

interface AppState {
  // Authentication
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<void>;
  refreshUser: () => Promise<void>;
  setUser: (user: User | null) => void;

  // Projects
  projects: Project[];
  setProjects: (projects: Project[]) => void;
  addProject: (project: Project) => void;
  updateProject: (id: string, updates: Partial<Project>) => void;

  // Active run
  activeRun: ProjectRun | null;
  setActiveRun: (run: ProjectRun | null) => void;
  updateActiveRun: (updates: Partial<ProjectRun>) => void;

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

export const useAppStore = create<AppState>((set) => ({
  // ── Authentication ──────────────────────────────────────────────────────────
  user: null,
  isAuthenticated: false,
  isLoading: false,

  login: async (data: LoginRequest) => {
    set({ isLoading: true });
    try {
      const response = await authApi.login(data);
      tokenService.setTokens(response.access_token, response.refresh_token);
      set({ 
        user: response.user, 
        isAuthenticated: true, 
        isLoading: false 
      });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  register: async (data: RegisterRequest) => {
    set({ isLoading: true });
    try {
      await authApi.register(data);
      set({ isLoading: false });
      // Note: User needs to login after registration
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    try {
      await authApi.logout();
    } catch (error) {
      // Continue with logout even if server request fails
      console.warn("Logout request failed:", error);
    } finally {
      tokenService.clearTokens();
      set({ 
        user: null, 
        isAuthenticated: false,
        projects: [], // Clear user data
        activeRun: null,
        liveEvents: [],
        selectedProjectId: null,
      });
    }
  },

  checkAuth: async () => {
    const token = tokenService.getToken();
    if (!token) {
      set({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }

    set({ isLoading: true });
    try {
      const user = await authApi.me();
      set({ 
        user, 
        isAuthenticated: true, 
        isLoading: false 
      });
    } catch (error) {
      // Token is invalid, clear it
      console.error('Auth check failed:', error);
      tokenService.clearTokens();
      set({ 
        user: null, 
        isAuthenticated: false, 
        isLoading: false 
      });
    }
  },

  setUser: (user: User | null) => set({ user, isAuthenticated: !!user }),

  refreshUser: async () => {
    const token = tokenService.getToken();
    if (!token) {
      return;
    }

    try {
      const user = await authApi.me();
      set({ user, isAuthenticated: true });
    } catch (error) {
      // If refresh fails, don't clear auth - user might be temporarily offline
      console.error('Failed to refresh user data:', error);
    }
  },

  // ── Projects ────────────────────────────────────────────────────────────────
  projects: [],

  setProjects: (projects: Project[]) => set({ projects }),

  addProject: (project: Project) =>
    set((state: AppState) => ({ projects: [project, ...state.projects] })),

  updateProject: (id: string, updates: Partial<Project>) =>
    set((state: AppState) => ({
      projects: state.projects.map((p: Project) =>
        p.id === id ? { ...p, ...updates } : p
      ),
    })),

  // ── Active Run ───────────────────────────────────────────────────────────────
  activeRun: null,

  setActiveRun: (run: ProjectRun | null) => set({ activeRun: run }),

  updateActiveRun: (updates: Partial<ProjectRun>) =>
    set((state: AppState) => ({
      activeRun: state.activeRun ? { ...state.activeRun, ...updates } : null,
    })),

  // ── Live Events ──────────────────────────────────────────────────────────────
  liveEvents: [],

  addLiveEvent: (event: WsMessage) =>
    set((state: AppState) => ({
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
  setSelectedProjectId: (id: string | null) => set({ selectedProjectId: id }),

  isReviewModalOpen: false,
  setReviewModalOpen: (open: boolean) => set({ isReviewModalOpen: open }),
}));

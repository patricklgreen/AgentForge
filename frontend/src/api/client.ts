import axios from "axios";
import type {
  Project,
  ProjectCreate,
  ProjectRun,
  HumanFeedback,
  FeedbackResponse,
  CancelResponse,
  Artifact,
  ArtifactContent,
  DownloadUrlResponse,
  RunStateResponse,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const WS_BASE  = import.meta.env.VITE_WS_URL  ?? "ws://localhost:8000";

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

// ─── Token Management ─────────────────────────────────────────────────────────

const TOKEN_KEY = "auth_token";
const REFRESH_TOKEN_KEY = "refresh_token";

export const tokenService = {
  getToken: (): string | null => localStorage.getItem(TOKEN_KEY),
  getRefreshToken: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),
  setTokens: (accessToken: string, refreshToken: string) => {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },
  clearTokens: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

// ─── Request / response interceptors ─────────────────────────────────────────

// Add auth token to all requests
api.interceptors.request.use(
  (config) => {
    const token = tokenService.getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle token refresh and auth errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      const refreshToken = tokenService.getRefreshToken();
      if (refreshToken) {
        try {
          const response = await axios.post(`${API_BASE}/api/v1/auth/refresh`, {
            refresh_token: refreshToken,
          });
          
          const { access_token, refresh_token: newRefreshToken } = response.data;
          tokenService.setTokens(access_token, newRefreshToken);
          
          // Retry the original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed, clear tokens and redirect to login
          tokenService.clearTokens();
          window.location.href = '/login';
          return Promise.reject(refreshError);
        }
      } else {
        // No refresh token, redirect to login
        window.location.href = '/login';
      }
    }
    
    if (error.response) {
      // Attach a human-readable message to the error
      const detail =
        error.response.data?.detail ??
        error.response.data?.message ??
        `HTTP ${error.response.status}`;
      error.message = typeof detail === "string" ? detail : JSON.stringify(detail);
    }
    return Promise.reject(error);
  }
);

// ─── Authentication API ──────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  username: string;
  full_name?: string;
  role: "admin" | "user" | "viewer";
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface RegisterRequest {
  email: string;
  username: string;
  password: string;
  full_name?: string;
}

export const authApi = {
  /** Login with email and password */
  login: (data: LoginRequest): Promise<LoginResponse> =>
    api.post("/auth/login", data).then((r) => r.data),

  /** Register a new user account */
  register: (data: RegisterRequest): Promise<User> =>
    api.post("/auth/register", data).then((r) => r.data),

  /** Get current user profile */
  me: (): Promise<User> =>
    api.get("/auth/me").then((r) => r.data),

  /** Refresh access token */
  refresh: (refreshToken: string): Promise<{ access_token: string; refresh_token: string }> =>
    api.post("/auth/refresh", { refresh_token: refreshToken }).then((r) => r.data),

  /** Logout (invalidate tokens) */
  logout: (): Promise<void> => {
    const refreshToken = tokenService.getRefreshToken();
    if (!refreshToken) {
      // No refresh token to revoke, just clear local tokens
      tokenService.clearTokens();
      return Promise.resolve();
    }
    
    return api.post("/auth/logout", { refresh_token: refreshToken }).then(() => undefined);
  },
};

// ─── Projects API ─────────────────────────────────────────────────────────────

export const projectsApi = {
  /** Create a new project */
  create: (data: ProjectCreate): Promise<Project> =>
    api.post("/projects/", data).then((r) => r.data),

  /** List projects with optional pagination */
  list: (skip = 0, limit = 20): Promise<Project[]> =>
    api.get(`/projects/?skip=${skip}&limit=${limit}`).then((r) => r.data),

  /** Get a project by ID */
  get: (id: string): Promise<Project> =>
    api.get(`/projects/${id}`).then((r) => r.data),

  /** Start a new agent pipeline run for a project */
  startRun: (projectId: string): Promise<ProjectRun> =>
    api.post(`/projects/${projectId}/runs`).then((r) => r.data),

  /** List all runs for a project */
  listRuns: (projectId: string): Promise<ProjectRun[]> =>
    api.get(`/projects/${projectId}/runs`).then((r) => r.data),

  /** Get a specific run with its events */
  getRun: (projectId: string, runId: string): Promise<ProjectRun> =>
    api.get(`/projects/${projectId}/runs/${runId}`).then((r) => r.data),

  /** Submit human review feedback to resume a paused run */
  submitFeedback: (
    projectId: string,
    runId: string,
    feedback: HumanFeedback
  ): Promise<FeedbackResponse> =>
    api
      .post(`/projects/${projectId}/runs/${runId}/feedback`, feedback)
      .then((r) => r.data),

  /** Cancel a run that is paused at a human-review checkpoint */
  cancelRun: (projectId: string, runId: string): Promise<CancelResponse> =>
    api
      .post(`/projects/${projectId}/runs/${runId}/cancel`)
      .then((r) => r.data),

  /** Get the full LangGraph state for a run (includes zip_url) */
  getRunState: (projectId: string, runId: string): Promise<RunStateResponse> =>
    api
      .get(`/projects/${projectId}/runs/${runId}/state`)
      .then((r) => r.data),

  /** Delete a project and all associated data */
  delete: (projectId: string): Promise<void> =>
    api
      .delete(`/projects/${projectId}`)
      .then(() => undefined),

  /** Get cost summary for a specific run */
  getRunCost: (projectId: string, runId: string): Promise<any> =>
    api
      .get(`/projects/${projectId}/runs/${runId}/cost`)
      .then((r) => r.data),

  /** Get cost analytics for a project */
  getCostAnalytics: (projectId: string): Promise<any> =>
    api
      .get(`/projects/${projectId}/cost-analytics`)
      .then((r) => r.data),

  /** Upload visual reference file */
  uploadVisualReference: (file: File, description?: string): Promise<any> => {
    const formData = new FormData();
    formData.append('file', file);
    if (description) {
      formData.append('description', description);
    }
    
    return api
      .post('/projects/visual-reference/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      .then((r) => r.data);
  },
};

// ─── Artifacts API ────────────────────────────────────────────────────────────

export const artifactsApi = {
  /** List all artifacts for a project */
  list: (projectId: string): Promise<Artifact[]> =>
    api.get(`/artifacts/project/${projectId}`).then((r) => r.data),

  /** Get the raw content of an artifact */
  getContent: (artifactId: string): Promise<ArtifactContent> =>
    api.get(`/artifacts/${artifactId}/content`).then((r) => r.data),

  /** Get a pre-signed S3 download URL for an artifact */
  getDownloadUrl: (artifactId: string): Promise<DownloadUrlResponse> =>
    api
      .get(`/artifacts/${artifactId}/download-url`)
      .then((r) => r.data),
};

// ─── Email Verification API ─────────────────────────────────────────

export const emailVerificationApi = {
  /** Send email verification */
  sendVerificationEmail: (email: string): Promise<{success: boolean; message: string}> =>
    api.post("/auth/verify/send", { email }).then((r) => r.data),

  /** Confirm email verification with token */
  confirmEmailVerification: (token: string): Promise<{message: string; is_verified: boolean}> =>
    api.post("/auth/verify/confirm", { token }).then((r) => r.data),

  /** Get current user's verification status */
  getVerificationStatus: (): Promise<{is_verified: boolean; email: string; has_pending_verification: boolean}> =>
    api.get("/auth/verify/status").then((r) => r.data),
};

// ─── WebSocket Client ─────────────────────────────────────────────────────────

type EventHandler = (data: unknown) => void;

export class RunWebSocket {
  private ws: WebSocket | null = null;
  private readonly runId: string;
  private listeners: Map<string, EventHandler[]> = new Map();
  private reconnectAttempts = 0;
  private readonly maxReconnects = 5;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private isManuallyDisconnected = false;

  constructor(runId: string) {
    this.runId = runId;
  }

  connect(): void {
    if (this.isManuallyDisconnected) return;

    // Add authentication token as query parameter for WebSocket
    const token = tokenService.getToken();
    const authParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const url = `${WS_BASE}/ws/${this.runId}${authParam}`;
    
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data as string) as unknown;
        const msg = data as { type?: string };

        // Fire type-specific handlers
        if (msg.type) {
          const handlers = this.listeners.get(msg.type) ?? [];
          handlers.forEach((h: EventHandler) => h(data));
        }

        // Fire wildcard handlers for every message
        const wildcardHandlers = this.listeners.get("*") ?? [];
        wildcardHandlers.forEach((h: EventHandler) => h(data));
      } catch (e) {
        console.error("[RunWebSocket] Failed to parse message:", e);
      }
    };

    this.ws.onclose = () => {
      if (!this.isManuallyDisconnected && this.reconnectAttempts < this.maxReconnects) {
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30_000);
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(() => this.connect(), delay);
      }
    };

    this.ws.onerror = () => {
      console.error("[RunWebSocket] Connection error");
    };
  }

  on(eventType: string, handler: EventHandler): void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType)!.push(handler);
  }

  off(eventType: string, handler: EventHandler): void {
    const handlers = this.listeners.get(eventType) ?? [];
    this.listeners.set(
      eventType,
      handlers.filter((h: EventHandler) => h !== handler)
    );
  }

  disconnect(): void {
    this.isManuallyDisconnected = true;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
    this.listeners.clear();
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

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

// ─── Request / response interceptors ─────────────────────────────────────────

api.interceptors.response.use(
  (response) => response,
  (error) => {
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

// ─── Projects API ─────────────────────────────────────────────────────────────

export const projectsApi = {
  /** Create a new project */
  create: (data: ProjectCreate): Promise =>
    api.post("/projects/", data).then((r) => r.data),

  /** List projects with optional pagination */
  list: (skip = 0, limit = 20): Promise =>
    api.get(`/projects/?skip=${skip}&limit=${limit}`).then((r) => r.data),

  /** Get a project by ID */
  get: (id: string): Promise =>
    api.get(`/projects/${id}`).then((r) => r.data),

  /** Start a new agent pipeline run for a project */
  startRun: (projectId: string): Promise =>
    api.post(`/projects/${projectId}/runs`).then((r) => r.data),

  /** List all runs for a project */
  listRuns: (projectId: string): Promise =>
    api.get(`/projects/${projectId}/runs`).then((r) => r.data),

  /** Get a specific run with its events */
  getRun: (projectId: string, runId: string): Promise =>
    api.get(`/projects/${projectId}/runs/${runId}`).then((r) => r.data),

  /** Submit human review feedback to resume a paused run */
  submitFeedback: (
    projectId: string,
    runId: string,
    feedback: HumanFeedback
  ): Promise =>
    api
      .post(`/projects/${projectId}/runs/${runId}/feedback`, feedback)
      .then((r) => r.data),

  /** Cancel a run that is paused at a human-review checkpoint */
  cancelRun: (projectId: string, runId: string): Promise =>
    api
      .post(`/projects/${projectId}/runs/${runId}/cancel`)
      .then((r) => r.data),

  /** Get the full LangGraph state for a run (includes zip_url) */
  getRunState: (projectId: string, runId: string): Promise =>
    api
      .get(`/projects/${projectId}/runs/${runId}/state`)
      .then((r) => r.data),
};

// ─── Artifacts API ────────────────────────────────────────────────────────────

export const artifactsApi = {
  /** List all artifacts for a project */
  list: (projectId: string): Promise =>
    api.get(`/artifacts/project/${projectId}`).then((r) => r.data),

  /** Get the raw content of an artifact */
  getContent: (artifactId: string): Promise =>
    api.get(`/artifacts/${artifactId}/content`).then((r) => r.data),

  /** Get a pre-signed S3 download URL for an artifact */
  getDownloadUrl: (artifactId: string): Promise =>
    api
      .get(`/artifacts/${artifactId}/download-url`)
      .then((r) => r.data),
};

// ─── WebSocket Client ─────────────────────────────────────────────────────────

type EventHandler = (data: unknown) => void;

export class RunWebSocket {
  private ws: WebSocket | null = null;
  private readonly runId: string;
  private listeners: Map = new Map();
  private reconnectAttempts = 0;
  private readonly maxReconnects = 5;
  private reconnectTimer: ReturnType | null = null;
  private isManuallyDisconnected = false;

  constructor(runId: string) {
    this.runId = runId;
  }

  connect(): void {
    if (this.isManuallyDisconnected) return;

    const url = `${WS_BASE}/ws/${this.runId}`;
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
          handlers.forEach((h) => h(data));
        }

        // Fire wildcard handlers for every message
        const wildcardHandlers = this.listeners.get("*") ?? [];
        wildcardHandlers.forEach((h) => h(data));
      } catch (e) {
        console.error("[RunWebSocket] Failed to parse message:", e);
      }
    };

    this.ws.onclose = (event: CloseEvent) => {
      if (!this.isManuallyDisconnected && this.reconnectAttempts < this.maxReconnects) {
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30_000);
        this.reconnectAttempts++;
        this.reconnectTimer = setTimeout(() => this.connect(), delay);
      }
    };

    this.ws.onerror = (error: Event) => {
      console.error("[RunWebSocket] Error:", error);
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
      handlers.filter((h) => h !== handler)
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

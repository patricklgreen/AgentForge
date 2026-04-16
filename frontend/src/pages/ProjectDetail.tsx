import React, {
  useEffect,
  useRef,
  useState,
  useCallback,
  useMemo,
} from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Play,
  Package,
  Loader2,
  AlertCircle,
  CheckCircle,
  Terminal,
  FileCode,
  RefreshCw,
  ArrowLeft,
  XCircle,
  Clock,
  ExternalLink,
  StopCircle,
  Trash2,
  Download,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { clsx } from "clsx";

import { projectsApi, artifactsApi, RunWebSocket, tokenService } from "../api/client";
import { AgentTimeline } from "../components/AgentTimeline";
import { HumanReviewModal } from "../components/HumanReviewModal";
import { CodeViewer } from "../components/CodeViewer";
import CostAnalytics from "../components/CostAnalytics";
import type {
  WsMessage,
  InterruptPayload,
  HumanFeedback,
  RunEvent,
  ProjectRun,
  CodeFile,
  ProjectStatus,
  RunStatus,
} from "../types";

// ─── Status Configurations ────────────────────────────────────────────────────

const PROJECT_STATUS_CONFIG: Record<
  ProjectStatus,
  { label: string; icon: React.ReactNode; badgeClass: string; textClass: string }
> = {
  pending: {
    label:      "Pending",
    icon:       <Clock className="h-4 w-4" />,
    badgeClass: "bg-gray-800      border-gray-700",
    textClass:  "text-gray-400",
  },
  running: {
    label:      "Building",
    icon:       <Loader2 className="h-4 w-4 animate-spin" />,
    badgeClass: "bg-indigo-900/50 border-indigo-700",
    textClass:  "text-indigo-300",
  },
  waiting_review: {
    label:      "Review Required",
    icon:       <AlertCircle className="h-4 w-4" />,
    badgeClass: "bg-yellow-900/50 border-yellow-700",
    textClass:  "text-yellow-300",
  },
  completed: {
    label:      "Completed",
    icon:       <CheckCircle className="h-4 w-4" />,
    badgeClass: "bg-green-900/50  border-green-700",
    textClass:  "text-green-300",
  },
  failed: {
    label:      "Failed",
    icon:       <XCircle className="h-4 w-4" />,
    badgeClass: "bg-red-900/50    border-red-700",
    textClass:  "text-red-400",
  },
  cancelled: {
    label:      "Cancelled",
    icon:       <XCircle className="h-4 w-4" />,
    badgeClass: "bg-gray-800      border-gray-700",
    textClass:  "text-gray-500",
  },
};

const RUN_STATUS_CONFIG: Record<RunStatus, { label: string; textClass: string }> = {
  pending:        { label: "Pending",         textClass: "text-gray-500"   },
  running:        { label: "Running",         textClass: "text-indigo-400" },
  waiting_review: { label: "Awaiting Review", textClass: "text-yellow-400" },
  completed:      { label: "Completed",       textClass: "text-green-400"  },
  failed:         { label: "Failed",          textClass: "text-red-400"    },
  cancelled:      { label: "Cancelled",       textClass: "text-gray-500"   },
};

// ─── Types ────────────────────────────────────────────────────────────────────

type ActiveTab = "timeline" | "logs" | "code" | "history";

interface LogEntry {
  id:        string;
  timestamp: Date;
  type:      string;
  agent?:    string;
  step?:     string;
  message:   string;
  data?:     Record<string, unknown>;
}

// ─── Token Refresh Hook ────────────────────────────────────────────────────────

/**
 * Hook to automatically refresh JWT tokens during long-running operations.
 * Refreshes token every 25 minutes (before 30-minute expiry) while component is mounted.
 */
const useTokenRefresh = () => {
  const refreshToken = useCallback(async () => {
    try {
      const refreshTokenValue = tokenService.getRefreshToken();
      
      if (!refreshTokenValue) {
        console.log('🔑 No refresh token available - user needs to log in');
        return;
      }

      const response = await fetch('http://localhost:8000/api/v1/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshTokenValue }),
      });

      if (response.ok) {
        const data = await response.json();
        tokenService.setTokens(data.access_token, data.refresh_token);
        console.log('🔄 Token refreshed successfully');
      } else if (response.status === 401) {
        console.warn('🔑 Refresh token expired or invalid - user needs to log in again');
        // Don't clear tokens here - let the user stay on page but they'll need to re-login for API calls
      } else {
        console.warn('🔄 Token refresh failed:', response.status);
      }
    } catch (error) {
      console.error('🔄 Token refresh error:', error);
    }
  }, []);

  useEffect(() => {
    // Only refresh immediately if we have a refresh token
    const refreshTokenValue = tokenService.getRefreshToken();
    
    if (refreshTokenValue) {
      // Don't refresh immediately - wait 23 minutes before first refresh
      // This avoids refreshing right after login when tokens are fresh
      console.log('🔄 Token auto-refresh scheduled for 23 minutes');
      
      // Schedule refresh every 23 minutes (7 minute safety buffer before 30-minute expiry)
      const interval = setInterval(refreshToken, 23 * 60 * 1000);
      
      return () => clearInterval(interval);
    } else {
      console.log('🔑 No refresh token found - skipping auto-refresh');
    }
  }, [refreshToken]);
};

// ─── Component ────────────────────────────────────────────────────────────────

export function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Refs
  const wsRef           = useRef<RunWebSocket | null>(null);
  const logEndRef       = useRef<HTMLDivElement>(null);
  const activeRunIdRef  = useRef<string | null>(null);  // DB UUID of active run
  const activeTabRef    = useRef<ActiveTab>("timeline");

  // State
  const [liveLogEntries,  setLiveLogEntries]  = useState<LogEntry[]>([]);
  const [interruptPayload, setInterruptPayload] = useState<InterruptPayload | null>(null);
  const [lastFeedbackTime, setLastFeedbackTime] = useState<number>(0); // Track when feedback was last submitted
  const [lastFeedbackStep, setLastFeedbackStep] = useState<string | null>(null); // Track which step we last gave feedback for
  const [shownInterruptIds, setShownInterruptIds] = useState<Set<string>>(new Set()); // Track which interrupts we've already shown
  const [activeTab,        setActiveTab]        = useState<ActiveTab>("timeline");
  const [liveCodeFiles,    setLiveCodeFiles]    = useState<CodeFile[]>([]);
  const [isDownloading,    setIsDownloading]    = useState(false);
  const [downloadError,    setDownloadError]    = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Keep ref in sync (used in callbacks to avoid stale closure)
  activeTabRef.current = activeTab;

  // ─── Token Refresh ──────────────────────────────────────────────────────────────
  
  // Automatically refresh tokens during long-running pipelines
  useTokenRefresh();

  // ─── Helper Functions ──────────────────────────────────────────────────────────

  /**
   * Safely show an interrupt payload modal with deduplication.
   * Prevents showing the same interrupt multiple times.
   */
  const showInterruptPayload = useCallback((payload: InterruptPayload, source: string) => {
    try {
      // Create a unique ID for this interrupt based on step and a hash of the payload
      const dataString = JSON.stringify(payload.data || {});
      const payloadHash = dataString.substring(0, 8);
      const interruptId = `${payload.step}-${payloadHash}`;
      
      console.log(`🔔 Attempting to show interrupt from ${source}:`, { 
        step: payload.step, 
        interruptId,
        alreadyShown: shownInterruptIds.has(interruptId),
        currentModal: !!interruptPayload
      });

    // Only show if we haven't shown this exact interrupt before
    if (!shownInterruptIds.has(interruptId)) {
      setInterruptPayload(payload);
      setShownInterruptIds(prev => new Set([...Array.from(prev), interruptId]));
    } else {
      console.log(`🔕 Skipping duplicate interrupt: ${interruptId}`);
    }
  } catch (error) {
    console.error('Error in showInterruptPayload:', error, { payload, source });
    // Fallback: still try to show the modal even if ID generation failed
    setInterruptPayload(payload);
  }
}, [shownInterruptIds, interruptPayload]);

  // ─── Data Fetching ──────────────────────────────────────────────────────────

  const {
    data: project,
    isLoading: projectLoading,
    error: projectError,
  } = useQuery({
    queryKey:        ["project", projectId],
    queryFn:         () => projectsApi.get(projectId!),
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return s === "running" || s === "waiting_review" ? 3000 : 10_000;
    },
    enabled: !!projectId,
  });

  const { data: runs = [], isLoading: runsLoading } = useQuery({
    queryKey:        ["runs", projectId],
    queryFn:         () => projectsApi.listRuns(projectId!),
    refetchInterval: (query) => {
      const latest = query.state.data?.[0];
      // Faster refresh for recently failed runs to get final event data
      const isRecentlyFailed = latest?.status === "failed" && 
        latest?.completed_at && 
        (Date.now() - new Date(latest.completed_at).getTime()) < 60000; // within 1 minute
      
      return latest?.status === "running" || latest?.status === "waiting_review" || isRecentlyFailed
        ? 5000
        : 15_000;
    },
    enabled: !!projectId,
  });

  const latestRun: ProjectRun | undefined = runs[0];

  // ─── Derived State ──────────────────────────────────────────────────────────

  const isRunning   = project?.status === "running";
  const isWaiting   = project?.status === "waiting_review";
  const isCompleted = project?.status === "completed";
  const isFailed    = project?.status === "failed";
  const isCancelled = project?.status === "cancelled";
  const canStart    = project?.status === "pending"
                   || project?.status === "failed"
                   || project?.status === "cancelled";

  // Check if requirements analysis has been completed (any step after requirements_analysis)
  const hasRequirementsCompleted = latestRun && latestRun.current_step && 
    latestRun.current_step !== "requirements_analysis" &&
    latestRun.current_step !== "pending";

  // ─── WebSocket ──────────────────────────────────────────────────────────────

  const addLogEntry = useCallback((msg: WsMessage) => {
    setLiveLogEntries((prev) =>
      [
        ...prev,
        {
          id:        crypto.randomUUID(),
          timestamp: new Date(),
          type:      msg.type,
          agent:     msg.agent,
          step:      msg.step,
          message:   msg.message,
          data:      msg.data,
        },
      ].slice(-500)
    );
  }, []);

  const connectWebSocket = useCallback(
    (threadId: string, runDbId: string) => {
      if (wsRef.current) {
        wsRef.current.disconnect();
        wsRef.current = null;
      }

      activeRunIdRef.current = runDbId;
      const ws = new RunWebSocket(threadId);

      ws.on("*", (rawData: unknown) => {
        const msg = rawData as WsMessage;
        addLogEntry(msg);

        // Auto-scroll log if on logs tab
        if (activeTabRef.current === "logs") {
          setTimeout(
            () => logEndRef.current?.scrollIntoView({ behavior: "smooth" }),
            50
          );
        }

        // Handle interrupt — show review modal
        if (msg.type === "interrupt" && msg.data) {
          showInterruptPayload(msg.data as InterruptPayload, "websocket");
          queryClient.invalidateQueries({ queryKey: ["runs",    projectId] });
          queryClient.invalidateQueries({ queryKey: ["project", projectId] });
        }

        // Handle agent complete events
        if (msg.type === "agent_complete") {
          queryClient.invalidateQueries({ queryKey: ["runs", projectId] });

          // Capture live code files as they arrive
          if (msg.data?.code_files && Array.isArray(msg.data.code_files)) {
            setLiveCodeFiles((prev) => {
              const newFiles = msg.data!.code_files as CodeFile[];
              const existing = new Set(prev.map((f) => f.path));
              return [...prev, ...newFiles.filter((f) => !existing.has(f.path))];
            });
          }
        }

        // Handle terminal events
        if (
          msg.type === "run_complete" ||
          msg.type === "run_cancelled" ||
          msg.type === "error"
        ) {
          queryClient.invalidateQueries({ queryKey: ["project", projectId] });
          queryClient.invalidateQueries({ queryKey: ["runs",    projectId] });
        }
      });

      ws.connect();
      wsRef.current = ws;
    },
    [addLogEntry, projectId, queryClient, showInterruptPayload]
  );

  // Connect when there's an active run
  useEffect(() => {
    if (!latestRun) return;

    const shouldConnect =
      latestRun.status === "running" ||
      latestRun.status === "waiting_review";

    if (shouldConnect && activeRunIdRef.current !== latestRun.id) {
      connectWebSocket(latestRun.thread_id, latestRun.id);

      // Restore interrupt payload from DB on reconnect or show new interrupt
      if (latestRun.status === "waiting_review" && latestRun.interrupt_payload) {
        const newPayload = latestRun.interrupt_payload as InterruptPayload;
        showInterruptPayload(newPayload, "connection");
      }
    }

    return () => {
      wsRef.current?.disconnect();
      wsRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestRun?.id, latestRun?.status, showInterruptPayload]);

  // ─── Fallback: Periodic check for missed review modals ────────────────────
  
  useEffect(() => {
    const checkForPendingReviews = () => {
      const latestRun = runs?.[0];
      const timeSinceLastFeedback = Date.now() - lastFeedbackTime;
      
      if (latestRun?.status === "waiting_review" && latestRun.interrupt_payload) {
        const payload = latestRun.interrupt_payload as InterruptPayload;
        
        // Only show modal if:
        // 1. No current modal AND
        // 2. It's a different step than we just gave feedback for AND
        // 3. At least 3 minutes have passed since last feedback (gives backend plenty of time to process)
        if (!interruptPayload && 
            payload.step !== lastFeedbackStep &&
            timeSinceLastFeedback > 180000) {
          console.log("🔄 Fallback: Auto-showing missed review modal");
          showInterruptPayload(payload, "fallback");
        }
      }
    };

    // Check immediately and then every 10 seconds
    checkForPendingReviews();
    const interval = setInterval(checkForPendingReviews, 10000);

    return () => clearInterval(interval);
  }, [runs, interruptPayload, lastFeedbackTime, lastFeedbackStep, showInterruptPayload]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.disconnect();
    };
  }, []);

  // ─── Mutations ──────────────────────────────────────────────────────────────

  const startRunMutation = useMutation({
    mutationFn: () => projectsApi.startRun(projectId!),
    onSuccess: (run) => {
      setLiveLogEntries([]);
      setLiveCodeFiles([]);
      setInterruptPayload(null);
      setShownInterruptIds(new Set()); // Clear shown interrupts for new run
      setActiveTab("timeline");
      queryClient.invalidateQueries({ queryKey: ["runs",    projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      connectWebSocket(run.thread_id, run.id);
    },
  });

  const feedbackMutation = useMutation({
    mutationFn: (feedback: HumanFeedback) => {
      console.log("🔄 [FEEDBACK_DEBUG] Starting feedback mutation...");
      console.log("🔄 [FEEDBACK_DEBUG] Feedback data:", feedback);
      
      const runId = activeRunIdRef.current ?? latestRun?.id;
      console.log("🔄 [FEEDBACK_DEBUG] Run ID:", runId);
      console.log("🔄 [FEEDBACK_DEBUG] Project ID:", projectId);
      
      if (!runId) throw new Error("No active run ID");
      if (!projectId) throw new Error("No project ID");
      
      console.log("🔄 [FEEDBACK_DEBUG] Making API call to submitFeedback...");
      return projectsApi.submitFeedback(projectId!, runId, feedback);
    },
    onSuccess: (data) => {
      console.log("✅ [FEEDBACK_DEBUG] Feedback successful:", data);
      setInterruptPayload(null);
      setLastFeedbackTime(Date.now()); // Record feedback submission time
      // Record the step we just gave feedback for
      if (interruptPayload?.step) {
        setLastFeedbackStep(interruptPayload.step);
      }
      queryClient.invalidateQueries({ queryKey: ["runs",    projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
    onError: (err) => {
      console.error("❌ [FEEDBACK_DEBUG] Feedback failed:", err);
      console.error("❌ [FEEDBACK_DEBUG] Error details:", {
        message: err?.message,
        response: err?.response?.data,
        status: err?.response?.status,
        stack: err?.stack
      });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => {
      const runId = activeRunIdRef.current ?? latestRun?.id;
      if (!runId) throw new Error("No active run ID");
      return projectsApi.cancelRun(projectId!, runId);
    },
    onSuccess: () => {
      setInterruptPayload(null);
      queryClient.invalidateQueries({ queryKey: ["runs",    projectId] });
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
    onError: (err) => {
      console.error("Cancel failed:", err);
    },
  });

  const deleteProjectMutation = useMutation({
    mutationFn: () => projectsApi.delete(projectId!),
    onSuccess: () => {
      // Navigate back to dashboard after successful deletion
      navigate("/");
    },
    onError: (error) => {
      console.error("Failed to delete project:", error);
      setShowDeleteConfirm(false);
    },
  });

  // ─── Download Requirements ────────────────────────────────────────────────

  const downloadRequirements = async () => {
    if (!projectId) return;
    
    try {
      const data = await projectsApi.getRequirements(projectId);
      
      // Create downloadable file
      const content = JSON.stringify(data.specification, null, 2);
      const blob = new Blob([content], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      
      // Trigger download
      const a = document.createElement("a");
      a.href = url;
      a.download = `${data.project_name}-requirements-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Failed to download requirements:", error);
      // Could add toast notification here
    }
  };

  const downloadRequirementsMutation = useMutation({
    mutationFn: downloadRequirements,
    onError: (error) => {
      console.error("Download requirements failed:", error);
    },
  });

  // ─── Download Handler ────────────────────────────────────────────────────────

  const handleDownload = async () => {
    if (!projectId || !latestRun) return;

    setIsDownloading(true);
    setDownloadError(null);

    try {
      // Strategy 1: zip_url from LangGraph run state
      const stateResponse = await projectsApi.getRunState(projectId, latestRun.id);
      const zipUrl = stateResponse.state?.zip_url as string | undefined;

      if (zipUrl) {
        triggerDownload(zipUrl, `${project?.name ?? "project"}.zip`);
        return;
      }

      // Strategy 2: artifacts table
      const artifacts = await artifactsApi.list(projectId);
      const zipArtifact = artifacts.find(
        (a) =>
          a.artifact_type === "zip" ||
          a.file_path.endsWith(".zip") ||
          a.name.endsWith(".zip")
      );

      if (zipArtifact) {
        const { url } = await artifactsApi.getDownloadUrl(zipArtifact.id);
        triggerDownload(url, `${project?.name ?? "project"}.zip`);
        return;
      }

      setDownloadError(
        "No downloadable archive found. " +
          "The project may not have completed the packaging step."
      );
    } catch (err) {
      console.error("Download failed:", err);
      setDownloadError("Failed to generate download link. Please try again.");
    } finally {
      setIsDownloading(false);
    }
  };

  const triggerDownload = (url: string, filename: string) => {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename.replace(/\s+/g, "-").toLowerCase();
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
  };

  // ─── Computed ────────────────────────────────────────────────────────────────

  const displayCodeFiles = useMemo<CodeFile[]>(() => {
    if (liveCodeFiles.length > 0) return liveCodeFiles;
    if (!latestRun?.events) return [];
    return latestRun.events
      .filter(
        (e: RunEvent) =>
          e.event_type === "agent_complete" &&
          Array.isArray(e.data?.code_files)
      )
      .flatMap((e: RunEvent) => (e.data!.code_files as CodeFile[]) ?? []);
  }, [liveCodeFiles, latestRun?.events]);

  const runStats = useMemo(() => {
    if (!latestRun?.events) return null;
    const events = latestRun.events;
    return {
      agentsCompleted: events.filter((e) => e.event_type === "agent_complete").length,
      totalEvents:     events.length,
      hasErrors:       events.some((e) => e.event_type === "error"),
    };
  }, [latestRun?.events]);

  // Combined log entries: database events + live WebSocket events
  const allLogEntries = useMemo(() => {
    const databaseEntries: LogEntry[] = latestRun?.events?.map(event => ({
      id: event.id,
      timestamp: new Date(event.created_at),
      type: event.event_type,
      agent: event.agent_name,
      step: event.step,
      message: event.message,
      data: event.data,
    })) ?? [];

    // Combine and sort by timestamp, remove duplicates
    const combined = [...databaseEntries, ...liveLogEntries];
    const unique = combined.reduce((acc, entry) => {
      // Avoid duplicates by checking if we already have an entry with same timestamp and message
      const exists = acc.find(e => 
        Math.abs(e.timestamp.getTime() - entry.timestamp.getTime()) < 1000 &&
        e.message === entry.message &&
        e.agent === entry.agent
      );
      if (!exists) {
        acc.push(entry);
      }
      return acc;
    }, [] as LogEntry[]);

    return unique.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
  }, [latestRun?.events, liveLogEntries]);

  // ─── Log Entry Renderer ──────────────────────────────────────────────────────

  const renderLogEntry = (entry: LogEntry) => {
    const colorMap: Record<string, string> = {
      agent_start:    "text-indigo-400",
      agent_complete: "text-green-400",
      interrupt:      "text-yellow-400",
      error:          "text-red-400",
      human_feedback: "text-purple-400",
      run_complete:   "text-green-300",
      run_cancelled:  "text-gray-500",
    };
    const color = colorMap[entry.type] ?? "text-gray-600";
    const label = entry.agent ? `[${entry.agent}]` : `[${entry.type}]`;

    return (
      <div
        key={entry.id}
        className={clsx(
          "flex items-start gap-3 py-0.5 px-2 rounded hover:bg-gray-900/40",
          entry.type === "error" && "bg-red-950/30 border-l-2 border-red-800"
        )}
      >
        <span className="text-gray-700 text-xs font-mono flex-shrink-0 w-20 pt-px">
          {entry.timestamp.toLocaleTimeString("en-US", {
            hour12:  false,
            hour:    "2-digit",
            minute:  "2-digit",
            second:  "2-digit",
          })}
        </span>
        <span className={clsx("text-xs font-mono flex-shrink-0 w-28 pt-px truncate", color)}>
          {label}
        </span>
        <span className="text-gray-300 text-xs font-mono leading-relaxed break-all">
          {entry.message}
          {entry.data?.total_files !== undefined && (
            <span className="text-gray-600 ml-2">
              ({entry.data.total_files as number} files)
            </span>
          )}
          {entry.data?.zip_url && typeof entry.data.zip_url === 'string' ? (
            <a
              href={entry.data.zip_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-2 text-indigo-400 hover:text-indigo-300 inline-flex items-center gap-1"
            >
              <ExternalLink className="h-3 w-3" />
              Download ZIP
            </a>
          ) : null}
        </span>
      </div>
    );
  };

  // ─── Loading / Error ─────────────────────────────────────────────────────────

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-10 w-10 animate-spin text-indigo-400" />
      </div>
    );
  }

  if (projectError || !project) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <div className="bg-red-900/20 border border-red-800 rounded-2xl p-8 text-center max-w-md">
          <XCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
          <h2 className="text-white font-semibold mb-2">Project Not Found</h2>
          <p className="text-red-400 text-sm mb-4">
            {projectError instanceof Error
              ? projectError.message
              : "Unable to load this project."}
          </p>
          <Link
            to="/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-xl text-sm transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const statusCfg = PROJECT_STATUS_CONFIG[project.status];

  // ─── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 px-8 py-5 border-b border-gray-800 bg-gray-950">
        {/* Top row */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-start gap-4 min-w-0">
            <Link
              to="/"
              className="mt-0.5 p-1.5 rounded-lg hover:bg-gray-800 text-gray-600 hover:text-gray-300 transition-colors flex-shrink-0"
              title="Back to dashboard"
            >
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-3 flex-wrap mb-1">
                <h1 className="text-xl font-bold text-white truncate">
                  {project.name}
                </h1>
                <span
                  className={clsx(
                    "inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border",
                    statusCfg.badgeClass,
                    statusCfg.textClass
                  )}
                >
                  {statusCfg.icon}
                  {statusCfg.label}
                </span>
              </div>
              <p className="text-gray-500 text-sm truncate max-w-xl">
                {project.description}
              </p>
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs bg-indigo-900/40 text-indigo-300 border border-indigo-800/50">
                  {project.target_language}
                </span>
                {project.target_framework && (
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs bg-gray-800 text-gray-400 border border-gray-700">
                    {project.target_framework}
                  </span>
                )}
                {latestRun && (
                  <span className="text-xs text-gray-600">
                    Last run{" "}
                    {formatDistanceToNow(new Date(latestRun.created_at), {
                      addSuffix: true,
                    })}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {/* Download ZIP */}
            {isCompleted && (
              <button
                onClick={handleDownload}
                disabled={isDownloading}
                className={clsx(
                  "flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors",
                  isDownloading
                    ? "bg-green-900 text-green-500 cursor-wait"
                    : "bg-green-600 hover:bg-green-500 text-white"
                )}
              >
                {isDownloading ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Preparing...</>
                ) : (
                  <><Package className="h-4 w-4" /> Download ZIP</>
                )}
              </button>
            )}

            {/* Cancel (when waiting for review) */}
            {isWaiting && (
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-400 hover:text-gray-200 rounded-xl text-sm font-medium transition-colors border border-gray-700"
                title="Cancel this build"
              >
                {cancelMutation.isPending ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Cancelling...</>
                ) : (
                  <><StopCircle className="h-4 w-4" /> Cancel Build</>
                )}
              </button>
            )}

            {/* Start / Retry */}
            {canStart && (
              <button
                onClick={() => startRunMutation.mutate()}
                disabled={startRunMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-colors"
              >
                {startRunMutation.isPending ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Starting...</>
                ) : (
                  <><Play className="h-4 w-4" /> {isFailed || isCancelled ? "Retry Build" : "Start Build"}</>
                )}
              </button>
            )}

            {/* Cancel Button */}
            {(isRunning || isWaiting) && (
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-colors"
              >
                {cancelMutation.isPending ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Cancelling...</>
                ) : (
                  <><XCircle className="h-4 w-4" /> Cancel Build</>
                )}
              </button>
            )}

            {/* Re-run when completed */}
            {isCompleted && (
              <button
                onClick={() => startRunMutation.mutate()}
                disabled={startRunMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 text-gray-300 rounded-xl text-sm font-medium transition-colors"
                title="Regenerate the project"
              >
                <RefreshCw className="h-4 w-4" />
                Re-run
              </button>
            )}

            {/* Download Requirements - Available after requirements analysis step */}
            {latestRun && hasRequirementsCompleted && (
              <button
                onClick={() => downloadRequirementsMutation.mutate()}
                disabled={downloadRequirementsMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-colors"
                title="Download requirements specification as JSON"
              >
                {downloadRequirementsMutation.isPending ? (
                  <><Loader2 className="h-4 w-4 animate-spin" /> Downloading...</>
                ) : (
                  <><Download className="h-4 w-4" /> Download Requirements</>
                )}
              </button>
            )}

            {/* Delete Project Button */}
            <button
              onClick={() => setShowDeleteConfirm(true)}
              disabled={deleteProjectMutation.isPending || isRunning}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-sm font-medium transition-colors"
              title={isRunning ? "Cannot delete while build is running" : "Delete this project"}
            >
              <Trash2 className="h-4 w-4" />
              Delete Project
            </button>
          </div>
        </div>

        {/* Error alerts */}
        {downloadError && (
          <div className="mb-3 flex items-start gap-2.5 p-3 bg-red-900/20 border border-red-800 rounded-xl">
            <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-red-400 text-sm flex-1">{downloadError}</p>
            <button
              onClick={() => setDownloadError(null)}
              className="text-red-700 hover:text-red-400 flex-shrink-0"
            >
              <XCircle className="h-4 w-4" />
            </button>
          </div>
        )}

        {startRunMutation.isError && (
          <div className="mb-3 flex items-start gap-2.5 p-3 bg-red-900/20 border border-red-800 rounded-xl">
            <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
            <p className="text-red-400 text-sm">
              Failed to start build.{" "}
              {startRunMutation.error instanceof Error
                ? startRunMutation.error.message
                : "Please try again."}
            </p>
          </div>
        )}

        {cancelMutation.isError && (
          <div className="mb-3 flex items-start gap-2.5 p-3 bg-orange-900/20 border border-orange-800 rounded-xl">
            <AlertCircle className="h-4 w-4 text-orange-400 flex-shrink-0 mt-0.5" />
            <p className="text-orange-400 text-sm">
              Failed to cancel run.{" "}
              {cancelMutation.error instanceof Error
                ? cancelMutation.error.message
                : "Please try again."}
            </p>
          </div>
        )}

        {/* Tab navigation */}
        <nav className="flex gap-1 -mb-px">
          {(
            [
              {
                id:    "timeline" as const,
                label: "Timeline",
                icon:  <RefreshCw className="h-4 w-4" />,
                badge: null,
              },
              {
                id:    "logs" as const,
                label: "Live Logs",
                icon:  <Terminal className="h-4 w-4" />,
                badge: liveLogEntries.length > 0 ? liveLogEntries.length : null,
              },
              {
                id:    "code" as const,
                label: "Generated Code",
                icon:  <FileCode className="h-4 w-4" />,
                badge: displayCodeFiles.length > 0 ? displayCodeFiles.length : null,
              },
              {
                id:    "history" as const,
                label: "Run History",
                icon:  <Clock className="h-4 w-4" />,
                badge: runs.length > 1 ? runs.length : null,
              },
            ] satisfies Array<{
              id: ActiveTab;
              label: string;
              icon: React.ReactNode;
              badge: number | null;
            }>
          ).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                "flex items-center gap-2 px-4 py-2.5 rounded-t-lg text-sm font-medium transition-colors border-b-2",
                activeTab === tab.id
                  ? "bg-gray-900 text-white border-indigo-500"
                  : "bg-transparent text-gray-500 hover:text-gray-300 border-transparent hover:bg-gray-900/40"
              )}
            >
              {tab.icon}
              {tab.label}
              {tab.badge != null && tab.badge > 0 && (
                <span
                  className={clsx(
                    "inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full text-xs font-bold",
                    activeTab === tab.id
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-700 text-gray-400"
                  )}
                >
                  {tab.badge > 999 ? "999+" : tab.badge}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* ── Tab Content ─────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden bg-gray-950">
        {/* TIMELINE */}
        {activeTab === "timeline" && (
          <div className="h-full overflow-y-auto p-8">
            <div className="max-w-2xl">
              {/* Run summary card */}
              {latestRun && (
                <div className="mb-6 bg-gray-900 border border-gray-800 rounded-2xl p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-white">
                      Current Build Status
                    </h3>
                    <span
                      className={clsx(
                        "text-xs font-medium",
                        RUN_STATUS_CONFIG[latestRun.status].textClass
                      )}
                    >
                      {RUN_STATUS_CONFIG[latestRun.status].label}
                    </span>
                  </div>
                  {runStats && (
                    <div className="grid grid-cols-3 gap-3">
                      <div className="text-center bg-gray-800 rounded-xl p-3">
                        <p className="text-2xl font-bold text-indigo-400">
                          {runStats.agentsCompleted}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">Agents Done</p>
                      </div>
                      <div className="text-center bg-gray-800 rounded-xl p-3">
                        <p className="text-2xl font-bold text-gray-300">
                          {displayCodeFiles.length}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">Files</p>
                      </div>
                      <div className="text-center bg-gray-800 rounded-xl p-3">
                        <p
                          className={clsx(
                            "text-2xl font-bold",
                            runStats.hasErrors ? "text-red-400" : "text-green-400"
                          )}
                        >
                          {runStats.hasErrors ? "⚠" : "✓"}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {runStats.hasErrors ? "Errors" : "Clean"}
                        </p>
                      </div>
                    </div>
                  )}
                  {latestRun.error_message && (
                    <div className="mt-3 p-3 bg-red-900/20 border border-red-800/50 rounded-xl">
                      <p className="text-xs text-red-400 font-mono">
                        {latestRun.error_message}
                      </p>
                    </div>
                  )}
                </div>
              )}

              <AgentTimeline
                events={latestRun?.events ?? []}
                currentStep={latestRun?.current_step}
                runStatus={latestRun?.status}
                projectId={projectId}
                runId={latestRun?.id || ''}
              />

              {/* Cost Analytics */}
              <div className="mt-8">
                <CostAnalytics projectId={projectId} />
              </div>

              {!latestRun && !runsLoading && (
                <div className="text-center py-16">
                  <Play className="h-12 w-12 text-gray-800 mx-auto mb-4" />
                  <h3 className="text-gray-500 font-medium mb-2">No builds yet</h3>
                  <p className="text-gray-700 text-sm mb-5">
                    Click Start Build to begin the AI agent pipeline.
                  </p>
                  {canStart && (
                    <button
                      onClick={() => startRunMutation.mutate()}
                      disabled={startRunMutation.isPending}
                      className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-sm transition-colors"
                    >
                      <Play className="h-4 w-4" />
                      Start Build
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* LOGS */}
        {activeTab === "logs" && (
          <div className="h-full flex flex-col">
            <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-600 font-mono">
                  {allLogEntries.length} entries
                </span>
                {(isRunning || isWaiting) && (
                  <span className="flex items-center gap-1.5 text-xs text-indigo-400">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
                    Live
                  </span>
                )}
              </div>
              <button
                onClick={() => setLiveLogEntries([])}
                className="text-xs text-gray-700 hover:text-gray-400 transition-colors"
              >
                Clear Live
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 font-mono text-sm bg-gray-950">
              {allLogEntries.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center">
                  <Terminal className="h-8 w-8 text-gray-800 mb-3" />
                  <p className="text-gray-700 text-sm">
                    {isRunning
                      ? "Connecting to agent stream..."
                      : "No log entries yet. Start a build to see live output."}
                  </p>
                </div>
              ) : (
                <div className="space-y-0">
                  {allLogEntries.map(renderLogEntry)}
                  <div ref={logEndRef} className="h-4" />
                </div>
              )}
            </div>
          </div>
        )}

        {/* CODE */}
        {activeTab === "code" && (
          <div className="h-full flex flex-col">
            {displayCodeFiles.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center p-8">
                <FileCode className="h-12 w-12 text-gray-800 mb-4" />
                <h3 className="text-gray-500 font-medium mb-2">
                  No code generated yet
                </h3>
                <p className="text-gray-700 text-sm max-w-sm">
                  {isRunning
                    ? "Files will appear here as the Code Generator agent creates them."
                    : "Start a build to generate code files."}
                </p>
                {isRunning && (
                  <div className="mt-4 flex items-center gap-2 text-indigo-400 text-sm">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Generating...
                  </div>
                )}
              </div>
            ) : (
              <div className="flex-1 flex flex-col overflow-hidden">
                <div className="flex-shrink-0 flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
                  <span className="text-xs text-gray-600">
                    {displayCodeFiles.length} file
                    {displayCodeFiles.length !== 1 ? "s" : ""} generated
                  </span>
                  {isRunning && (
                    <span className="flex items-center gap-1.5 text-xs text-indigo-400">
                      <Loader2 className="h-3 w-3 animate-spin" />
                      More files incoming...
                    </span>
                  )}
                </div>
                <div className="flex-1 overflow-hidden p-4">
                  <CodeViewer
                    files={displayCodeFiles}
                    height="calc(100vh - 250px)"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* HISTORY */}
        {activeTab === "history" && (
          <div className="h-full overflow-y-auto p-8">
            <div className="max-w-3xl">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-4">
                Run History
              </h3>

              {runsLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
                </div>
              ) : runs.length === 0 ? (
                <p className="text-center text-gray-700 py-12 text-sm">
                  No runs yet.
                </p>
              ) : (
                <div className="space-y-3 mb-8">
                  {runs.map((run, index) => {
                    const statusCfgRun = RUN_STATUS_CONFIG[run.status];
                    return (
                      <div
                        key={run.id}
                        className={clsx(
                          "flex items-center justify-between p-4 rounded-xl border",
                          index === 0
                            ? "bg-gray-800/50 border-gray-700"
                            : "bg-gray-900 border-gray-800"
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className={clsx(
                              "w-2 h-2 rounded-full flex-shrink-0",
                              run.status === "completed"      ? "bg-green-400"               :
                              run.status === "running"        ? "bg-indigo-400 animate-pulse" :
                              run.status === "waiting_review" ? "bg-yellow-400"               :
                              run.status === "failed"         ? "bg-red-400"                  :
                              "bg-gray-600"
                            )}
                          />
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-200">
                                Run #{runs.length - index}
                              </span>
                              {index === 0 && (
                                <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-500">
                                  Latest
                                </span>
                              )}
                              <span className={clsx("text-xs", statusCfgRun.textClass)}>
                                {statusCfgRun.label}
                              </span>
                            </div>
                            <p className="text-xs text-gray-600 mt-0.5 font-mono">
                              {run.thread_id.substring(0, 18)}...
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs text-gray-600">
                          {run.current_step && (
                            <span className="hidden sm:block">
                              {run.current_step.replace(/_/g, " ")}
                            </span>
                          )}
                          <span>
                            {formatDistanceToNow(new Date(run.created_at), {
                              addSuffix: true,
                            })}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Original requirements */}
              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-3">
                  Original Requirements
                </h3>
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <pre className="text-xs text-gray-500 whitespace-pre-wrap font-mono leading-relaxed">
                    {project.requirements}
                  </pre>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Human Review Modal ──────────────────────────────────────────────── */}
      {interruptPayload && (
        <HumanReviewModal
          payload={interruptPayload}
          onSubmit={(feedback: HumanFeedback) =>
            feedbackMutation.mutate(feedback)
          }
          onClose={() => {
            // Always allow manual dismissal of modal
            setInterruptPayload(null);
            setLastFeedbackTime(Date.now());
            // Also record this as handled to prevent immediate re-showing
            if (interruptPayload?.step) {
              setLastFeedbackStep(interruptPayload.step);
            }
          }}
          isLoading={feedbackMutation.isPending}
          projectId={projectId}
          runId={activeRunIdRef.current ?? latestRun?.id}
        />
      )}

      {/* ── Delete Confirmation Modal ──────────────────────────────────────────── */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-white mb-2">
              Delete Project
            </h3>
            <p className="text-gray-400 text-sm mb-4">
              Are you sure you want to permanently delete <span className="text-white font-medium">"{project.name}"</span>?
            </p>
            <p className="text-gray-400 text-sm mb-6">
              This will permanently remove:
            </p>
            <ul className="text-gray-400 text-sm mb-6 space-y-1 ml-4">
              <li>• The project and all its configurations</li>
              <li>• All build runs and their history</li>
              <li>• All generated files and artifacts</li>
              <li>• All associated data and logs</li>
            </ul>
            <p className="text-red-400 text-sm font-medium mb-6">
              This action cannot be undone.
            </p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="flex-1 px-4 py-2 text-gray-400 border border-gray-700 rounded-xl hover:border-gray-600 transition-colors"
                disabled={deleteProjectMutation.isPending}
              >
                Cancel
              </button>
              <button
                onClick={() => deleteProjectMutation.mutate()}
                disabled={deleteProjectMutation.isPending}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-colors"
              >
                {deleteProjectMutation.isPending ? (
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Deleting...
                  </div>
                ) : (
                  "Delete Project"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

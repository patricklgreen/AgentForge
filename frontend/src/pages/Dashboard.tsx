import React from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  PlusCircle,
  Clock,
  CheckCircle,
  Loader2,
  XCircle,
  AlertCircle,
  ChevronRight,
  Bot,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { clsx } from "clsx";
import { projectsApi } from "../api/client";
import { useAppStore } from "../store";
import { VerificationBanner } from "../components/VerificationBanner";
import type { ProjectStatus } from "../types";

// ─── Status Configuration ──────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  ProjectStatus,
  { label: string; icon: React.ReactNode; badgeClass: string; textClass: string }
> = {
  pending: {
    label:      "Pending",
    icon:       <Clock className="h-3.5 w-3.5" />,
    badgeClass: "bg-gray-800     border-gray-700",
    textClass:  "text-gray-400",
  },
  running: {
    label:      "Building",
    icon:       <Loader2 className="h-3.5 w-3.5 animate-spin" />,
    badgeClass: "bg-indigo-900/50  border-indigo-800",
    textClass:  "text-indigo-400",
  },
  waiting_review: {
    label:      "Review Required",
    icon:       <AlertCircle className="h-3.5 w-3.5" />,
    badgeClass: "bg-yellow-900/50  border-yellow-800",
    textClass:  "text-yellow-400",
  },
  completed: {
    label:      "Completed",
    icon:       <CheckCircle className="h-3.5 w-3.5" />,
    badgeClass: "bg-green-900/50   border-green-800",
    textClass:  "text-green-400",
  },
  failed: {
    label:      "Failed",
    icon:       <XCircle className="h-3.5 w-3.5" />,
    badgeClass: "bg-red-900/50     border-red-800",
    textClass:  "text-red-400",
  },
  cancelled: {
    label:      "Cancelled",
    icon:       <XCircle className="h-3.5 w-3.5" />,
    badgeClass: "bg-gray-800       border-gray-700",
    textClass:  "text-gray-500",
  },
};

// ─── Component ────────────────────────────────────────────────────────────────

export function Dashboard() {
  const { user } = useAppStore();
  const {
    data: projects = [],
    isLoading,
    error,
  } = useQuery({
    queryKey:       ["projects"],
    queryFn:        () => projectsApi.list(),
    refetchInterval: 5000,
  });

  const stats = {
    total:     projects.length,
    running:   projects.filter((p) => p.status === "running").length,
    waiting:   projects.filter((p) => p.status === "waiting_review").length,
    completed: projects.filter((p) => p.status === "completed").length,
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-8 max-w-5xl mx-auto">
        {/* Verification Banner */}
        {user && <VerificationBanner user={user} />}
        
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Projects</h1>
            <p className="text-gray-500 mt-1 text-sm">
              AI-generated applications — describe it, we build it
            </p>
          </div>
          <Link
            to="/projects/new"
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium text-sm transition-colors"
          >
            <PlusCircle className="h-4 w-4" />
            New Project
          </Link>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total",           value: stats.total,     color: "text-white"      },
            { label: "Building",        value: stats.running,   color: "text-indigo-400" },
            { label: "Awaiting Review", value: stats.waiting,   color: "text-yellow-400" },
            { label: "Completed",       value: stats.completed, color: "text-green-400"  },
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-gray-900 border border-gray-800 rounded-xl p-4"
            >
              <p className="text-xs text-gray-500 mb-1">{stat.label}</p>
              <p className={clsx("text-3xl font-bold", stat.color)}>
                {stat.value}
              </p>
            </div>
          ))}
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-400" />
          </div>
        ) : error ? (
          <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-center">
            <p className="text-red-400 text-sm font-medium mb-1">
              Failed to load projects
            </p>
            <p className="text-red-600 text-xs">
              Is the AgentForge API running?
            </p>
          </div>
        ) : projects.length === 0 ? (
          <div className="bg-gray-900 border border-dashed border-gray-700 rounded-xl p-16 text-center">
            <Bot className="h-12 w-12 text-gray-700 mx-auto mb-4" />
            <h3 className="text-gray-400 font-medium mb-2">No projects yet</h3>
            <p className="text-gray-600 text-sm mb-5">
              Create your first AI-generated application
            </p>
            <Link
              to="/projects/new"
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm transition-colors"
            >
              <PlusCircle className="h-4 w-4" />
              Create Project
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {projects.map((project) => {
              const statusCfg = STATUS_CONFIG[project.status];
              return (
                <Link
                  key={project.id}
                  to={`/projects/${project.id}`}
                  className="block bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-xl p-5 transition-all group"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1.5 flex-wrap">
                        <h3 className="text-white font-semibold truncate">
                          {project.name}
                        </h3>
                        <span
                          className={clsx(
                            "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border",
                            statusCfg.badgeClass,
                            statusCfg.textClass
                          )}
                        >
                          {statusCfg.icon}
                          {statusCfg.label}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 truncate">
                        {project.description}
                      </p>
                      <div className="flex items-center gap-3 mt-3 flex-wrap">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs bg-indigo-900/40 text-indigo-300 border border-indigo-800/50">
                          {project.target_language}
                        </span>
                        {project.target_framework && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs bg-gray-800 text-gray-400 border border-gray-700">
                            {project.target_framework}
                          </span>
                        )}
                        <span className="text-xs text-gray-600">
                          {formatDistanceToNow(new Date(project.created_at), {
                            addSuffix: true,
                          })}
                        </span>
                      </div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-gray-700 group-hover:text-gray-500 transition-colors flex-shrink-0 mt-1" />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

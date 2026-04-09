import React from "react";
import { clsx } from "clsx";
import {
  CheckCircle,
  Circle,
  Loader2,
  XCircle,
  Clock,
  AlertCircle,
  ShieldCheck,
} from "lucide-react";
import type { RunEvent } from "../types";

// ─── Pipeline Step Definition ────────────────────────────────────────────────

interface PipelineStep {
  id: string;
  label: string;
  agent: string;
  icon?: React.ReactNode;
}

const STEPS: PipelineStep[] = [
  {
    id:    "requirements_analysis",
    label: "Requirements Analysis",
    agent: "RequirementsAnalyst",
  },
  {
    id:    "architecture_design",
    label: "Architecture Design",
    agent: "Architect",
  },
  {
    id:    "code_generation",
    label: "Code Generation",
    agent: "CodeGenerator",
  },
  {
    id:    "validation",
    label: "Code Validation",
    agent: "Validator",
    icon:  <ShieldCheck className="h-4 w-4" />,
  },
  {
    id:    "package_validation",
    label: "Package Validation", 
    agent: "PackageValidator",
    icon:  <AlertCircle className="h-4 w-4" />,
  },
  {
    id:    "test_writing",
    label: "Test Writing",
    agent: "TestWriter",
  },
  {
    id:    "code_review",
    label: "Code Review",
    agent: "CodeReviewer",
  },
  {
    id:    "devops_setup",
    label: "DevOps Setup",
    agent: "DevOps",
  },
  {
    id:    "documentation",
    label: "Documentation",
    agent: "Documentation",
  },
  {
    id:    "packaging",
    label: "Packaging",
    agent: "Packager",
  },
];

// ─── Step Status ─────────────────────────────────────────────────────────────

type StepStatus = "pending" | "running" | "waiting" | "complete" | "error";

function getStepStatus(
  stepId:      string,
  events:      RunEvent[],
  currentStep: string | undefined
): StepStatus {
  const stepEvents = events.filter((e) => e.step === stepId);

  if (stepEvents.some((e) => e.event_type === "error"))            return "error";
  if (stepEvents.some((e) => e.event_type === "agent_complete"))   return "complete";
  if (stepEvents.some((e) => e.event_type === "interrupt"))        return "waiting";
  if (stepEvents.some((e) => e.event_type === "agent_start"))      return "running";
  if (currentStep === stepId)                                       return "running";

  return "pending";
}

function getStepIcon(status: StepStatus): React.ReactNode {
  switch (status) {
    case "complete": return <CheckCircle className="h-5 w-5 text-green-500" />;
    case "running":  return <Loader2    className="h-5 w-5 text-blue-500 animate-spin" />;
    case "error":    return <XCircle    className="h-5 w-5 text-red-500" />;
    case "waiting":  return <Clock      className="h-5 w-5 text-yellow-500" />;
    case "pending":  return <Circle     className="h-5 w-5 text-gray-300" />;
    default:         return <Circle     className="h-5 w-5 text-gray-300" />;
  }
}

// ─── Component ───────────────────────────────────────────────────────────────

interface AgentTimelineProps {
  events:      RunEvent[];
  currentStep: string | undefined;
  runStatus:   string | undefined;
}

export function AgentTimeline({
  events,
  currentStep,
  runStatus,
}: AgentTimelineProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Agent Pipeline
      </h3>

      {STEPS.map((step, index) => {
        const status  = getStepStatus(step.id, events, currentStep);
        const isLast  = index === STEPS.length - 1;
        const isNewStep = step.id === "validation"; // highlight the new step

        return (
          <div key={step.id} className="flex items-start gap-4 relative">
            {/* Connector column */}
            <div className="flex flex-col items-center">
              {/* Status icon */}
              <div className={clsx(
                "flex items-center justify-center rounded-full border-2",
                isNewStep ? "ring-2 ring-blue-200 ring-offset-2" : "",
                status === "complete" ? "border-green-500 bg-green-50" :
                status === "running"  ? "border-blue-500 bg-blue-50" :
                status === "error"    ? "border-red-500 bg-red-50" :
                status === "waiting"  ? "border-yellow-500 bg-yellow-50" :
                                        "border-gray-300 bg-white"
              )}>
                {step.icon || getStepIcon(status)}
              </div>

              {/* Connector line */}
              {!isLast && (
                <div className={clsx(
                  "w-0.5 h-12 mt-2",
                  status === "complete" ? "bg-green-500" : "bg-gray-200"
                )} />
              )}
            </div>

            {/* Content column */}
            <div className="flex-1 min-h-[3rem] pb-6">
              <div className="flex items-center gap-2">
                <h4 className={clsx(
                  "text-sm font-medium",
                  status === "complete" ? "text-green-700" :
                  status === "running"  ? "text-blue-700" :
                  status === "error"    ? "text-red-700" :
                  status === "waiting"  ? "text-yellow-700" :
                                          "text-gray-500"
                )}>
                  {step.label}
                </h4>

                {isNewStep && (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                    New
                  </span>
                )}
              </div>

              <p className="text-xs text-gray-500 mt-1">
                {step.agent}
              </p>

              {/* Awaiting review badge */}
              {status === "waiting" && (
                <div className="mt-2 inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">
                  <AlertCircle className="h-3 w-3" />
                  Awaiting Review
                </div>
              )}

              {/* Error badge */}
              {status === "error" && (
                <div className="mt-2 inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                  <XCircle className="h-3 w-3" />
                  Error
                </div>
              )}
            </div>
          </div>
        );
      })}

      {/* Pipeline complete indicator */}
      {runStatus === "completed" && (
        <div className="mt-4 p-3 rounded-lg bg-green-50 border border-green-200">
          <div className="flex items-center gap-2 text-sm font-medium text-green-700">
            <CheckCircle className="h-4 w-4" />
            Pipeline complete
          </div>
        </div>
      )}
    </div>
  );
}
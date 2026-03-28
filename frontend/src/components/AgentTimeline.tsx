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
    icon:  ,
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
  currentStep: string | undefined,
  runStatus:   string | undefined
): StepStatus {
  const stepEvents = events.filter((e) => e.step === stepId);

  if (stepEvents.some((e) => e.event_type === "error"))            return "error";
  if (stepEvents.some((e) => e.event_type === "agent_complete"))   return "complete";
  if (stepEvents.some((e) => e.event_type === "interrupt"))        return "waiting";
  if (stepEvents.some((e) => e.event_type === "agent_start"))      return "running";
  if (currentStep === stepId)                                       return "running";

  return "pending";
}

// ─── Step Icon ────────────────────────────────────────────────────────────────

function StepIcon({ status }: { status: StepStatus }) {
  const base = "h-6 w-6 flex-shrink-0";
  switch (status) {
    case "complete":
      return ;
    case "running":
      return ;
    case "waiting":
      return ;
    case "error":
      return ;
    default:
      return ;
  }
}

// ─── Component ────────────────────────────────────────────────────────────────

interface AgentTimelineProps {
  events:      RunEvent[];
  currentStep?: string;
  runStatus?:  string;
}

export function AgentTimeline({
  events,
  currentStep,
  runStatus,
}: AgentTimelineProps) {
  return (
    
      
        Agent Pipeline
      

      {STEPS.map((step, index) => {
        const status  = getStepStatus(step.id, events, currentStep, runStatus);
        const isLast  = index === STEPS.length - 1;
        const isNewStep = step.id === "validation"; // highlight the new step

        return (
          
            {/* Connector column */}
            
              
              {!isLast && (
                
              )}
            

            {/* Step info */}
            
              
                
                  {step.label}
                
                {isNewStep && status === "complete" && (
                  
                    
                    auto-fix
                  
                )}
              

              {step.agent}

              {/* Awaiting review badge */}
              {status === "waiting" && (
                
                  
                  Awaiting Review
                
              )}

              {/* Error badge */}
              {status === "error" && (
                
                  
                  Error
                
              )}
            
          
        );
      })}

      {/* Pipeline complete indicator */}
      {runStatus === "completed" && (
        
          
            
            Pipeline complete
          
        
      )}

      {/* Cancelled indicator */}
      {runStatus === "cancelled" && (
        
          
            
            Pipeline cancelled
          
        
      )}
    
  );
}

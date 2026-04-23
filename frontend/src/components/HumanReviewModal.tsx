import React, { useState } from "react";
import {
  X,
  CheckCircle,
  XCircle,
  Edit3,
  AlertTriangle,
  ShieldCheck,
  Wrench,
  Loader2,
  Download,
  Save,
} from "lucide-react";
import { clsx } from "clsx";
import type { InterruptPayload, HumanFeedback } from "../types";
import { CodeViewer } from "./CodeViewer";
import { projectsApi } from "../api/client";

interface HumanReviewModalProps {
  payload:    InterruptPayload;
  onSubmit:   (feedback: HumanFeedback) => void;
  onClose:    () => void;
  isLoading?: boolean;
  projectId?: string;
  runId?:     string;
}

export function HumanReviewModal({
  payload,
  onSubmit,
  onClose,
  isLoading = false,
  projectId,
  runId,
}: HumanReviewModalProps) {
  const [action,   setAction]   = useState<"approve" | "reject" | "modify">("approve");
  const [feedback, setFeedback] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [editedSpec, setEditedSpec] = useState(payload.data?.specification || null);
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = () => {
    console.log("🎯 [MODAL_DEBUG] HandleSubmit called with:", { action, feedback: feedback.trim() || undefined });
    onSubmit({ action, feedback: feedback.trim() || undefined });
  };

  const isFeedbackRequired = action !== "approve";
  const canSubmit = !isLoading && (!isFeedbackRequired || feedback.trim().length > 0);

  // ─── Requirements Edit/Download Handlers ──────────────────────────────────────

  const downloadRequirements = () => {
    const spec = isEditing ? editedSpec : payload.data?.specification;
    if (!spec) return;

    const content = JSON.stringify(spec, null, 2);
    const blob = new Blob([content], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `requirements-specification-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const saveRequirements = async () => {
    if (!projectId || !runId || !editedSpec) return;

    setIsSaving(true);
    try {
      await projectsApi.updateRequirements(projectId, runId, editedSpec);
      // Update the payload data with the edited specification
      payload.data = payload.data || {};
      payload.data.specification = editedSpec;
      setIsEditing(false);
    } catch (error) {
      console.error("Failed to save requirements:", error);
      // TODO: Add toast notification for error
    } finally {
      setIsSaving(false);
    }
  };

  const cancelEdit = () => {
    setEditedSpec(payload.data?.specification || null);
    setIsEditing(false);
  };

  // ─── Content Renderers ────────────────────────────────────────────────────

  const renderSpecification = () => {
    const spec = isEditing ? editedSpec : payload.data?.specification;
    if (!spec) return <EmptyState message="No specification data available." />;

    return (
      <div className="space-y-5">
        {/* Action Bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-blue-400" />
            <span className="text-sm font-semibold text-gray-300">Requirements Specification</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={downloadRequirements}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-gray-300 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
              title="Download as JSON"
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </button>
            {payload.step === "requirements_analysis" && projectId && runId && (
              <>
                {!isEditing ? (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-blue-300 bg-blue-900/20 hover:bg-blue-900/30 rounded-lg transition-colors"
                  >
                    <Edit3 className="h-3.5 w-3.5" />
                    Edit
                  </button>
                ) : (
                  <div className="flex items-center gap-1">
                    <button
                      onClick={saveRequirements}
                      disabled={isSaving}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-green-300 bg-green-900/20 hover:bg-green-900/30 disabled:opacity-50 rounded-lg transition-colors"
                    >
                      {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                      Save
                    </button>
                    <button
                      onClick={cancelEdit}
                      disabled={isSaving}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-gray-300 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded-lg transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {isEditing ? (
          // Edit Mode
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Project Summary</label>
              <textarea
                value={editedSpec?.project_summary || ""}
                onChange={(e) =>
                  setEditedSpec((prev) =>
                    prev ? { ...prev, project_summary: e.target.value } : prev
                  )
                }
                className="w-full h-24 px-3 py-2 text-sm text-gray-300 bg-gray-800 border border-gray-700 rounded-lg focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none"
                placeholder="Enter project summary..."
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Functional Requirements ({editedSpec?.functional_requirements?.length ?? 0})
              </label>
              <div className="bg-gray-800 rounded-lg p-3">
                <textarea
                  value={JSON.stringify(editedSpec?.functional_requirements || [], null, 2)}
                  onChange={(e) => {
                    setEditedSpec((prev) => {
                      if (!prev) return prev;
                      try {
                        const parsed = JSON.parse(e.target.value);
                        return { ...prev, functional_requirements: parsed };
                      } catch {
                        return prev;
                      }
                    });
                  }}
                  className="w-full h-64 px-3 py-2 text-xs text-gray-300 bg-gray-900 border border-gray-700 rounded-lg focus:border-blue-500 focus:ring-1 focus:ring-blue-500 font-mono resize-none"
                  placeholder="Enter functional requirements as JSON array..."
                />
                <p className="text-xs text-gray-500 mt-2">
                  Edit the JSON structure directly. Each requirement should have: id, title, description, priority, acceptance_criteria.
                </p>
              </div>
            </div>
          </div>
        ) : (
          // View Mode
          <div className="space-y-5">
            <Section title="Project Summary">
              <p className="text-sm text-gray-400 leading-relaxed">{spec.project_summary}</p>
            </Section>

            <Section title={`Functional Requirements (${spec.functional_requirements?.length ?? 0})`}>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {spec.functional_requirements?.map((req) => (
                  <div key={req.id} className="bg-gray-800 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span className="text-xs font-mono text-indigo-400">{req.id}</span>
                      <span
                        className={clsx(
                          "text-xs px-1.5 py-0.5 rounded font-medium",
                          req.priority === "must"   && "bg-red-900/50    text-red-300",
                          req.priority === "should" && "bg-yellow-900/50 text-yellow-300",
                          req.priority === "could"  && "bg-gray-700      text-gray-400"
                        )}
                      >
                        {req.priority}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-white">{req.title}</p>
                    <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                      {req.description}
                    </p>
                    {req.acceptance_criteria?.length > 0 && (
                      <ul className="mt-2 space-y-0.5">
                        {req.acceptance_criteria.slice(0, 3).map((c, i) => (
                          <li key={i} className="text-xs text-gray-500 flex items-start gap-1.5">
                            <CheckCircle className="h-3 w-3 text-green-600 flex-shrink-0 mt-0.5" />
                            {c}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Recommended Tech Stack">
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(spec.tech_stack ?? {})
                  .filter(([, v]) => v && typeof v === "string")
                  .map(([key, value]) => (
                    <div key={key} className="bg-gray-800 rounded-lg p-2">
                      <p className="text-xs text-gray-500 capitalize">{key}</p>
                      <p className="text-sm text-gray-200 font-medium truncate">{value}</p>
                    </div>
                  ))}
              </div>
            </Section>
          </div>
        )}
      </div>
    );
  };

  const renderArchitecture = () => {
    const arch = payload.data?.architecture;
    if (!arch) return <EmptyState message="No architecture data available." />;

    return (
      <div className="space-y-5">
        <Section title="Architecture Pattern">
          <p className="text-sm text-gray-300 font-medium">{arch.architecture_pattern}</p>
        </Section>

        <Section title={`Files to Generate (${arch.files_to_generate?.length ?? 0})`}>
          <div className="max-h-60 overflow-y-auto space-y-1 pr-1">
            {arch.files_to_generate?.map((file, idx) => (
              <div key={idx} className="flex items-center gap-2 bg-gray-800 rounded px-3 py-2">
                <span className="text-gray-600 font-mono text-xs w-5 text-right flex-shrink-0">
                  {idx + 1}.
                </span>
                <span className="text-indigo-300 font-mono text-xs truncate flex-1">
                  {file.path}
                </span>
                <span className="text-gray-600 text-xs flex-shrink-0 hidden sm:block">
                  p{file.priority}
                </span>
              </div>
            ))}
          </div>
        </Section>

        {arch.design_decisions?.length > 0 && (
          <Section title="Key Design Decisions">
            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {arch.design_decisions.slice(0, 4).map((d, idx) => (
                <div key={idx} className="bg-gray-800 rounded-lg p-3">
                  <p className="text-sm font-medium text-white">{d.decision}</p>
                  <p className="text-xs text-gray-400 mt-1">{d.rationale}</p>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    );
  };

  const renderCodeReview = () => {
    const review     = payload.data?.review_comments;
    const codeFiles  = payload.data?.code_files ?? [];
    const valSummary = payload.data?.validation_summary;

    return (
      <div className="space-y-5">
        {/* Automated review score */}
        {review && (
          <div className="bg-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <Section title="Automated Review" />
              <div className="flex items-center gap-1">
                <span
                  className={clsx(
                    "text-2xl font-bold",
                    review.overall_score >= 80 ? "text-green-400" :
                    review.overall_score >= 60 ? "text-yellow-400" :
                    "text-red-400"
                  )}
                >
                  {review.overall_score}
                </span>
                <span className="text-gray-500 text-sm">/100</span>
              </div>
            </div>
            <p className="text-sm text-gray-400 leading-relaxed">{review.summary}</p>

            {review.critical_issues?.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold text-red-400 mb-2 flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {review.critical_issues.length} Critical Issue
                  {review.critical_issues.length !== 1 ? "s" : ""}
                </p>
                <div className="space-y-1.5">
                  {review.critical_issues.slice(0, 3).map((issue, idx) => (
                    <div
                      key={idx}
                      className="bg-red-900/20 border border-red-900/40 rounded-lg p-2.5"
                    >
                      <p className="text-xs font-mono text-red-400 mb-1">
                        {issue.file}
                        {issue.line_hint ? ` — ${issue.line_hint}` : ""}
                      </p>
                      <p className="text-xs text-gray-300">{issue.description}</p>
                      {issue.suggestion && (
                        <p className="text-xs text-green-400 mt-1">
                          💡 {issue.suggestion}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Validation summary from ValidationAgent */}
        {valSummary &&
          (valSummary.auto_fixed_count > 0 || valSummary.remaining_count > 0) && (
            <div className="bg-gray-800 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <ShieldCheck className="h-4 w-4 text-blue-400" />
                <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                  Validation Results
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 mb-3">
                <div className="bg-gray-900 rounded-lg p-2 text-center">
                  <p className="text-xl font-bold text-gray-300">
                    {valSummary.total_validated}
                  </p>
                  <p className="text-xs text-gray-600 mt-0.5">Checked</p>
                </div>
                <div className="bg-gray-900 rounded-lg p-2 text-center">
                  <p className="text-xl font-bold text-blue-400">
                    {valSummary.auto_fixed_count}
                  </p>
                  <p className="text-xs text-gray-600 mt-0.5">Auto-Fixed</p>
                </div>
                <div className="bg-gray-900 rounded-lg p-2 text-center">
                  <p
                    className={clsx(
                      "text-xl font-bold",
                      valSummary.remaining_count > 0
                        ? "text-yellow-400"
                        : "text-green-400"
                    )}
                  >
                    {valSummary.remaining_count}
                  </p>
                  <p className="text-xs text-gray-600 mt-0.5">Remaining</p>
                </div>
              </div>

              {valSummary.auto_fixed_files.length > 0 && (
                <div className="mb-3">
                  <p className="text-xs text-blue-400 font-medium mb-1.5 flex items-center gap-1.5">
                    <Wrench className="h-3.5 w-3.5" />
                    Auto-corrected
                  </p>
                  <div className="space-y-1">
                    {valSummary.auto_fixed_files.slice(0, 4).map((path, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-2 text-xs bg-blue-900/20 border border-blue-900/30 rounded px-2.5 py-1.5"
                      >
                        <ShieldCheck className="h-3 w-3 text-blue-400 flex-shrink-0" />
                        <span className="font-mono text-blue-300 truncate">{path}</span>
                      </div>
                    ))}
                    {valSummary.auto_fixed_files.length > 4 && (
                      <p className="text-xs text-gray-600 px-2.5">
                        +{valSummary.auto_fixed_files.length - 4} more
                      </p>
                    )}
                  </div>
                </div>
              )}

              {valSummary.remaining_issues.length > 0 && (
                <div>
                  <p className="text-xs text-yellow-400 font-medium mb-1.5 flex items-center gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5" />
                    Unresolved issues
                  </p>
                  <div className="space-y-1.5">
                    {valSummary.remaining_issues.slice(0, 3).map((issue, idx) => (
                      <div
                        key={idx}
                        className="bg-yellow-900/20 border border-yellow-900/30 rounded-lg p-2"
                      >
                        <p className="text-xs font-mono text-yellow-300">{issue.path}</p>
                        {issue.errors?.slice(0, 2).map((e, ei) => (
                          <p key={ei} className="text-xs text-gray-500 mt-0.5 truncate">
                            {e.output}
                          </p>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

        {/* Package Validation Results */}
        {payload.data?.package_validation && (
          <div className="bg-gray-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle className="h-4 w-4 text-orange-400" />
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                Package Validation
              </span>
              <div className="ml-auto">
                <span
                  className={clsx(
                    "text-xs px-2 py-1 rounded font-medium",
                    payload.data?.package_validation.validation_passed
                      ? "bg-green-900/50 text-green-300"
                      : "bg-red-900/50 text-red-300"
                  )}
                >
                  {payload.data?.package_validation.validation_passed ? "PASSED" : "ISSUES FOUND"}
                </span>
              </div>
            </div>
            
            {payload.data?.package_validation.validation_passed ? (
              <p className="text-sm text-green-400">
                ✅ All packages are current and compatible
              </p>
            ) : (
              <>
                <p className="text-sm text-red-400 mb-3">
                  {payload.data?.package_validation.critical_issues_count} critical issues found that may prevent the project from building or running properly:
                </p>
                
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {payload.data?.package_validation.critical_issues
                    ?.slice(0, 10)
                    .map((issue: string | Record<string, unknown>, idx: number) => (
                    <div
                      key={idx}
                      className="bg-red-900/20 border border-red-900/40 rounded-lg p-2.5"
                    >
                      <p className="text-xs text-red-300 font-mono">
                        Issue {idx + 1}:
                      </p>
                      <p className="text-xs text-gray-300 mt-1">
                        {typeof issue === 'string' ? issue : JSON.stringify(issue)}
                      </p>
                    </div>
                  ))}
                  {(payload.data?.package_validation.critical_issues?.length || 0) > 10 && (
                    <p className="text-xs text-gray-500 px-2.5">
                      +{(payload.data?.package_validation.critical_issues?.length || 0) - 10} more issues...
                    </p>
                  )}
                </div>

                <div className="mt-3 p-3 bg-blue-900/20 border border-blue-900/40 rounded-lg">
                  <p className="text-xs text-blue-300 font-medium mb-1">💡 Fix Recommendations:</p>
                  <p className="text-xs text-gray-400">
                    The validation results contain updated configuration files with current package versions. 
                    Consider applying these fixes before proceeding to ensure your project builds successfully.
                  </p>
                </div>
              </>
            )}
          </div>
        )}

        {/* Generated code files viewer */}
        {codeFiles.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Generated Files ({codeFiles.length})
            </p>
            <CodeViewer files={codeFiles} height="260px" />
          </div>
        )}
      </div>
    );
  };

  const renderFinalReview = () => {
    const data = payload.data || {};
    return (
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3">
          <BigStat label="Source Files"  value={data.code_files_count  ?? 0} color="text-indigo-400" />
          <BigStat label="Test Files"    value={data.test_files_count   ?? 0} color="text-green-400"  />
          <BigStat label="DevOps Files"  value={data.devops_files_count ?? 0} color="text-yellow-400" />
          <BigStat label="Docs"          value={data.doc_files_count    ?? 0} color="text-purple-400" />
        </div>

        {(data.review_score ?? 0) > 0 && (
          <div className="flex items-center gap-4 bg-gray-800 rounded-xl p-4">
            <div className="text-center flex-shrink-0">
              <p
                className={clsx(
                  "text-4xl font-bold",
                  (data.review_score ?? 0) >= 80 ? "text-green-400" :
                  (data.review_score ?? 0) >= 60 ? "text-yellow-400" :
                  "text-red-400"
                )}
              >
                {data.review_score}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">Quality / 100</p>
            </div>
            <div className="min-w-0">
              <p className="text-sm text-gray-300 leading-relaxed">
                {data.summary || "Project is ready for delivery."}
              </p>
              {(data.auto_fixed_count ?? 0) > 0 && (
                <p className="text-xs text-blue-400 mt-1 flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {data.auto_fixed_count} file(s) auto-corrected during validation
                </p>
              )}
            </div>
          </div>
        )}

        {data.all_files && data.all_files.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              All Files ({data.total_files})
            </p>
            <div className="max-h-48 overflow-y-auto space-y-1 pr-1">
              {data.all_files.map((f, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 text-xs bg-gray-800 rounded px-3 py-1.5"
                >
                  <span className="text-indigo-300 font-mono flex-1 truncate">{f.path}</span>
                  <span className="text-gray-600 flex-shrink-0">{f.type}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderContent = () => {
    switch (payload.step) {
      case "requirements_analysis": return renderSpecification();
      case "architecture_design":   return renderArchitecture();
      case "code_review":           return renderCodeReview();
      case "final_review":          return renderFinalReview();
      default:
        return (
          <pre className="text-xs text-gray-400 overflow-auto max-h-96 whitespace-pre-wrap font-mono">
            {JSON.stringify(payload.data || {}, null, 2)}
          </pre>
        );
    }
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="review-modal-title"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-gray-900 border border-gray-700 rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-800 flex-shrink-0">
          <div className="min-w-0 flex-1 pr-4">
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-indigo-900/50 text-indigo-400 border border-indigo-800 font-mono mb-2">
              {payload.step.replace(/_/g, " ")}
            </span>
            <h2 id="review-modal-title" className="text-lg font-semibold text-white">
              {payload.title}
            </h2>
            <p className="text-sm text-gray-400 mt-1 leading-relaxed">
              {payload.description}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors flex-shrink-0"
            aria-label="Close modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {renderContent()}
        </div>

        {/* Action Footer */}
        <div className="p-6 border-t border-gray-800 space-y-4 flex-shrink-0">
          <div className="flex gap-2">
            {(["approve", "modify", "reject"] as const).map((a) => (
              <button
                key={a}
                onClick={() => setAction(a)}
                className={clsx(
                  "flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium border transition-all",
                  action === a
                    ? a === "approve"  ? "bg-green-600  border-green-500  text-white"
                    : a === "reject"   ? "bg-red-600    border-red-500    text-white"
                                       : "bg-yellow-600 border-yellow-500 text-white"
                    : "bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600 hover:text-gray-200"
                )}
              >
                {a === "approve" ? (
                  <><CheckCircle className="h-4 w-4" /> Approve</>
                ) : a === "reject" ? (
                  <><XCircle    className="h-4 w-4" /> Reject</>
                ) : (
                  <><Edit3      className="h-4 w-4" /> Modify</>
                )}
              </button>
            ))}
          </div>

          {isFeedbackRequired && (
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={
                action === "modify"
                  ? "Describe the specific changes you'd like made..."
                  : "Explain why you're rejecting this stage..."
              }
              rows={3}
              className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              autoFocus
            />
          )}

          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={clsx(
              "w-full py-3 rounded-xl font-medium text-sm transition-colors",
              canSubmit
                ? action === "approve"  ? "bg-green-600  hover:bg-green-500  text-white"
                : action === "reject"   ? "bg-red-600    hover:bg-red-500    text-white"
                                        : "bg-yellow-600 hover:bg-yellow-500 text-white"
                : "bg-gray-800 text-gray-600 cursor-not-allowed"
            )}
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Submitting...
              </span>
            ) : action === "approve" ? "Approve & Continue"
              : action === "reject"  ? "Reject & Cancel Build"
              :                        "Submit Changes & Redo Stage"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function Section({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
        {title}
      </h4>
      {children}
    </div>
  );
}

function BigStat({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div className="bg-gray-800 rounded-xl p-3 text-center">
      <p className={clsx("text-3xl font-bold", color)}>{value}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-8 text-gray-600 text-sm">{message}</div>
  );
}

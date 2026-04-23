import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, Wand2, AlertCircle } from "lucide-react";
import { projectsApi } from "../api/client";
import type { ProjectCreate } from "../types/index";
import VisualReferences from "../components/VisualReferences";
import { useToast } from "../components/Toast";

function normalizeProjectCreatePayload(data: ProjectCreate): ProjectCreate {
  const fw = data.target_framework?.trim();
  return {
    ...data,
    target_framework: fw || undefined,
    visual_references:
      data.visual_references && data.visual_references.length > 0
        ? data.visual_references
        : undefined,
  };
}

// ─── Constants ────────────────────────────────────────────────────────────────

const LANGUAGES = [
  "Python",
  "TypeScript",
  "JavaScript",
  "Java",
  "C#",
  "Go",
  "Rust",
  "Ruby",
];

const FRAMEWORKS: Record<string, string[]> = {
  Python:     ["FastAPI", "Django", "Flask", "Starlette"],
  TypeScript: ["NestJS", "Next.js", "Express", "Fastify"],
  JavaScript: ["Express", "Fastify", "Next.js", "Nuxt.js"],
  Java:       ["Spring Boot", "Quarkus", "Micronaut"],
  "C#":       ["ASP.NET Core", "Minimal API"],
  Go:         ["Gin", "Fiber", "Echo", "Chi"],
  Rust:       ["Actix-web", "Axum", "Rocket"],
  Ruby:       ["Rails", "Sinatra"],
};

const EXAMPLE_REQUIREMENTS = `Build a modern task management application with the following features:

**Core Features:**
1. User authentication with JWT (register, login, logout, refresh tokens)
2. Project management (create, read, update, delete projects)
3. Task management within projects (CRUD, status tracking, priority levels)
4. Task assignments to team members
5. Due dates and overdue notifications
6. File attachments on tasks (upload to S3)
7. Activity feed / audit log for all changes
8. Real-time updates via WebSocket

**Technical Requirements:**
- RESTful API with auto-generated OpenAPI documentation
- PostgreSQL database with proper indexing
- Redis caching for frequently accessed data
- Email notifications for assignments and due dates
- Role-based access control (Admin, Manager, Member)
- Rate limiting on all endpoints (100 req/min per user)
- Full-text search on tasks and projects
- Pagination on all list endpoints

**Non-Functional Requirements:**
- API response time p95 < 200ms
- 99.9% uptime SLA
- Horizontal scalability
- 90%+ test coverage
- Docker containerisation with multi-stage builds`;

// ─── Pipeline Steps Info ──────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  "Requirements Analyst analyzes your requirements",
  "You review & approve the specification",
  "Architect designs the system architecture",
  "You review & approve the architecture",
  "Code Generator creates all source files",
  "Validator checks syntax and auto-corrects issues",   // ← validation step
  "Test Writer creates test suite (targeting ≥90% coverage)",
  "Code Reviewer performs automated quality review",
  "You review the code, tests & review findings",
  "DevOps Agent creates Docker, CI/CD & config files",
  "Documentation Agent writes README & API docs",
  "Final review → approve → download complete ZIP",
];

// ─── Component ────────────────────────────────────────────────────────────────

export function NewProject() {
  const navigate     = useNavigate();
  const queryClient  = useQueryClient();
  const { warning: showWarningToast, ToastContainer } = useToast();

  const [form, setForm] = useState<ProjectCreate>({
    name:             "",
    description:      "",
    requirements:     "",
    target_language:  "Python",
    target_framework: "FastAPI",
    visual_references: [],
  });

  const mutation = useMutation({
    mutationFn: async (data: ProjectCreate) => {
      const payload = normalizeProjectCreatePayload(data);
      const project = await projectsApi.create(payload);
      try {
        await projectsApi.startRun(project.id);
        return { project, runStarted: true as const };
      } catch (runErr) {
        const msg =
          runErr instanceof Error ? runErr.message : "Could not start the agent run.";
        return { project, runStarted: false as const, runError: msg };
      }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/projects/${result.project.id}`);
      if (!result.runStarted) {
        showWarningToast(
          "Build did not start automatically",
          result.runError ??
            "Open the project and use “Start run” when the API is ready."
        );
      }
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!requirementsValid || !descriptionValid || !form.name.trim()) return;
    mutation.mutate(form);
  };

  const handleLanguageChange = (language: string) => {
    setForm((prev) => ({
      ...prev,
      target_language:  language,
      target_framework: FRAMEWORKS[language]?.[0] ?? "",
    }));
  };

  const requirementsLength = form.requirements.trim().length;
  const requirementsValid  = requirementsLength >= 50;
  const descriptionLength  = form.description.trim().length;
  const descriptionValid   = descriptionLength >= 20;

  return (
    <div className="h-full overflow-y-auto">
      <ToastContainer />
      <div className="p-8 max-w-3xl mx-auto">
        {/* Header */}
        <div className="flex items-center gap-4 mb-8">
          <Link
            to="/"
            className="p-2 rounded-xl hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">New Project</h1>
            <p className="text-gray-500 text-sm mt-1">
              Describe your application and our AI agents will build it
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Project Name */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Project Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="e.g., Task Management API"
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
            />
          </div>

          {/* Short Description */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Short Description <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              placeholder="One-line description of what you're building"
              className={`w-full bg-gray-900 border rounded-xl px-4 py-2.5 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all ${
                descriptionLength > 0 && !descriptionValid 
                  ? 'border-yellow-600' 
                  : 'border-gray-700'
              }`}
            />
            <div className="flex items-center justify-between mt-1.5">
              <span
                className={`text-xs ${
                  descriptionValid || descriptionLength === 0 
                    ? "text-gray-600" 
                    : "text-yellow-600"
                }`}
              >
                {descriptionLength} / 20 chars minimum
              </span>
              {!descriptionValid && descriptionLength > 0 && (
                <span className="text-xs text-yellow-500 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  Need {20 - descriptionLength} more characters
                </span>
              )}
            </div>
          </div>

          {/* Language & Framework */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Language <span className="text-red-400">*</span>
              </label>
              <select
                value={form.target_language}
                onChange={(e) => handleLanguageChange(e.target.value)}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Framework
              </label>
              <select
                value={form.target_framework ?? ""}
                onChange={(e) =>
                  setForm((p) => ({ ...p, target_framework: e.target.value }))
                }
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
              >
                <option value="">Auto-select best fit</option>
                {(FRAMEWORKS[form.target_language] ?? []).map((fw) => (
                  <option key={fw} value={fw}>
                    {fw}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Requirements */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-300">
                Business Requirements{" "}
                <span className="text-red-400">*</span>
              </label>
              <button
                type="button"
                onClick={() =>
                  setForm((p) => ({ ...p, requirements: EXAMPLE_REQUIREMENTS }))
                }
                className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1.5 transition-colors"
              >
                <Wand2 className="h-3 w-3" />
                Load Example
              </button>
            </div>
            <textarea
              required
              value={form.requirements}
              onChange={(e) =>
                setForm((p) => ({ ...p, requirements: e.target.value }))
              }
              rows={14}
              placeholder={
                "Describe what you need in detail. Include:\n" +
                "• Core features and user stories\n" +
                "• Data models and relationships\n" +
                "• API endpoints needed\n" +
                "• Authentication and authorization rules\n" +
                "• Performance and scalability requirements\n" +
                "• External integrations\n\n" +
                "The more detail you provide, the higher quality the output."
              }
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent resize-none font-mono text-sm leading-relaxed transition-all"
            />
            <div className="flex items-center justify-between mt-1.5">
              <span
                className={`text-xs ${
                  requirementsValid ? "text-gray-600" : "text-yellow-600"
                }`}
              >
                {requirementsLength} / 50 chars minimum
              </span>
              {!requirementsValid && requirementsLength > 0 && (
                <span className="text-xs text-yellow-500 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  Need {50 - requirementsLength} more characters
                </span>
              )}
            </div>
          </div>

          {/* Visual References */}
          <VisualReferences
            references={form.visual_references || []}
            onChange={(references) => setForm(p => ({ ...p, visual_references: references }))}
          />

          {/* Pipeline Info */}
          <div className="bg-indigo-950/40 border border-indigo-900/50 rounded-xl p-5">
            <p className="text-sm font-semibold text-indigo-300 mb-3 flex items-center gap-2">
              🤖 What happens after you submit
            </p>
            <ol className="space-y-1.5">
              {PIPELINE_STEPS.map((step, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="text-xs text-indigo-600 font-mono w-5 flex-shrink-0 text-right mt-0.5">
                    {idx + 1}.
                  </span>
                  <span
                    className={`text-xs leading-relaxed ${
                      step.includes("You review") || step.includes("Final review")
                        ? "text-yellow-400/80 font-medium"
                        : "text-indigo-400/70"
                    }`}
                  >
                    {step}
                  </span>
                </li>
              ))}
            </ol>
          </div>

          {/* Error display */}
          {mutation.isError && (
            <div className="bg-red-900/20 border border-red-800 rounded-xl p-4 flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-400">
                  Could not create project
                </p>
                <p className="text-xs text-red-600 mt-0.5">
                  {mutation.error instanceof Error
                    ? mutation.error.message
                    : "Please try again."}
                </p>
              </div>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={mutation.isPending || !requirementsValid || !descriptionValid || !form.name.trim()}
            className="w-full flex items-center justify-center gap-2 py-3 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-colors text-sm"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Creating Project & Starting Build...
              </>
            ) : (
              <>
                <Wand2 className="h-5 w-5" />
                Create Project & Start Build
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

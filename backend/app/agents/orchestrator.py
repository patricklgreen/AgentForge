import logging
import asyncio
from typing import Any, Optional, Dict
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import interrupt, Command

from app.agents.requirements_analyst import RequirementsAnalystAgent
from app.agents.architect import ArchitectAgent
from app.agents.code_generator import CodeGeneratorAgent
from app.agents.validation_agent import ValidationAgent
from app.agents.test_writer import TestWriterAgent
from app.agents.build_validation_agent import BuildValidationAgent
from app.agents.code_reviewer import CodeReviewerAgent
from app.agents.devops_agent import DevOpsAgent
from app.agents.documentation_agent import DocumentationAgent
from app.agents.package_validation_agent import PackageValidationAgent
from app.services.s3 import s3_service
from app.services.websocket_manager import ws_manager
from app.services.cost_tracker import CostTracker
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─── State ────────────────────────────────────────────────────────────────────

class ProjectState(TypedDict):
    """
    Complete state threaded through every node in the pipeline.

    run_id                    — LangGraph thread_id == ProjectRun.thread_id.
                                Also the WebSocket channel key and PostgreSQL checkpoint key.
                                The DB primary key (ProjectRun.id) lives only in routes.
    validation_results        — Populated by ValidationAgent; one record per source file.
    build_validation_results  — Populated by BuildValidationAgent; build/test/runtime validation.
    quality_violations        — Reserved for optional QualityGateAgent; empty list = OK.
    zip_url                   — 24-hour pre-signed S3 URL written by packaging node;
                                persisted so the frontend can retrieve it at any time
                                via GET /projects/{id}/runs/{id}/state.
    """
    project_id:               str
    run_id:                   str
    requirements:             str
    target_language:          str
    target_framework:         Optional[str]
    visual_references:        Optional[list]
    specification:            Optional[dict]
    architecture:             Optional[dict]
    code_files:               list[dict]
    test_files:               list[dict]
    review_comments:          Optional[dict]
    devops_files:             list[dict]
    documentation:            Optional[dict]
    human_feedback:           list[dict]
    current_step:             str
    error:                    Optional[str]
    validation_results:       list[dict]
    build_validation_results: list[dict]
    quality_violations:       list[str]
    zip_url:                  Optional[str]
    cost_summary:             Optional[dict]


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class AgentOrchestrator:
    """
    Stateful multi-agent workflow built on LangGraph.

    Pipeline
    ────────
    START → analyze_requirements
          → human_review_requirements  (interrupt — approve/modify/reject)
          → design_architecture
          → human_review_architecture  (interrupt — approve/modify/reject)
          → generate_code
          → validate_code              ← catches syntax errors, auto-fixes
          → write_tests
          → build_validate             ← NEW: builds, tests, runtime validation
          → review_code
          → human_review_code          (interrupt — approve/modify/reject)
          → setup_devops
          → write_documentation
          → human_final_review         (interrupt — approve/modify/reject)
          → package_artifacts → END

    approve  → continue to next stage
    modify   → re-run current stage with feedback incorporated
    reject   → handle_rejection → END
    """

    def __init__(self, db_connection_string: str) -> None:
        self.db_connection_string = db_connection_string
        self._graph:       Any = None
        self._checkpointer: AsyncPostgresSaver | None = None
        self._active_tasks: Dict[str, asyncio.Task] = {}  # Track running tasks by thread_id

        self.requirements_agent  = RequirementsAnalystAgent()
        self.architect_agent     = ArchitectAgent()
        self.code_generator      = CodeGeneratorAgent()
        self.validation_agent    = ValidationAgent()
        self.package_validator   = PackageValidationAgent()
        self.test_writer         = TestWriterAgent()
        self.build_validator     = BuildValidationAgent()
        self.code_reviewer       = CodeReviewerAgent()
        self.devops_agent        = DevOpsAgent()
        self.documentation_agent = DocumentationAgent()

    # ─── Initialisation ───────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """
        Set up the PostgreSQL connection string and compile the LangGraph workflow.
        Called once at application startup.
        """
        self.clean_conn = (
            self.db_connection_string
            .replace("postgresql+psycopg://",  "postgresql://")
            .replace("postgresql+asyncpg://",  "postgresql://")
            .replace("postgresql+psycopg2//", "postgresql://")
        )
        
        # Don't create the checkpointer here - create fresh ones per run
        self._checkpointer = None
        
        self._graph = self._build_graph()
        logger.info("AgentOrchestrator initialised")

    def _set_cost_tracker_for_agents(self, cost_tracker: CostTracker) -> None:
        """Set the cost tracker for all agents."""
        agents = [
            self.requirements_agent, self.architect_agent, self.code_generator,
            self.validation_agent, self.package_validator, self.test_writer,
            self.build_validator, self.code_reviewer, self.devops_agent,
            self.documentation_agent
        ]
        for agent in agents:
            agent.set_cost_tracker(cost_tracker)

    # ─── Graph ────────────────────────────────────────────────────────────────

    def _build_graph(self) -> Any:
        wf = StateGraph(ProjectState)

        wf.add_node("analyze_requirements",      self._analyze_requirements_node)
        wf.add_node("human_review_requirements", self._human_review_requirements_node)
        wf.add_node("design_architecture",       self._design_architecture_node)
        wf.add_node("human_review_architecture", self._human_review_architecture_node)
        wf.add_node("generate_code",             self._generate_code_node)
        wf.add_node("validate_code",             self._validate_code_node)
        wf.add_node("validate_packages",         self._validate_packages_node)
        wf.add_node("write_tests",               self._write_tests_node)
        wf.add_node("build_validate",            self._build_validate_node)
        wf.add_node("review_code",               self._review_code_node)
        wf.add_node("human_review_code",         self._human_review_code_node)
        wf.add_node("setup_devops",              self._setup_devops_node)
        wf.add_node("write_documentation",       self._write_documentation_node)
        wf.add_node("human_final_review",        self._human_final_review_node)
        wf.add_node("package_artifacts",         self._package_artifacts_node)
        wf.add_node("handle_rejection",          self._handle_rejection_node)

        wf.add_edge(START, "analyze_requirements")
        wf.add_edge("analyze_requirements", "human_review_requirements")

        wf.add_conditional_edges(
            "human_review_requirements", self._route_after_review,
            {"continue": "design_architecture", "redo": "analyze_requirements", "reject": "handle_rejection"},
        )

        wf.add_edge("design_architecture", "human_review_architecture")

        wf.add_conditional_edges(
            "human_review_architecture", self._route_after_review,
            {"continue": "generate_code", "redo": "design_architecture", "reject": "handle_rejection"},
        )

        wf.add_edge("generate_code", "validate_code")
        wf.add_edge("validate_code", "validate_packages")  
        wf.add_edge("validate_packages", "write_tests")
        wf.add_edge("write_tests",     "build_validate")
        wf.add_edge("build_validate",  "review_code")
        wf.add_edge("review_code",     "human_review_code")

        wf.add_conditional_edges(
            "human_review_code", self._route_after_review,
            {"continue": "setup_devops", "redo": "generate_code", "reject": "handle_rejection"},
        )

        wf.add_edge("setup_devops",        "write_documentation")
        wf.add_edge("write_documentation", "human_final_review")

        wf.add_conditional_edges(
            "human_final_review", self._route_after_review,
            {"continue": "package_artifacts", "redo": "setup_devops", "reject": "handle_rejection"},
        )

        wf.add_edge("package_artifacts", END)
        wf.add_edge("handle_rejection",  END)

        return wf  # Return uncompiled workflow - will compile with fresh checkpointer per run

    @staticmethod
    def _route_after_review(state: ProjectState) -> str:
        feedback = state.get("human_feedback", [])
        if not feedback:
            return "continue"
        action = feedback[-1].get("action", "approve")
        if action == "reject":
            return "reject"
        if action == "modify":
            return "redo"
        return "continue"

    # ─── Agent Nodes ──────────────────────────────────────────────────────────

    async def _analyze_requirements_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "RequirementsAnalyst",
                           "requirements_analysis", "Analyzing business requirements...")
        result = await self.requirements_agent.execute(state)
        fr = len(result.get("specification", {}).get("functional_requirements", []))
        await self._notify(state, "agent_complete", "RequirementsAnalyst",
                           "requirements_analysis",
                           f"Analysis complete — {fr} functional requirements",
                           {"requirements_count": fr})
        return {**result, "current_step": "requirements_analysis"}

    async def _human_review_requirements_node(self, state: ProjectState) -> ProjectState:
        spec = state.get("specification") or {}
        payload = {
            "step":        "requirements_analysis",
            "title":       "Review Requirements Specification",
            "description": (
                f"The analyst identified "
                f"{len(spec.get('functional_requirements', []))} functional requirements. "
                "Approve to proceed, Modify to request changes, or Reject to cancel."
            ),
            "data": {"specification": spec},
        }
        await self._notify(state, "interrupt", "Orchestrator", "requirements_analysis",
                           "Human review required — requirements specification ready", payload)
        human_response = interrupt(payload)
        feedback = {
            "step":          "requirements_analysis",
            "action":        human_response.get("action", "approve"),
            "feedback":      human_response.get("feedback", ""),
            "modifications": human_response.get("modifications", {}),
        }
        logger.info(f"Human review: requirements_analysis → {feedback['action']}")
        return {**state, "human_feedback": [*state.get("human_feedback", []), feedback],
                "current_step": "requirements_analysis"}

    async def _design_architecture_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "Architect",
                           "architecture_design", "Designing system architecture...")
        result       = await self.architect_agent.execute(state)
        files_planned = len(result.get("architecture", {}).get("files_to_generate", []))
        await self._notify(state, "agent_complete", "Architect",
                           "architecture_design",
                           f"Architecture complete — {files_planned} files planned",
                           {"files_to_generate": files_planned})
        return {**result, "current_step": "architecture_design"}

    async def _human_review_architecture_node(self, state: ProjectState) -> ProjectState:
        arch = state.get("architecture") or {}
        payload = {
            "step":        "architecture_design",
            "title":       "Review System Architecture",
            "description": (
                f"The architect designed a {arch.get('architecture_pattern', 'layered')} "
                f"architecture with {len(arch.get('files_to_generate', []))} files. "
                "Approve to begin code generation, Modify to request changes, or Reject."
            ),
            "data": {"architecture": arch, "specification": state.get("specification")},
        }
        await self._notify(state, "interrupt", "Orchestrator", "architecture_design",
                           "Human review required — architecture ready", payload)
        human_response = interrupt(payload)
        feedback = {
            "step":          "architecture_design",
            "action":        human_response.get("action", "approve"),
            "feedback":      human_response.get("feedback", ""),
            "modifications": human_response.get("modifications", {}),
        }
        logger.info(f"Human review: architecture_design → {feedback['action']}")
        return {**state, "human_feedback": [*state.get("human_feedback", []), feedback],
                "current_step": "architecture_design"}

    async def _generate_code_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "CodeGenerator",
                           "code_generation", "Generating source code files...")
        result = await self.code_generator.execute(state)
        fc     = len(result.get("code_files", []))
        await self._notify(state, "agent_complete", "CodeGenerator",
                           "code_generation",
                           f"Code generation complete — {fc} files created",
                           {"files_count": fc, "code_files": result.get("code_files", [])})
        return {**result, "current_step": "code_generation"}

    async def _validate_code_node(self, state: ProjectState) -> ProjectState:
        code_files = state.get("code_files", [])
        await self._notify(state, "agent_start", "Validator",
                           "validation",
                           f"Validating {len(code_files)} generated files...")
        result = await self.validation_agent.execute(state)
        vr     = result.get("validation_results", [])
        fixed  = sum(1 for r in vr if r.get("was_fixed"))
        broken = sum(1 for r in vr if r.get("has_errors") and not r.get("was_fixed"))
        msg    = f"Validation complete — {fixed} auto-fixed"
        if broken:
            msg += f", {broken} still have issues (flagged for review)"
        await self._notify(state, "agent_complete", "Validator", "validation", msg,
                           {"auto_fixed": fixed, "still_erroring": broken})
        return {**result, "current_step": "validation"}

    async def _validate_packages_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "PackageValidator",
                           "package_validation", "Validating packages for current versions and compatibility...")
        result = await self.package_validator.execute(state)
        
        critical_issues = result.get("critical_issues", [])
        validation_passed = result.get("validation_passed", False)
        
        status_msg = "Package validation complete"
        if validation_passed:
            status_msg += " — All packages current and compatible ✅"
        else:
            status_msg += f" — {len(critical_issues)} critical issues found ⚠️"
            
        await self._notify(state, "agent_complete", "PackageValidator", 
                           "package_validation", status_msg,
                           {"critical_issues_count": len(critical_issues), 
                            "validation_passed": validation_passed})
        return {**result, "current_step": "package_validation"}

    async def _write_tests_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "TestWriter",
                           "test_writing", "Writing comprehensive test suite...")
        result = await self.test_writer.execute(state)
        tc     = len(result.get("test_files", []))
        await self._notify(state, "agent_complete", "TestWriter",
                           "test_writing",
                           f"Test suite complete — {tc} files (targeting ≥90% coverage)",
                           {"test_count": tc})
        return {**result, "current_step": "test_writing"}

    async def _build_validate_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "BuildValidator",
                           "build_validation", "Validating project builds and runs successfully...")
        result = await self.build_validator.execute(state)
        
        validation_results = result.get("build_validation_results", [])
        passed_steps = sum(1 for r in validation_results if r.get("status") == "success")
        total_steps = len(validation_results)
        build_passed = result.get("build_validation_passed", False)
        
        status_msg = "Build validation passed" if build_passed else "Build validation failed"
        
        await self._notify(state, "agent_complete", "BuildValidator",
                           "build_validation",
                           f"{status_msg} — {passed_steps}/{total_steps} steps passed",
                           {
                               "validation_results": validation_results,
                               "build_passed": build_passed,
                               "steps_passed": passed_steps,
                               "total_steps": total_steps
                           })
        return {**result, "current_step": "build_validation"}

    async def _review_code_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "CodeReviewer",
                           "code_review", "Running automated code review...")
        result   = await self.code_reviewer.execute(state)
        review   = result.get("review_comments") or {}
        score    = review.get("overall_score", 0)
        critical = len(review.get("critical_issues", []))
        await self._notify(state, "agent_complete", "CodeReviewer",
                           "code_review",
                           f"Review complete — Score: {score}/100 | {critical} critical issues",
                           {"overall_score": score, "critical_count": critical})
        return {**result, "current_step": "code_review"}

    async def _human_review_code_node(self, state: ProjectState) -> ProjectState:
        code_files         = state.get("code_files", [])
        test_files         = state.get("test_files", [])
        review             = state.get("review_comments") or {}
        validation_results = state.get("validation_results", [])
        auto_fixed         = [r["path"] for r in validation_results if r.get("was_fixed")]
        remaining          = [r for r in validation_results
                              if r.get("has_errors") and not r.get("was_fixed")]
        payload = {
            "step":        "code_review",
            "title":       "Review Generated Code & Tests",
            "description": (
                f"Review {len(code_files)} source files and {len(test_files)} test files. "
                f"Quality score: {review.get('overall_score', 0)}/100."
                + (f" {len(auto_fixed)} file(s) auto-corrected by validator." if auto_fixed else "")
                + " Approve to proceed, Modify to regenerate, or Reject."
            ),
            "data": {
                "code_files":        code_files,
                "test_files":        test_files,
                "review_comments":   review,
                "validation_summary": {
                    "auto_fixed_count": len(auto_fixed),
                    "auto_fixed_files": auto_fixed,
                    "remaining_issues": remaining,
                },
            },
        }
        await self._notify(state, "interrupt", "Orchestrator", "code_review",
                           "Human review required — code and tests ready", payload)
        human_response = interrupt(payload)
        feedback = {
            "step":          "code_review",
            "action":        human_response.get("action", "approve"),
            "feedback":      human_response.get("feedback", ""),
            "modifications": human_response.get("modifications", {}),
        }
        logger.info(f"Human review: code_review → {feedback['action']}")
        return {**state, "human_feedback": [*state.get("human_feedback", []), feedback],
                "current_step": "code_review"}

    async def _setup_devops_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "DevOps",
                           "devops_setup", "Creating DevOps configurations...")
        result = await self.devops_agent.execute(state)
        dc     = len(result.get("devops_files", []))
        await self._notify(state, "agent_complete", "DevOps", "devops_setup",
                           f"DevOps setup complete — {dc} files", {"devops_count": dc})
        return {**result, "current_step": "devops_setup"}

    async def _write_documentation_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "Documentation",
                           "documentation", "Generating project documentation...")
        result = await self.documentation_agent.execute(state)
        dc     = len(result.get("documentation", {}).get("files", []))
        await self._notify(state, "agent_complete", "Documentation", "documentation",
                           f"Documentation complete — {dc} documents", {"doc_count": dc})
        return {**result, "current_step": "documentation"}

    async def _human_final_review_node(self, state: ProjectState) -> ProjectState:
        code_files   = state.get("code_files", [])
        test_files   = state.get("test_files", [])
        devops_files = state.get("devops_files", [])
        doc_files    = state.get("documentation", {}).get("files", [])
        all_files    = code_files + test_files + devops_files + doc_files
        review       = state.get("review_comments") or {}
        spec         = state.get("specification") or {}
        vr           = state.get("validation_results", [])
        auto_fixed   = sum(1 for r in vr if r.get("was_fixed"))
        payload = {
            "step":        "final_review",
            "title":       "Final Project Review",
            "description": (
                f"All {len(all_files)} files ready "
                f"({len(code_files)} source, {len(test_files)} tests, "
                f"{len(devops_files)} DevOps, {len(doc_files)} docs"
                + (f"; {auto_fixed} auto-corrected" if auto_fixed else "")
                + "). Approve to package, Modify to regenerate docs/DevOps, or Reject."
            ),
            "data": {
                "total_files":       len(all_files),
                "code_files_count":  len(code_files),
                "test_files_count":  len(test_files),
                "devops_files_count": len(devops_files),
                "doc_files_count":   len(doc_files),
                "summary":           spec.get("project_summary", ""),
                "review_score":      review.get("overall_score", 0),
                "auto_fixed_count":  auto_fixed,
                "all_files": [
                    {"path": f["path"], "type": f.get("type", "source"),
                     "language": f.get("language", "")}
                    for f in all_files
                ],
            },
        }
        await self._notify(state, "interrupt", "Orchestrator", "final_review",
                           "Human review required — final approval", payload)
        human_response = interrupt(payload)
        feedback = {
            "step":          "final_review",
            "action":        human_response.get("action", "approve"),
            "feedback":      human_response.get("feedback", ""),
            "modifications": human_response.get("modifications", {}),
        }
        logger.info(f"Human review: final_review → {feedback['action']}")
        return {**state, "human_feedback": [*state.get("human_feedback", []), feedback],
                "current_step": "final_review"}

    async def _package_artifacts_node(self, state: ProjectState) -> ProjectState:
        await self._notify(state, "agent_start", "Packager",
                           "packaging", "Packaging all artifacts...")
        project_id   = state["project_id"]
        run_id       = state["run_id"]
        code_files   = state.get("code_files", [])
        test_files   = state.get("test_files", [])
        devops_files = state.get("devops_files", [])
        doc_files    = state.get("documentation", {}).get("files", [])
        all_files    = code_files + test_files + devops_files + doc_files
        upload_errors: list[str] = []

        for f in all_files:
            try:
                await s3_service.upload_project_artifact(
                    project_id=project_id, run_id=run_id,
                    file_path=f["path"], content=f["content"],
                )
            except Exception as exc:
                upload_errors.append(f["path"])
                logger.error(f"Upload failed for {f['path']}: {exc}")

        zip_url: Optional[str] = None
        try:
            zip_key = await s3_service.create_project_zip(
                project_id=project_id, run_id=run_id, files=all_files
            )
            zip_url = await s3_service.get_presigned_url(zip_key, expiry=86_400)
        except Exception as exc:
            logger.error(f"ZIP creation failed: {exc}", exc_info=True)

        data = {
            "zip_url":          zip_url,
            "total_files":      len(all_files),
            "code_files_count": len(code_files),
            "test_files_count": len(test_files),
            "upload_errors":    upload_errors,
        }
        await self._notify(state, "agent_complete", "Packager", "packaging",
                           f"Packaging complete — {len(all_files)} files", data)
        await self._notify(state, "run_complete", "Orchestrator", "completed",
                           "Build complete — project ready to download.", data)
        return {**state, "current_step": "completed", "zip_url": zip_url}

    async def _handle_rejection_node(self, state: ProjectState) -> ProjectState:
        rejection = next(
            (fb for fb in reversed(state.get("human_feedback", []))
             if fb.get("action") == "reject"),
            {},
        )
        step   = rejection.get("step", state.get("current_step", "unknown"))
        reason = rejection.get("feedback") or "No reason provided"
        msg    = f"Build cancelled at step '{step}'. Reason: {reason}"
        logger.info(msg)
        await self._notify(state, "run_cancelled", "Orchestrator", step, msg,
                           {"rejected_at_step": step, "reason": reason})
        return {**state, "current_step": "cancelled", "error": msg}

    # ─── Private helpers ──────────────────────────────────────────────────────

    async def _notify(
        self,
        state:      ProjectState,
        event_type: str,
        agent_name: str,
        step:       str,
        message:    str,
        data:       Optional[dict] = None,
    ) -> None:
        try:
            # Send real-time WebSocket notification
            await ws_manager.send_agent_event(
                run_id=state["run_id"],
                event_type=event_type,
                agent_name=agent_name,
                step=step,
                message=message,
                data=data,
            )
            
            # Also create permanent database record for live logs
            from app.database import AsyncSessionLocal
            from app.models.project import RunEvent
            import uuid
            
            async with AsyncSessionLocal() as db:
                # Find the run by thread_id to get the database run_id
                from sqlalchemy import select
                from app.models.project import ProjectRun
                
                stmt = select(ProjectRun).where(ProjectRun.thread_id == state["run_id"])
                result = await db.execute(stmt)
                run = result.scalar_one_or_none()
                
                if run:
                    event = RunEvent(
                        run_id=run.id,
                        event_type=event_type,
                        agent_name=agent_name,
                        step=step,
                        message=message,
                        data=data or {},
                    )
                    db.add(event)
                    
                    # Real-time current_step updates: sync DB with actual workflow progress
                    if event_type == "agent_complete" and step:
                        # Update current_step immediately when agent completes to fix UI sync issues
                        run.current_step = step
                        logger.info(f"📝 Updated current_step to '{step}' after {agent_name} completion")
                    
                    await db.commit()
                    
        except Exception as exc:
            logger.warning(f"Notification failed (non-fatal): {exc}")

    async def _get_run_result(self, config: dict, graph=None) -> dict:
        try:
            graph = graph or self._graph
            s = await graph.aget_state(config)
            if not s:
                return {"status": "completed", "interrupt_payload": None, "current_step": None}
            if s.next:
                payload = None
                for task in (s.tasks or []):
                    its = getattr(task, "interrupts", [])
                    if its:
                        payload = its[0].value
                        break
                # Include current_step even when interrupted
                vals = s.values or {}
                step = vals.get("current_step")
                return {"status": "interrupted", "interrupt_payload": payload, "current_step": step}
            vals  = s.values or {}
            step  = vals.get("current_step")
            error = vals.get("error")
            if step == "cancelled":
                return {"status": "cancelled", "interrupt_payload": None, "current_step": step, "error": error}
            return {"status": "completed", "interrupt_payload": None, "current_step": step}
        except Exception as exc:
            logger.error(f"Failed to inspect run result: {exc}", exc_info=True)
            return {"status": "failed", "interrupt_payload": None, "error": str(exc)}

    # ─── Public API ───────────────────────────────────────────────────────────

    async def start_run(
        self,
        project_id:       str,
        run_id:           str,
        requirements:     str,
        target_language:  str,
        target_framework: Optional[str] = None,
        visual_references: Optional[list] = None,
    ) -> dict:
        """Start a new pipeline run. Returns status dict."""
        if not self._graph:
            await self.initialize()

        # Create a fresh checkpointer for this run to avoid connection issues
        checkpointer_cm = AsyncPostgresSaver.from_conn_string(self.clean_conn)
        checkpointer = await checkpointer_cm.__aenter__()
        
        # Temporarily update the graph with the fresh checkpointer
        graph_with_checkpointer = self._graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": run_id}}
        
        # Initialize cost tracking for this run
        cost_tracker = CostTracker(run_id=run_id)
        self._set_cost_tracker_for_agents(cost_tracker)
        
        initial: ProjectState = {
            "project_id":        project_id,
            "run_id":            run_id,
            "requirements":      requirements,
            "target_language":   target_language,
            "target_framework":  target_framework,
            "visual_references": visual_references or [],
            "specification":     None,
            "architecture":      None,
            "code_files":        [],
            "test_files":        [],
            "review_comments":   None,
            "devops_files":      [],
            "documentation":     None,
            "human_feedback":    [],
            "current_step":      "starting",
            "error":             None,
            "validation_results": [],
            "build_validation_results": [],
            "quality_violations": [],
            "zip_url":           None,
            "cost_summary":      None,
        }
        try:
            # Add timeout to prevent infinite hanging
            import asyncio
            timeout_hours = 2  # Maximum 2 hours for any workflow
            timeout_seconds = timeout_hours * 3600
            
            try:
                async with asyncio.timeout(timeout_seconds):
                    async for event in graph_with_checkpointer.astream(initial, config=config, stream_mode="updates"):
                        logger.debug(f"Node completed: {list(event.keys())}")
                        # Log progress every few nodes to help debug stalls
                        if any(key in ["generate_code", "validate_code", "write_tests", "review_code"] for key in event.keys()):
                            logger.info(f"✅ Major milestone completed: {list(event.keys())}")
            except asyncio.TimeoutError:
                error_msg = f"Workflow timed out after {timeout_hours} hours"
                logger.error(f"Run {run_id} timed out: {error_msg}")
                # Try to get current state for debugging
                try:
                    state = await graph_with_checkpointer.aget_state(config)
                    logger.error(f"Workflow was stuck at step: {state.values.get('current_step', 'unknown')}")
                except Exception as state_error:
                    logger.error(f"Could not retrieve state after timeout: {state_error}")
                raise Exception(error_msg)

            result = await self._get_run_result(config, graph_with_checkpointer)
            
            # Add cost summary to the final result if cost tracker is available
            if cost_tracker:
                cost_summary = cost_tracker.summary()
                logger.info(f"Run {run_id} cost summary: ${cost_summary['total_cost_usd']:.4f}")
                
                # Try to update the state with cost summary
                try:
                    current_state = await graph_with_checkpointer.aget_state(config)
                    if current_state and current_state.values:
                        updated_state = {**current_state.values, "cost_summary": cost_summary}
                        await graph_with_checkpointer.aupdate_state(config, updated_state)
                except Exception as exc:
                    logger.warning(f"Failed to update state with cost summary: {exc}")
                
                # Add cost summary to result
                result["cost_summary"] = cost_summary
            
            return result
        except Exception as exc:
            logger.error(f"Run {run_id} failed: {exc}", exc_info=True)
            raise
        finally:
            # Clean up the checkpointer connection
            try:
                await checkpointer_cm.__aexit__(None, None, None)
            except:
                pass  # Ignore cleanup errors

    async def resume_run(self, run_id: str, human_feedback: dict) -> dict:
        """Resume a paused run after human review. Returns status dict."""
        if not self._graph:
            await self.initialize()
            
        # Create a fresh checkpointer for this run to avoid connection issues
        checkpointer_cm = AsyncPostgresSaver.from_conn_string(self.clean_conn)
        checkpointer = await checkpointer_cm.__aenter__()
        
        # Compile the graph with the fresh checkpointer
        graph_with_checkpointer = self._graph.compile(checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": run_id}}
        
        try:
            # First check if there's actually an active interrupt
            state = await graph_with_checkpointer.aget_state(config)
            logger.info(f"Current state for {run_id}: next={state.next}, tasks={len(state.tasks or [])}")
            
            if not state.next:
                logger.warning(f"No pending state for run {run_id} - returning current state")
                return await self._get_run_result(config, graph_with_checkpointer)
            
            # Check if there are interrupts waiting
            has_interrupts = False
            if state.tasks:
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        has_interrupts = True
                        break
            
            if not has_interrupts:
                logger.warning(f"No interrupts found for run {run_id} - continuing normal execution")
                # Just continue the graph execution without Command
                async for event in graph_with_checkpointer.astream(None, config=config, stream_mode="updates"):
                    logger.debug(f"Continue node: {list(event.keys())}")
                    await self._handle_streaming_event(event, run_id)
            else:
                logger.info(f"Resuming interrupted run {run_id} with feedback: {human_feedback}")
                # Resume with the human feedback
                async for event in graph_with_checkpointer.astream(
                    Command(resume=human_feedback), config=config, stream_mode="updates"
                ):
                    logger.debug(f"Resume node: {list(event.keys())}")
                    await self._handle_streaming_event(event, run_id)
            
            return await self._get_run_result(config, graph_with_checkpointer)
        except Exception as exc:
            logger.error(f"Resume {run_id} failed: {exc}", exc_info=True)
            raise
        finally:
            try:
                await checkpointer_cm.__aexit__(None, None, None)
            except:
                pass  # Ignore cleanup errors

    async def _handle_streaming_event(self, event: dict, run_id: str) -> None:
        """Handle streaming events during resume to create notifications."""
        # Extract the node/agent info from the event
        for node_name, data in event.items():
            if isinstance(data, dict) and "current_step" in data:
                step = data["current_step"]
                # Create notifications based on the step
                if step == "requirements_analysis":
                    await self._notify_from_event("agent_complete", "RequirementsAnalyst", step, 
                                                 "Requirements analysis completed", run_id)
                elif step == "architecture_design":
                    await self._notify_from_event("agent_start", "Architect", step,
                                                 "Starting architecture design", run_id)
                # Add more step notifications as needed
    
    async def _notify_from_event(self, event_type: str, agent_name: str, step: str, message: str, run_id: str) -> None:
        """Create WebSocket notification for streaming events."""
        try:
            # Send real-time WebSocket notification
            await ws_manager.send_agent_event(
                run_id=run_id,
                event_type=event_type,
                agent_name=agent_name,
                step=step,
                message=message,
                data={},
            )
            
            # Also create permanent database record for live logs
            from app.database import AsyncSessionLocal
            from app.models.project import RunEvent
            
            async with AsyncSessionLocal() as db:
                # Find the run by thread_id to get the database run_id
                from sqlalchemy import select
                from app.models.project import ProjectRun
                
                stmt = select(ProjectRun).where(ProjectRun.thread_id == run_id)
                result = await db.execute(stmt)
                run = result.scalar_one_or_none()
                
                if run:
                    event = RunEvent(
                        run_id=run.id,
                        event_type=event_type,
                        agent_name=agent_name,
                        step=step,
                        message=message,
                        data={},
                    )
                    db.add(event)
                    
                    # Real-time current_step updates: sync DB with actual workflow progress  
                    if event_type == "agent_complete" and step:
                        # Update current_step immediately when agent completes to fix UI sync issues
                        run.current_step = step
                        logger.info(f"📝 Updated current_step to '{step}' after {agent_name} completion")
                    
                    await db.commit()
                    
        except Exception as exc:
            logger.warning(f"WebSocket notification failed (non-fatal): {exc}")

    async def get_run_state(self, run_id: str) -> Optional[dict]:
        """Return the full LangGraph state for a run (includes zip_url)."""
        if not self._graph:
            await self.initialize()
        config = {"configurable": {"thread_id": run_id}}
        try:
            s = await self._graph.aget_state(config)
            return dict(s.values) if s and s.values else None
        except Exception as exc:
            logger.error(f"get_run_state failed for {run_id}: {exc}", exc_info=True)
            return None

    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a running or paused run."""
        if not self._graph:
            await self.initialize()
        config = {"configurable": {"thread_id": run_id}}
        
        # First, cancel any active tasks for this run
        if run_id in self._active_tasks:
            task = self._active_tasks[run_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Successfully cancelled active task for run {run_id}")
                except Exception as exc:
                    logger.warning(f"Task cancellation for {run_id} raised: {exc}")
            del self._active_tasks[run_id]
        
        try:
            s = await self._graph.aget_state(config)
        except Exception as exc:
            logger.error(f"Cannot read state for cancel: {exc}")
            return False
        
        if not s:
            logger.warning(f"No state found for run {run_id}")
            return False
            
        # Case 1: Run is paused at human-review interrupt
        if s.next:
            try:
                async for _ in self._graph.astream(
                    Command(resume={"action": "reject", "feedback": "Cancelled by user"}),
                    config=config, stream_mode="updates",
                ):
                    pass
                logger.info(f"Successfully cancelled paused run {run_id}")
                return True
            except Exception as exc:
                logger.error(f"Cancel failed for paused run {run_id}: {exc}", exc_info=True)
                return False
        
        # Case 2: Run is actively running - mark as cancelled in state
        try:
            # Update the state to mark as cancelled
            current_state = s.values or {}
            cancelled_state = {
                **current_state,
                "current_step": "cancelled",
                "error": "Build cancelled by user"
            }
            
            # Update the checkpointer state directly
            await self._graph.aupdate_state(config, cancelled_state)
            logger.info(f"Successfully cancelled active run {run_id}")
            return True
            
        except Exception as exc:
            logger.error(f"Cancel failed for active run {run_id}: {exc}", exc_info=True)
            return False

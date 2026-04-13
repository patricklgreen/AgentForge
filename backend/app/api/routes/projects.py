import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from sqlalchemy.orm import selectinload

from app.database import get_db, AsyncSessionLocal
from app.models.project import Project, ProjectRun, RunEvent, RunStatus, ProjectStatus, Artifact
from app.models.auth import UserRole
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectRunResponse,
    HumanFeedback,
    FeedbackResponse,
    CancelResponse,
    RunStateResponse,
)
from app.agents.orchestrator import AgentOrchestrator
from app.config import get_settings
from app.auth.dependencies import CurrentUser

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/projects", tags=["projects"])

# ─── Shared orchestrator singleton ────────────────────────────────────────────

_orchestrator: Optional[AgentOrchestrator] = None


async def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(
            db_connection_string=settings.database_sync_url
        )
        await _orchestrator.initialize()
    return _orchestrator


# ─── Project CRUD ──────────────────────────────────────────────────────────────

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Create a new project."""
    project = Project(
        user_id=user.id,
        name=data.name,
        description=data.description,
        requirements=data.requirements,
        target_language=data.target_language,
        target_framework=data.target_framework,
        status=ProjectStatus.PENDING,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return project


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    user: CurrentUser,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    """List user's projects, newest first."""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == user.id)
        .order_by(desc(Project.created_at))
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Get a single project by ID."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    return project


# ─── Run Management ────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/runs",
    response_model=ProjectRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_project_run(
    project_id: uuid.UUID,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> ProjectRun:
    """Create and start a new agent pipeline run for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")

    thread_id = str(uuid.uuid4())
    run = ProjectRun(
        project_id=project_id,
        thread_id=thread_id,
        status=RunStatus.RUNNING,
    )
    db.add(run)
    project.status = ProjectStatus.RUNNING

    # Commit BEFORE spawning background task so the task can read committed data
    await db.commit()
    await db.refresh(run, ["events"])  # Load events relationship to prevent MissingGreenlet

    background_tasks.add_task(
        _run_agents,
        orchestrator=orchestrator,
        project_id=project_id,
        run_db_id=run.id,
        thread_id=thread_id,
        requirements=project.requirements,
        target_language=project.target_language,
        target_framework=project.target_framework,
    )
    return run


@router.get("/{project_id}/runs", response_model=list[ProjectRunResponse])
async def list_project_runs(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRun]:
    """List all runs for a project, newest first."""
    # First check if user has access to the project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    result = await db.execute(
        select(ProjectRun)
        .where(ProjectRun.project_id == project_id)
        .options(selectinload(ProjectRun.events))
        .order_by(desc(ProjectRun.created_at))
    )
    return list(result.scalars().all())


@router.get("/{project_id}/runs/{run_id}", response_model=ProjectRunResponse)
async def get_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ProjectRun:
    """Get a specific run with all its events."""
    # First check if user has access to the project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    result = await db.execute(
        select(ProjectRun)
        .where(ProjectRun.id == run_id, ProjectRun.project_id == project_id)
        .options(selectinload(ProjectRun.events))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/{project_id}/runs/{run_id}/state", response_model=RunStateResponse)
async def get_run_state(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> RunStateResponse:
    """
    Return the full LangGraph checkpoint state for a run.

    Includes zip_url, specification, architecture, code_files, etc.
    The frontend calls this to retrieve the download URL after packaging.
    """
    # First check if user has access to the project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    result = await db.execute(
        select(ProjectRun).where(
            ProjectRun.id == run_id,
            ProjectRun.project_id == project_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Try to get ZIP URL from run events data first (more reliable than LangGraph state)
    events_result = await db.execute(
        select(RunEvent).where(
            RunEvent.run_id == run_id,
            RunEvent.data.isnot(None),
            RunEvent.data.op("->>")(text("'zip_url'")).isnot(None)
        ).order_by(RunEvent.created_at.desc()).limit(1)
    )
    latest_zip_event = events_result.scalar_one_or_none()
    
    if latest_zip_event and latest_zip_event.data:
        zip_url = latest_zip_event.data.get("zip_url")
        if zip_url:
            return RunStateResponse(
                state={
                    "zip_url": zip_url,
                    "run_status": run.status,
                    "current_step": run.current_step,
                }
            )

    # Fallback: try to get state from orchestrator (may not work for completed runs)
    try:
        # Use thread_id (LangGraph identifier), NOT the DB UUID
        state = await orchestrator.get_run_state(run.thread_id)
        return RunStateResponse(state=state)
    except Exception as exc:
        logger.warning(f"Could not retrieve LangGraph state for run {run_id}: {exc}")
        # Return basic state info without ZIP URL
        return RunStateResponse(
            state={
                "run_status": run.status,
                "current_step": run.current_step,
                "error": "State retrieval failed - run may be completed"
            }
        )


@router.post("/{project_id}/runs/{run_id}/feedback", response_model=FeedbackResponse)
async def submit_human_feedback(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    feedback: HumanFeedback,
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> FeedbackResponse:
    """
    Submit a human review decision to resume a paused run.

    The run must be in WAITING_REVIEW status.
    Actions: approve | modify | reject
    """
    # First check if user has access to the project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    result = await db.execute(
        select(ProjectRun).where(
            ProjectRun.id == run_id,
            ProjectRun.project_id == project_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.WAITING_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Run is not waiting for review. "
                f"Current status: {run.status}"
            ),
        )

    # Immediately mark as running so subsequent requests don't double-submit
    run.status            = RunStatus.RUNNING
    run.interrupt_payload = None

    # Also update project status to running when resuming
    project = await db.get(Project, project_id)
    if project:
        project.status = ProjectStatus.RUNNING

    event = RunEvent(
        run_id=run_id,
        event_type="human_feedback",
        agent_name="Human",
        step=run.current_step,
        message=f"Human feedback submitted: {feedback.action}",
        data=feedback.model_dump(),
    )
    db.add(event)
    await db.commit()

    background_tasks.add_task(
        _resume_agents,
        orchestrator=orchestrator,
        thread_id=str(run.thread_id),
        feedback=feedback.model_dump(),
        run_db_id=run_id,
        project_id=project_id,
    )
    return FeedbackResponse(status="resumed", action=feedback.action)


@router.post("/{project_id}/runs/{run_id}/cancel", response_model=CancelResponse)
async def cancel_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> CancelResponse:
    """
    Cancel a running or paused run.

    For paused runs (WAITING_REVIEW): Injects a reject action into the LangGraph interrupt.
    For running builds: Stops the execution and marks as cancelled.
    """
    # First check if user has access to the project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    result = await db.execute(
        select(ProjectRun).where(
            ProjectRun.id == run_id,
            ProjectRun.project_id == project_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Allow cancelling RUNNING or WAITING_REVIEW runs
    if run.status not in [RunStatus.RUNNING, RunStatus.WAITING_REVIEW]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only RUNNING or WAITING_REVIEW runs can be cancelled. "
                f"Current status: {run.status}"
            ),
        )

    success = await orchestrator.cancel_run(run.thread_id)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel run — the graph may not be at an interrupt point.",
        )

    run.status = RunStatus.CANCELLED
    project = await db.get(Project, project_id)
    if project:
        project.status = ProjectStatus.CANCELLED
    await db.commit()

    return CancelResponse(status="cancelled", message="Run cancelled successfully")


# ─── Background task helpers ──────────────────────────────────────────────────

def _apply_result_to_run(
    run: ProjectRun,
    project: Optional[Project],
    result: dict,
) -> None:
    """
    Apply the orchestrator result dict to the DB run and project records.

    result shape: {
        "status":            "completed" | "interrupted" | "cancelled" | "failed",
        "current_step":      str | None   (current step identifier)
        "interrupt_payload": dict | None,
        "error":             str | None   (only on failed/cancelled)
    }
    """
    run_status = result.get("status", "completed")
    
    # Always update current_step if present in result
    if "current_step" in result:
        run.current_step = result["current_step"]

    if run_status == "interrupted":
        run.status            = RunStatus.WAITING_REVIEW
        run.interrupt_payload = result.get("interrupt_payload")
        if project:
            project.status = ProjectStatus.WAITING_REVIEW

    elif run_status == "completed":
        run.status       = RunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        if project:
            project.status = ProjectStatus.COMPLETED

    elif run_status == "cancelled":
        run.status        = RunStatus.CANCELLED
        run.error_message = result.get("error", "Cancelled by reviewer")
        if project:
            project.status = ProjectStatus.CANCELLED

    else:  # "failed" or unknown
        run.status        = RunStatus.FAILED
        run.error_message = result.get("error", "Unknown error")
        if project:
            project.status = ProjectStatus.FAILED


async def _run_agents(
    orchestrator:     AgentOrchestrator,
    project_id:       uuid.UUID,
    run_db_id:        uuid.UUID,
    thread_id:        str,
    requirements:     str,
    target_language:  str,
    target_framework: Optional[str],
) -> None:
    """
    Background task: execute the full agent pipeline for a brand-new run.

    Uses a fresh AsyncSession (separate from the request session) for all
    DB writes so there are no cross-task session conflicts.
    """
    logger.info(f"🚀 Starting background task for run {thread_id}")
    
    # Mark run as started
    async with AsyncSessionLocal() as db:
        run = await db.get(ProjectRun, run_db_id)
        if not run:
            logger.error(f"Run {run_db_id} not found at start of background task")
            return
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

    try:
        logger.info(f"🔄 Calling orchestrator.start_run for thread {thread_id}")
        result = await orchestrator.start_run(
            project_id=str(project_id),
            run_id=thread_id,
            requirements=requirements,
            target_language=target_language,
            target_framework=target_framework,
        )
        logger.info(f"✅ Orchestrator.start_run completed for thread {thread_id}")

        async with AsyncSessionLocal() as db:
            run     = await db.get(ProjectRun, run_db_id)
            project = await db.get(Project, project_id)
            if run:
                _apply_result_to_run(run, project, result)
                await db.commit()

    except Exception as exc:
        logger.error(
            f"Agent run {thread_id} failed with unhandled exception: {exc}",
            exc_info=True,
        )
        async with AsyncSessionLocal() as db:
            run     = await db.get(ProjectRun, run_db_id)
            project = await db.get(Project, project_id)
            if run:
                run.status        = RunStatus.FAILED
                run.error_message = str(exc)[:2000]
            if project:
                project.status = ProjectStatus.FAILED
            await db.commit()


async def _resume_agents(
    orchestrator: AgentOrchestrator,
    thread_id:    str,
    feedback:     dict,
    run_db_id:    uuid.UUID,
    project_id:   uuid.UUID,
) -> None:
    """
    Background task: resume a paused run after human feedback is submitted.
    """
    logger.info(f"🔄 Starting resume_agents background task for thread {thread_id}")
    try:
        logger.info(f"🔄 Calling orchestrator.resume_run for thread {thread_id}")
        # Add timeout to prevent hanging indefinitely
        result = await asyncio.wait_for(
            orchestrator.resume_run(
                run_id=thread_id,
                human_feedback=feedback,
            ),
            timeout=3600.0  # 1 hour timeout with Haiku (much faster than Opus)
        )
        logger.info(f"✅ Orchestrator.resume_run completed for thread {thread_id}")

        async with AsyncSessionLocal() as db:
            run     = await db.get(ProjectRun, run_db_id)
            project = await db.get(Project, project_id)
            if run:
                logger.info(f"📝 Applying result to run {run_db_id}: status={result.get('status')}")
                _apply_result_to_run(run, project, result)
                await db.commit()
                logger.info(f"✅ Applied result to run {run_db_id} successfully")

    except asyncio.TimeoutError:
        logger.error(f"❌ Resume of run {thread_id} timed out after 1 hour")
        async with AsyncSessionLocal() as db:
            run     = await db.get(ProjectRun, run_db_id)
            project = await db.get(Project, project_id)
            if run:
                run.status        = RunStatus.FAILED
                run.error_message = "Resume operation timed out after 1 hour"
            if project:
                project.status = ProjectStatus.FAILED
            await db.commit()
            logger.error(f"❌ Marked run {run_db_id} as failed due to timeout (1 hour)")

    except Exception as exc:
        logger.error(
            f"Resume of run {thread_id} failed with exception: {exc}",
            exc_info=True,
        )
        async with AsyncSessionLocal() as db:
            run     = await db.get(ProjectRun, run_db_id)
            project = await db.get(Project, project_id)
            if run:
                run.status        = RunStatus.FAILED
                run.error_message = str(exc)[:2000]
            if project:
                project.status = ProjectStatus.FAILED
            await db.commit()
            logger.error(f"❌ Marked run {run_db_id} as failed due to resume error")


@router.get("/{project_id}/runs/{run_id}/cost")
async def get_run_cost_summary(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get cost summary for a specific run."""
    # Verify project access
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get the run and its state
    run_query = select(ProjectRun).where(ProjectRun.id == run_id, ProjectRun.project_id == project_id)
    result = await db.execute(run_query)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Try to get cost summary from orchestrator state if available
    try:
        # Get the run result which includes cost summary
        orchestrator = get_orchestrator()
        config = {"configurable": {"thread_id": run.thread_id}}
        run_result = await orchestrator._get_run_result(config)
        
        if run_result.get("cost_summary"):
            return run_result["cost_summary"]
    except Exception as exc:
        logger.warning(f"Failed to get cost summary from orchestrator: {exc}")

    # Return empty cost summary if not available
    return {
        "run_id": str(run_id),
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "call_count": 0,
        "calls_by_agent": {},
        "cost_by_agent": {},
        "note": "Cost tracking not available for this run"
    }


@router.get("/{project_id}/cost-analytics")
async def get_project_cost_analytics(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get cost analytics for all runs in a project."""
    # Verify project access
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get all runs for the project
    runs_query = (
        select(ProjectRun)
        .where(ProjectRun.project_id == project_id)
        .order_by(ProjectRun.created_at.desc())
        .limit(50)  # Limit to recent runs
    )
    result = await db.execute(runs_query)
    runs = result.scalars().all()

    # Aggregate cost data across runs
    total_cost = 0.0
    total_tokens = 0
    run_costs = []
    agent_costs = {}

    orchestrator = get_orchestrator()
    
    for run in runs:
        try:
            config = {"configurable": {"thread_id": run.thread_id}}
            run_result = await orchestrator._get_run_result(config)
            cost_summary = run_result.get("cost_summary")
            
            if cost_summary:
                run_cost = cost_summary.get("total_cost_usd", 0.0)
                run_tokens = cost_summary.get("total_tokens", 0)
                
                total_cost += run_cost
                total_tokens += run_tokens
                
                run_costs.append({
                    "run_id": str(run.id),
                    "created_at": run.created_at.isoformat(),
                    "status": run.status.value,
                    "cost_usd": run_cost,
                    "tokens": run_tokens
                })
                
                # Aggregate agent costs
                for agent, cost in cost_summary.get("cost_by_agent", {}).items():
                    agent_costs[agent] = agent_costs.get(agent, 0.0) + cost
                    
        except Exception as exc:
            logger.warning(f"Failed to get cost for run {run.id}: {exc}")

    return {
        "project_id": str(project_id),
        "project_name": project.name,
        "total_runs": len(runs),
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "average_cost_per_run": round(total_cost / len(runs), 6) if runs else 0.0,
        "cost_by_agent": {k: round(v, 6) for k, v in agent_costs.items()},
        "recent_runs": run_costs[:10],  # Last 10 runs
        "cost_trend": run_costs  # All runs for trend analysis
    }


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a project and all associated data including:
    - All project runs and their events
    - All artifacts and S3 files
    - The project itself
    """
    # First check if user has access to the project
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check ownership (admins can access all projects)
    if project.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    
    try:
        # Get all runs for S3 cleanup
        runs_result = await db.execute(
            select(ProjectRun).where(ProjectRun.project_id == project_id)
        )
        runs = runs_result.scalars().all()
        
        # Get all artifacts for S3 cleanup
        artifacts_result = await db.execute(
            select(Artifact).where(Artifact.project_id == project_id)
        )
        artifacts = artifacts_result.scalars().all()
        
        # Clean up S3 artifacts
        from app.services.s3 import s3_service
        
        # Delete all S3 objects for this project using the prefix
        project_prefix = f"projects/{project_id}/"
        deleted_count = await s3_service.delete_objects_by_prefix(project_prefix)
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} S3 objects for project {project_id}")
        
        # Delete individual artifacts from S3 (if they have specific S3 keys not following the pattern)
        for artifact in artifacts:
            if hasattr(artifact, 's3_key') and artifact.s3_key:
                # Only delete if it's not already covered by the prefix deletion
                if not artifact.s3_key.startswith(project_prefix):
                    try:
                        await s3_service.delete_object(artifact.s3_key)
                        logger.info(f"Deleted artifact S3 object: {artifact.s3_key}")
                    except Exception as e:
                        logger.warning(f"Failed to delete S3 artifact {artifact.s3_key}: {e}")
        
        # Note: Project ZIP files should be covered by the prefix deletion above
        
        # Delete from database - CASCADE will handle related records
        await db.delete(project)
        await db.commit()
        
        logger.info(f"Successfully deleted project {project_id} and all associated data")
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete project {project_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )

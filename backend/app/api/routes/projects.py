import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.database import get_db, AsyncSessionLocal
from app.models.project import Project, ProjectRun, RunEvent, RunStatus, ProjectStatus
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
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Create a new project."""
    project = Project(
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
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    """List all projects, newest first."""
    result = await db.execute(
        select(Project).order_by(desc(Project.created_at)).offset(skip).limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Project:
    """Get a single project by ID."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ─── Run Management ────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/runs",
    response_model=ProjectRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_project_run(
    project_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> ProjectRun:
    """Create and start a new agent pipeline run for a project."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

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
    await db.refresh(run)

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
    db: AsyncSession = Depends(get_db),
) -> list[ProjectRun]:
    """List all runs for a project, newest first."""
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
    db: AsyncSession = Depends(get_db),
) -> ProjectRun:
    """Get a specific run with all its events."""
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
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> RunStateResponse:
    """
    Return the full LangGraph checkpoint state for a run.

    Includes zip_url, specification, architecture, code_files, etc.
    The frontend calls this to retrieve the download URL after packaging.
    """
    result = await db.execute(
        select(ProjectRun).where(
            ProjectRun.id == run_id,
            ProjectRun.project_id == project_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Use thread_id (LangGraph identifier), NOT the DB UUID
    state = await orchestrator.get_run_state(run.thread_id)
    return RunStateResponse(state=state)


@router.post("/{project_id}/runs/{run_id}/feedback", response_model=FeedbackResponse)
async def submit_human_feedback(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    feedback: HumanFeedback,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> FeedbackResponse:
    """
    Submit a human review decision to resume a paused run.

    The run must be in WAITING_REVIEW status.
    Actions: approve | modify | reject
    """
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
    db: AsyncSession = Depends(get_db),
    orchestrator: AgentOrchestrator = Depends(get_orchestrator),
) -> CancelResponse:
    """
    Cancel a run that is currently paused at a human-review checkpoint.

    Injects a reject action into the LangGraph interrupt, which routes
    to handle_rejection and terminates the pipeline gracefully.
    """
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
                f"Only WAITING_REVIEW runs can be cancelled. "
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
        "interrupt_payload": dict | None,
        "error":             str | None   (only on failed/cancelled)
    }
    """
    run_status = result.get("status", "completed")

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
    # Mark run as started
    async with AsyncSessionLocal() as db:
        run = await db.get(ProjectRun, run_db_id)
        if not run:
            logger.error(f"Run {run_db_id} not found at start of background task")
            return
        run.started_at = datetime.now(timezone.utc)
        await db.commit()

    try:
        result = await orchestrator.start_run(
            project_id=str(project_id),
            run_id=thread_id,
            requirements=requirements,
            target_language=target_language,
            target_framework=target_framework,
        )

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
    try:
        result = await orchestrator.resume_run(
            run_id=thread_id,
            human_feedback=feedback,
        )

        async with AsyncSessionLocal() as db:
            run     = await db.get(ProjectRun, run_db_id)
            project = await db.get(Project, project_id)
            if run:
                _apply_result_to_run(run, project, result)
                await db.commit()

    except Exception as exc:
        logger.error(
            f"Resume of run {thread_id} failed: {exc}",
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

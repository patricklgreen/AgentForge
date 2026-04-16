import uuid
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from sqlalchemy.orm import selectinload

from app.database import get_db, AsyncSessionLocal
from app.models.project import Project, ProjectRun, RunEvent, RunStatus, ProjectStatus, Artifact
from app.models.auth import UserRole, User
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
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import get_settings
from app.auth.dependencies import CurrentUser, get_current_user
from app.services.s3 import s3_service

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
        visual_references=[ref.model_dump() for ref in (data.visual_references or [])] if data.visual_references else None,
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
        visual_references=project.visual_references,
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
    try:

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

        # Don't immediately mark as running here - let the direct fix handle it
        # to avoid conflicts with the database state
        
        # Temporarily disable duplicate checking to isolate the issue
        # TODO: Re-enable with proper timezone handling once workflow is stable
        
        logger.info(f"🔄 [FEEDBACK_DEBUG] Processing feedback for run {run_id}, step: {run.current_step}")
        

        # Also update project status to running when resuming
        project = await db.get(Project, project_id)
        if project:
            project.status = ProjectStatus.RUNNING

        # Mark this step as approved to prevent showing duplicate modals
        if feedback.action == "approve":
            approved_steps = run.approved_steps or []
            if run.current_step and run.current_step not in approved_steps:
                approved_steps.append(run.current_step)
                run.approved_steps = approved_steps
                logger.info(f"✅ Marked step '{run.current_step}' as approved for duplicate prevention")

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

        # Handle workflow resumption synchronously to avoid background task issues
        # DIRECT FIX: Bypass complex orchestrator resumption and update database directly
        try:
            # Database debug: Record function entry
            debug_event = RunEvent(
                run_id=run_id,
                event_type="debug",
                agent_name="DirectFix",
                step=run.current_step,
                message="DIRECT_FIX: Function started",
                data={"action": feedback.action, "thread_id": str(run.thread_id)},
            )
            db.add(debug_event)
            await db.commit()
            
            logger.error(f"🔄 [DIRECT_FIX] Applying direct database updates to fix workflow")
            
            # Clear the interrupt payload completely
            run.interrupt_payload = None
            
            # Progress to the next step after requirements_analysis
            if run.current_step == "requirements_analysis" and feedback.action == "approve":
                run.current_step = "architecture_design"
                logger.error(f"🔄 [DIRECT_FIX] Progressed from requirements_analysis to architecture_design")
            
            # Update run status to running
            run.status = RunStatus.RUNNING
            
            # Update project status to running
            if project:
                project.status = ProjectStatus.RUNNING
                
            # Commit the direct database updates
            await db.commit()
            
            # Database debug: Record database updates completed
            debug_event2 = RunEvent(
                run_id=run_id,
                event_type="debug",
                agent_name="DirectFix",
                step=run.current_step,
                message="DIRECT_FIX: Database updates completed",
                data={
                    "new_step": run.current_step, 
                    "new_status": run.status.value,
                    "interrupt_cleared": run.interrupt_payload is None
                },
            )
            db.add(debug_event2)
            await db.commit()
            
            logger.error(f"✅ [DIRECT_FIX] Database updated successfully - Run: RUNNING, Current step: {run.current_step}, interrupt cleared")
            
            # MANUAL TRIGGER: Actually start the workflow execution 
            try:
                # Database debug: Record manual trigger start
                debug_event3 = RunEvent(
                    run_id=run_id,
                    event_type="debug",
                    agent_name="ManualTrigger",
                    step=run.current_step,
                    message="MANUAL_TRIGGER: Starting workflow execution",
                    data={"thread_id": str(run.thread_id)},
                )
                db.add(debug_event3)
                await db.commit()
                
                logger.error(f"🚀 [MANUAL_TRIGGER] Starting workflow execution for thread_id: {run.thread_id}")
                
                # Step 1: Initialize orchestrator if needed
                logger.error(f"🔧 [MANUAL_TRIGGER] Step 1 - Checking orchestrator initialization")
                if not orchestrator._graph:
                    # Database debug: Record orchestrator initialization
                    debug_event4 = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message="MANUAL_TRIGGER: Initializing orchestrator",
                        data={},
                    )
                    db.add(debug_event4)
                    await db.commit()
                    
                    logger.error(f"🔧 [MANUAL_TRIGGER] Orchestrator graph not initialized, initializing now...")
                    await orchestrator.initialize()
                    logger.error(f"✅ [MANUAL_TRIGGER] Orchestrator initialized successfully")
                else:
                    logger.error(f"✅ [MANUAL_TRIGGER] Orchestrator already initialized")
                    
                # Step 2: Create checkpointer for this run
                logger.error(f"🔧 [MANUAL_TRIGGER] Step 2 - Creating checkpointer")
                try:
                    checkpointer_cm = AsyncPostgresSaver.from_conn_string(orchestrator.clean_conn)
                    checkpointer = await checkpointer_cm.__aenter__()
                    logger.error(f"✅ [MANUAL_TRIGGER] Checkpointer created successfully")
                    
                    # Database debug: Record checkpointer success
                    debug_event5 = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message="MANUAL_TRIGGER: Checkpointer created successfully",
                        data={},
                    )
                    db.add(debug_event5)
                    await db.commit()
                    
                except Exception as cp_error:
                    logger.error(f"❌ [MANUAL_TRIGGER] Failed to create checkpointer: {cp_error}", exc_info=True)
                    
                    # Database debug: Record checkpointer failure
                    debug_event_error = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message=f"MANUAL_TRIGGER: Checkpointer creation failed: {str(cp_error)}",
                        data={"error_type": type(cp_error).__name__},
                    )
                    db.add(debug_event_error)
                    await db.commit()
                    raise
                
                # Step 3: Compile graph with checkpointer
                logger.error(f"🔧 [MANUAL_TRIGGER] Step 3 - Compiling graph with checkpointer")
                try:
                    graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer)
                    logger.error(f"✅ [MANUAL_TRIGGER] Graph compiled successfully")
                    
                    # Database debug: Record graph compilation success
                    debug_event6 = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message="MANUAL_TRIGGER: Graph compiled successfully",
                        data={},
                    )
                    db.add(debug_event6)
                    await db.commit()
                    
                except Exception as graph_error:
                    logger.error(f"❌ [MANUAL_TRIGGER] Failed to compile graph: {graph_error}", exc_info=True)
                    
                    # Database debug: Record graph compilation failure
                    debug_event_error = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message=f"MANUAL_TRIGGER: Graph compilation failed: {str(graph_error)}",
                        data={"error_type": type(graph_error).__name__},
                    )
                    db.add(debug_event_error)
                    await db.commit()
                    raise
                
                config = {"configurable": {"thread_id": run.thread_id}}
                logger.error(f"✅ [MANUAL_TRIGGER] Config created: {config}")
                
                # Step 4: Get current state and inject feedback
                logger.error(f"🔧 [MANUAL_TRIGGER] Step 4 - Getting current state")
                try:
                    state = await graph_with_checkpointer.aget_state(config)
                    logger.error(f"✅ [MANUAL_TRIGGER] Current state retrieved: next={state.next}, has_values={state.values is not None}")
                    
                    # Database debug: Record state retrieval success
                    debug_event7 = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message="MANUAL_TRIGGER: State retrieved successfully",
                        data={
                            "has_next": state.next is not None,
                            "has_values": state.values is not None,
                            "state_keys": list(state.values.keys()) if state.values else []
                        },
                    )
                    db.add(debug_event7)
                    await db.commit()
                    
                    if state.values:
                        logger.error(f"🔍 [MANUAL_TRIGGER] State keys: {list(state.values.keys())}")
                    else:
                        logger.error(f"⚠️ [MANUAL_TRIGGER] State values is None")
                except Exception as state_error:
                    logger.error(f"❌ [MANUAL_TRIGGER] Failed to get state: {state_error}", exc_info=True)
                    
                    # Database debug: Record state retrieval failure
                    debug_event_error = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message=f"MANUAL_TRIGGER: State retrieval failed: {str(state_error)}",
                        data={"error_type": type(state_error).__name__},
                    )
                    db.add(debug_event_error)
                    await db.commit()
                    raise
                
                # Step 5: Inject the human feedback into the workflow state
                logger.error(f"🔧 [MANUAL_TRIGGER] Step 5 - Injecting feedback into state")
                try:
                    current_state = state.values or {}
                    existing_feedback = current_state.get("human_feedback", [])
                    
                    # Find the step that was actually approved by looking at the latest interrupt event
                    result = await db.execute(
                        select(RunEvent)
                        .where(RunEvent.run_id == run_id)
                        .where(RunEvent.event_type == "interrupt")
                        .order_by(RunEvent.created_at.desc())
                        .limit(1)
                    )
                    latest_interrupt = result.scalar_one_or_none()
                    
                    # Extract the step from the interrupt data
                    approved_step = run.current_step  # Default fallback
                    if latest_interrupt and latest_interrupt.data:
                        interrupt_data = latest_interrupt.data
                        approved_step = interrupt_data.get("step", run.current_step)
                    
                    # Create feedback with step information
                    feedback_with_step = {
                        "step": approved_step,      # Use the step from the interrupt
                        **feedback.model_dump()    # Include action, feedback, modifications
                    }
                    updated_feedback = [*existing_feedback, feedback_with_step]
                    updated_state = {**current_state, "human_feedback": updated_feedback}

                    logger.error(f"🔍 [MANUAL_TRIGGER] Existing feedback count: {len(existing_feedback)}")
                    logger.error(f"🔍 [MANUAL_TRIGGER] Updated feedback count: {len(updated_feedback)}")
                    logger.error(f"🔍 [MANUAL_TRIGGER] Injecting feedback for step: {approved_step} (was current_step: {run.current_step})")

                    # Update state with feedback
                    await graph_with_checkpointer.aupdate_state(config, updated_state)
                    logger.error(f"✅ [MANUAL_TRIGGER] Injected feedback into workflow state successfully")
                    
                    # Database debug: Record feedback injection success
                    debug_event8 = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message="MANUAL_TRIGGER: Feedback injected successfully",
                        data={
                            "existing_feedback_count": len(existing_feedback),
                            "total_feedback_count": len(updated_feedback)
                        },
                    )
                    db.add(debug_event8)
                    await db.commit()
                    
                except Exception as feedback_error:
                    logger.error(f"❌ [MANUAL_TRIGGER] Failed to inject feedback: {feedback_error}", exc_info=True)
                    
                    # Database debug: Record feedback injection failure
                    debug_event_error = RunEvent(
                        run_id=run_id,
                        event_type="debug",
                        agent_name="ManualTrigger",
                        step=run.current_step,
                        message=f"MANUAL_TRIGGER: Feedback injection failed: {str(feedback_error)}",
                        data={"error_type": type(feedback_error).__name__},
                    )
                    db.add(debug_event_error)
                    await db.commit()
                    raise
                
                # Step 6: Trigger workflow execution in background
                logger.error(f"🔧 [MANUAL_TRIGGER] Step 6 - Starting background workflow execution")
                
                # Database debug: Record workflow execution start
                debug_event9 = RunEvent(
                    run_id=run_id,
                    event_type="debug",
                    agent_name="ManualTrigger",
                    step=run.current_step,
                    message="MANUAL_TRIGGER: Starting background workflow execution",
                    data={},
                )
                db.add(debug_event9)
                await db.commit()
                
                async def continue_workflow():
                    workflow_logger = logging.getLogger(f"workflow_{run.thread_id}")
                    final_result = None
                    
                    try:
                        workflow_logger.error(f"🔥 [WORKFLOW_EXECUTION] Starting background workflow execution")
                        logger.error(f"🔥 [WORKFLOW_EXECUTION] Starting background workflow execution")

                        # Database debug: Record workflow execution startup
                        async with AsyncSessionLocal() as workflow_db:
                            debug_workflow_start = RunEvent(
                                run_id=run_id,
                                event_type="debug",
                                agent_name="WorkflowExecution",
                                step=run.current_step,
                                message="WORKFLOW_EXECUTION: Background task started",
                                data={},
                            )
                            workflow_db.add(debug_workflow_start)
                            await workflow_db.commit()

                        # Stream the workflow execution
                        step_count = 0
                        last_chunk = None
                        detected_interrupt = None
                        
                        async for chunk in graph_with_checkpointer.astream(None, config):
                            step_count += 1
                            last_chunk = chunk
                            workflow_logger.error(f"📋 [WORKFLOW_EXECUTION] Step {step_count} completed: {chunk}")
                            logger.error(f"📋 [WORKFLOW_EXECUTION] Step {step_count} completed: {chunk}")
                            
                            # Debug: Always log chunk type and basic info
                            logger.error(f"🔍 [WORKFLOW_EXECUTION] Chunk type: {type(chunk)}, is_dict: {isinstance(chunk, dict)}")
                            if isinstance(chunk, dict):
                                logger.error(f"🔍 [WORKFLOW_EXECUTION] Chunk keys: {list(chunk.keys())}")
                                if "__interrupt__" in chunk:
                                    logger.error(f"🔍 [WORKFLOW_EXECUTION] FOUND __interrupt__ KEY!")

                            # ═══ CRITICAL: Detect interrupts during streaming ═══
                            if isinstance(chunk, dict) and "__interrupt__" in chunk:
                                interrupt_obj = chunk["__interrupt__"]
                                logger.error(f"🔍 [WORKFLOW_EXECUTION] Raw interrupt object: {type(interrupt_obj)} - {interrupt_obj}")
                                
                                # Extract the interrupt payload
                                if hasattr(interrupt_obj, 'value'):
                                    detected_interrupt = interrupt_obj.value
                                elif isinstance(interrupt_obj, tuple) and len(interrupt_obj) > 0:
                                    # Sometimes it might be a tuple containing the Interrupt object
                                    if hasattr(interrupt_obj[0], 'value'):
                                        detected_interrupt = interrupt_obj[0].value
                                    else:
                                        detected_interrupt = interrupt_obj[0]
                                else:
                                    # Fallback: use the object itself if it looks like interrupt data
                                    detected_interrupt = interrupt_obj
                                
                                logger.error(f"🔍 [WORKFLOW_EXECUTION] Interrupt detected during streaming: {detected_interrupt}")
                                
                                # Database debug: Record interrupt detection
                                async with AsyncSessionLocal() as workflow_db:
                                    debug_interrupt_detected = RunEvent(
                                        run_id=run_id,
                                        event_type="debug",
                                        agent_name="WorkflowExecution",
                                        step=run.current_step,
                                        message="WORKFLOW_EXECUTION: Interrupt detected during streaming",
                                        data={
                                            "interrupt_step": detected_interrupt.get("step") if isinstance(detected_interrupt, dict) else str(detected_interrupt)[:100],
                                            "interrupt_type": str(type(interrupt_obj))
                                        },
                                    )
                                    workflow_db.add(debug_interrupt_detected)
                                    await workflow_db.commit()

                            # Database debug: Record workflow step completion
                            async with AsyncSessionLocal() as workflow_db:
                                debug_workflow_step = RunEvent(
                                    run_id=run_id,
                                    event_type="debug",
                                    agent_name="WorkflowExecution",
                                    step=run.current_step,
                                    message=f"WORKFLOW_EXECUTION: Step {step_count} completed",
                                    data={"chunk": str(chunk)[:500]},  # Truncate large chunks
                                )
                                workflow_db.add(debug_workflow_step)
                                await workflow_db.commit()

                        logger.error(f"✅ [WORKFLOW_EXECUTION] Background workflow completed after {step_count} steps")
                        
                        # ═══ CRITICAL FIX: Use detected interrupt instead of inspection ═══
                        if detected_interrupt:
                            # We detected an interrupt during streaming
                            final_result = {
                                "status": "interrupted",
                                "interrupt_payload": detected_interrupt,
                                "current_step": detected_interrupt.get("step")
                            }
                            logger.error(f"🔍 [WORKFLOW_EXECUTION] Using detected interrupt as final result: {final_result}")
                        else:
                            # No interrupt detected - try inspection as fallback
                            try:
                                # Get the orchestrator instance to inspect the final result
                                orchestrator = await get_orchestrator()
                                final_result = await orchestrator._inspect_run_result(run.thread_id)
                                logger.error(f"🔍 [WORKFLOW_EXECUTION] Inspection result (no interrupt detected): {final_result}")
                            except Exception as inspect_error:
                                logger.error(f"⚠️ [WORKFLOW_EXECUTION] Failed to inspect final result: {inspect_error}")
                                # Fallback: assume completed if we can't inspect  
                                final_result = {"status": "completed", "interrupt_payload": None}

                        # Database debug: Record workflow completion with status
                        async with AsyncSessionLocal() as workflow_db:
                            debug_workflow_complete = RunEvent(
                                run_id=run_id,
                                event_type="debug",
                                agent_name="WorkflowExecution",
                                step=run.current_step,
                                message=f"WORKFLOW_EXECUTION: Completed after {step_count} steps",
                                data={
                                    "total_steps": step_count,
                                    "final_status": final_result.get("status") if final_result else "unknown"
                                },
                            )
                            workflow_db.add(debug_workflow_complete)
                            await workflow_db.commit()
                        
                    except Exception as e:
                        workflow_logger.error(f"❌ [WORKFLOW_EXECUTION] Error in background workflow: {e}", exc_info=True)
                        logger.error(f"❌ [WORKFLOW_EXECUTION] Error in background workflow: {e}", exc_info=True)
                        
                        # Set error result
                        final_result = {"status": "failed", "interrupt_payload": None, "error": str(e)}
                        
                        # Database debug: Record workflow error
                        try:
                            async with AsyncSessionLocal() as workflow_db:
                                debug_workflow_error = RunEvent(
                                    run_id=run_id,
                                    event_type="debug",
                                    agent_name="WorkflowExecution",
                                    step=run.current_step,
                                    message=f"WORKFLOW_EXECUTION: Error: {str(e)}",
                                    data={"error_type": type(e).__name__},
                                )
                                workflow_db.add(debug_workflow_error)
                                await workflow_db.commit()
                        except:
                            pass  # Don't fail on debug logging
                    
                    finally:
                        # ═══ CRITICAL FIX: Apply final result to database ═══
                        if final_result:
                            try:
                                logger.error(f"🔄 [WORKFLOW_EXECUTION] Applying final result to database: {final_result}")
                                
                                async with AsyncSessionLocal() as workflow_db:
                                    # Re-fetch the run and project to get fresh data
                                    updated_run = await workflow_db.get(ProjectRun, run.id)
                                    updated_project = await workflow_db.get(Project, project_id)
                                    
                                    if updated_run:
                                        # Apply the orchestrator result to update status and interrupt_payload
                                        _apply_result_to_run(updated_run, updated_project, final_result)
                                        await workflow_db.commit()
                                        
                                        logger.error(f"✅ [WORKFLOW_EXECUTION] Database updated - Status: {updated_run.status}, Interrupt: {updated_run.interrupt_payload is not None}")
                                        
                                        # Database debug: Record successful application
                                        debug_applied = RunEvent(
                                            run_id=run_id,
                                            event_type="debug",
                                            agent_name="WorkflowExecution", 
                                            step=run.current_step,
                                            message="WORKFLOW_EXECUTION: Final result applied to database",
                                            data={
                                                "final_status": final_result.get("status"),
                                                "db_status": updated_run.status.value if hasattr(updated_run.status, 'value') else str(updated_run.status),
                                                "has_interrupt_payload": updated_run.interrupt_payload is not None
                                            },
                                        )
                                        workflow_db.add(debug_applied)
                                        await workflow_db.commit()
                                    else:
                                        logger.error(f"❌ [WORKFLOW_EXECUTION] Could not find run {run.id} to update")
                                        
                            except Exception as apply_error:
                                logger.error(f"❌ [WORKFLOW_EXECUTION] Failed to apply final result: {apply_error}", exc_info=True)
                                
                                # Database debug: Record application failure
                                try:
                                    async with AsyncSessionLocal() as workflow_db:
                                        debug_apply_error = RunEvent(
                                            run_id=run_id,
                                            event_type="debug",
                                            agent_name="WorkflowExecution",
                                            step=run.current_step,
                                            message=f"WORKFLOW_EXECUTION: Failed to apply result: {str(apply_error)}",
                                            data={"error_type": type(apply_error).__name__},
                                        )
                                        workflow_db.add(debug_apply_error)
                                        await workflow_db.commit()
                                except:
                                    pass
                        
                        # Cleanup checkpointer
                        try:
                            await checkpointer_cm.__aexit__(None, None, None)
                            logger.error(f"🧹 [WORKFLOW_EXECUTION] Checkpointer cleanup completed")
                        except Exception as cleanup_error:
                            logger.error(f"⚠️ [WORKFLOW_EXECUTION] Checkpointer cleanup error: {cleanup_error}")
                
                # Start workflow in background
                import asyncio
                task = asyncio.create_task(continue_workflow())
                logger.error(f"🚀 [MANUAL_TRIGGER] Workflow execution task started: {task}")
                logger.error(f"✅ [MANUAL_TRIGGER] All steps completed successfully")
                
                # Database debug: Record manual trigger completion
                debug_event10 = RunEvent(
                    run_id=run_id,
                    event_type="debug",
                    agent_name="ManualTrigger",
                    step=run.current_step,
                    message="MANUAL_TRIGGER: All steps completed successfully",
                    data={"task_started": True},
                )
                db.add(debug_event10)
                await db.commit()
                
            except Exception as trigger_error:
                logger.error(f"❌ [MANUAL_TRIGGER] Failed to trigger workflow: {trigger_error}", exc_info=True)
                logger.error(f"❌ [MANUAL_TRIGGER] Trigger error type: {type(trigger_error).__name__}")
                logger.error(f"❌ [MANUAL_TRIGGER] Trigger error args: {trigger_error.args}")
                
                # Database debug: Record manual trigger failure
                debug_event_final_error = RunEvent(
                    run_id=run_id,
                    event_type="debug",
                    agent_name="ManualTrigger",
                    step=run.current_step,
                    message=f"MANUAL_TRIGGER: Failed with error: {str(trigger_error)}",
                    data={
                        "error_type": type(trigger_error).__name__,
                        "error_args": str(trigger_error.args)
                    },
                )
                db.add(debug_event_final_error)
                await db.commit()
                # Re-raise to see the full stack trace
                raise
            
        except Exception as e:
            logger.error(f"❌ [DIRECT_FIX] Failed to apply direct fix: {e}", exc_info=True)
            
            # Database debug: Record overall failure
            try:
                debug_event_final = RunEvent(
                    run_id=run_id,
                    event_type="debug",
                    agent_name="DirectFix",
                    step=run.current_step,
                    message=f"DIRECT_FIX: Failed with error: {str(e)}",
                    data={"error_type": type(e).__name__},
                )
                db.add(debug_event_final)
                await db.commit()
            except:
                pass  # Don't fail on debug logging
                
            # Don't fail the API call - the feedback was recorded successfully

        return FeedbackResponse(
            status="resumed", 
            action=feedback.action
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"❌ [FEEDBACK_DEBUG] Unexpected error in feedback processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Feedback processing error: {str(e)}")


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


@router.put("/{project_id}/runs/{run_id}/requirements")
async def update_requirements(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    requirements: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Update the requirements specification for an active run."""
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    run = await db.get(ProjectRun, run_id)
    if not run or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="Run not found")

    # Update the LangGraph state with the new requirements
    orchestrator = await get_orchestrator()
    try:
        config = {"configurable": {"thread_id": run.thread_id}}
        
        # Get current state
        checkpointer_cm = AsyncPostgresSaver.from_conn_string(orchestrator.clean_conn)
        checkpointer = await checkpointer_cm.__aenter__()
        graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer) if orchestrator._graph else None
        
        if not graph_with_checkpointer:
            await orchestrator.initialize()
            graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer)
        
        current_state = await graph_with_checkpointer.aget_state(config)
        if not current_state or not current_state.values:
            raise HTTPException(status_code=400, detail="No active state found for this run")
        
        # Update the specification in the state
        updated_state = {
            **current_state.values,
            "specification": requirements
        }
        
        await graph_with_checkpointer.aupdate_state(config, updated_state)
        
        # Cleanup
        await checkpointer_cm.__aexit__(None, None, None)
        
        return {"status": "updated", "message": "Requirements updated successfully"}
        
    except Exception as exc:
        logger.error(f"Failed to update requirements for run {run_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update requirements: {str(exc)}")


@router.get("/{project_id}/requirements")
async def get_requirements(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Get the current requirements specification for a project."""
    logger.info(f"🔍 [REQUIREMENTS_DEBUG] Getting requirements for project {project_id}")
    
    project = await db.get(Project, project_id)
    if not project:
        logger.error(f"❌ [REQUIREMENTS_DEBUG] Project {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != current_user.id:
        logger.error(f"❌ [REQUIREMENTS_DEBUG] User {current_user.id} not authorized for project {project_id}")
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get the latest run for this project
    logger.info(f"🔍 [REQUIREMENTS_DEBUG] Getting latest run for project {project_id}")
    result = await db.execute(
        select(ProjectRun)
        .where(ProjectRun.project_id == project_id)
        .order_by(desc(ProjectRun.created_at))
        .limit(1)
    )
    latest_run = result.scalar_one_or_none()
    
    if not latest_run:
        logger.error(f"❌ [REQUIREMENTS_DEBUG] No runs found for project {project_id}")
        raise HTTPException(status_code=404, detail="No runs found for this project")

    logger.info(f"🔍 [REQUIREMENTS_DEBUG] Found run {latest_run.id}, thread_id: {latest_run.thread_id}")

    # Get the requirements from the LangGraph state
    orchestrator = await get_orchestrator()
    try:
        config = {"configurable": {"thread_id": latest_run.thread_id}}
        logger.info(f"🔍 [REQUIREMENTS_DEBUG] Creating checkpointer for requirements lookup")
        
        # Get current state
        checkpointer_cm = AsyncPostgresSaver.from_conn_string(orchestrator.clean_conn)
        checkpointer = await checkpointer_cm.__aenter__()
        logger.info(f"🔍 [REQUIREMENTS_DEBUG] Checkpointer created successfully")
        
        graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer) if orchestrator._graph else None
        
        if not graph_with_checkpointer:
            logger.info(f"🔍 [REQUIREMENTS_DEBUG] Initializing orchestrator")
            await orchestrator.initialize()
            graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer)
        
        logger.info(f"🔍 [REQUIREMENTS_DEBUG] Getting state for config: {config}")
        current_state = await graph_with_checkpointer.aget_state(config)
        if not current_state or not current_state.values:
            logger.error(f"❌ [REQUIREMENTS_DEBUG] No active state found for project {project_id}")
            await checkpointer_cm.__aexit__(None, None, None)
            raise HTTPException(status_code=400, detail="No active state found for this project")
        
        logger.info(f"🔍 [REQUIREMENTS_DEBUG] State retrieved successfully")
        specification = current_state.values.get("specification")
        if not specification:
            logger.error(f"❌ [REQUIREMENTS_DEBUG] No requirements specification found in state")
            await checkpointer_cm.__aexit__(None, None, None)
            raise HTTPException(status_code=404, detail="No requirements specification found")
        
        logger.info(f"✅ [REQUIREMENTS_DEBUG] Requirements found successfully, returning data")
        
        # Cleanup
        await checkpointer_cm.__aexit__(None, None, None)
        
        return {
            "project_name": project.name,
            "project_id": str(project_id),
            "run_id": str(latest_run.id),
            "specification": specification,
            "generated_at": latest_run.created_at.isoformat(),
        }
        
    except Exception as exc:
        logger.error(f"❌ [REQUIREMENTS_DEBUG] Failed to get requirements for project {project_id}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get requirements: {str(exc)}")


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
    visual_references: Optional[list],
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
            visual_references=visual_references,
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
                
                # Mark step as approved if feedback was approve and run succeeded
                if feedback.get("action") == "approve" and result.get("status") in ["completed", "interrupted"]:
                    step = feedback.get("step")
                    if step:
                        approved_steps = run.approved_steps or []
                        if step not in approved_steps:
                            approved_steps.append(step)
                            run.approved_steps = approved_steps
                            logger.info(f"✅ Marked step '{step}' as approved")
                
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
        logger.info(f"🔍 [COST_DEBUG] Getting cost summary for run {run_id}, thread_id: {run.thread_id}")
        orchestrator = await get_orchestrator()
        config = {"configurable": {"thread_id": run.thread_id}}
        
        # Get state to check for cost_summary
        logger.info(f"🔍 [COST_DEBUG] Creating checkpointer for cost lookup")
        checkpointer_cm = AsyncPostgresSaver.from_conn_string(orchestrator.clean_conn)
        checkpointer = await checkpointer_cm.__aenter__()
        logger.info(f"🔍 [COST_DEBUG] Checkpointer created successfully")
        
        graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer) if orchestrator._graph else None
        
        if not graph_with_checkpointer:
            logger.info(f"🔍 [COST_DEBUG] Graph not available, initializing orchestrator")
            await orchestrator.initialize()
            graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer)
        
        logger.info(f"🔍 [COST_DEBUG] Getting state for config: {config}")
        current_state = await graph_with_checkpointer.aget_state(config)
        logger.info(f"🔍 [COST_DEBUG] State retrieved, values available: {bool(current_state and current_state.values)}")
        
        if current_state and current_state.values:
            cost_summary = current_state.values.get("cost_summary")
            logger.info(f"🔍 [COST_DEBUG] Cost summary found: {bool(cost_summary)}")
            if cost_summary:
                logger.info(f"🔍 [COST_DEBUG] Cost summary details: total_cost={cost_summary.get('total_cost_usd', 'N/A')}, tokens={cost_summary.get('total_tokens', 'N/A')}")
                # Cleanup
                await checkpointer_cm.__aexit__(None, None, None)
                return cost_summary
        
        # Cleanup
        logger.info(f"🔍 [COST_DEBUG] No cost summary found, cleaning up")
        await checkpointer_cm.__aexit__(None, None, None)
        
    except Exception as exc:
        logger.error(f"❌ [COST_DEBUG] Failed to get cost summary from orchestrator: {exc}", exc_info=True)

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

    orchestrator = await get_orchestrator()

    logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Starting cost analytics for project {project_id}, found {len(runs)} runs")
    
    for run in runs:
        try:
            logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Processing run {run.id}, thread_id: {run.thread_id}")
            config = {"configurable": {"thread_id": run.thread_id}}
            
            # Get state to check for cost_summary
            logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Creating checkpointer for run {run.id}")
            checkpointer_cm = AsyncPostgresSaver.from_conn_string(orchestrator.clean_conn)
            checkpointer = await checkpointer_cm.__aenter__()
            graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer) if orchestrator._graph else None
            
            if not graph_with_checkpointer:
                logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Initializing orchestrator for run {run.id}")
                await orchestrator.initialize()
                graph_with_checkpointer = orchestrator._graph.compile(checkpointer=checkpointer)
            
            logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Getting state for run {run.id}")
            current_state = await graph_with_checkpointer.aget_state(config)
            cost_summary = None
            if current_state and current_state.values:
                cost_summary = current_state.values.get("cost_summary")
                logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Run {run.id} cost summary found: {bool(cost_summary)}")
            else:
                logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Run {run.id} no state or values found")
            
            # Cleanup
            await checkpointer_cm.__aexit__(None, None, None)
            
            if cost_summary:
                run_cost = cost_summary.get("total_cost_usd", 0.0)
                run_tokens = cost_summary.get("total_tokens", 0)
                logger.info(f"🔍 [COST_ANALYTICS_DEBUG] Run {run.id} adding cost: ${run_cost}, tokens: {run_tokens}")
                
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
            logger.error(f"❌ [COST_ANALYTICS_DEBUG] Failed to get cost for run {run.id}: {exc}", exc_info=True)

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


@router.post("/visual-reference/upload")
async def upload_visual_reference(
    file: UploadFile = File(...),
    description: Optional[str] = None,
    user: CurrentUser = CurrentUser,
) -> dict:
    """Upload a visual reference image (mockup, design, screenshot)."""
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="Only image files are allowed for visual references"
        )
    
    # Validate file size (max 10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size must be less than 10MB"
        )
    
    try:
        # Generate S3 key
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        s3_key = f"visual-references/{user.id}/{uuid.uuid4()}.{file_extension}"
        
        # Upload to S3
        await s3_service.upload_file(
            file_obj=file.file,
            s3_key=s3_key,
            content_type=file.content_type
        )
        
        # Generate presigned URL for immediate preview
        preview_url = await s3_service.generate_presigned_url(s3_key, expires_in=3600)  # 1 hour
        
        return {
            "s3_key": s3_key,
            "file_name": file.filename,
            "file_size": file_size,
            "content_type": file.content_type,
            "description": description,
            "preview_url": preview_url
        }
        
    except Exception as e:
        logger.error(f"Failed to upload visual reference: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to upload visual reference"
        )


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

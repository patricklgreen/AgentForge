"""Persist LLM cost snapshots to project_runs for UI polling and durable totals."""

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.project import ProjectRun

if TYPE_CHECKING:
    from app.services.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


async def persist_run_cost_snapshot(thread_id: str, cost_tracker: "CostTracker") -> None:
    """Write current cumulative cost to the run row (used during and after pipeline execution)."""
    try:
        summary = cost_tracker.summary()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ProjectRun).where(ProjectRun.thread_id == thread_id)
            )
            run = result.scalar_one_or_none()
            if run:
                run.cost_summary = summary
                await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist cost snapshot for %s: %s", thread_id, exc)

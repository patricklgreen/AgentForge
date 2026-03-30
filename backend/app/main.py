import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.api.routes import projects, artifacts, auth
from app.services.websocket_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle handler."""
    logger.info("Starting AgentForge API...")

    # In development, create tables from models.
    # In production, Alembic migrations handle schema management.
    if settings.app_env != "production":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified / created")

    # Pre-initialise the orchestrator so the first user request never
    # blocks on cold-start initialisation (which can take several seconds
    # when the LangGraph checkpointer sets up its PostgreSQL tables).
    from app.api.routes.projects import get_orchestrator
    orchestrator = await get_orchestrator()
    app.state.orchestrator = orchestrator
    logger.info("Orchestrator pre-initialised")

    logger.info(
        f"AgentForge API ready — env={settings.app_env}, "
        f"model={settings.bedrock_model_id}"
    )
    yield

    logger.info("Shutting down AgentForge API...")
    await engine.dispose()
    logger.info("Database connections closed")


app = FastAPI(
    title="AgentForge API",
    description=(
        "AI-powered application builder using a multi-agent workflow. "
        "Provide business requirements and receive production-ready code."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url=f"{settings.api_prefix}/docs",
    redoc_url=f"{settings.api_prefix}/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

# ─── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(artifacts.router, prefix=settings.api_prefix)


# ─── Health endpoint ──────────────────────────────────────────────────────────

@app.get(f"{settings.api_prefix}/health", tags=["health"])
async def health() -> dict:
    """Health check endpoint used by ALB and ECS health checks."""
    return {
        "status":  "healthy",
        "service": "agentforge-api",
        "env":     settings.app_env,
    }


# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws/{run_id}")
async def websocket_endpoint(websocket: WebSocket, run_id: str) -> None:
    """
    WebSocket endpoint for real-time agent run progress.

    Clients connect with the LangGraph thread_id (= ProjectRun.thread_id).
    The server pushes structured events as agents execute:
      { type, agent, step, message, data }

    Special event types:
      interrupt    — pipeline paused; data contains the review payload
      run_complete — packaging done; data.zip_url is the download link
      run_cancelled — pipeline rejected by reviewer
      error        — unhandled agent error
    """
    await ws_manager.connect(websocket, run_id)
    logger.info(f"WebSocket client connected: run_id={run_id}")
    try:
        while True:
            # Keep the connection alive; ignore any client messages.
            # Future: accept feedback directly via WebSocket as an alternative
            # to the REST feedback endpoint.
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: run_id={run_id}")
    except Exception as exc:
        logger.error(f"WebSocket error for run {run_id}: {exc}")
    finally:
        ws_manager.disconnect(websocket, run_id)

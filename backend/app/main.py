import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
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

# Custom CORS middleware since FastAPI CORS middleware is not working
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, PlainTextResponse

class CustomCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = PlainTextResponse("OK", status_code=200)
        else:
            response = await call_next(request)
        
        # Add CORS headers to all responses
        response.headers["Access-Control-Allow-Origin"] = "http://localhost:5173"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"
        
        return response

app.add_middleware(CustomCORSMiddleware)

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
async def websocket_endpoint(
    websocket: WebSocket, 
    run_id: str,
    token: str = Query(None)
) -> None:
    """
    WebSocket endpoint for real-time agent run progress.

    Clients connect with the LangGraph thread_id (= ProjectRun.thread_id).
    Authentication is via ?token=<jwt_token> query parameter.
    
    The server pushes structured events as agents execute:
      { type, agent, step, message, data }

    Special event types:
      interrupt    — pipeline paused; data contains the review payload
      run_complete — packaging done; data.zip_url is the download link
      run_cancelled — pipeline rejected by reviewer
      error        — unhandled agent error
    """
    # SIMPLIFIED VERSION FOR DEBUGGING
    try:
        logger.info(f"🔍 [WS_DEBUG] WebSocket connection attempt for run_id: {run_id}")
        
        # Accept the connection immediately
        await websocket.accept()
        logger.info(f"✅ [WS_DEBUG] WebSocket accepted for run_id: {run_id}")
        
        # Add to manager
        if run_id not in ws_manager._connections:
            ws_manager._connections[run_id] = []
        ws_manager._connections[run_id].append(websocket)
        logger.info(f"✅ [WS_DEBUG] WebSocket registered for run_id: {run_id}")
        
        # Keep connection alive
        while True:
            try:
                await websocket.receive_text()
            except Exception:
                break
                
    except Exception as exc:
        logger.error(f"❌ [WS_DEBUG] WebSocket error for run {run_id}: {exc}", exc_info=True)
    finally:
        logger.info(f"🧹 [WS_DEBUG] Cleaning up WebSocket connection for run_id: {run_id}")
        if run_id in ws_manager._connections and websocket in ws_manager._connections[run_id]:
            ws_manager._connections[run_id].remove(websocket)

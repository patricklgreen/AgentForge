import json
import logging
from typing import Any, Optional

import redis.asyncio as redis
from fastapi import WebSocket

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ConnectionManager:
    """
    Manages WebSocket connections with optional Redis pub/sub for
    multi-instance deployments.

    Local connections are stored in-process.  Events are also published
    to a Redis channel so other application instances can relay them to
    their own connected clients.
    """

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}
        self._redis: Optional[redis.Redis] = None  # type: ignore[type-arg]

    async def get_redis(self) -> redis.Redis:  # type: ignore[type-arg]
        if self._redis is None:
            self._redis = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def connect(self, websocket: WebSocket, run_id: str) -> None:
        await websocket.accept()
        if run_id not in self._connections:
            self._connections[run_id] = []
        self._connections[run_id].append(websocket)
        logger.info(f"WebSocket connected for run: {run_id}")

    def disconnect(self, websocket: WebSocket, run_id: str) -> None:
        if run_id in self._connections:
            try:
                self._connections[run_id].remove(websocket)
            except ValueError:
                pass
            # Clean up empty lists
            if not self._connections[run_id]:
                del self._connections[run_id]
        logger.info(f"WebSocket disconnected for run: {run_id}")

    async def broadcast_to_run(
        self, run_id: str, event: dict[str, Any]
    ) -> None:
        """Send an event to all WebSocket clients subscribed to a run."""
        message = json.dumps(event, default=str)

        # Local connections
        if run_id in self._connections:
            dead: list[WebSocket] = []
            for connection in list(self._connections[run_id]):
                try:
                    await connection.send_text(message)
                except Exception:
                    dead.append(connection)
            for d in dead:
                try:
                    self._connections[run_id].remove(d)
                except ValueError:
                    pass

        # Redis pub/sub for other instances (best-effort)
        try:
            r = await self.get_redis()
            await r.publish(f"run:{run_id}", message)
        except Exception as exc:
            logger.warning(f"Redis publish failed (non-fatal): {exc}")

    async def send_agent_event(
        self,
        run_id: str,
        event_type: str,
        agent_name: str,
        step: str,
        message: str,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Send a structured agent lifecycle event."""
        await self.broadcast_to_run(
            run_id,
            {
                "type":    event_type,
                "agent":   agent_name,
                "step":    step,
                "message": message,
                "data":    data or {},
            },
        )

    async def send_interrupt(
        self,
        run_id: str,
        step: str,
        payload: dict[str, Any],
    ) -> None:
        """Notify frontend that the pipeline is paused for human review."""
        await self.broadcast_to_run(
            run_id,
            {
                "type":    "interrupt",
                "step":    step,
                "payload": payload,
                "message": f"Human review required at step: {step}",
            },
        )


# Module-level singleton
ws_manager = ConnectionManager()

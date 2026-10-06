import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from src.core.cookie_settings import CookieSettings
from src.security.jwt import decode_access_token

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Real-Time Streaming (WebSocket & SSE)"])


def _authenticate_ws(websocket: WebSocket) -> tuple[str | None, str, str | None]:
    """
    Extract and verify credentials from WebSocket cookies or query parameters.
    Returns (user_id, role, tenant_id).
    """
    token = websocket.cookies.get(CookieSettings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        token = websocket.query_params.get("token")

    if token:
        try:
            payload = decode_access_token(token)
            return (
                payload.get("sub"),
                payload.get("role", "viewer"),
                payload.get("tenant_id", "default"),
            )
        except Exception:
            pass

    # Fallback to query param tenant_id if provided
    tenant_param = websocket.query_params.get("tenant_id")
    return (None, "viewer", tenant_param or "default")


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {
            "tasks": [],
            "workers": [],
            "metrics": [],
            "queues": [],
            "live": [],
        }
        self.connection_meta: dict[WebSocket, dict[str, Any]] = {}

    async def connect(
        self,
        websocket: WebSocket,
        channel: str,
        tenant_id: str | None = None,
        role: str = "viewer",
    ) -> None:
        await websocket.accept()
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        self.active_connections[channel].append(websocket)
        self.connection_meta[websocket] = {
            "channel": channel,
            "tenant_id": tenant_id,
            "role": role,
        }

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)
        self.connection_meta.pop(websocket, None)

    async def broadcast(self, channel: str, message: dict, tenant_id: str | None = None) -> None:
        target_tenant = tenant_id
        if target_tenant is None:
            target_tenant = message.get("tenant_id")
            if target_tenant is None and isinstance(message.get("data"), dict):
                target_tenant = message["data"].get("tenant_id")

        # Collect distinct websockets subscribed to the channel or to "live"
        targets: set[WebSocket] = set()
        if channel in self.active_connections:
            targets.update(self.active_connections[channel])
        if channel != "live" and "live" in self.active_connections:
            targets.update(self.active_connections["live"])

        dead: list[WebSocket] = []
        for ws in targets:
            meta = self.connection_meta.get(ws, {})
            client_tenant = meta.get("tenant_id")
            client_role = meta.get("role", "viewer")

            # Multi-tenant isolation enforcement:
            # If event belongs to a specific tenant, only send to matching tenant
            # or global admin with cluster-wide privileges.
            if target_tenant is not None and client_tenant is not None:
                is_same_tenant = client_tenant == target_tenant
                is_global_admin = client_role == "admin" and client_tenant in (
                    None,
                    "default",
                    "*",
                )
                if not (is_same_tenant or is_global_admin):
                    continue

            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)

        for ws in dead:
            for ch in list(self.active_connections.keys()):
                self.disconnect(ws, ch)


ws_manager = ConnectionManager()


async def _handle_ws_messages(websocket: WebSocket) -> None:
    """Handle incoming WebSocket text/json messages including heartbeats."""
    while True:
        data = await websocket.receive_text()
        if data == "ping":
            await websocket.send_text("pong")
        else:
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict) and parsed.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except Exception:
                pass


@router.websocket("/ws/live")
async def ws_live_endpoint(websocket: WebSocket) -> None:
    user_id, role, tenant_id = _authenticate_ws(websocket)
    await ws_manager.connect(websocket, "live", tenant_id=tenant_id, role=role)
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "live",
                "tenant_id": tenant_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await _handle_ws_messages(websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "live")


@router.websocket("/ws/tasks")
async def ws_tasks_endpoint(websocket: WebSocket) -> None:
    user_id, role, tenant_id = _authenticate_ws(websocket)
    await ws_manager.connect(websocket, "tasks", tenant_id=tenant_id, role=role)
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "tasks",
                "tenant_id": tenant_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await _handle_ws_messages(websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "tasks")


@router.websocket("/ws/workers")
async def ws_workers_endpoint(websocket: WebSocket) -> None:
    user_id, role, tenant_id = _authenticate_ws(websocket)
    await ws_manager.connect(websocket, "workers", tenant_id=tenant_id, role=role)
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "workers",
                "tenant_id": tenant_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await _handle_ws_messages(websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "workers")


@router.websocket("/ws/metrics")
async def ws_metrics_endpoint(websocket: WebSocket) -> None:
    user_id, role, tenant_id = _authenticate_ws(websocket)
    await ws_manager.connect(websocket, "metrics", tenant_id=tenant_id, role=role)
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "metrics",
                "tenant_id": tenant_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await _handle_ws_messages(websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "metrics")


@router.websocket("/ws/queues")
async def ws_queues_endpoint(websocket: WebSocket) -> None:
    user_id, role, tenant_id = _authenticate_ws(websocket)
    await ws_manager.connect(websocket, "queues", tenant_id=tenant_id, role=role)
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "queues",
                "tenant_id": tenant_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        await _handle_ws_messages(websocket)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "queues")


async def sse_event_generator() -> AsyncGenerator[str]:
    try:
        while True:
            payload = {
                "event": "heartbeat",
                "data": {"timestamp": datetime.now(UTC).isoformat(), "status": "connected"},
            }
            yield f"event: heartbeat\ndata: {json.dumps(payload['data'])}\n\n"
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass


@router.get("/events", summary="Server-Sent Events (SSE) streaming fallback endpoint")
async def sse_stream() -> StreamingResponse:
    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

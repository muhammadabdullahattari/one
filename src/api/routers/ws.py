import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Real-Time Streaming (WebSocket & SSE)"])


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {
            "tasks": [],
            "workers": [],
            "metrics": [],
        }

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        await websocket.accept()
        if channel in self.active_connections:
            self.active_connections[channel].append(websocket)

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        if channel in self.active_connections and websocket in self.active_connections[channel]:
            self.active_connections[channel].remove(websocket)

    async def broadcast(self, channel: str, message: dict) -> None:
        if channel not in self.active_connections:
            return
        dead = []
        for ws in self.active_connections[channel]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, channel)


ws_manager = ConnectionManager()


@router.websocket("/ws/tasks")
async def ws_tasks_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket, "tasks")
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "tasks",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "tasks")


@router.websocket("/ws/workers")
async def ws_workers_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket, "workers")
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "workers",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "workers")


@router.websocket("/ws/metrics")
async def ws_metrics_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket, "metrics")
    try:
        await websocket.send_json(
            {
                "type": "connection.ack",
                "channel": "metrics",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, "metrics")


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

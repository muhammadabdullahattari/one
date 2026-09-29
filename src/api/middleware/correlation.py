from collections.abc import Callable
from uuid import uuid4

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.constants import HttpHeader


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get(HttpHeader.REQUEST_ID.value)
        if not request_id:
            request_id = f"req-{uuid4().hex[:12]}"
        trace_id = request.headers.get(HttpHeader.TRACE_ID.value)
        if not trace_id:
            trace_id = f"trace-{uuid4().hex[:16]}"
        request.state.request_id = request_id
        request.state.trace_id = trace_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            trace_id=trace_id,
            client_ip=request.client.host if request.client else "unknown",
            path=request.url.path,
            method=request.method,
        )
        response: Response = await call_next(request)
        response.headers[HttpHeader.REQUEST_ID.value] = request_id
        response.headers[HttpHeader.TRACE_ID.value] = trace_id
        return response

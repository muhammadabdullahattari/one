import time
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        path = request.url.path
        is_noisy = path in ("/api/v1/health", "/api/v1/metrics", "/health")
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if not is_noisy:
                logger.info(
                    "http_request_finished",
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    path=path,
                    method=request.method,
                )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "http_request_failed",
                error=str(exc),
                duration_ms=duration_ms,
                path=path,
                method=request.method,
                exc_info=True,
            )
            raise

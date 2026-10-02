from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.schemas.common import ErrorDetail, ErrorResponse
from src.domain.exceptions import (
    IdempotencyConflictError,
    InvalidStateTransitionError,
    TaskNotFoundError,
    TaskRateLimitExceededError,
)

logger = structlog.get_logger(__name__)


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req-unknown")


def _clean_validation_errors(raw_errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for err in raw_errors:
        item = dict(err)
        if "ctx" in item and isinstance(item["ctx"], dict):
            item["ctx"] = {
                k: str(v) if isinstance(v, Exception) else v for k, v in item["ctx"].items()
            }
        cleaned.append(item)
    return cleaned


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = _get_request_id(request)
        error_code = f"HTTP_{exc.status_code}"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            error_code = "RESOURCE_NOT_FOUND"
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            error_code = "FORBIDDEN"
        detail_msg = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        payload = ErrorResponse(
            error=ErrorDetail(
                code=error_code,
                message=detail_msg,
                details={},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        headers = exc.headers if exc.headers else {}
        return JSONResponse(
            status_code=exc.status_code, content=payload.model_dump(mode="json"), headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        cleaned_errors = _clean_validation_errors(exc.errors())
        logger.warning("request_validation_failed", errors=cleaned_errors, path=request.url.path)

        primary_msg = "Invalid request parameters or payload structure."
        if cleaned_errors:
            first_err = cleaned_errors[0]
            loc_parts = [str(l) for l in first_err.get("loc", []) if l != "body"]
            loc = " -> ".join(loc_parts)
            msg = str(first_err.get("msg", ""))
            if msg.startswith("Value error, "):
                msg = msg.replace("Value error, ", "", 1)
            primary_msg = f"{loc}: {msg}" if loc else msg

        payload = ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message=primary_msg,
                details={"errors": jsonable_encoder(cleaned_errors)},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found_handler(request: Request, exc: TaskNotFoundError) -> JSONResponse:
        request_id = _get_request_id(request)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="TASK_NOT_FOUND",
                message=str(exc),
                details={},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content=payload.model_dump(mode="json")
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_state_handler(
        request: Request, exc: InvalidStateTransitionError
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="INVALID_STATE_TRANSITION",
                message=str(exc),
                details={},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content=payload.model_dump(mode="json")
        )

    @app.exception_handler(TaskRateLimitExceededError)
    async def rate_limit_handler(request: Request, exc: TaskRateLimitExceededError) -> JSONResponse:
        request_id = _get_request_id(request)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="RATE_LIMIT_EXCEEDED",
                message=str(exc),
                details={},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, content=payload.model_dump(mode="json")
        )

    @app.exception_handler(IdempotencyConflictError)
    async def idempotency_conflict_handler(
        request: Request, exc: IdempotencyConflictError
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="IDEMPOTENCY_CONFLICT",
                message=str(exc),
                details={},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content=payload.model_dump(mode="json")
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        request_id = _get_request_id(request)
        payload = ErrorResponse(
            error=ErrorDetail(
                code="INVALID_ARGUMENT",
                message=str(exc),
                details={},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content=payload.model_dump(mode="json")
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.error(
            "unhandled_server_exception", error=str(exc), path=request.url.path, exc_info=True
        )
        payload = ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An unexpected server error occurred. Please contact support with the request ID.",
                details={"error_type": type(exc).__name__},
                request_id=request_id,
                timestamp=datetime.now(UTC),
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload.model_dump(mode="json"),
        )

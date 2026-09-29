import contextvars
import logging
import sys
from typing import Any, cast

import structlog

from src.core.config import get_settings
from src.observability.redaction import sanitize_data

ctx_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_request_id", default=None
)
ctx_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_trace_id", default=None
)
ctx_task_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_task_id", default=None
)
ctx_attempt_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_attempt_id", default=None
)
ctx_queue: contextvars.ContextVar[str | None] = contextvars.ContextVar("ctx_queue", default=None)
ctx_worker_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ctx_worker_id", default=None
)


def context_injector(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    req_id = ctx_request_id.get()
    tr_id = ctx_trace_id.get()
    t_id = ctx_task_id.get()
    att_id = ctx_attempt_id.get()
    q = ctx_queue.get()
    w_id = ctx_worker_id.get()

    if req_id is not None and "request_id" not in event_dict:
        event_dict["request_id"] = req_id
    if tr_id is not None and "trace_id" not in event_dict:
        event_dict["trace_id"] = tr_id
    if t_id is not None and "task_id" not in event_dict:
        event_dict["task_id"] = t_id
    if att_id is not None and "attempt_id" not in event_dict:
        event_dict["attempt_id"] = att_id
    if q is not None and "queue" not in event_dict:
        event_dict["queue"] = q
    if w_id is not None and "worker_id" not in event_dict:
        event_dict["worker_id"] = w_id

    return event_dict


def secret_redactor(_logger: Any, _method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    sanitized = sanitize_data(event_dict)
    if isinstance(sanitized, dict):
        return cast(dict[str, Any], sanitized)
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        context_injector,
        secret_redactor,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

_context_logger = structlog.get_logger("task_engine.context")


@dataclass
class TaskContext:
    task_id: str
    idempotency_key: str | None = None
    attempt: int = 1
    queue: str = "default"
    priority: int = 5
    headers: dict[str, str] = field(default_factory=dict)
    tenant_id: str = "default"
    created_at: datetime | str | None = None
    logger: Any = None

    def __post_init__(self) -> None:
        if self.logger is None:
            self.logger = _context_logger.bind(
                task_id=self.task_id,
                tenant_id=self.tenant_id,
                queue=self.queue,
                attempt=self.attempt,
            )


_current_task_context: ContextVar[TaskContext | None] = ContextVar(
    "_current_task_context", default=None
)


def get_current_context() -> TaskContext | None:
    return _current_task_context.get()


def set_current_context(ctx: TaskContext | None) -> Token[TaskContext | None]:
    return _current_task_context.set(ctx)

import asyncio
import time
from typing import Any

import structlog

from src.domain.task_registry import TaskRegistry, global_task_registry

logger = structlog.get_logger(__name__)


class TaskExecutionResult:
    def __init__(
        self,
        success: bool,
        result: Any = None,
        error_class: str | None = None,
        error_message: str | None = None,
        duration_seconds: float = 0.0,
    ) -> None:
        self.success = success
        self.result = result
        self.error_class = error_class
        self.error_message = error_message
        self.duration_seconds = duration_seconds


class TaskExecutor:
    def __init__(self, registry: TaskRegistry | None = None) -> None:
        self.registry = registry or global_task_registry

    async def execute(
        self, task_type: str, payload: dict[str, Any] | None, timeout_seconds: int = 300
    ) -> TaskExecutionResult:
        start_time = time.perf_counter()
        try:
            task_def = self.registry.get_or_raise(task_type)
        except ValueError as exc:
            duration = time.perf_counter() - start_time
            return TaskExecutionResult(
                success=False,
                error_class="UnregisteredTaskError",
                error_message=str(exc),
                duration_seconds=duration,
            )
        kwargs = payload or {}
        try:
            if task_def.is_async:
                result = await asyncio.wait_for(
                    task_def.handler(**kwargs), timeout=float(timeout_seconds)
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(task_def.handler, **kwargs), timeout=float(timeout_seconds)
                )
            duration = time.perf_counter() - start_time
            return TaskExecutionResult(success=True, result=result, duration_seconds=duration)
        except TimeoutError:
            duration = time.perf_counter() - start_time
            logger.error("Task execution timed out", task_type=task_type, timeout=timeout_seconds)
            return TaskExecutionResult(
                success=False,
                error_class="TaskTimeoutError",
                error_message=f"Task exceeded timeout limit of {timeout_seconds}s",
                duration_seconds=duration,
            )
        except Exception as exc:
            duration = time.perf_counter() - start_time
            error_class = exc.__class__.__name__
            error_message = str(exc)
            logger.error(
                "Task execution failed with exception", task_type=task_type, error=error_message
            )
            return TaskExecutionResult(
                success=False,
                error_class=error_class,
                error_message=error_message,
                duration_seconds=duration,
            )

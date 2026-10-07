import asyncio
import inspect
import time
from typing import Any

import structlog
from task_engine.context import TaskContext, set_current_context

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

    def _prepare_call(
        self, handler: Any, payload: dict[str, Any] | None, context: TaskContext | None
    ) -> tuple[list[Any], dict[str, Any]]:
        sig = inspect.signature(handler)
        params = list(sig.parameters.values())
        data = payload or {}

        def _is_ctx(param: inspect.Parameter) -> bool:
            return (
                param.name in {"context", "ctx"}
                or getattr(param.annotation, "__name__", "") == "TaskContext"
                or str(param.annotation).endswith("TaskContext")
            )

        if len(params) == 2 and any(_is_ctx(p) for p in params):
            if _is_ctx(params[0]):
                return [context, data], {}
            return [data, context], {}

        if "args" in data and isinstance(data["args"], list | tuple):
            pos_args = list(data["args"])
            kw_args = dict(data.get("kwargs", {}))
            if any(_is_ctx(p) for p in params):
                kw_args["context"] = context
            return pos_args, kw_args

        kwargs = dict(data)
        if any(_is_ctx(p) for p in params) and "context" not in kwargs and "ctx" not in kwargs:
            for p in params:
                if _is_ctx(p):
                    kwargs[p.name] = context
                    break

        if len(params) == 1 and params[0].kind not in (
            inspect.Parameter.VAR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        ):
            param_name = params[0].name
            if param_name not in kwargs:
                return [data], {}

        return [], kwargs

    async def execute(
        self,
        task_type: str,
        payload: dict[str, Any] | None,
        timeout_seconds: int = 300,
        context: TaskContext | None = None,
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

        set_current_context(context)
        try:
            args, kwargs = self._prepare_call(task_def.handler, payload, context)
            if task_def.is_async:
                result = await asyncio.wait_for(
                    task_def.handler(*args, **kwargs), timeout=float(timeout_seconds)
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(task_def.handler, *args, **kwargs),
                    timeout=float(timeout_seconds),
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
        finally:
            set_current_context(None)

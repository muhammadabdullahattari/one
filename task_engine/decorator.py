from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.domain.task_registry import global_task_registry

if TYPE_CHECKING:
    from task_engine.client import TaskEngineClient
    from task_engine.result import AsyncResult


class TaskWrapper:
    def __init__(
        self,
        fn: Callable[..., Any],
        name: str,
        queue: str = "default",
        priority: int = 5,
        max_attempts: int = 3,
        timeout_seconds: int = 300,
        description: str = "",
        client: TaskEngineClient | None = None,
    ) -> None:
        self.fn = fn
        self.name = name
        self.queue = queue
        self.priority = priority
        self.max_attempts = max_attempts
        self.max_retries = max_attempts
        self.timeout_seconds = timeout_seconds
        self.description = description
        self.is_async = inspect.iscoroutinefunction(fn)
        self.client = client
        functools.update_wrapper(self, fn)

    def bind(self, client: TaskEngineClient) -> TaskWrapper:
        self.client = client
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    def _format_payload(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if len(args) == 1 and not kwargs and isinstance(args[0], dict):
            return args[0]
        if args and kwargs:
            return {"args": list(args), "kwargs": kwargs}
        if args:
            return {"args": list(args)}
        return kwargs

    def delay(self, *args: Any, **kwargs: Any) -> AsyncResult:
        payload = self._format_payload(*args, **kwargs)
        return self.apply_async(kwargs=payload)

    def apply_async(
        self,
        args: list[Any] | tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
        queue: str | None = None,
        priority: int | None = None,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> AsyncResult:
        from task_engine.client import TaskEngineClient

        active_client = self.client or TaskEngineClient.get_default()

        payload: dict[str, Any] = {}
        if args is not None and kwargs is not None:
            payload = {"args": list(args), "kwargs": kwargs}
        elif args is not None:
            payload = {"args": list(args)}
        elif kwargs is not None:
            payload = kwargs

        return active_client.submit(
            task_type=self.name,
            payload=payload,
            queue=queue or self.queue,
            priority=priority if priority is not None else self.priority,
            max_attempts=max_attempts if max_attempts is not None else self.max_attempts,
            timeout_seconds=timeout_seconds
            if timeout_seconds is not None
            else self.timeout_seconds,
            delay_seconds=delay_seconds,
            idempotency_key=idempotency_key,
            headers=headers,
        )


def task(
    fn: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    queue: str = "default",
    priority: int = 5,
    max_attempts: int | None = None,
    max_retries: int | None = None,
    timeout_seconds: int = 300,
    description: str = "",
    client: TaskEngineClient | None = None,
) -> Any:
    eff_attempts = max_attempts if max_attempts is not None else (max_retries or 3)

    def decorator(target_fn: Callable[..., Any]) -> TaskWrapper:
        task_name = name or target_fn.__name__
        wrapper = TaskWrapper(
            fn=target_fn,
            name=task_name,
            queue=queue,
            priority=priority,
            max_attempts=eff_attempts,
            timeout_seconds=timeout_seconds,
            description=description,
            client=client,
        )

        global_task_registry.register(
            name=task_name,
            handler=target_fn,
            queue=queue,
            priority=priority,
            max_retries=eff_attempts,
            timeout_seconds=timeout_seconds,
            description=description,
            is_async=inspect.iscoroutinefunction(target_fn),
        )

        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator

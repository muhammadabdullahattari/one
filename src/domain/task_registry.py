from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TaskDefinition:
    name: str
    handler: Callable[..., Any]
    queue: str = "default"
    priority: int = 5
    max_retries: int = 3
    timeout_seconds: int = 300
    description: str = ""
    is_async: bool = True


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskDefinition] = {}

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        queue: str = "default",
        priority: int = 5,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        description: str = "",
        is_async: bool = True,
    ) -> TaskDefinition:
        if not name or not isinstance(name, str):
            raise ValueError("Task name must be a non-empty string.")
        if not callable(handler):
            raise ValueError(f"Task handler for '{name}' must be a callable.")
        task_def = TaskDefinition(
            name=name,
            handler=handler,
            queue=queue,
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            description=description,
            is_async=is_async,
        )
        self._tasks[name] = task_def
        return task_def

    def task(
        self,
        name: str | None = None,
        queue: str = "default",
        priority: int = 5,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        description: str = "",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            task_name = name or fn.__name__
            import inspect

            is_async = inspect.iscoroutinefunction(fn)
            self.register(
                name=task_name,
                handler=fn,
                queue=queue,
                priority=priority,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
                description=description,
                is_async=is_async,
            )
            return fn

        return decorator

    def get(self, task_type: str) -> TaskDefinition | None:
        return self._tasks.get(task_type)

    def get_or_raise(self, task_type: str) -> TaskDefinition:
        task_def = self.get(task_type)
        if task_def is None:
            raise ValueError(
                f"Unregistered task_type '{task_type}'. Workers only execute registered task types (SRS §15.2)."
            )
        return task_def

    def list_tasks(self) -> list[TaskDefinition]:
        return list(self._tasks.values())

    def clear(self) -> None:
        self._tasks.clear()


global_task_registry = TaskRegistry()

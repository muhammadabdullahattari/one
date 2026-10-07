from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from task_engine.client import TaskEngineClient
from task_engine.decorator import TaskWrapper, task
from task_engine.result import AsyncResult
from task_engine.worker import TaskEngineWorker


class TaskEngine:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        tenant_id: str | None = None,
        timeout: float = 30.0,
        direct_mode: bool = False,
    ) -> None:
        self.client = TaskEngineClient(
            base_url=base_url,
            api_key=api_key,
            tenant_id=tenant_id,
            timeout=timeout,
            direct_mode=direct_mode,
        )
        TaskEngineClient.set_default(self.client)

    @classmethod
    def from_env(cls, env_file: str | Path | None = None, direct_mode: bool = False) -> TaskEngine:
        if env_file:
            path = Path(env_file)
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip())

        return cls(
            base_url=os.getenv("TASK_ENGINE_API_URL") or os.getenv("API_URL"),
            api_key=os.getenv("TASK_ENGINE_API_KEY") or os.getenv("API_KEY"),
            tenant_id=os.getenv("TASK_ENGINE_TENANT_ID") or "default",
            direct_mode=direct_mode,
        )

    def task(
        self,
        name: str | None = None,
        queue: str = "default",
        priority: int = 5,
        max_attempts: int | None = None,
        max_retries: int | None = None,
        timeout_seconds: int = 300,
        description: str = "",
    ) -> Callable[[Callable[..., Any]], TaskWrapper]:
        def decorator(fn: Callable[..., Any]) -> TaskWrapper:
            wrapper = task(
                fn,
                name=name,
                queue=queue,
                priority=priority,
                max_attempts=max_attempts,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
                description=description,
                client=self.client,
            )
            return cast(TaskWrapper, wrapper)

        return decorator

    def _resolve_task_submission(
        self,
        task_or_name: str | Callable[..., Any] | TaskWrapper,
        payload: dict[str, Any] | None = None,
        queue: str | None = None,
        priority: int | None = None,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        **kwargs: Any,
    ) -> tuple[str, dict[str, Any], str, int, int | None, int | None]:
        task_name: str
        eff_queue = queue or "default"
        eff_priority = priority if priority is not None else 5
        eff_attempts = max_attempts
        eff_timeout = timeout_seconds

        if isinstance(task_or_name, TaskWrapper):
            task_name = task_or_name.name
            eff_queue = queue or task_or_name.queue
            eff_priority = priority if priority is not None else task_or_name.priority
            eff_attempts = max_attempts if max_attempts is not None else task_or_name.max_attempts
            eff_timeout = (
                timeout_seconds if timeout_seconds is not None else task_or_name.timeout_seconds
            )
        elif callable(task_or_name):
            task_name = getattr(task_or_name, "__name__", str(task_or_name))
        else:
            task_name = str(task_or_name)

        combined_payload: dict[str, Any] = {}
        if payload is not None:
            combined_payload.update(payload)
        if kwargs:
            combined_payload.update(kwargs)

        return task_name, combined_payload, eff_queue, eff_priority, eff_attempts, eff_timeout

    def submit(
        self,
        task_or_name: str | Callable[..., Any] | TaskWrapper,
        payload: dict[str, Any] | None = None,
        queue: str | None = None,
        priority: int | None = None,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        tenant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncResult:
        task_name, combined_payload, eff_queue, eff_priority, eff_attempts, eff_timeout = (
            self._resolve_task_submission(
                task_or_name,
                payload=payload,
                queue=queue,
                priority=priority,
                max_attempts=max_attempts,
                timeout_seconds=timeout_seconds,
                **kwargs,
            )
        )
        return self.client.submit(
            task_type=task_name,
            payload=combined_payload,
            queue=eff_queue,
            priority=eff_priority,
            max_attempts=eff_attempts,
            timeout_seconds=eff_timeout,
            delay_seconds=delay_seconds,
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            metadata=metadata,
        )

    async def submit_async(
        self,
        task_or_name: str | Callable[..., Any] | TaskWrapper,
        payload: dict[str, Any] | None = None,
        queue: str | None = None,
        priority: int | None = None,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        tenant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> AsyncResult:
        task_name, combined_payload, eff_queue, eff_priority, eff_attempts, eff_timeout = (
            self._resolve_task_submission(
                task_or_name,
                payload=payload,
                queue=queue,
                priority=priority,
                max_attempts=max_attempts,
                timeout_seconds=timeout_seconds,
                **kwargs,
            )
        )
        return await self.client.submit_async(
            task_type=task_name,
            payload=combined_payload,
            queue=eff_queue,
            priority=eff_priority,
            max_attempts=eff_attempts,
            timeout_seconds=eff_timeout,
            delay_seconds=delay_seconds,
            idempotency_key=idempotency_key,
            tenant_id=tenant_id,
            metadata=metadata,
        )

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self.client.get_task(task_id)

    async def get_task_async(self, task_id: str) -> dict[str, Any]:
        return await self.client.get_task_async(task_id)

    def get_result(self, task_id: str) -> dict[str, Any]:
        return self.client.get_result(task_id)

    async def get_result_async(self, task_id: str) -> dict[str, Any]:
        return await self.client.get_result_async(task_id)

    def cancel_task(
        self, task_id: str, reason: str = "User requested cancellation"
    ) -> dict[str, Any]:
        return self.client.cancel_task(task_id, reason=reason)

    async def cancel_task_async(
        self, task_id: str, reason: str = "User requested cancellation"
    ) -> dict[str, Any]:
        return await self.client.cancel_task_async(task_id, reason=reason)

    def register_schedule(
        self,
        name: str,
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        task_type: str | None = None,
        payload: dict[str, Any] | None = None,
        queue: str = "default",
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        return self.client.register_schedule(
            name=name,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            task_type=task_type,
            payload=payload,
            queue=queue,
            timezone=timezone,
        )

    async def register_schedule_async(
        self,
        name: str,
        cron_expression: str | None = None,
        interval_seconds: int | None = None,
        task_type: str | None = None,
        payload: dict[str, Any] | None = None,
        queue: str = "default",
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        return await self.client.register_schedule_async(
            name=name,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            task_type=task_type,
            payload=payload,
            queue=queue,
            timezone=timezone,
        )

    def worker(
        self,
        app: str | Any | None = None,
        queues: list[str] | None = None,
        concurrency: int | None = None,
        worker_id: str | None = None,
        broker_type: str = "native",
    ) -> TaskEngineWorker:
        return TaskEngineWorker(
            app=app,
            queues=queues,
            concurrency=concurrency,
            worker_id=worker_id,
            tenant_id=self.client.tenant_id,
            broker_type=broker_type,
        )

    def __enter__(self) -> TaskEngine:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.client.close()

    async def __aenter__(self) -> TaskEngine:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.client.close_async()

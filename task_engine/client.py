from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import UUID

import httpx

from task_engine.exceptions import (
    AuthenticationError,
    ConnectionError,
    TaskEngineError,
    TaskNotFoundError,
)
from task_engine.result import AsyncResult


class TaskEngineClient:
    _default_client: TaskEngineClient | None = None

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        tenant_id: str | None = None,
        timeout: float = 30.0,
        direct_mode: bool = False,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("TASK_ENGINE_API_URL")
            or os.getenv("API_URL")
            or "http://localhost:8000"
        ).rstrip("/")
        self.api_key = api_key or os.getenv("TASK_ENGINE_API_KEY") or os.getenv("API_KEY")
        self.tenant_id = tenant_id or os.getenv("TASK_ENGINE_TENANT_ID") or "default"
        self.timeout = timeout
        self.direct_mode = direct_mode

        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

        if TaskEngineClient._default_client is None:
            TaskEngineClient._default_client = self

    @classmethod
    def get_default(cls) -> TaskEngineClient:
        if cls._default_client is None:
            cls._default_client = cls()
        return cls._default_client

    @classmethod
    def set_default(cls, client: TaskEngineClient) -> None:
        cls._default_client = client

    def _get_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Tenant-Id": self.tenant_id,
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_sync_client(self) -> httpx.Client:
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._sync_client

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._async_client

    def is_terminal_status(self, status: str) -> bool:
        return status.upper() in {"SUCCEEDED", "FAILED", "CANCELLED", "DEAD_LETTERED"}

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code in {200, 201, 202}:
            return response.json()
        if response.status_code == 401:
            raise AuthenticationError(f"Authentication failed: {response.text}")
        if response.status_code == 404:
            raise TaskNotFoundError("Requested resource not found")
        raise TaskEngineError(
            f"API request failed with status {response.status_code}: {response.text}"
        )

    def submit(
        self,
        task_type: str,
        payload: dict[str, Any] | None = None,
        queue: str = "default",
        priority: int = 5,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        tenant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> AsyncResult:
        if self.direct_mode:
            return self._submit_direct(
                task_type=task_type,
                payload=payload,
                queue=queue,
                priority=priority,
                max_attempts=max_attempts,
                timeout_seconds=timeout_seconds,
                delay_seconds=delay_seconds,
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                metadata=metadata,
            )

        client = self._get_sync_client()
        body: dict[str, Any] = {
            "task_type": task_type,
            "payload": payload or {},
            "queue": queue,
            "priority": priority,
            "tenant_id": tenant_id or self.tenant_id,
        }
        if max_attempts is not None:
            body["max_attempts"] = max_attempts
        if timeout_seconds is not None:
            body["timeout_seconds"] = timeout_seconds
        if delay_seconds is not None:
            body["delay_seconds"] = delay_seconds
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key
        if metadata is not None:
            body["metadata"] = metadata

        try:
            resp = client.post("/api/v1/tasks", json=body)
            data = self._handle_response(resp)
            return AsyncResult(task_id=str(data["task_id"]), client=self, initial_data=data)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ConnectionError(
                f"Could not connect to Task Engine API at {self.base_url}: {exc}"
            ) from exc

    async def submit_async(
        self,
        task_type: str,
        payload: dict[str, Any] | None = None,
        queue: str = "default",
        priority: int = 5,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        tenant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> AsyncResult:
        if self.direct_mode:
            return await self._submit_direct_async(
                task_type=task_type,
                payload=payload,
                queue=queue,
                priority=priority,
                max_attempts=max_attempts,
                timeout_seconds=timeout_seconds,
                delay_seconds=delay_seconds,
                idempotency_key=idempotency_key,
                tenant_id=tenant_id,
                metadata=metadata,
            )

        client = self._get_async_client()
        body: dict[str, Any] = {
            "task_type": task_type,
            "payload": payload or {},
            "queue": queue,
            "priority": priority,
            "tenant_id": tenant_id or self.tenant_id,
        }
        if max_attempts is not None:
            body["max_attempts"] = max_attempts
        if timeout_seconds is not None:
            body["timeout_seconds"] = timeout_seconds
        if delay_seconds is not None:
            body["delay_seconds"] = delay_seconds
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key
        if metadata is not None:
            body["metadata"] = metadata

        try:
            resp = await client.post("/api/v1/tasks", json=body)
            data = self._handle_response(resp)
            return AsyncResult(task_id=str(data["task_id"]), client=self, initial_data=data)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise ConnectionError(
                f"Could not connect to Task Engine API at {self.base_url}: {exc}"
            ) from exc

    def _submit_direct(
        self,
        task_type: str,
        payload: dict[str, Any] | None = None,
        queue: str = "default",
        priority: int = 5,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        tenant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncResult:
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                asyncio.run,
                self._submit_direct_async(
                    task_type=task_type,
                    payload=payload,
                    queue=queue,
                    priority=priority,
                    max_attempts=max_attempts,
                    timeout_seconds=timeout_seconds,
                    delay_seconds=delay_seconds,
                    idempotency_key=idempotency_key,
                    tenant_id=tenant_id,
                    metadata=metadata,
                ),
            )
            return future.result()

    async def _submit_direct_async(
        self,
        task_type: str,
        payload: dict[str, Any] | None = None,
        queue: str = "default",
        priority: int = 5,
        max_attempts: int | None = None,
        timeout_seconds: int | None = None,
        delay_seconds: int | None = None,
        idempotency_key: str | None = None,
        tenant_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncResult:
        from src.application.task_service import TaskService
        from src.persistence.repositories.idempotency_repository import IdempotencyRepository
        from src.persistence.repositories.outbox_repository import OutboxRepository
        from src.persistence.repositories.queue_repository import QueueRepository
        from src.persistence.repositories.task_repository import TaskRepository
        from src.persistence.session import session_scope
        from src.rate_limit.limiter import RedisTokenBucketRateLimiter

        async with session_scope() as session:
            service = TaskService(
                task_repo=TaskRepository(session),
                outbox_repo=OutboxRepository(session),
                idempotency_repo=IdempotencyRepository(session),
                rate_limiter=RedisTokenBucketRateLimiter(redis=None),
                queue_repo=QueueRepository(session),
            )
            task_entity = await service.submit_task(
                task_type=task_type,
                payload=payload or {},
                queue=queue,
                priority=priority,
                max_attempts=max_attempts or 3,
                timeout_seconds=timeout_seconds or 300,
                idempotency_key=idempotency_key,
                delay_seconds=delay_seconds,
                tenant_id=tenant_id or self.tenant_id,
                metadata=metadata,
            )
            return AsyncResult(
                task_id=str(task_entity.task_id),
                client=self,
                initial_data={
                    "task_id": str(task_entity.task_id),
                    "task_type": task_entity.task_type,
                    "queue": task_entity.queue,
                    "priority": task_entity.priority,
                    "status": task_entity.status.value,
                    "payload": task_entity.payload,
                    "tenant_id": task_entity.tenant_id,
                },
            )

    def get_task(self, task_id: str) -> dict[str, Any]:
        if self.direct_mode:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, self.get_task_async(task_id))
                return future.result()
        client = self._get_sync_client()
        resp = client.get(f"/api/v1/tasks/{task_id}")
        return self._handle_response(resp)

    async def get_task_async(self, task_id: str) -> dict[str, Any]:
        if self.direct_mode:
            from src.persistence.repositories.task_repository import TaskRepository
            from src.persistence.session import session_scope

            async with session_scope() as session:
                repo = TaskRepository(session)
                entity = await repo.get_task(UUID(task_id))
                if entity is None:
                    raise TaskNotFoundError(task_id)
                return {
                    "task_id": str(entity.task_id),
                    "task_type": entity.task_type,
                    "queue": entity.queue,
                    "priority": entity.priority,
                    "status": entity.status.value,
                    "attempt_count": entity.attempt_count,
                    "max_attempts": entity.max_attempts,
                    "timeout_seconds": entity.timeout_seconds,
                    "tenant_id": entity.tenant_id,
                    "payload": entity.payload,
                    "result": entity.result,
                    "error": entity.status_reason,
                    "error_message": entity.status_reason,
                    "created_at": entity.created_at.isoformat() if entity.created_at else None,
                    "started_at": entity.started_at.isoformat() if entity.started_at else None,
                    "finished_at": entity.finished_at.isoformat() if entity.finished_at else None,
                }
        client = self._get_async_client()
        resp = await client.get(f"/api/v1/tasks/{task_id}")
        return self._handle_response(resp)

    def get_result(self, task_id: str) -> dict[str, Any]:
        task_data = self.get_task(task_id)
        return {
            "task_id": task_id,
            "status": task_data.get("status"),
            "result_data": task_data.get("result"),
            "error_message": task_data.get("error_message") or task_data.get("error"),
        }

    async def get_result_async(self, task_id: str) -> dict[str, Any]:
        task_data = await self.get_task_async(task_id)
        return {
            "task_id": task_id,
            "status": task_data.get("status"),
            "result_data": task_data.get("result"),
            "error_message": task_data.get("error_message") or task_data.get("error"),
        }

    def cancel_task(
        self, task_id: str, reason: str = "User requested cancellation"
    ) -> dict[str, Any]:
        client = self._get_sync_client()
        resp = client.delete(f"/api/v1/tasks/{task_id}", params={"reason": reason})
        return self._handle_response(resp)

    async def cancel_task_async(
        self, task_id: str, reason: str = "User requested cancellation"
    ) -> dict[str, Any]:
        client = self._get_async_client()
        resp = await client.delete(f"/api/v1/tasks/{task_id}", params={"reason": reason})
        return self._handle_response(resp)

    def retry_task(
        self, task_id: str, delay_seconds: int = 0, reset_attempts: bool = False
    ) -> dict[str, Any]:
        client = self._get_sync_client()
        resp = client.post(
            f"/api/v1/tasks/{task_id}/retry",
            json={"delay_seconds": delay_seconds, "reset_attempts": reset_attempts},
        )
        return self._handle_response(resp)

    async def retry_task_async(
        self, task_id: str, delay_seconds: int = 0, reset_attempts: bool = False
    ) -> dict[str, Any]:
        client = self._get_async_client()
        resp = await client.post(
            f"/api/v1/tasks/{task_id}/retry",
            json={"delay_seconds": delay_seconds, "reset_attempts": reset_attempts},
        )
        return self._handle_response(resp)

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
        client = self._get_sync_client()
        body: dict[str, Any] = {
            "task_type": task_type or name,
            "queue": queue,
            "payload": payload or {},
            "timezone": timezone,
            "tenant_id": self.tenant_id,
        }
        if cron_expression:
            body["cron"] = cron_expression
        elif interval_seconds:
            body["interval_seconds"] = interval_seconds
        resp = client.post("/api/v1/schedules", json=body)
        return self._handle_response(resp)

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
        client = self._get_async_client()
        body: dict[str, Any] = {
            "task_type": task_type or name,
            "queue": queue,
            "payload": payload or {},
            "timezone": timezone,
            "tenant_id": self.tenant_id,
        }
        if cron_expression:
            body["cron"] = cron_expression
        elif interval_seconds:
            body["interval_seconds"] = interval_seconds
        resp = await client.post("/api/v1/schedules", json=body)
        return self._handle_response(resp)

    def list_tasks(
        self,
        queue: str | None = None,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        client = self._get_sync_client()
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if queue:
            params["queue"] = queue
        if status:
            params["status"] = status
        if task_type:
            params["task_type"] = task_type
        resp = client.get("/api/v1/tasks", params=params)
        data = self._handle_response(resp)
        return data.get("items", [])

    async def list_tasks_async(
        self,
        queue: str | None = None,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        client = self._get_async_client()
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if queue:
            params["queue"] = queue
        if status:
            params["status"] = status
        if task_type:
            params["task_type"] = task_type
        resp = await client.get("/api/v1/tasks", params=params)
        data = self._handle_response(resp)
        return data.get("items", [])

    def list_queues(self) -> list[dict[str, Any]]:
        client = self._get_sync_client()
        resp = client.get("/api/v1/queues")
        return self._handle_response(resp)

    async def list_queues_async(self) -> list[dict[str, Any]]:
        client = self._get_async_client()
        resp = await client.get("/api/v1/queues")
        return self._handle_response(resp)

    def list_workers(self) -> list[dict[str, Any]]:
        client = self._get_sync_client()
        resp = client.get("/api/v1/workers")
        return self._handle_response(resp)

    async def list_workers_async(self) -> list[dict[str, Any]]:
        client = self._get_async_client()
        resp = await client.get("/api/v1/workers")
        return self._handle_response(resp)

    def ping(self) -> bool:
        try:
            client = self._get_sync_client()
            resp = client.get("/health/live")
            return resp.status_code == 200
        except Exception:
            return False

    async def ping_async(self) -> bool:
        try:
            client = self._get_async_client()
            resp = await client.get("/health/live")
            return resp.status_code == 200
        except Exception:
            return False

    def health(self) -> dict[str, Any]:
        client = self._get_sync_client()
        resp = client.get("/health/ready")
        return self._handle_response(resp)

    async def health_async(self) -> dict[str, Any]:
        client = self._get_async_client()
        resp = await client.get("/health/ready")
        return self._handle_response(resp)

    def close(self) -> None:
        if self._sync_client and not self._sync_client.is_closed:
            self._sync_client.close()

    async def close_async(self) -> None:
        if self._async_client and not self._async_client.is_closed:
            await self._async_client.aclose()

    def __enter__(self) -> TaskEngineClient:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    async def __aenter__(self) -> TaskEngineClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close_async()

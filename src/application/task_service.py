import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog

from src.core.config import get_settings
from src.core.constants import DEFAULT_QUEUE_NAME, TaskStatus
from src.domain.entities import IdempotencyKey, Task, TaskOutbox
from src.domain.exceptions import TaskNotFoundError
from src.domain.task_registry import global_task_registry
from src.persistence.models.task import TaskModel
from src.persistence.repositories.idempotency_repository import IdempotencyRepository
from src.persistence.repositories.outbox_repository import OutboxRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.result_backend import ResultBackend
from src.persistence.session import session_scope
from src.rate_limit.limiter import TokenBucketRateLimiter

logger = structlog.get_logger(__name__)


class TaskLifecycleService:
    def __init__(
        self,
        task_repo: TaskRepository | None = None,
        outbox_repo: OutboxRepository | None = None,
        idempotency_repo: IdempotencyRepository | None = None,
        rate_limiter: TokenBucketRateLimiter | None = None,
        result_backend: ResultBackend | None = None,
    ) -> None:
        self.settings = get_settings()
        self._task_repo = task_repo
        self._outbox_repo = outbox_repo
        self._idempotency_repo = idempotency_repo
        self.rate_limiter = rate_limiter or TokenBucketRateLimiter()
        self.result_backend = result_backend or ResultBackend(self.settings.task_max_payload_bytes)

    async def submit_task(
        self,
        task_type: str,
        payload: dict[str, Any] | None = None,
        queue: str = DEFAULT_QUEUE_NAME,
        priority: int = 5,
        tenant_id: str | None = None,
        idempotency_key: str | None = None,
        timeout_seconds: int | None = None,
        max_attempts: int | None = None,
        delay_seconds: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        tenant = tenant_id or "default"
        task_def = global_task_registry.get(task_type)
        if task_def:
            priority = priority or task_def.priority
            timeout_seconds = timeout_seconds or task_def.timeout_seconds
            max_attempts = max_attempts or task_def.max_retries
            queue = queue or task_def.queue
        timeout_sec = timeout_seconds or self.settings.default_timeout_seconds
        max_att = max_attempts or self.settings.default_max_attempts
        rate_limit_key = f"{tenant}:{queue}"
        is_allowed = await self.rate_limiter.acquire(
            key=rate_limit_key, rate_limit_rps=self.settings.default_rate_limit_rps
        )
        if not is_allowed:
            raise PermissionError(
                f"Rate limit exceeded for tenant '{tenant}' on queue '{queue}' (SRS §14.3)."
            )
        inline_payload = payload
        payload_ref = None
        if payload is not None:
            serialized_payload = json.dumps(payload, default=str)
            payload_bytes = len(serialized_payload.encode("utf-8"))
            if payload_bytes > self.settings.task_max_payload_bytes:
                inline_payload = None
                _, payload_ref = await self.result_backend.store_result(uuid4(), payload)
        task_id = uuid4()
        now = datetime.now(UTC)
        scheduled_at = (
            now + timedelta(seconds=delay_seconds) if delay_seconds and delay_seconds > 0 else now
        )
        status = TaskStatus.SCHEDULED if delay_seconds and delay_seconds > 0 else TaskStatus.PENDING
        if idempotency_key:
            req_hash = hashlib.sha256(
                json.dumps(payload or {}, sort_keys=True).encode()
            ).hexdigest()
            if self._idempotency_repo and self._task_repo:
                existing = await self._idempotency_repo.get_key(
                    scope=tenant, idempotency_key=idempotency_key
                )
                if existing:
                    existing_task = await self._task_repo.get_by_id(existing.task_id)
                    if existing_task:
                        return existing_task
                await self._idempotency_repo.record_key(
                    IdempotencyKey(
                        scope=tenant,
                        idempotency_key=idempotency_key,
                        task_id=task_id,
                        request_hash=req_hash,
                        expires_at=now + timedelta(seconds=self.settings.lease_seconds * 10),
                    )
                )
            else:
                async with session_scope() as session:
                    idem_repo = IdempotencyRepository(session)
                    existing = await idem_repo.get_key(
                        scope=tenant, idempotency_key=idempotency_key
                    )
                    if existing:
                        task_repo = TaskRepository(session)
                        existing_task = await task_repo.get_by_id(existing.task_id)
                        if existing_task:
                            return existing_task
                    await idem_repo.record_key(
                        IdempotencyKey(
                            scope=tenant,
                            idempotency_key=idempotency_key,
                            task_id=task_id,
                            request_hash=req_hash,
                            expires_at=now + timedelta(seconds=self.settings.lease_seconds * 10),
                        )
                    )
        task = Task(
            task_id=task_id,
            tenant_id=tenant,
            task_type=task_type,
            queue=queue,
            status=status,
            priority=priority,
            payload=inline_payload,
            payload_ref=payload_ref,
            idempotency_key=idempotency_key,
            timeout_seconds=timeout_sec,
            max_attempts=max_att,
            created_at=now,
            scheduled_at=scheduled_at,
        )
        outbox = TaskOutbox(
            task_id=task_id,
            event_type="task.created",
            payload={"task_type": task_type, "queue": queue, "priority": priority},
            created_at=now,
        )
        if self._task_repo:
            await self._task_repo.create_with_outbox(task, outbox)
        else:
            async with session_scope() as session:
                task_repo = TaskRepository(session)
                await task_repo.create_with_outbox(task, outbox)
        logger.info("task_submitted", task_id=str(task.task_id), queue=queue, task_type=task_type)
        return task

    async def get_task(self, task_id: UUID) -> Task | None:
        if self._task_repo:
            return await self._task_repo.get_by_id(task_id)
        async with session_scope() as session:
            task_repo = TaskRepository(session)
            return await task_repo.get_by_id(task_id)

    async def cancel_task(self, task_id: UUID, reason: str = "Cancelled by user") -> Task:
        if self._task_repo:
            task = await self._task_repo.cancel_task(task_id, reason=reason)
        else:
            async with session_scope() as session:
                task_repo = TaskRepository(session)
                task = await task_repo.cancel_task(task_id, reason=reason)
        if not task:
            raise TaskNotFoundError(f"Task '{task_id}' not found.")
        return task

    async def retry_task(
        self, task_id: UUID, delay_seconds: int = 0, reset_attempts: bool = False
    ) -> Task:
        now = datetime.now(UTC)
        scheduled_at = now + timedelta(seconds=delay_seconds) if delay_seconds > 0 else now
        async with session_scope() as session:
            task_model = await session.get(TaskModel, task_id)
            if not task_model:
                raise TaskNotFoundError(f"Task '{task_id}' not found.")
            task_model.status = TaskStatus.QUEUED.value
            task_model.status_reason = "Manual operator retry"
            task_model.scheduled_at = scheduled_at
            if reset_attempts:
                task_model.attempt_count = 0
            task_model.updated_at = now
            task_model.version += 1
            task_repo = TaskRepository(session)
            task_entity = task_repo._to_entity(task_model)
        return task_entity


TaskService = TaskLifecycleService

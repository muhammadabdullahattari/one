from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from src.api.schemas.tasks import TaskEventsData
from src.core.constants import TaskEventType, TaskStatus
from src.domain.entities import Task, TaskAttempt, TaskOutbox
from src.persistence.models.outbox import TaskOutboxModel
from src.persistence.models.task import TaskModel
from src.persistence.models.task_attempt import TaskAttemptModel
from src.persistence.models.task_event import TaskEventModel
from src.persistence.repositories.base import BaseRepository


class TaskRepository(BaseRepository[TaskModel]):
    async def create_with_outbox(self, task: Task, outbox: TaskOutbox) -> Task:
        now = datetime.now(UTC)
        task_model = TaskModel(
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            task_type=task.task_type,
            queue=task.queue,
            status=task.status.value,
            priority=task.priority,
            payload=task.payload,
            payload_ref=task.payload_ref,
            result=task.result,
            result_ref=task.result_ref,
            schedule_id=task.schedule_id,
            idempotency_key=task.idempotency_key,
            timeout_seconds=task.timeout_seconds,
            max_attempts=task.max_attempts,
            attempt_count=task.attempt_count,
            current_worker_id=task.current_worker_id,
            lease_expires_at=task.lease_expires_at,
            scheduled_at=task.scheduled_at,
            started_at=task.started_at,
            finished_at=task.finished_at,
            status_reason=task.status_reason,
            version=task.version,
            created_at=task.created_at or now,
            updated_at=now,
        )
        outbox_model = TaskOutboxModel(
            outbox_id=outbox.outbox_id,
            task_id=outbox.task_id,
            event_type=outbox.event_type,
            payload=outbox.payload,
            created_at=outbox.created_at or now,
            attempts=0,
        )
        event_model = TaskEventModel(
            task_id=task.task_id,
            event_type=TaskEventType.TASK_CREATED.value,
            actor_type="producer",
            actor_id=task.tenant_id,
            event_time=now,
            metadata_json={
                "queue": task.queue,
                "task_type": task.task_type,
                "priority": task.priority,
            },
        )
        self.session.add(task_model)
        self.session.add(outbox_model)
        self.session.add(event_model)
        await self.session.flush()
        return task

    async def gettaskeventdata(self) -> TaskEventsData | None:
        query = select(TaskModel).limit(1)
        res = await self.session.execute(query)
        task = res.scalar_one_or_none()
        if task is None:
            return None
        return TaskEventsData(
            task_id=task.task_id,
            tenant_id=str(task.tenant_id),
            task_type=task.task_type,
            status=task.status,
        )

    async def get_by_id(self, task_id: UUID) -> Task | None:
        stmt = select(TaskModel).where(TaskModel.task_id == task_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def get_by_ids(self, task_ids: list[UUID]) -> dict[UUID, Task]:
        if not task_ids:
            return {}
        stmt = select(TaskModel).where(TaskModel.task_id.in_(task_ids))
        result = await self.session.execute(stmt)
        return {m.task_id: self._to_entity(m) for m in result.scalars().all()}

    async def claim_next(
        self, queue: str, worker_id: str, lease_seconds: int = 300
    ) -> tuple[Task, TaskAttempt] | None:
        now = datetime.now(UTC)
        lease_expires = now + timedelta(seconds=lease_seconds)
        stmt = (
            select(TaskModel)
            .where(
                TaskModel.queue == queue,
                TaskModel.status.in_([TaskStatus.QUEUED.value, TaskStatus.PENDING.value]),
            )
            .order_by(TaskModel.priority.asc(), TaskModel.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        task_model = result.scalar_one_or_none()
        if task_model is None:
            return None
        task_model.status = TaskStatus.RUNNING.value
        task_model.current_worker_id = worker_id
        task_model.lease_expires_at = lease_expires
        task_model.attempt_count += 1
        task_model.started_at = task_model.started_at or now
        task_model.updated_at = now
        task_model.version += 1
        attempt_model = TaskAttemptModel(
            task_id=task_model.task_id,
            worker_id=worker_id,
            attempt_number=task_model.attempt_count,
            status=TaskStatus.RUNNING.value,
            leased_at=now,
            lease_expires_at=lease_expires,
            started_at=now,
        )
        self.session.add(attempt_model)
        event_model = TaskEventModel(
            task_id=task_model.task_id,
            attempt_id=attempt_model.attempt_id,
            event_type=TaskEventType.TASK_STARTED.value,
            actor_type="worker",
            actor_id=worker_id,
            event_time=now,
            metadata_json={"attempt_number": task_model.attempt_count},
        )
        self.session.add(event_model)
        await self.session.flush()
        task_entity = self._to_entity(task_model)
        attempt_entity = TaskAttempt(
            attempt_id=attempt_model.attempt_id,
            task_id=attempt_model.task_id,
            worker_id=attempt_model.worker_id,
            attempt_number=attempt_model.attempt_number,
            status=TaskStatus.RUNNING,
            leased_at=attempt_model.leased_at,
            lease_expires_at=attempt_model.lease_expires_at,
            started_at=attempt_model.started_at,
        )
        return (task_entity, attempt_entity)

    async def complete_task(
        self,
        task_id: UUID,
        attempt_id: UUID | None,
        result_data: dict[str, Any] | None = None,
        result_ref: str | None = None,
    ) -> Task | None:
        now = datetime.now(UTC)
        stmt = select(TaskModel).where(TaskModel.task_id == task_id).with_for_update()
        res = await self.session.execute(stmt)
        task_model = res.scalar_one_or_none()
        if not task_model:
            return None
        task_model.status = TaskStatus.SUCCEEDED.value
        task_model.result = result_data
        task_model.result_ref = result_ref
        task_model.finished_at = now
        task_model.updated_at = now
        task_model.version += 1
        if attempt_id:
            att_stmt = (
                update(TaskAttemptModel)
                .where(TaskAttemptModel.attempt_id == attempt_id)
                .values(status=TaskStatus.SUCCEEDED.value, finished_at=now, result_ref=result_ref)
            )
            await self.session.execute(att_stmt)
        event = TaskEventModel(
            task_id=task_id,
            attempt_id=attempt_id,
            event_type=TaskEventType.TASK_SUCCEEDED.value,
            actor_type="worker",
            actor_id=task_model.current_worker_id or "worker",
            event_time=now,
        )
        self.session.add(event)
        await self.session.flush()
        return self._to_entity(task_model)

    async def fail_task(
        self,
        task_id: UUID,
        attempt_id: UUID | None,
        error_class: str,
        error_message_redacted: str,
        retryable: bool,
        next_retry_at: datetime | None = None,
    ) -> Task | None:
        now = datetime.now(UTC)
        stmt = select(TaskModel).where(TaskModel.task_id == task_id).with_for_update()
        res = await self.session.execute(stmt)
        task_model = res.scalar_one_or_none()
        if not task_model:
            return None
        new_status = (
            TaskStatus.RETRY_WAIT
            if retryable and task_model.attempt_count < task_model.max_attempts
            else TaskStatus.FAILED
        )
        task_model.status = new_status.value
        task_model.status_reason = f"{error_class}: {error_message_redacted[:200]}"
        task_model.scheduled_at = next_retry_at if new_status == TaskStatus.RETRY_WAIT else None
        task_model.finished_at = now if new_status != TaskStatus.RETRY_WAIT else None
        task_model.updated_at = now
        task_model.version += 1
        if attempt_id:
            att_stmt = (
                update(TaskAttemptModel)
                .where(TaskAttemptModel.attempt_id == attempt_id)
                .values(
                    status=TaskStatus.FAILED.value,
                    finished_at=now,
                    error_class=error_class,
                    error_message_redacted=error_message_redacted,
                )
            )
            await self.session.execute(att_stmt)
        event_type = (
            TaskEventType.TASK_RETRY_SCHEDULED.value
            if new_status == TaskStatus.RETRY_WAIT
            else TaskEventType.TASK_FAILED.value
        )
        event = TaskEventModel(
            task_id=task_id,
            attempt_id=attempt_id,
            event_type=event_type,
            actor_type="worker",
            actor_id=task_model.current_worker_id or "worker",
            event_time=now,
            metadata_json={"error_class": error_class, "retryable": retryable},
        )
        self.session.add(event)
        await self.session.flush()
        return self._to_entity(task_model)

    async def cancel_task(
        self, task_id: UUID, reason: str = "Cancelled by operator"
    ) -> Task | None:
        now = datetime.now(UTC)
        stmt = select(TaskModel).where(TaskModel.task_id == task_id).with_for_update()
        res = await self.session.execute(stmt)
        task_model = res.scalar_one_or_none()
        if not task_model:
            return None
        task_model.status = TaskStatus.CANCELLED.value
        task_model.status_reason = reason
        task_model.finished_at = now
        task_model.updated_at = now
        task_model.version += 1
        event = TaskEventModel(
            task_id=task_id,
            event_type=TaskEventType.TASK_CANCELLED.value,
            actor_type="operator",
            actor_id="api",
            event_time=now,
            metadata_json={"reason": reason},
        )
        self.session.add(event)
        await self.session.flush()
        return self._to_entity(task_model)

    async def get_expired_leases(self, cutoff_time: datetime, limit: int = 100) -> list[Task]:
        stmt = (
            select(TaskModel)
            .where(
                TaskModel.status == TaskStatus.RUNNING.value,
                TaskModel.lease_expires_at < cutoff_time,
            )
            .order_by(TaskModel.lease_expires_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [self._to_entity(m) for m in res.scalars().all()]

    async def get_stuck_pending(self, cutoff_time: datetime, limit: int = 100) -> list[Task]:
        stmt = (
            select(TaskModel)
            .where(TaskModel.status == TaskStatus.PENDING.value, TaskModel.created_at < cutoff_time)
            .order_by(TaskModel.created_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [self._to_entity(m) for m in res.scalars().all()]

    async def get_task(self, task_id: UUID) -> Task | None:
        return await self.get_by_id(task_id)

    async def count_tasks(
        self,
        queue: str | None = None,
        status: TaskStatus | None = None,
        task_type: str | None = None,
        tenant_id: str | None = None,
    ) -> int:
        from sqlalchemy import func

        stmt = select(func.count(TaskModel.task_id))
        if queue:
            stmt = stmt.where(TaskModel.queue == queue)
        if status:
            stmt = stmt.where(TaskModel.status == status.value)
        if task_type:
            stmt = stmt.where(TaskModel.task_type == task_type)
        if tenant_id:
            stmt = stmt.where(TaskModel.tenant_id == tenant_id)
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def list_tasks(
        self,
        queue: str | None = None,
        status: TaskStatus | None = None,
        task_type: str | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Task]:
        stmt = select(TaskModel)
        if queue:
            stmt = stmt.where(TaskModel.queue == queue)
        if status:
            stmt = stmt.where(TaskModel.status == status.value)
        if task_type:
            stmt = stmt.where(TaskModel.task_type == task_type)
        if tenant_id:
            stmt = stmt.where(TaskModel.tenant_id == tenant_id)
        stmt = stmt.order_by(TaskModel.created_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [self._to_entity(m) for m in res.scalars().all()]

    async def get_task_attempts(self, task_id: UUID) -> list[TaskAttempt]:
        stmt = (
            select(TaskAttemptModel)
            .where(TaskAttemptModel.task_id == task_id)
            .order_by(TaskAttemptModel.attempt_number.asc())
        )
        res = await self.session.execute(stmt)
        return [
            TaskAttempt(
                attempt_id=m.attempt_id,
                task_id=m.task_id,
                worker_id=m.worker_id,
                attempt_number=m.attempt_number,
                status=TaskStatus(m.status)
                if m.status in TaskStatus.__members__.values()
                else TaskStatus.RUNNING,
                leased_at=m.leased_at,
                lease_expires_at=m.lease_expires_at,
                started_at=m.started_at,
                finished_at=m.finished_at,
                error_class=m.error_class,
                error_message_redacted=m.error_message_redacted,
                result_ref=m.result_ref,
            )
            for m in res.scalars().all()
        ]

    async def get_task_events(self, task_id: UUID) -> list[Any]:
        stmt = (
            select(TaskEventModel)
            .where(TaskEventModel.task_id == task_id)
            .order_by(TaskEventModel.event_time.asc())
        )
        res = await self.session.execute(stmt)
        from src.domain.entities import TaskEvent

        return [
            TaskEvent(
                event_id=m.event_id,
                task_id=m.task_id,
                attempt_id=m.attempt_id,
                event_type=TaskEventType(m.event_type)
                if m.event_type in [e.value for e in TaskEventType]
                else TaskEventType.TASK_CREATED,
                actor_type=m.actor_type,
                actor_id=m.actor_id,
                event_time=m.event_time,
                metadata_json=m.metadata_json,
            )
            for m in res.scalars().all()
        ]

    def _to_entity(self, model: TaskModel) -> Task:
        return Task(
            task_id=model.task_id,
            tenant_id=model.tenant_id,
            task_type=model.task_type,
            queue=model.queue,
            status=TaskStatus(model.status),
            priority=model.priority,
            payload=model.payload,
            payload_ref=model.payload_ref,
            result=model.result,
            result_ref=model.result_ref,
            schedule_id=model.schedule_id,
            idempotency_key=model.idempotency_key,
            timeout_seconds=model.timeout_seconds,
            max_attempts=model.max_attempts,
            attempt_count=model.attempt_count,
            current_worker_id=model.current_worker_id,
            lease_expires_at=model.lease_expires_at,
            created_at=model.created_at,
            scheduled_at=model.scheduled_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
            status_reason=model.status_reason,
            version=model.version,
        )

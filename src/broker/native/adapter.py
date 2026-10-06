from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.core.adapter import BrokerAdapter
from src.broker.core.envelope import BrokerStats, TaskEnvelope, TaskMessage
from src.core.constants import TaskStatus
from src.domain.entities import DLQEntry
from src.persistence.models.task import TaskModel
from src.persistence.models.task_attempt import TaskAttemptModel
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope


class NativeBrokerAdapter(BrokerAdapter):
    @property
    def backend_name(self) -> str:
        return "native"

    async def publish(
        self, queue: str, envelope: TaskEnvelope, session: AsyncSession | None = None
    ) -> str:
        now = datetime.now(UTC)
        stmt = (
            update(TaskModel)
            .where(TaskModel.task_id == envelope.task_id)
            .values(
                status=TaskStatus.QUEUED.value,
                queue=queue,
                priority=envelope.priority,
                updated_at=now,
            )
        )
        if session is not None:
            await session.execute(stmt)
        else:
            async with session_scope() as sess:
                await sess.execute(stmt)
        return str(envelope.task_id)

    async def consume(
        self, queue: str, worker_id: str, batch_size: int = 1, tenant_id: str | None = None
    ) -> list[TaskMessage]:
        messages: list[TaskMessage] = []
        async with session_scope() as session:
            task_repo = TaskRepository(session)
            for _ in range(batch_size):
                claim_result = await task_repo.claim_next(
                    queue=queue, worker_id=worker_id, lease_seconds=300, tenant_id=tenant_id
                )
                if claim_result is None:
                    break
                task_entity, attempt_entity = claim_result
                envelope = TaskEnvelope(
                    task_id=task_entity.task_id,
                    tenant_id=task_entity.tenant_id,
                    task_type=task_entity.task_type,
                    queue=task_entity.queue,
                    priority=task_entity.priority,
                    payload=task_entity.payload,
                    payload_ref=task_entity.payload_ref,
                    timeout_seconds=task_entity.timeout_seconds,
                    max_attempts=task_entity.max_attempts,
                    attempt_count=task_entity.attempt_count,
                    created_at=task_entity.created_at,
                )
                message = TaskMessage(
                    message_id=str(task_entity.task_id),
                    queue=queue,
                    envelope=envelope,
                    delivery_count=task_entity.attempt_count,
                    published_at=task_entity.created_at,
                )
                messages.append(message)
        return messages

    async def acknowledge(self, queue: str, message_id: str) -> None:
        pass

    async def nack(self, queue: str, message_id: str, requeue: bool = True) -> None:
        task_uuid = UUID(message_id)
        now = datetime.now(UTC)
        new_status = TaskStatus.QUEUED.value if requeue else TaskStatus.FAILED.value
        async with session_scope() as session:
            stmt = (
                update(TaskModel)
                .where(TaskModel.task_id == task_uuid)
                .values(
                    status=new_status, current_worker_id=None, lease_expires_at=None, updated_at=now
                )
            )
            await session.execute(stmt)

    async def extend_lease(self, message_id: str, duration: int) -> None:
        task_uuid = UUID(message_id)
        now = datetime.now(UTC)
        new_lease = now + timedelta(seconds=duration)
        async with session_scope() as session:
            stmt = (
                update(TaskModel)
                .where(TaskModel.task_id == task_uuid, TaskModel.status == TaskStatus.RUNNING.value)
                .values(lease_expires_at=new_lease, updated_at=now)
            )
            await session.execute(stmt)
            att_stmt = (
                update(TaskAttemptModel)
                .where(
                    TaskAttemptModel.task_id == task_uuid,
                    TaskAttemptModel.status == TaskStatus.RUNNING.value,
                )
                .values(lease_expires_at=new_lease)
            )
            await session.execute(att_stmt)

    async def dead_letter(self, message_id: str, reason: str) -> None:
        task_uuid = UUID(message_id)
        now = datetime.now(UTC)
        async with session_scope() as session:
            stmt = (
                update(TaskModel)
                .where(TaskModel.task_id == task_uuid)
                .values(
                    status=TaskStatus.DEAD.value,
                    status_reason=reason[:500],
                    finished_at=now,
                    updated_at=now,
                )
                .returning(TaskModel.tenant_id)
            )
            res = await session.execute(stmt)
            task_tenant = res.scalar_one_or_none() or "default"
            dlq_repo = DLQRepository(session)
            await dlq_repo.create_entry(
                DLQEntry(
                    task_id=task_uuid,
                    tenant_id=task_tenant,
                    reason=reason,
                    error_class="DeadLetterException",
                    dead_at=now,
                )
            )

    async def stats(self, queue: str) -> BrokerStats:
        now = datetime.now(UTC)
        async with session_scope() as session:
            depth_stmt = select(func.count(TaskModel.task_id)).where(
                TaskModel.queue == queue,
                TaskModel.status.in_(
                    [TaskStatus.QUEUED.value, TaskStatus.PENDING.value, TaskStatus.RETRY_WAIT.value]
                ),
            )
            depth_res = await session.execute(depth_stmt)
            depth = int(depth_res.scalar_one() or 0)
            oldest_stmt = select(func.min(TaskModel.created_at)).where(
                TaskModel.queue == queue,
                TaskModel.status.in_([TaskStatus.QUEUED.value, TaskStatus.PENDING.value]),
            )
            oldest_res = await session.execute(oldest_stmt)
            oldest_created = oldest_res.scalar_one_or_none()
            oldest_age = 0.0
            if oldest_created:
                if oldest_created.tzinfo is None:
                    oldest_created = oldest_created.replace(tzinfo=UTC)
                oldest_age = max(0.0, (now - oldest_created).total_seconds())
            active_stmt = select(func.count(func.distinct(TaskModel.current_worker_id))).where(
                TaskModel.queue == queue,
                TaskModel.status == TaskStatus.RUNNING.value,
                TaskModel.lease_expires_at > now,
            )
            active_res = await session.execute(active_stmt)
            active_consumers = int(active_res.scalar_one() or 0)
        return BrokerStats(
            backend_name="native",
            queue=queue,
            depth=depth,
            active_consumers=active_consumers,
            oldest_task_age_seconds=oldest_age,
            is_healthy=True,
        )

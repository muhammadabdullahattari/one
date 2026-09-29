from datetime import UTC, datetime

from sqlalchemy import func, select, update

from src.core.constants import TaskStatus
from src.domain.entities import Queue
from src.persistence.models.queue import QueueModel
from src.persistence.models.task import TaskModel
from src.persistence.repositories.base import BaseRepository


class QueueRepository(BaseRepository[QueueModel]):
    async def get_by_name(self, queue_name: str) -> Queue | None:
        stmt = select(QueueModel).where(QueueModel.queue_name == queue_name)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def create_or_update_queue(self, queue: Queue) -> Queue:
        now = datetime.now(UTC)
        existing = await self.get_by_name(queue.queue_name)
        if existing:
            stmt = (
                update(QueueModel)
                .where(QueueModel.queue_name == queue.queue_name)
                .values(
                    enabled=queue.enabled,
                    default_priority=queue.default_priority,
                    max_concurrency=queue.max_concurrency,
                    rate_limit_rps=queue.rate_limit_rps,
                    retry_defaults=queue.retry_defaults,
                    retention_days=queue.retention_days,
                    broker_backend=queue.broker_backend,
                    updated_at=now,
                )
            )
            await self.session.execute(stmt)
        else:
            model = QueueModel(
                queue_name=queue.queue_name,
                enabled=queue.enabled,
                default_priority=queue.default_priority,
                max_concurrency=queue.max_concurrency,
                rate_limit_rps=queue.rate_limit_rps,
                retry_defaults=queue.retry_defaults,
                retention_days=queue.retention_days,
                broker_backend=queue.broker_backend,
                created_at=queue.created_at or now,
                updated_at=now,
            )
            self.session.add(model)
            await self.session.flush()
        return queue

    async def list_queues(self) -> list[Queue]:
        stmt = select(QueueModel).order_by(QueueModel.queue_name.asc())
        res = await self.session.execute(stmt)
        return [self._to_entity(m) for m in res.scalars().all()]

    async def get_queue_depth(self, queue_name: str) -> int:
        stmt = select(func.count(TaskModel.task_id)).where(
            TaskModel.queue == queue_name,
            TaskModel.status.in_(
                [TaskStatus.PENDING.value, TaskStatus.QUEUED.value, TaskStatus.RETRY_WAIT.value]
            ),
        )
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def delete_queue(self, queue_name: str) -> bool:
        from sqlalchemy import delete

        stmt = delete(QueueModel).where(QueueModel.queue_name == queue_name)
        res = await self.session.execute(stmt)
        rowcount = getattr(res, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def get_oldest_task_age(self, queue_name: str) -> float | None:
        stmt = (
            select(TaskModel.created_at)
            .where(
                TaskModel.queue == queue_name,
                TaskModel.status.in_(
                    [TaskStatus.PENDING.value, TaskStatus.QUEUED.value, TaskStatus.RETRY_WAIT.value]
                ),
            )
            .order_by(TaskModel.created_at.asc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        oldest_created = res.scalar_one_or_none()
        if not oldest_created:
            return None
        now = datetime.now(UTC)
        if oldest_created.tzinfo is None:
            oldest_created = oldest_created.replace(tzinfo=UTC)
        return max(0.0, (now - oldest_created).total_seconds())

    def _to_entity(self, m: QueueModel) -> Queue:
        return Queue(
            queue_name=m.queue_name,
            enabled=m.enabled,
            default_priority=m.default_priority,
            max_concurrency=m.max_concurrency,
            rate_limit_rps=m.rate_limit_rps,
            retry_defaults=m.retry_defaults,
            retention_days=m.retention_days,
            broker_backend=m.broker_backend,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

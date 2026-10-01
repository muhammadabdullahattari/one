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

    async def backend_exists(self, backend_name: str) -> bool:
        from src.persistence.models.broker_backend import BrokerBackendModel

        stmt = (
            select(func.count())
            .select_from(BrokerBackendModel)
            .where(BrokerBackendModel.backend_name == backend_name)
        )
        res = await self.session.execute(stmt)
        return bool((res.scalar() or 0) > 0)

    async def create_or_update_queue(self, queue: Queue) -> Queue:
        now = datetime.now(UTC)
        backend = queue.broker_backend or "native"
        existing = await self.get_by_name(queue.queue_name)
        if existing:
            backend = queue.broker_backend or existing.broker_backend or "native"
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
                    broker_backend=backend,
                    updated_at=now,
                )
            )
            await self.session.execute(stmt)
            queue.updated_at = now
            queue.broker_backend = backend
        else:
            model = QueueModel(
                queue_name=queue.queue_name,
                enabled=queue.enabled,
                default_priority=queue.default_priority,
                max_concurrency=queue.max_concurrency,
                rate_limit_rps=queue.rate_limit_rps,
                retry_defaults=queue.retry_defaults,
                retention_days=queue.retention_days,
                broker_backend=backend,
                created_at=queue.created_at or now,
                updated_at=now,
            )
            self.session.add(model)
            await self.session.flush()
            queue.updated_at = now
            queue.broker_backend = backend
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

    async def get_queue_backlog_summary(self) -> list[tuple[str, int, float | None]]:
        now = datetime.now(UTC)
        stmt = (
            select(
                QueueModel.queue_name,
                func.count(TaskModel.task_id).label("depth"),
                func.min(TaskModel.created_at).label("oldest_created_at"),
            )
            .outerjoin(
                TaskModel,
                (TaskModel.queue == QueueModel.queue_name)
                & (
                    TaskModel.status.in_(
                        [
                            TaskStatus.PENDING.value,
                            TaskStatus.QUEUED.value,
                            TaskStatus.RETRY_WAIT.value,
                        ]
                    )
                ),
            )
            .group_by(QueueModel.queue_name)
            .order_by(QueueModel.queue_name.asc())
        )
        res = await self.session.execute(stmt)
        summary: list[tuple[str, int, float | None]] = []
        for row in res.all():
            q_name = str(row[0])
            depth = int(row[1] or 0)
            oldest_created = row[2]
            oldest_age: float | None = None
            if oldest_created is not None:
                if oldest_created.tzinfo is None:
                    oldest_created = oldest_created.replace(tzinfo=UTC)
                oldest_age = max(0.0, round((now - oldest_created).total_seconds(), 3))
            summary.append((q_name, depth, oldest_age))
        return summary

    async def count_tasks(self, queue_name: str, statuses: list[str] | None = None) -> int:
        stmt = select(func.count(TaskModel.task_id)).where(TaskModel.queue == queue_name)
        if statuses:
            stmt = stmt.where(TaskModel.status.in_(statuses))
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def reassign_tasks(self, from_queue: str, to_queue: str = "default") -> int:
        from src.persistence.models.schedule import ScheduleModel

        terminal_statuses = [
            TaskStatus.SUCCEEDED.value,
            TaskStatus.FAILED.value,
            TaskStatus.TIMED_OUT.value,
            TaskStatus.CANCELLED.value,
            TaskStatus.DEAD.value,
        ]
        stmt = (
            update(TaskModel)
            .where(
                TaskModel.queue == from_queue,
                TaskModel.status.in_(terminal_statuses),
            )
            .values(queue=to_queue)
        )
        res = await self.session.execute(stmt)
        task_rowcount = int(getattr(res, "rowcount", 0))

        sched_stmt = (
            update(ScheduleModel).where(ScheduleModel.queue == from_queue).values(queue=to_queue)
        )
        await self.session.execute(sched_stmt)

        return task_rowcount

    async def delete_queue(self, queue_name: str) -> bool:
        from sqlalchemy import delete
        from sqlalchemy.exc import IntegrityError

        try:
            stmt = delete(QueueModel).where(QueueModel.queue_name == queue_name)
            res = await self.session.execute(stmt)
            rowcount = getattr(res, "rowcount", 0)
            return bool(rowcount and rowcount > 0)
        except IntegrityError:
            await self.session.rollback()
            raise

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

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update

from src.domain.entities import TaskOutbox
from src.persistence.models.outbox import TaskOutboxModel
from src.persistence.repositories.base import BaseRepository


class OutboxRepository(BaseRepository[TaskOutboxModel]):
    async def get_undelivered(self, limit: int = 100) -> list[TaskOutbox]:
        now = datetime.now(UTC)
        stmt = (
            select(TaskOutboxModel)
            .where(
                TaskOutboxModel.published_at.is_(None),
                TaskOutboxModel.next_attempt_at.is_(None)
                | (TaskOutboxModel.next_attempt_at <= now),
            )
            .order_by(TaskOutboxModel.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [
            TaskOutbox(
                outbox_id=m.outbox_id,
                task_id=m.task_id,
                event_type=m.event_type,
                payload=m.payload,
                created_at=m.created_at,
                published_at=m.published_at,
                attempts=m.attempts,
                last_error=m.last_error,
                next_attempt_at=m.next_attempt_at,
            )
            for m in res.scalars().all()
        ]

    async def mark_published(self, outbox_id: UUID) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(TaskOutboxModel)
            .where(TaskOutboxModel.outbox_id == outbox_id)
            .values(published_at=now)
        )
        await self.session.execute(stmt)

    async def record_failure(
        self, outbox_id: UUID, error_message: str, next_attempt_at: datetime | None = None
    ) -> None:
        stmt = (
            update(TaskOutboxModel)
            .where(TaskOutboxModel.outbox_id == outbox_id)
            .values(
                attempts=TaskOutboxModel.attempts + 1,
                last_error=error_message[:1000],
                next_attempt_at=next_attempt_at,
            )
        )
        await self.session.execute(stmt)

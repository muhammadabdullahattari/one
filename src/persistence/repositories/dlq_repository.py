from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update

from src.domain.entities import DLQEntry
from src.persistence.models.dlq import DLQEntryModel
from src.persistence.models.task import TaskModel
from src.persistence.repositories.base import BaseRepository


class DLQRepository(BaseRepository[DLQEntryModel]):
    async def create_entry(self, dlq_entry: DLQEntry) -> DLQEntry:
        now = datetime.now(UTC)
        tenant = dlq_entry.tenant_id
        if not tenant or tenant == "default":
            task_res = await self.session.execute(
                select(TaskModel.tenant_id).where(TaskModel.task_id == dlq_entry.task_id)
            )
            t_id = task_res.scalar_one_or_none()
            if t_id:
                tenant = t_id
            else:
                tenant = tenant or "default"

        model = DLQEntryModel(
            dlq_id=dlq_entry.dlq_id,
            task_id=dlq_entry.task_id,
            tenant_id=tenant,
            final_attempt_id=dlq_entry.final_attempt_id,
            reason=dlq_entry.reason,
            error_class=dlq_entry.error_class,
            payload_ref=dlq_entry.payload_ref,
            dead_at=dlq_entry.dead_at or now,
            replay_count=dlq_entry.replay_count,
            last_replayed_at=dlq_entry.last_replayed_at,
        )
        self.session.add(model)
        await self.session.flush()
        return dlq_entry

    async def get_by_id(self, dlq_id: UUID) -> DLQEntry | None:
        stmt = select(DLQEntryModel).where(DLQEntryModel.dlq_id == dlq_id)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def get_by_task_id(self, task_id: UUID) -> DLQEntry | None:
        stmt = select(DLQEntryModel).where(DLQEntryModel.task_id == task_id)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def mark_replayed(self, task_or_dlq_id: UUID) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(DLQEntryModel)
            .where(
                (DLQEntryModel.dlq_id == task_or_dlq_id) | (DLQEntryModel.task_id == task_or_dlq_id)
            )
            .values(
                replay_count=DLQEntryModel.replay_count + 1,
                last_replayed_at=now,
            )
        )
        await self.session.execute(stmt)

    async def list_entries(
        self,
        limit: int = 50,
        offset: int = 0,
        tenant_id: str | None = None,
        include_replayed: bool = False,
    ) -> list[DLQEntry]:
        stmt = select(DLQEntryModel)
        if not include_replayed:
            stmt = stmt.where(DLQEntryModel.last_replayed_at.is_(None))
        if tenant_id:
            stmt = stmt.where(DLQEntryModel.tenant_id == tenant_id)
        stmt = stmt.order_by(DLQEntryModel.dead_at.desc()).limit(limit).offset(offset)
        res = await self.session.execute(stmt)
        return [self._to_entity(m) for m in res.scalars().all()]

    async def count_entries(
        self, tenant_id: str | None = None, include_replayed: bool = False
    ) -> int:
        stmt = select(func.count(DLQEntryModel.dlq_id))
        if not include_replayed:
            stmt = stmt.where(DLQEntryModel.last_replayed_at.is_(None))
        if tenant_id:
            stmt = stmt.where(DLQEntryModel.tenant_id == tenant_id)
        res = await self.session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def delete_entry(self, dlq_id: UUID) -> bool:
        stmt = delete(DLQEntryModel).where(DLQEntryModel.dlq_id == dlq_id)
        res = await self.session.execute(stmt)
        rowcount = getattr(res, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    def _to_entity(self, m: DLQEntryModel) -> DLQEntry:
        return DLQEntry(
            dlq_id=m.dlq_id,
            task_id=m.task_id,
            tenant_id=getattr(m, "tenant_id", "default"),
            final_attempt_id=m.final_attempt_id,
            reason=m.reason,
            error_class=m.error_class,
            payload_ref=m.payload_ref,
            dead_at=m.dead_at,
            replay_count=m.replay_count,
            last_replayed_at=m.last_replayed_at,
        )

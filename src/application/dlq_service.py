from datetime import UTC, datetime
from uuid import UUID

import structlog

from src.core.constants import TaskStatus
from src.domain.entities import DLQEntry, TaskOutbox
from src.persistence.models.outbox import TaskOutboxModel
from src.persistence.models.task import TaskModel
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope

logger = structlog.get_logger(__name__)


class DLQService:
    def __init__(
        self,
        dlq_repo: DLQRepository | None = None,
        task_repo: TaskRepository | None = None,
        outbox_repo: object | None = None,
    ) -> None:
        self._dlq_repo = dlq_repo
        self._task_repo = task_repo

    async def list_dlq(self, limit: int = 50, offset: int = 0) -> list[DLQEntry]:
        if self._dlq_repo:
            return await self._dlq_repo.list_entries(limit=limit, offset=offset)
        async with session_scope() as session:
            repo = DLQRepository(session)
            return await repo.list_entries(limit=limit, offset=offset)

    async def get_entry(self, dlq_id: UUID) -> DLQEntry | None:
        if self._dlq_repo:
            return await self._dlq_repo.get_by_id(dlq_id)
        async with session_scope() as session:
            repo = DLQRepository(session)
            return await repo.get_by_id(dlq_id)

    async def replay(self, dlq_id: UUID, reset_attempts: bool = True) -> bool:
        now = datetime.now(UTC)
        async with session_scope() as session:
            dlq_repo = DLQRepository(session)
            entry = await dlq_repo.get_by_id(dlq_id)
            if not entry:
                return False
            task_model = await session.get(TaskModel, entry.task_id)
            if not task_model:
                return False
            task_model.status = TaskStatus.QUEUED.value
            task_model.status_reason = f"Operator DLQ replay from {dlq_id}"
            if reset_attempts:
                task_model.attempt_count = 0
            task_model.updated_at = now
            task_model.version += 1
            outbox = TaskOutbox(
                task_id=task_model.task_id,
                event_type="task.replayed",
                payload={"dlq_id": str(dlq_id), "task_type": task_model.task_type},
            )
            session.add(
                TaskOutboxModel(
                    outbox_id=outbox.outbox_id,
                    task_id=outbox.task_id,
                    event_type=outbox.event_type,
                    payload=outbox.payload,
                    created_at=now,
                )
            )
            await dlq_repo.mark_replayed(dlq_id)
            logger.info("task_replayed_from_dlq", dlq_id=str(dlq_id), task_id=str(entry.task_id))
            return True

    async def bulk_replay(
        self,
        dlq_ids: list[UUID] | None = None,
        limit: int = 50,
        reset_attempts: bool = True,
        tenant_id: str | None = None,
    ) -> int:
        from sqlalchemy import select

        now = datetime.now(UTC)
        async with session_scope() as session:
            dlq_repo = DLQRepository(session)
            if dlq_ids:
                entries: list[DLQEntry] = []
                for did in dlq_ids:
                    e = await dlq_repo.get_by_id(did)
                    if e and (tenant_id is None or e.tenant_id == tenant_id):
                        entries.append(e)
            else:
                entries = await dlq_repo.list_entries(limit=limit, tenant_id=tenant_id)

            if not entries:
                return 0

            task_ids = [e.task_id for e in entries]
            stmt = select(TaskModel).where(TaskModel.task_id.in_(task_ids))
            res = await session.execute(stmt)
            task_models = {m.task_id: m for m in res.scalars().all()}

            replayed_count = 0
            for entry in entries:
                task_model = task_models.get(entry.task_id)
                if not task_model:
                    continue
                task_model.status = TaskStatus.QUEUED.value
                task_model.status_reason = f"Operator DLQ replay from {entry.dlq_id}"
                if reset_attempts:
                    task_model.attempt_count = 0
                task_model.updated_at = now
                task_model.version += 1

                outbox = TaskOutbox(
                    task_id=task_model.task_id,
                    event_type="task.replayed",
                    payload={"dlq_id": str(entry.dlq_id), "task_type": task_model.task_type},
                )
                session.add(
                    TaskOutboxModel(
                        outbox_id=outbox.outbox_id,
                        task_id=outbox.task_id,
                        event_type=outbox.event_type,
                        payload=outbox.payload,
                        created_at=now,
                    )
                )
                await dlq_repo.mark_replayed(entry.dlq_id)
                replayed_count += 1
            return replayed_count

from datetime import UTC, datetime

from sqlalchemy import select, update

from src.domain.entities import Worker
from src.persistence.models.worker import WorkerModel
from src.persistence.repositories.base import BaseRepository


class WorkerRepository(BaseRepository[WorkerModel]):
    async def register_worker(self, worker: Worker) -> Worker:
        now = datetime.now(UTC)
        stmt = select(WorkerModel).where(WorkerModel.worker_id == worker.worker_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.hostname = worker.hostname
            existing.process_id = worker.process_id
            existing.version = worker.version
            existing.protocol_version = worker.protocol_version
            existing.capabilities_json = worker.capabilities_json
            existing.queues_json = worker.queues_json
            existing.concurrency = worker.concurrency
            existing.status = "active"
            existing.last_heartbeat = now
        else:
            model = WorkerModel(
                worker_id=worker.worker_id,
                hostname=worker.hostname,
                process_id=worker.process_id,
                version=worker.version,
                protocol_version=worker.protocol_version,
                capabilities_json=worker.capabilities_json,
                queues_json=worker.queues_json,
                concurrency=worker.concurrency,
                active_slots=0,
                status="active",
                last_heartbeat=now,
                registered_at=now,
            )
            self.session.add(model)
        await self.session.flush()
        return worker

    async def record_heartbeat(self, worker_id: str, active_slots: int = 0) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(WorkerModel)
            .where(WorkerModel.worker_id == worker_id)
            .values(last_heartbeat=now, active_slots=active_slots)
        )
        await self.session.execute(stmt)

    async def set_draining(self, worker_id: str) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(WorkerModel)
            .where(WorkerModel.worker_id == worker_id)
            .values(status="draining", drained_at=now)
        )
        await self.session.execute(stmt)

    async def list_workers(self, status: str | None = None) -> list[Worker]:
        stmt = select(WorkerModel)
        if status:
            stmt = stmt.where(WorkerModel.status == status)
        stmt = stmt.order_by(WorkerModel.last_heartbeat.desc())
        res = await self.session.execute(stmt)
        return [
            Worker(
                worker_id=m.worker_id,
                hostname=m.hostname,
                process_id=m.process_id,
                version=m.version,
                protocol_version=m.protocol_version,
                capabilities_json=m.capabilities_json,
                queues_json=m.queues_json,
                concurrency=m.concurrency,
                active_slots=m.active_slots,
                status=m.status,
                last_heartbeat=m.last_heartbeat,
                registered_at=m.registered_at,
                drained_at=m.drained_at,
            )
            for m in res.scalars().all()
        ]

    async def get_by_id(self, worker_id: str) -> Worker | None:
        stmt = select(WorkerModel).where(WorkerModel.worker_id == worker_id)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            return None
        return Worker(
            worker_id=m.worker_id,
            hostname=m.hostname,
            process_id=m.process_id,
            version=m.version,
            protocol_version=m.protocol_version,
            capabilities_json=m.capabilities_json,
            queues_json=m.queues_json,
            concurrency=m.concurrency,
            active_slots=m.active_slots,
            status=m.status,
            last_heartbeat=m.last_heartbeat,
            registered_at=m.registered_at,
            drained_at=m.drained_at,
        )

    async def delete_worker(self, worker_id: str) -> bool:
        from sqlalchemy import delete

        stmt = delete(WorkerModel).where(WorkerModel.worker_id == worker_id)
        res = await self.session.execute(stmt)
        rowcount = getattr(res, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

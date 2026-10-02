from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text, update

from src.core.constants import MisfirePolicy
from src.domain.entities import Schedule
from src.persistence.models.schedule import ScheduleModel
from src.persistence.repositories.base import BaseRepository


class ScheduleRepository(BaseRepository[ScheduleModel]):
    async def create_schedule(self, schedule: Schedule) -> Schedule:
        now = datetime.now(UTC)
        model = ScheduleModel(
            schedule_id=schedule.schedule_id,
            tenant_id=schedule.tenant_id,
            task_type=schedule.task_type,
            queue=schedule.queue,
            payload=schedule.payload,
            payload_ref=schedule.payload_ref,
            cron_expression=schedule.cron_expression,
            interval_seconds=schedule.interval_seconds,
            timezone=schedule.timezone,
            misfire_policy=schedule.misfire_policy.value,
            enabled=schedule.enabled,
            next_run_at=schedule.next_run_at,
            last_run_at=schedule.last_run_at,
            version=schedule.version,
            created_at=schedule.created_at or now,
            updated_at=now,
        )
        self.session.add(model)
        await self.session.flush()
        return schedule

    async def get_by_id(self, schedule_id: UUID) -> Schedule | None:
        stmt = select(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return self._to_entity(m) if m else None

    async def get_due_schedules(self, now_utc: datetime, limit: int = 50) -> list[Schedule]:
        stmt = (
            select(ScheduleModel)
            .where(
                ScheduleModel.enabled.is_(True),
                ScheduleModel.next_run_at.is_not(None),
                ScheduleModel.next_run_at <= now_utc,
            )
            .order_by(ScheduleModel.next_run_at.asc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [self._to_entity(m) for m in res.scalars().all()]

    async def update_run_times(
        self, schedule_id: UUID, last_run_at: datetime, next_run_at: datetime | None
    ) -> None:
        now = datetime.now(UTC)
        stmt = (
            update(ScheduleModel)
            .where(ScheduleModel.schedule_id == schedule_id)
            .values(
                last_run_at=last_run_at,
                next_run_at=next_run_at,
                updated_at=now,
                version=ScheduleModel.version + 1,
            )
        )
        await self.session.execute(stmt)

    async def acquire_advisory_lock(self, lock_key: int = 428912) -> bool:
        stmt = text("SELECT pg_try_advisory_xact_lock(:lock_key)")
        result = await self.session.execute(stmt, {"lock_key": lock_key})
        acquired = bool(result.scalar_one())
        return acquired

    async def list_schedules(
        self, enabled_only: bool = False, tenant_id: str | None = None
    ) -> list[Schedule]:
        stmt = select(ScheduleModel)
        if enabled_only:
            stmt = stmt.where(ScheduleModel.enabled.is_(True))
        if tenant_id:
            stmt = stmt.where(ScheduleModel.tenant_id == tenant_id)
        stmt = stmt.order_by(ScheduleModel.created_at.desc())
        res = await self.session.execute(stmt)
        return [self._to_entity(m) for m in res.scalars().all()]

    async def update_schedule(self, schedule: Schedule) -> Schedule:
        now = datetime.now(UTC)
        stmt = (
            update(ScheduleModel)
            .where(ScheduleModel.schedule_id == schedule.schedule_id)
            .values(
                task_type=schedule.task_type,
                queue=schedule.queue,
                payload=schedule.payload,
                payload_ref=schedule.payload_ref,
                cron_expression=schedule.cron_expression,
                interval_seconds=schedule.interval_seconds,
                timezone=schedule.timezone,
                misfire_policy=schedule.misfire_policy.value,
                enabled=schedule.enabled,
                next_run_at=schedule.next_run_at,
                updated_at=now,
                version=ScheduleModel.version + 1,
            )
        )
        await self.session.execute(stmt)
        return schedule

    async def delete_schedule(self, schedule_id: UUID) -> bool:
        from sqlalchemy import delete

        stmt = delete(ScheduleModel).where(ScheduleModel.schedule_id == schedule_id)
        res = await self.session.execute(stmt)
        rowcount = getattr(res, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    def _to_entity(self, m: ScheduleModel) -> Schedule:
        return Schedule(
            schedule_id=m.schedule_id,
            tenant_id=getattr(m, "tenant_id", "default"),
            task_type=m.task_type,
            queue=m.queue,
            payload=m.payload,
            payload_ref=m.payload_ref,
            cron_expression=m.cron_expression,
            interval_seconds=m.interval_seconds,
            timezone=m.timezone,
            misfire_policy=MisfirePolicy(m.misfire_policy),
            enabled=m.enabled,
            next_run_at=m.next_run_at,
            last_run_at=m.last_run_at,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )

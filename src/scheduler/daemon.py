import asyncio
from datetime import UTC, datetime

import structlog

from src.core.config import get_settings
from src.domain.entities import Task, TaskOutbox
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope
from src.scheduler.misfire import evaluate_misfires

logger = structlog.get_logger(__name__)


class SchedulerDaemon:
    def __init__(self, leader_lock_key: int = 428912) -> None:
        self.leader_lock_key = leader_lock_key
        self.settings = get_settings()
        self._running = False
        self._is_leader = False

    async def run(self) -> None:
        self._running = True
        logger.info("Scheduler daemon starting", tick_seconds=self.settings.scheduler_tick_seconds)

        while self._running:
            try:
                await self.tick()
            except Exception as e:
                logger.error("Error during scheduler tick", error=str(e), exc_info=True)
            await asyncio.sleep(self.settings.scheduler_tick_seconds)

    async def stop(self) -> None:
        self._running = False
        logger.info("Scheduler daemon stopped")

    async def tick(self) -> None:

        now = datetime.now(UTC)

        async with session_scope() as session:
            sched_repo = ScheduleRepository(session)
            task_repo = TaskRepository(session)
            is_leader = await sched_repo.acquire_advisory_lock(self.leader_lock_key)
            self._is_leader = is_leader

            if not is_leader:
                logger.debug(
                    "Standing by as secondary scheduler instance (leader lock held elsewhere)"
                )
                return
            due_schedules = await sched_repo.get_due_schedules(now)

            if not due_schedules:
                return

            logger.info("Evaluating due schedules", count=len(due_schedules))

            for sched in due_schedules:
                if sched.next_run_at is None:
                    continue
                runs, next_run = evaluate_misfires(
                    cron_expression=sched.cron_expression,
                    interval_seconds=sched.interval_seconds,
                    timezone_name=sched.timezone,
                    scheduled_run_at=sched.next_run_at,
                    now_utc=now,
                    misfire_policy=sched.misfire_policy,
                )
                for run_timestamp in runs:
                    task = Task(
                        task_type=sched.task_type,
                        queue=sched.queue,
                        payload_ref=sched.payload_ref,
                        schedule_id=sched.schedule_id,
                        scheduled_at=run_timestamp,
                    )

                    outbox = TaskOutbox(
                        task_id=task.task_id,
                        event_type="task.scheduled",
                        payload={
                            "schedule_id": str(sched.schedule_id),
                            "task_type": sched.task_type,
                        },
                    )

                    await task_repo.create_with_outbox(task, outbox)

                await sched_repo.update_run_times(
                    schedule_id=sched.schedule_id, last_run_at=now, next_run_at=next_run
                )

                logger.info(
                    "Schedule executed",
                    schedule_id=str(sched.schedule_id),
                    task_type=sched.task_type,
                    emitted_tasks=len(runs),
                    next_run_at=str(next_run),
                )

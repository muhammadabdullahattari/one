import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from src.core.constants import TaskStatus
from src.persistence.models.audit import AuditEventModel
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope

logger = structlog.get_logger(__name__)


class Reconciler:
    def __init__(
        self,
        reconcile_interval_seconds: float = 10.0,
        stuck_pending_threshold_seconds: float = 60.0,
    ) -> None:
        self.interval = reconcile_interval_seconds
        self.stuck_pending_threshold = stuck_pending_threshold_seconds
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("Reconciler daemon started", interval=self.interval)
        while self._running:
            try:
                await self.reconcile()
            except Exception as e:
                logger.error("Error during reconciliation pass", error=str(e), exc_info=True)
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("Reconciler daemon stopped")

    async def reconcile(self) -> dict[str, int]:
        now = datetime.now(UTC)
        pending_cutoff = now - timedelta(seconds=self.stuck_pending_threshold)
        recovered_leases = 0
        recovered_pending = 0
        async with session_scope() as session:
            task_repo = TaskRepository(session)
            expired_tasks = await task_repo.get_expired_leases(cutoff_time=now)
            for task in expired_tasks:
                logger.warn(
                    "Recovering task with expired worker lease",
                    task_id=str(task.task_id),
                    worker_id=task.current_worker_id,
                    attempt_count=task.attempt_count,
                    max_attempts=task.max_attempts,
                )
                if task.attempt_count < task.max_attempts:
                    await task_repo.fail_task(
                        task_id=task.task_id,
                        attempt_id=None,
                        error_class="WorkerLeaseExpiredException",
                        error_message_redacted=f"Worker {task.current_worker_id} lease expired before completion",
                        retryable=True,
                    )
                else:
                    await task_repo.fail_task(
                        task_id=task.task_id,
                        attempt_id=None,
                        error_class="WorkerLeaseExpiredException",
                        error_message_redacted=f"Worker {task.current_worker_id} lease expired; max attempts reached",
                        retryable=False,
                    )
                audit = AuditEventModel(
                    actor="reconciler",
                    action="RECOVER_EXPIRED_LEASE",
                    resource_type="task",
                    resource_id=str(task.task_id),
                    timestamp=now,
                    outcome="SUCCESS",
                    metadata_json={"previous_worker": task.current_worker_id},
                )
                session.add(audit)
                recovered_leases += 1
            stuck_pending = await task_repo.get_stuck_pending(cutoff_time=pending_cutoff)
            for task in stuck_pending:
                logger.info(
                    "Transitioning stuck PENDING task to QUEUED",
                    task_id=str(task.task_id),
                    queue=task.queue,
                )
                task.status = TaskStatus.QUEUED
                recovered_pending += 1
        return {"recovered_leases": recovered_leases, "recovered_pending": recovered_pending}

import asyncio

import structlog

from src.broker.core.envelope import TaskEnvelope
from src.broker.registry import get_broker_adapter
from src.persistence.repositories.outbox_repository import OutboxRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope

logger = structlog.get_logger(__name__)


class OutboxPublisher:
    def __init__(self, poll_interval_seconds: float = 1.0, batch_size: int = 100) -> None:
        self.poll_interval = poll_interval_seconds
        self.batch_size = batch_size
        self._running = False

    async def run(self) -> None:
        self._running = True
        logger.info("OutboxPublisher starting", poll_interval=self.poll_interval)
        while self._running:
            try:
                published_count = await self.publish_batch()
                if published_count == 0:
                    await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error("Error in OutboxPublisher loop", error=str(e), exc_info=True)
                await asyncio.sleep(self.poll_interval)

    async def stop(self) -> None:
        self._running = False
        logger.info("OutboxPublisher stopped")

    async def publish_batch(self) -> int:
        published_count = 0
        async with session_scope() as session:
            outbox_repo = OutboxRepository(session)
            task_repo = TaskRepository(session)
            entries = await outbox_repo.get_undelivered(limit=self.batch_size)
            if not entries:
                return 0
            tasks_map = await task_repo.get_by_ids([entry.task_id for entry in entries])
            for entry in entries:
                try:
                    task = tasks_map.get(entry.task_id)
                    if not task:
                        logger.warning(
                            "Outbox task not found in database", task_id=str(entry.task_id)
                        )
                        await outbox_repo.mark_published(entry.outbox_id)
                        continue
                    adapter = get_broker_adapter("native")
                    envelope = TaskEnvelope(
                        task_id=task.task_id,
                        tenant_id=task.tenant_id,
                        task_type=task.task_type,
                        queue=task.queue,
                        priority=task.priority,
                        payload=task.payload,
                        payload_ref=task.payload_ref,
                        timeout_seconds=task.timeout_seconds,
                        max_attempts=task.max_attempts,
                        attempt_count=task.attempt_count,
                        created_at=task.created_at,
                    )
                    from src.broker.native.adapter import NativeBrokerAdapter

                    if isinstance(adapter, NativeBrokerAdapter):
                        await adapter.publish(task.queue, envelope, session=session)
                    else:
                        await adapter.publish(task.queue, envelope)
                    await outbox_repo.mark_published(entry.outbox_id)
                    published_count += 1
                except Exception as exc:
                    logger.error(
                        "Failed to publish outbox entry to broker",
                        outbox_id=str(entry.outbox_id),
                        task_id=str(entry.task_id),
                        error=str(exc),
                    )
                    await outbox_repo.record_failure(entry.outbox_id, str(exc))
        return published_count

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from src.broker.adapters.redis.adapter import RedisBrokerAdapter
from src.broker.core.envelope import TaskEnvelope
from src.core.constants import TaskStatus
from src.domain.entities import (
    DLQEntry,
    Queue,
    Schedule,
    Task,
    TaskOutbox,
)
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope

from tests.broker_conformance.mock_redis import MockRedisStreamsClient


@pytest.mark.asyncio
async def test_task_not_lost_on_worker_crash() -> None:
    mock_redis: Any = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_redis)
    queue = f"reg-crash-{uuid4().hex[:6]}"
    task_id = uuid4()

    await adapter.publish(queue, TaskEnvelope(task_id=task_id, task_type="crash_task", queue=queue))
    msgs = await adapter.consume(queue=queue, worker_id="crashed-worker-node", batch_size=1)
    assert len(msgs) == 1

    recovered = await adapter.claim_stale(
        queue=queue, worker_id="failover-worker-node", min_idle_time_ms=0, count=10
    )
    assert len(recovered) == 1
    assert recovered[0].envelope.task_id == task_id
    await adapter.close()


@pytest.mark.asyncio
async def test_no_duplicate_scheduled_execution() -> None:
    sched_id = uuid4()
    now = datetime.now(UTC)

    async with session_scope() as session:
        s_repo = ScheduleRepository(session)
        schedule = Schedule(
            schedule_id=sched_id,
            task_type="dedup_scheduled_task",
            queue="default",
            cron_expression="*/5 * * * *",
            timezone="UTC",
            enabled=True,
            last_run_at=now,
            next_run_at=now + timedelta(minutes=5),
        )
        await s_repo.create_schedule(schedule)

    async with session_scope() as session:
        s_repo = ScheduleRepository(session)
        due_now = await s_repo.get_due_schedules(now)
        matching = [s for s in due_now if s.schedule_id == sched_id]
        assert len(matching) == 0


@pytest.mark.asyncio
async def test_dlq_replay_does_not_double_submit() -> None:
    task_id = uuid4()
    queue = f"reg-dlq-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with session_scope() as session:
        q_repo = QueueRepository(session)
        await q_repo.create_or_update_queue(Queue(queue_name=queue, broker_backend="native"))

        t_repo = TaskRepository(session)
        task = Task(
            task_id=task_id,
            task_type="dlq_double_submit_check",
            queue=queue,
            status=TaskStatus.DEAD,
        )
        await t_repo.create_with_outbox(task, TaskOutbox(task_id=task_id))

        dlq_repo = DLQRepository(session)
        await dlq_repo.create_entry(
            DLQEntry(
                task_id=task_id,
                reason="Transient failure exhausted",
                error_class="TimeoutException",
                dead_at=now,
            )
        )

    async with session_scope() as session:
        dlq_repo = DLQRepository(session)
        entry = await dlq_repo.get_by_task_id(task_id)
        assert entry is not None
        assert entry.last_replayed_at is None

        await dlq_repo.mark_replayed(task_id)
        replayed_entry = await dlq_repo.get_by_task_id(task_id)
        assert replayed_entry is not None
        assert replayed_entry.last_replayed_at is not None

        await dlq_repo.mark_replayed(task_id)
        second_entry = await dlq_repo.get_by_task_id(task_id)
        assert second_entry is not None
        assert second_entry.replay_count == 2

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
    Worker,
)
from src.observability.metrics import (
    TASKS_SUBMITTED_TOTAL,
    generate_metrics_text,
)
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.outbox_repository import OutboxRepository
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.repositories.worker_repository import WorkerRepository
from src.persistence.session import session_scope

from tests.broker_conformance.mock_redis import MockRedisStreamsClient


@pytest.mark.asyncio
async def test_it_001_api_and_postgres_transactional_acceptance() -> None:
    task_id = uuid4()
    task = Task(
        task_id=task_id,
        tenant_id="tenant-it",
        task_type="it_test_task",
        queue="default",
        priority=6,
        payload={"order_id": "ORD-IT-001"},
    )
    outbox = TaskOutbox(
        task_id=task_id,
        event_type="task.created",
        payload={"order_id": "ORD-IT-001"},
    )
    async with session_scope() as session:
        task_repo = TaskRepository(session)
        await task_repo.create_with_outbox(task, outbox)

    async with session_scope() as session:
        task_repo = TaskRepository(session)
        outbox_repo = OutboxRepository(session)
        saved_task = await task_repo.get_by_id(task_id)
        assert saved_task is not None
        assert saved_task.task_id == task_id
        assert saved_task.status == TaskStatus.PENDING

        undelivered = await outbox_repo.get_undelivered()
        outbox_item = next((o for o in undelivered if o.task_id == task_id), None)
        assert outbox_item is not None
        assert outbox_item.event_type == "task.created"


@pytest.mark.asyncio
async def test_it_002_outbox_and_redis_publishing() -> None:
    mock_redis: Any = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_redis)
    task_id = uuid4()
    envelope = TaskEnvelope(
        task_id=task_id,
        tenant_id="tenant-it",
        task_type="outbox_published_task",
        queue="it-queue-outbox",
        priority=8,
    )
    msg_id = await adapter.publish("it-queue-outbox", envelope)
    assert msg_id is not None

    stats = await adapter.stats("it-queue-outbox")
    assert stats.depth >= 1
    await adapter.close()


@pytest.mark.asyncio
async def test_it_003_redis_consumer_group_dispatch() -> None:
    mock_redis: Any = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_redis)
    queue = f"it-cg-{uuid4().hex[:6]}"

    t1_id, t2_id = uuid4(), uuid4()
    await adapter.publish(queue, TaskEnvelope(task_id=t1_id, task_type="cg_task", queue=queue))
    await adapter.publish(queue, TaskEnvelope(task_id=t2_id, task_type="cg_task", queue=queue))

    w1_msgs = await adapter.consume(queue=queue, worker_id="worker-node-1", batch_size=1)
    w2_msgs = await adapter.consume(queue=queue, worker_id="worker-node-2", batch_size=1)

    assert len(w1_msgs) == 1
    assert len(w2_msgs) == 1
    assert w1_msgs[0].envelope.task_id != w2_msgs[0].envelope.task_id
    await adapter.close()


@pytest.mark.asyncio
async def test_it_004_ack_semantics_recoverability() -> None:
    mock_redis: Any = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_redis)
    queue = f"it-ack-{uuid4().hex[:6]}"
    task_id = uuid4()

    await adapter.publish(queue, TaskEnvelope(task_id=task_id, task_type="ack_task", queue=queue))
    msgs = await adapter.consume(queue=queue, worker_id="worker-temp", batch_size=1)
    assert len(msgs) == 1

    pel_key = f"task_engine:stream:{queue}:task_engine:cg:{queue}"
    assert msgs[0].message_id in mock_redis.pel.get(pel_key, {})

    await adapter.acknowledge(queue, msgs[0].message_id)
    assert msgs[0].message_id not in mock_redis.pel.get(pel_key, {})
    await adapter.close()


@pytest.mark.asyncio
async def test_it_005_lease_recovery_stale_claim() -> None:
    mock_redis: Any = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_redis)
    queue = f"it-stale-{uuid4().hex[:6]}"
    task_id = uuid4()

    await adapter.publish(queue, TaskEnvelope(task_id=task_id, task_type="stale_task", queue=queue))
    await adapter.consume(queue=queue, worker_id="crashed-worker", batch_size=1)

    reclaimed = await adapter.claim_stale(
        queue=queue, worker_id="healthy-worker", min_idle_time_ms=0, count=5
    )
    assert len(reclaimed) == 1
    assert reclaimed[0].envelope.task_id == task_id
    await adapter.close()


@pytest.mark.asyncio
async def test_it_006_result_persistence_retrieval() -> None:
    task_id = uuid4()
    test_queue = f"it-res-{uuid4().hex[:6]}"

    async with session_scope() as session:
        q_repo = QueueRepository(session)
        await q_repo.create_or_update_queue(Queue(queue_name=test_queue, broker_backend="native"))

        t_repo = TaskRepository(session)
        task = Task(
            task_id=task_id,
            task_type="compute_result",
            queue=test_queue,
            result={"output_code": 200, "data_rows": 1500},
            status=TaskStatus.SUCCEEDED,
        )
        await t_repo.create_with_outbox(task, TaskOutbox(task_id=task_id))

    async with session_scope() as session:
        t_repo = TaskRepository(session)
        fetched = await t_repo.get_by_id(task_id)
        assert fetched is not None
        assert fetched.result == {"output_code": 200, "data_rows": 1500}


@pytest.mark.asyncio
async def test_it_007_scheduler_and_db_exact_once_task_creation() -> None:
    sched_id = uuid4()
    now = datetime.now(UTC)
    async with session_scope() as session:
        sched_repo = ScheduleRepository(session)
        schedule = Schedule(
            schedule_id=sched_id,
            task_type="hourly_backup",
            queue="default",
            cron_expression="0 * * * *",
            timezone="UTC",
            enabled=True,
            next_run_at=now - timedelta(minutes=1),
        )
        await sched_repo.create_schedule(schedule)

    async with session_scope() as session:
        sched_repo = ScheduleRepository(session)
        due_schedules = await sched_repo.get_due_schedules(now)
        matching = [s for s in due_schedules if s.schedule_id == sched_id]
        assert len(matching) == 1
        assert matching[0].task_type == "hourly_backup"


@pytest.mark.asyncio
async def test_it_008_dlq_replay_requeue() -> None:
    task_id = uuid4()
    queue = f"it-dlq-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with session_scope() as session:
        q_repo = QueueRepository(session)
        await q_repo.create_or_update_queue(Queue(queue_name=queue, broker_backend="native"))
        t_repo = TaskRepository(session)
        task = Task(task_id=task_id, task_type="failed_task", queue=queue, status=TaskStatus.DEAD)
        await t_repo.create_with_outbox(task, TaskOutbox(task_id=task_id))

        dlq_repo = DLQRepository(session)
        await dlq_repo.create_entry(
            DLQEntry(
                task_id=task_id,
                reason="Max retries exhausted",
                error_class="FatalProcessingError",
                dead_at=now,
            )
        )

    async with session_scope() as session:
        dlq_repo = DLQRepository(session)
        entries = await dlq_repo.list_entries(limit=50)
        entry = next((e for e in entries if e.task_id == task_id), None)
        assert entry is not None
        assert entry.reason == "Max retries exhausted"


@pytest.mark.asyncio
async def test_it_009_worker_heartbeat_freshness() -> None:
    worker_id = f"worker-hb-{uuid4().hex[:6]}"
    now = datetime.now(UTC)

    async with session_scope() as session:
        w_repo = WorkerRepository(session)
        worker = Worker(
            worker_id=worker_id,
            hostname="node-01.internal",
            process_id=1234,
            concurrency=8,
            active_slots=2,
            last_heartbeat=now,
        )
        await w_repo.register_worker(worker)

    async with session_scope() as session:
        w_repo = WorkerRepository(session)
        active_workers = await w_repo.list_workers(status="active")
        matching = [w for w in active_workers if w.worker_id == worker_id]
        assert len(matching) == 1
        assert matching[0].hostname == "node-01.internal"


def test_it_010_metrics_export_with_correct_labels() -> None:
    TASKS_SUBMITTED_TOTAL.labels(task_type="it_sample_task", queue="it-metrics-queue").inc()
    metrics_text = generate_metrics_text().decode("utf-8")
    assert "tasks_submitted_total" in metrics_text
    assert 'task_type="it_sample_task"' in metrics_text
    assert 'queue="it-metrics-queue"' in metrics_text

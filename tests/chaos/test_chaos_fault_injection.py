import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from src.application.reconciler import Reconciler
from src.application.task_service import TaskLifecycleService
from src.broker.adapters.redis.adapter import RedisBrokerAdapter
from src.broker.core.envelope import TaskEnvelope, TaskMessage
from src.core.constants import MisfirePolicy, TaskStatus
from src.domain.entities import Queue, Task
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope
from src.retry.policy import JitterStrategy, RetryPolicy
from src.scheduler.misfire import evaluate_misfires
from src.worker.runtime import WorkerRuntime

from tests.broker_conformance.mock_redis import MockRedisStreamsClient


@pytest.mark.asyncio
async def test_chaos_worker_crash_mid_execution_lease_recovery() -> None:
    queue_name = f"chaos-q-{uuid4().hex[:6]}"
    task_id = uuid4()
    now = datetime.now(UTC)
    expired_lease = now - timedelta(seconds=30)

    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

        task_repo = TaskRepository(session)
        await task_repo.create_task(
            Task(
                task_id=task_id,
                tenant_id="tenant-chaos",
                task_type="crashed_job",
                queue=queue_name,
                status=TaskStatus.RUNNING,
                attempt_count=1,
                max_attempts=3,
                current_worker_id="crashed-worker-pid-9999",
                lease_expires_at=expired_lease,
                started_at=expired_lease,
            )
        )

    reconciler = Reconciler()
    stats = await reconciler.reconcile()
    assert stats["recovered_leases"] >= 1

    task_service = TaskLifecycleService()
    recovered_task = await task_service.get_task(task_id)
    assert recovered_task is not None
    assert recovered_task.status in (TaskStatus.RETRY_WAIT, TaskStatus.QUEUED)
    assert "WorkerLeaseExpiredException" in (recovered_task.status_reason or "")


@pytest.mark.asyncio
async def test_chaos_worker_crash_post_persist_pre_ack() -> None:
    queue_name = f"chaos-ack-{uuid4().hex[:6]}"
    task_id = uuid4()
    now = datetime.now(UTC)

    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

        task_repo = TaskRepository(session)
        await task_repo.create_task(
            Task(
                task_id=task_id,
                tenant_id="tenant-chaos",
                task_type="persisted_before_ack",
                queue=queue_name,
                status=TaskStatus.SUCCEEDED,
                result={"status": "already_computed", "val": 100},
                finished_at=now,
            )
        )

    task_service = TaskLifecycleService()
    existing_task = await task_service.get_task(task_id)
    assert existing_task is not None
    assert existing_task.status == TaskStatus.SUCCEEDED

    envelope = TaskEnvelope(
        task_id=task_id,
        tenant_id="tenant-chaos",
        task_type="persisted_before_ack",
        queue=queue_name,
        payload={},
    )
    msg = TaskMessage(
        message_id=str(task_id),
        queue=queue_name,
        envelope=envelope,
        delivery_count=2,
    )

    worker = WorkerRuntime(
        worker_id=f"recovery-worker-{uuid4().hex[:6]}",
        queues=[queue_name],
        concurrency=1,
    )
    await worker.broker.acknowledge(queue_name, msg.message_id)

    persisted_task = await task_service.get_task(task_id)
    assert persisted_task is not None
    assert persisted_task.status == TaskStatus.SUCCEEDED
    assert persisted_task.result == {"status": "already_computed", "val": 100}


@pytest.mark.asyncio
async def test_chaos_broker_transient_failure_resilience() -> None:
    mock_client = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_client)

    task_id = uuid4()
    envelope = TaskEnvelope(
        task_id=task_id,
        tenant_id="tenant-chaos",
        task_type="resilient_publish",
        queue="chaos-stream",
    )

    original_xadd = mock_client.xadd
    call_tracker = {"attempts": 0}

    async def flaky_xadd(*args: object, **kwargs: object) -> str:
        call_tracker["attempts"] += 1
        if call_tracker["attempts"] == 1:
            raise ConnectionError("Redis cluster connection refused")
        return await original_xadd(*args, **kwargs)

    mock_client.xadd = flaky_xadd

    published_id = None
    for _ in range(2):
        try:
            published_id = await adapter.publish("chaos-stream", envelope)
            break
        except ConnectionError:
            await asyncio.sleep(0.05)

    assert published_id is not None
    assert call_tracker["attempts"] == 2


@pytest.mark.asyncio
async def test_chaos_dual_scheduler_advisory_lock_race() -> None:
    lock_key = 887711
    results: list[bool] = []

    async with session_scope() as session1:
        sched_repo1 = ScheduleRepository(session1)
        res1 = await sched_repo1.acquire_advisory_lock(lock_key)
        results.append(res1)

        async with session_scope() as session2:
            sched_repo2 = ScheduleRepository(session2)
            res2 = await sched_repo2.acquire_advisory_lock(lock_key)
            results.append(res2)

    assert results[0] is True
    assert results[1] is False


@pytest.mark.asyncio
async def test_chaos_clock_skew_monotonic_safety() -> None:
    now_utc = datetime.now(UTC)
    drifted_past = now_utc - timedelta(seconds=12)
    drifted_future = now_utc + timedelta(seconds=8)

    runs, next_run = evaluate_misfires(
        cron_expression="* * * * *",
        interval_seconds=None,
        timezone_name="UTC",
        scheduled_run_at=drifted_past,
        now_utc=drifted_future,
        misfire_policy=MisfirePolicy.COALESCING,
    )
    assert len(runs) >= 1
    assert next_run is not None
    assert next_run >= now_utc

    policy = RetryPolicy(
        initial_interval_seconds=2.0,
        backoff_factor=2.0,
        jitter_strategy=JitterStrategy.NONE,
    )
    delay1 = policy.compute_backoff_seconds(1)
    delay2 = policy.compute_backoff_seconds(2)
    assert delay1 >= 0.0
    assert delay2 >= delay1

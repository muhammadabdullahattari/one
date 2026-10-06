import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from src.application.outbox_publisher import OutboxPublisher
from src.application.task_service import TaskLifecycleService
from src.core.constants import MisfirePolicy, TaskStatus
from src.domain.entities import DLQEntry, Queue, Schedule, Task, TaskOutbox
from src.domain.task_registry import global_task_registry
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.outbox_repository import OutboxRepository
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope
from src.scheduler.daemon import SchedulerDaemon
from src.worker.runtime import WorkerRuntime


@pytest.mark.asyncio
async def test_st_001_happy_path_async_task_execution() -> None:
    queue_name = f"st01-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    @global_task_registry.task(name=f"math_multiply_{queue_name}", queue=queue_name)
    async def math_multiply(a: int, b: int) -> dict[str, int]:
        return {"result": a * b}

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type=f"math_multiply_{queue_name}",
        payload={"a": 6, "b": 7},
        queue=queue_name,
        tenant_id="tenant-st001",
    )
    assert task.status == TaskStatus.PENDING

    publisher = OutboxPublisher(batch_size=20)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"worker-{uuid4().hex[:6]}", queues=[queue_name], concurrency=2
    )
    messages = await worker.broker.consume(
        queue=queue_name, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages) == 1
    await worker._process_message(messages[0])

    completed = await task_service.get_task(task.task_id)
    assert completed is not None
    assert completed.status == TaskStatus.SUCCEEDED
    assert completed.result == {"result": 42}


@pytest.mark.asyncio
async def test_st_002_automatic_retry_on_transient_error() -> None:
    queue_name = f"st02-q-{uuid4().hex[:6]}"
    attempts_tracker = {"count": 0}

    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    @global_task_registry.task(name=f"flaky_call_{queue_name}", queue=queue_name, max_retries=3)
    async def flaky_call() -> dict[str, str]:
        attempts_tracker["count"] += 1
        if attempts_tracker["count"] == 1:
            raise ConnectionError("Transient network failure")
        return {"status": "ok"}

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type=f"flaky_call_{queue_name}",
        payload={},
        queue=queue_name,
        tenant_id="tenant-st002",
        max_attempts=3,
    )

    publisher = OutboxPublisher(batch_size=20)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"worker-{uuid4().hex[:6]}", queues=[queue_name], concurrency=2
    )
    messages = await worker.broker.consume(
        queue=queue_name, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages) == 1

    await worker._process_message(messages[0])

    failed_first = await task_service.get_task(task.task_id)
    assert failed_first is not None
    assert failed_first.status in (TaskStatus.RETRY_WAIT, TaskStatus.QUEUED)

    messages_retry = await worker.broker.consume(
        queue=queue_name, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages_retry) == 1
    await worker._process_message(messages_retry[0])

    succeeded = await task_service.get_task(task.task_id)
    assert succeeded is not None
    assert succeeded.status == TaskStatus.SUCCEEDED
    assert attempts_tracker["count"] == 2


@pytest.mark.asyncio
async def test_st_003_max_retries_exhaustion_routes_to_dlq() -> None:
    queue_name = f"st03-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    @global_task_registry.task(name=f"always_failing_{queue_name}", queue=queue_name, max_retries=1)
    async def always_failing() -> None:
        raise RuntimeError("Permanent failure for test")

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type=f"always_failing_{queue_name}",
        payload={},
        queue=queue_name,
        tenant_id="tenant-st003",
        max_attempts=1,
    )

    publisher = OutboxPublisher(batch_size=20)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"worker-{uuid4().hex[:6]}", queues=[queue_name], concurrency=2
    )
    messages = await worker.broker.consume(
        queue=queue_name, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages) == 1

    await worker._process_message(messages[0])

    failed_task = await task_service.get_task(task.task_id)
    assert failed_task is not None
    assert failed_task.status == TaskStatus.FAILED

    async with session_scope() as session:
        dlq_repo = DLQRepository(session)
        dlq_entry = await dlq_repo.create_entry(
            DLQEntry(
                task_id=task.task_id,
                tenant_id="tenant-st003",
                reason="Max retries exhausted",
                error_class="RuntimeError",
            )
        )
        assert dlq_entry.task_id == task.task_id
        saved_dlq = await dlq_repo.get_by_task_id(task.task_id)
        assert saved_dlq is not None
        assert saved_dlq.error_class == "RuntimeError"


@pytest.mark.asyncio
async def test_st_004_non_retryable_fatal_error_immediate_dlq() -> None:
    queue_name = f"st04-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    @global_task_registry.task(name=f"fatal_task_{queue_name}", queue=queue_name)
    async def fatal_task() -> None:
        raise TypeError("Fatal TypeError unrecoverable")

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type=f"fatal_task_{queue_name}",
        payload={},
        queue=queue_name,
        tenant_id="tenant-st004",
        max_attempts=5,
    )

    publisher = OutboxPublisher(batch_size=20)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"worker-{uuid4().hex[:6]}", queues=[queue_name], concurrency=2
    )
    messages = await worker.broker.consume(
        queue=queue_name, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages) == 1

    await worker._process_message(messages[0])

    failed = await task_service.get_task(task.task_id)
    assert failed is not None
    assert failed.status in (TaskStatus.FAILED, TaskStatus.RETRY_WAIT)


@pytest.mark.asyncio
async def test_st_005_deduplication_via_idempotency_key() -> None:
    queue_name = f"st05-q-{uuid4().hex[:6]}"
    idem_key = f"key-{uuid4().hex}"

    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    task_service = TaskLifecycleService()
    first_task = await task_service.submit_task(
        task_type="any_task_idem",
        payload={"invoice_id": 9988},
        queue=queue_name,
        tenant_id="tenant-st005",
        idempotency_key=idem_key,
    )

    second_task = await task_service.submit_task(
        task_type="any_task_idem",
        payload={"invoice_id": 9988},
        queue=queue_name,
        tenant_id="tenant-st005",
        idempotency_key=idem_key,
    )

    assert first_task.task_id == second_task.task_id


@pytest.mark.asyncio
async def test_st_006_task_cancellation_in_queued_state() -> None:
    queue_name = f"st06-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type="cancellable_task",
        payload={"test": 1},
        queue=queue_name,
        tenant_id="tenant-st006",
    )

    cancelled = await task_service.cancel_task(task.task_id, reason="Admin cancelled")
    assert cancelled.status == TaskStatus.CANCELLED

    reloaded = await task_service.get_task(task.task_id)
    assert reloaded is not None
    assert reloaded.status == TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_st_007_task_cancellation_in_running_state() -> None:
    task_id = uuid4()
    now = datetime.now(UTC)
    async with session_scope() as session:
        task_repo = TaskRepository(session)
        await task_repo.create_task(
            Task(
                task_id=task_id,
                tenant_id="tenant-st007",
                task_type="running_cancellable",
                queue="default",
                status=TaskStatus.RUNNING,
                started_at=now,
            )
        )

    task_service = TaskLifecycleService()
    cancelled = await task_service.cancel_task(task_id, reason="Terminated mid-flight")
    assert cancelled.status == TaskStatus.CANCELLED
    assert cancelled.status_reason == "Terminated mid-flight"


@pytest.mark.asyncio
async def test_st_008_task_execution_timeout_enforcement() -> None:
    queue_name = f"st08-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    @global_task_registry.task(
        name=f"sleepy_task_{queue_name}", queue=queue_name, timeout_seconds=1
    )
    async def sleepy_task() -> None:
        await asyncio.sleep(2.0)

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type=f"sleepy_task_{queue_name}",
        payload={},
        queue=queue_name,
        tenant_id="tenant-st008",
        timeout_seconds=1,
    )

    publisher = OutboxPublisher(batch_size=20)
    await publisher.publish_batch()

    worker = WorkerRuntime(
        worker_id=f"worker-{uuid4().hex[:6]}", queues=[queue_name], concurrency=2
    )
    messages = await worker.broker.consume(
        queue=queue_name, worker_id=worker.worker_id, batch_size=1
    )
    assert len(messages) == 1

    await worker._process_message(messages[0])

    failed = await task_service.get_task(task.task_id)
    assert failed is not None
    assert failed.status in (TaskStatus.FAILED, TaskStatus.RETRY_WAIT, TaskStatus.QUEUED)
    assert "TaskTimeoutError" in (failed.status_reason or "")


@pytest.mark.asyncio
async def test_st_009_anti_starvation_queue_fairness() -> None:
    q_high = f"fair-high-{uuid4().hex[:6]}"
    q_low = f"fair-low-{uuid4().hex[:6]}"

    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(Queue(queue_name=q_high, broker_backend="native"))
        await queue_repo.create_or_update_queue(Queue(queue_name=q_low, broker_backend="native"))

    task_service = TaskLifecycleService()
    for _ in range(3):
        await task_service.submit_task(
            task_type="high_job", queue=q_high, priority=1, tenant_id="tenant-fair"
        )

    await task_service.submit_task(
        task_type="low_job", queue=q_low, priority=9, tenant_id="tenant-fair"
    )

    worker = WorkerRuntime(
        worker_id=f"worker-{uuid4().hex[:6]}", queues=[q_high, q_low], concurrency=10
    )
    consumed_low = await worker.broker.consume(
        queue=q_low, worker_id=worker.worker_id, batch_size=1
    )
    assert len(consumed_low) == 1
    assert consumed_low[0].envelope.task_type == "low_job"


@pytest.mark.asyncio
async def test_st_010_per_tenant_concurrency_limits() -> None:
    tenant_id = f"tenant-{uuid4().hex[:6]}"
    now = datetime.now(UTC)
    task_ids = [uuid4() for _ in range(3)]

    async with session_scope() as session:
        task_repo = TaskRepository(session)
        for tid in task_ids:
            await task_repo.create_task(
                Task(
                    task_id=tid,
                    tenant_id=tenant_id,
                    task_type="heavy_computation",
                    queue="default",
                    status=TaskStatus.RUNNING,
                    started_at=now,
                )
            )

        running_tasks = await task_repo.list_tasks(tenant_id=tenant_id, status=TaskStatus.RUNNING)
        assert len(running_tasks) == 3

        await task_repo.complete_task(
            task_id=task_ids[0], attempt_id=None, result_data={"done": True}
        )

        active_remaining = await task_repo.list_tasks(
            tenant_id=tenant_id, status=TaskStatus.RUNNING
        )
        assert len(active_remaining) == 2


@pytest.mark.asyncio
async def test_st_011_cron_schedule_task_generation() -> None:
    schedule_id = uuid4()
    past_due = datetime.now(UTC) - timedelta(minutes=10)
    schedule = Schedule(
        schedule_id=schedule_id,
        tenant_id="tenant-cron",
        task_type="generate_nightly_backup",
        queue="default",
        cron_expression="* * * * *",
        enabled=True,
        next_run_at=past_due,
        misfire_policy=MisfirePolicy.COALESCING,
    )

    async with session_scope() as session:
        sched_repo = ScheduleRepository(session)
        await sched_repo.create_schedule(schedule)

    daemon = SchedulerDaemon()
    await daemon.tick()

    async with session_scope() as session:
        sched_repo = ScheduleRepository(session)
        updated_schedule = await sched_repo.get_by_id(schedule_id)
        assert updated_schedule is not None
        assert updated_schedule.last_run_at is not None
        assert updated_schedule.next_run_at is not None
        assert updated_schedule.next_run_at > past_due


@pytest.mark.asyncio
async def test_st_012_interval_schedule_with_misfire_policy() -> None:
    schedule_id = uuid4()
    past_due = datetime.now(UTC) - timedelta(hours=2)
    schedule = Schedule(
        schedule_id=schedule_id,
        tenant_id="tenant-interval",
        task_type="ping_external_api",
        queue="default",
        interval_seconds=60,
        enabled=True,
        next_run_at=past_due,
        misfire_policy=MisfirePolicy.SKIP,
    )

    async with session_scope() as session:
        sched_repo = ScheduleRepository(session)
        await sched_repo.create_schedule(schedule)

    daemon = SchedulerDaemon()
    await daemon.tick()

    async with session_scope() as session:
        sched_repo = ScheduleRepository(session)
        updated = await sched_repo.get_by_id(schedule_id)
        assert updated is not None
        assert updated.last_run_at is not None
        assert updated.next_run_at is not None


@pytest.mark.asyncio
async def test_st_013_outbox_reliable_delivery_guarantee() -> None:
    task_id = uuid4()
    task = Task(
        task_id=task_id,
        tenant_id="tenant-outbox",
        task_type="reliable_transaction",
        queue="default",
        payload={"msg": "atomic"},
    )
    outbox = TaskOutbox(
        task_id=task_id,
        event_type="task.created",
        payload={"msg": "atomic"},
    )

    async with session_scope() as session:
        task_repo = TaskRepository(session)
        await task_repo.create_with_outbox(task, outbox)

    async with session_scope() as session:
        outbox_repo = OutboxRepository(session)
        stored_outbox = await outbox_repo.get_by_task_id(task_id)
        assert stored_outbox is not None
        assert stored_outbox.published_at is None
        await outbox_repo.mark_published(stored_outbox.outbox_id)

    async with session_scope() as session:
        outbox_repo = OutboxRepository(session)
        delivered_outbox = await outbox_repo.get_by_task_id(task_id)
        assert delivered_outbox is not None
        assert delivered_outbox.published_at is not None


@pytest.mark.asyncio
async def test_st_014_dlq_replay_admin_workflow() -> None:
    queue_name = f"st14-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    task_id = uuid4()
    dlq_id = uuid4()

    async with session_scope() as session:
        task_repo = TaskRepository(session)
        dlq_repo = DLQRepository(session)

        await task_repo.create_task(
            Task(
                task_id=task_id,
                tenant_id="tenant-st014",
                task_type="repayable_task",
                queue=queue_name,
                status=TaskStatus.FAILED,
                status_reason="Simulated failure",
            )
        )
        await dlq_repo.create_entry(
            DLQEntry(
                dlq_id=dlq_id,
                task_id=task_id,
                tenant_id="tenant-st014",
                reason="Simulated failure",
                error_class="SimulatedError",
            )
        )

    task_service = TaskLifecycleService()
    replayed_task = await task_service.retry_task(task_id=task_id, reset_attempts=True)
    assert replayed_task.status == TaskStatus.QUEUED
    assert replayed_task.attempt_count == 0

    async with session_scope() as session:
        dlq_repo = DLQRepository(session)
        await dlq_repo.mark_replayed(dlq_id)
        entry = await dlq_repo.get_by_id(dlq_id)
        assert entry is not None
        assert entry.replay_count >= 1
        assert entry.last_replayed_at is not None


@pytest.mark.asyncio
async def test_st_015_multi_tenant_data_isolation() -> None:
    tenant_a = f"tenant-a-{uuid4().hex[:6]}"
    tenant_b = f"tenant-b-{uuid4().hex[:6]}"

    task_a_id = uuid4()
    task_b_id = uuid4()

    async with session_scope() as session:
        task_repo = TaskRepository(session)
        await task_repo.create_task(
            Task(
                task_id=task_a_id,
                tenant_id=tenant_a,
                task_type="tenant_a_task",
                queue="default",
            )
        )
        await task_repo.create_task(
            Task(
                task_id=task_b_id,
                tenant_id=tenant_b,
                task_type="tenant_b_task",
                queue="default",
            )
        )

        tasks_a = await task_repo.list_tasks(tenant_id=tenant_a)
        assert all(t.tenant_id == tenant_a for t in tasks_a)
        assert any(t.task_id == task_a_id for t in tasks_a)
        assert not any(t.task_id == task_b_id for t in tasks_a)

        tasks_b = await task_repo.list_tasks(tenant_id=tenant_b)
        assert all(t.tenant_id == tenant_b for t in tasks_b)
        assert any(t.task_id == task_b_id for t in tasks_b)
        assert not any(t.task_id == task_a_id for t in tasks_b)

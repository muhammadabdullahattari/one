from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from src.core.constants import TaskStatus
from src.domain.entities import Queue, Schedule, Task, TaskOutbox, Worker
from src.persistence.repositories.outbox_repository import OutboxRepository
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.repositories.worker_repository import WorkerRepository
from src.persistence.session import session_scope


@pytest.mark.asyncio
async def test_create_task_with_outbox_atomic() -> None:
    task_id = uuid4()
    task = Task(
        task_id=task_id,
        tenant_id="tenant-test",
        task_type="test_task_create",
        queue="default",
        priority=3,
        payload={"order_id": "ORD-1234"},
    )
    outbox = TaskOutbox(
        task_id=task_id, event_type="task.created", payload={"order_id": "ORD-1234"}
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
        assert saved_task.priority == 3
        assert saved_task.payload == {"order_id": "ORD-1234"}
        undelivered = await outbox_repo.get_undelivered()
        outbox_entry = next((o for o in undelivered if o.task_id == task_id), None)
        assert outbox_entry is not None
        assert outbox_entry.task_id == task_id
        assert outbox_entry.event_type == "task.created"


@pytest.mark.asyncio
async def test_task_claim_and_completion_lifecycle() -> None:
    test_queue = f"repo-q-{uuid4().hex[:6]}"
    task_id = uuid4()
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=test_queue, broker_backend="native")
        )
        task = Task(
            task_id=task_id,
            tenant_id="tenant-test",
            task_type="test_task_claim",
            queue=test_queue,
            priority=1,
            status=TaskStatus.QUEUED,
            payload={"data": "test"},
        )
        outbox = TaskOutbox(task_id=task_id, payload={"data": "test"})
        task_repo = TaskRepository(session)
        await task_repo.create_with_outbox(task, outbox)
    async with session_scope() as session:
        task_repo = TaskRepository(session)
        claim_result = await task_repo.claim_next(
            queue=test_queue, worker_id="worker-test-1", lease_seconds=120
        )
        assert claim_result is not None
        claimed_task, attempt = claim_result
        assert claimed_task.task_id == task_id
        assert claimed_task.status == TaskStatus.RUNNING
        assert claimed_task.current_worker_id == "worker-test-1"
        assert attempt.attempt_number == 1
        assert attempt.worker_id == "worker-test-1"
    async with session_scope() as session:
        task_repo = TaskRepository(session)
        completed_task = await task_repo.complete_task(
            task_id=task_id,
            attempt_id=attempt.attempt_id,
            result_data={"success": True, "processed_items": 42},
        )
        assert completed_task is not None
        assert completed_task.status == TaskStatus.SUCCEEDED
        assert completed_task.result == {"success": True, "processed_items": 42}
        assert completed_task.finished_at is not None


@pytest.mark.asyncio
async def test_worker_registration_and_heartbeat() -> None:
    worker = Worker(
        worker_id=f"worker-node-{uuid4().hex[:6]}",
        hostname="cluster-node-1.internal",
        process_id=9876,
        concurrency=16,
    )
    async with session_scope() as session:
        worker_repo = WorkerRepository(session)
        await worker_repo.register_worker(worker)
    async with session_scope() as session:
        worker_repo = WorkerRepository(session)
        workers = await worker_repo.list_workers(status="active")
        registered = next((w for w in workers if w.worker_id == worker.worker_id), None)
        assert registered is not None
        assert registered.concurrency == 16
        assert registered.status == "active"
        await worker_repo.record_heartbeat(worker.worker_id, active_slots=4)
    async with session_scope() as session:
        worker_repo = WorkerRepository(session)
        workers = await worker_repo.list_workers()
        updated = next((w for w in workers if w.worker_id == worker.worker_id), None)
        assert updated is not None
        assert updated.active_slots == 4


@pytest.mark.asyncio
async def test_scheduler_due_query_and_advisory_lock() -> None:
    schedule_id = uuid4()
    past_due = datetime.now(UTC) - timedelta(minutes=5)
    schedule = Schedule(
        schedule_id=schedule_id,
        task_type="periodic_report",
        queue="default",
        cron_expression="0 * * * *",
        enabled=True,
        next_run_at=past_due,
    )
    async with session_scope() as session:
        sched_repo = ScheduleRepository(session)
        await sched_repo.create_schedule(schedule)
        lock_acquired = await sched_repo.acquire_advisory_lock(lock_key=991122)
        assert lock_acquired is True
        now = datetime.now(UTC)
        due_list = await sched_repo.get_due_schedules(now)
        due_item = next((s for s in due_list if s.schedule_id == schedule_id), None)
        assert due_item is not None
        assert due_item.task_type == "periodic_report"

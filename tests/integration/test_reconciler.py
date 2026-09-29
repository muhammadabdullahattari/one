from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from src.application.reconciler import Reconciler
from src.core.constants import TaskStatus
from src.domain.entities import Task, TaskOutbox
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope


@pytest.mark.asyncio
async def test_reconciler_recovers_expired_lease_crashed_worker() -> None:
    task_id = uuid4()
    past_lease = datetime.now(UTC) - timedelta(minutes=10)
    task = Task(
        task_id=task_id,
        task_type="crashed_worker_job",
        queue="default",
        status=TaskStatus.RUNNING,
        current_worker_id="crashed-worker-node-99",
        lease_expires_at=past_lease,
        max_attempts=3,
        attempt_count=1,
    )
    outbox = TaskOutbox(task_id=task_id)
    async with session_scope() as session:
        repo = TaskRepository(session)
        await repo.create_with_outbox(task, outbox)
    reconciler = Reconciler()
    stats = await reconciler.reconcile()
    assert stats["recovered_leases"] >= 1
    async with session_scope() as session:
        repo = TaskRepository(session)
        recovered_task = await repo.get_by_id(task_id)
        assert recovered_task is not None
        assert recovered_task.status == TaskStatus.RETRY_WAIT
        assert "Worker crashed-worker-node-99 lease expired" in (recovered_task.status_reason or "")

from uuid import uuid4

import pytest
from src.broker.core.envelope import TaskEnvelope
from src.broker.native.adapter import NativeBrokerAdapter
from src.core.constants import TaskStatus
from src.domain.entities import Queue, Task, TaskOutbox
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope


@pytest.mark.asyncio
async def test_native_broker_publish_and_consume() -> None:
    adapter = NativeBrokerAdapter()
    assert adapter.backend_name == "native"
    queue_name = f"native-q-{uuid4().hex[:6]}"
    task_id = uuid4()
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )
        task = Task(task_id=task_id, task_type="broker_test_task", queue=queue_name, priority=2)
        outbox = TaskOutbox(task_id=task_id, payload={})
        repo = TaskRepository(session)
        await repo.create_with_outbox(task, outbox)
    envelope = TaskEnvelope(
        task_id=task_id, task_type="broker_test_task", queue=queue_name, priority=2
    )
    msg_id = await adapter.publish(queue_name, envelope)
    assert msg_id == str(task_id)
    messages = await adapter.consume(queue_name, worker_id="worker-native-1", batch_size=1)
    assert len(messages) == 1
    consumed_msg = messages[0]
    assert consumed_msg.envelope.task_id == task_id
    assert consumed_msg.envelope.task_type == "broker_test_task"
    stats = await adapter.stats(queue_name)
    assert stats.backend_name == "native"
    assert stats.queue == queue_name
    assert stats.is_healthy is True
    await adapter.acknowledge(queue_name, msg_id)


@pytest.mark.asyncio
async def test_native_broker_extend_lease_and_dead_letter() -> None:
    adapter = NativeBrokerAdapter()
    queue_name = f"native-q-{uuid4().hex[:6]}"
    task_id = uuid4()
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )
        task = Task(
            task_id=task_id, task_type="lease_test", queue=queue_name, status=TaskStatus.RUNNING
        )
        outbox = TaskOutbox(task_id=task_id)
        repo = TaskRepository(session)
        await repo.create_with_outbox(task, outbox)
    await adapter.extend_lease(str(task_id), duration=600)
    await adapter.dead_letter(str(task_id), reason="Corrupted input payload")
    async with session_scope() as session:
        repo = TaskRepository(session)
        saved = await repo.get_by_id(task_id)
        assert saved is not None
        assert saved.status == TaskStatus.DEAD
        assert "Corrupted input payload" in (saved.status_reason or "")

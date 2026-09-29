from uuid import uuid4

import pytest
from src.application.outbox_publisher import OutboxPublisher
from src.application.task_service import TaskLifecycleService
from src.core.constants import TaskStatus
from src.domain.entities import Queue
from src.domain.task_registry import global_task_registry
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.session import session_scope
from src.worker.runtime import WorkerRuntime


@pytest.mark.asyncio
async def test_full_task_lifecycle_end_to_end() -> None:
    test_queue = f"e2e-q-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=test_queue, broker_backend="native")
        )

    @global_task_registry.task(name="calculate_invoice_total", queue=test_queue)
    async def calculate_invoice_total(subtotal: float, tax_rate: float) -> dict[str, float]:
        return {"total": round(subtotal * (1.0 + tax_rate), 2)}

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type="calculate_invoice_total",
        payload={"subtotal": 100.0, "tax_rate": 0.15},
        queue=test_queue,
        priority=3,
        tenant_id="tenant-acme",
    )
    assert task.status == TaskStatus.PENDING
    publisher = OutboxPublisher(batch_size=10)
    published = await publisher.publish_batch()
    assert published >= 1
    worker = WorkerRuntime(worker_id="test-worker-e2e", queues=[test_queue], concurrency=2)
    messages = await worker.broker.consume(
        queue=test_queue, worker_id="test-worker-e2e", batch_size=1
    )
    assert len(messages) == 1
    target_msg = messages[0]
    assert target_msg.envelope.task_id == task.task_id
    await worker._process_message(target_msg)
    completed_task = await task_service.get_task(task.task_id)
    assert completed_task is not None
    assert completed_task.status == TaskStatus.SUCCEEDED
    assert completed_task.result == {"total": 115.0}

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import pytest
from src.broker.adapters.redis.adapter import RedisBrokerAdapter
from src.broker.core.adapter import BrokerAdapter
from src.broker.core.envelope import TaskEnvelope
from src.broker.native.adapter import NativeBrokerAdapter
from src.domain.entities import Queue, Task, TaskOutbox
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.session import session_scope

from tests.broker_conformance.mock_redis import MockRedisStreamsClient


@pytest.fixture
async def native_broker() -> BrokerAdapter:
    return NativeBrokerAdapter()


@pytest.fixture
async def redis_broker() -> AsyncGenerator[BrokerAdapter]:
    mock_client: Any = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_client)
    yield adapter
    await adapter.close()


@pytest.fixture(params=["native", "redis"])
async def broker(
    request: pytest.FixtureRequest,
    native_broker: BrokerAdapter,
    redis_broker: BrokerAdapter,
) -> BrokerAdapter:
    if request.param == "native":
        return native_broker
    return redis_broker


async def _create_db_task_if_native(broker: BrokerAdapter, task_id: Any, queue: str) -> None:
    if broker.backend_name == "native":
        async with session_scope() as session:
            queue_repo = QueueRepository(session)
            await queue_repo.create_or_update_queue(
                Queue(queue_name=queue, broker_backend="native")
            )
            task_repo = TaskRepository(session)
            task = Task(
                task_id=task_id,
                tenant_id="tenant-conformance",
                task_type="test_conformance_task",
                queue=queue,
                priority=7,
                payload={"order_id": 12345},
                timeout_seconds=120,
                max_attempts=5,
            )
            outbox = TaskOutbox(task_id=task_id, payload={"order_id": 12345})
            await task_repo.create_with_outbox(task, outbox)


async def test_broker_health_check_conformance(broker: BrokerAdapter) -> None:
    is_healthy = await broker.health_check()
    assert is_healthy is True


async def test_broker_publish_and_consume_conformance(broker: BrokerAdapter) -> None:
    queue = f"conf-queue-{uuid4().hex[:8]}"
    task_id = uuid4()
    await _create_db_task_if_native(broker, task_id, queue)
    envelope = TaskEnvelope(
        task_id=task_id,
        tenant_id="tenant-conformance",
        task_type="test_conformance_task",
        queue=queue,
        priority=7,
        payload={"order_id": 12345},
        timeout_seconds=120,
        max_attempts=5,
    )
    published_msg_id = await broker.publish(queue, envelope)
    assert published_msg_id is not None
    assert len(str(published_msg_id)) > 0
    messages = await broker.consume(queue=queue, worker_id="worker-test-1", batch_size=1)
    assert len(messages) == 1
    msg = messages[0]
    assert msg.queue == queue
    assert msg.envelope.task_id == task_id
    assert msg.envelope.task_type == "test_conformance_task"
    assert msg.envelope.priority == 7
    assert msg.envelope.payload == {"order_id": 12345}


async def test_broker_acknowledge_conformance(broker: BrokerAdapter) -> None:
    queue = f"conf-ack-{uuid4().hex[:8]}"
    task_id = uuid4()
    await _create_db_task_if_native(broker, task_id, queue)
    envelope = TaskEnvelope(
        task_id=task_id,
        task_type="ack_task",
        queue=queue,
    )
    await broker.publish(queue, envelope)
    messages = await broker.consume(queue=queue, worker_id="worker-ack", batch_size=1)
    assert len(messages) == 1
    msg = messages[0]
    await broker.acknowledge(queue=queue, message_id=msg.message_id)


async def test_broker_nack_conformance(broker: BrokerAdapter) -> None:
    queue = f"conf-nack-{uuid4().hex[:8]}"
    task_id = uuid4()
    await _create_db_task_if_native(broker, task_id, queue)
    envelope = TaskEnvelope(
        task_id=task_id,
        task_type="nack_task",
        queue=queue,
    )
    await broker.publish(queue, envelope)
    messages = await broker.consume(queue=queue, worker_id="worker-nack", batch_size=1)
    assert len(messages) == 1
    msg = messages[0]
    await broker.nack(queue=queue, message_id=msg.message_id, requeue=True)


async def test_broker_extend_lease_conformance(broker: BrokerAdapter) -> None:
    queue = f"conf-lease-{uuid4().hex[:8]}"
    task_id = uuid4()
    await _create_db_task_if_native(broker, task_id, queue)
    envelope = TaskEnvelope(
        task_id=task_id,
        task_type="lease_task",
        queue=queue,
    )
    await broker.publish(queue, envelope)
    messages = await broker.consume(queue=queue, worker_id="worker-lease", batch_size=1)
    assert len(messages) == 1
    msg = messages[0]
    await broker.extend_lease(message_id=msg.message_id, duration=60)


async def test_broker_dead_letter_conformance(broker: BrokerAdapter) -> None:
    queue = f"conf-dlq-{uuid4().hex[:8]}"
    task_id = uuid4()
    await _create_db_task_if_native(broker, task_id, queue)
    envelope = TaskEnvelope(
        task_id=task_id,
        task_type="dead_letter_task",
        queue=queue,
    )
    await broker.publish(queue, envelope)
    messages = await broker.consume(queue=queue, worker_id="worker-dlq", batch_size=1)
    assert len(messages) == 1
    msg = messages[0]
    await broker.dead_letter(message_id=msg.message_id, reason="Exceeded maximum attempt ceiling")


async def test_broker_stats_conformance(broker: BrokerAdapter) -> None:
    queue = f"conf-stats-{uuid4().hex[:8]}"
    task_id = uuid4()
    await _create_db_task_if_native(broker, task_id, queue)
    envelope = TaskEnvelope(
        task_id=task_id,
        task_type="stats_task",
        queue=queue,
    )
    await broker.publish(queue, envelope)
    stats = await broker.stats(queue)
    assert stats.queue == queue
    assert stats.backend_name in ["native", "redis"]
    assert stats.depth >= 0
    assert stats.is_healthy is True


async def test_redis_claim_stale_conformance() -> None:
    mock_client: Any = MockRedisStreamsClient()
    adapter = RedisBrokerAdapter(redis_client=mock_client)
    queue = f"conf-stale-{uuid4().hex[:8]}"
    task_id = uuid4()
    envelope = TaskEnvelope(
        task_id=task_id,
        task_type="stale_task",
        queue=queue,
    )
    await adapter.publish(queue, envelope)
    msgs = await adapter.consume(queue=queue, worker_id="dead-worker", batch_size=1)
    assert len(msgs) == 1
    claimed = await adapter.claim_stale(
        queue=queue,
        worker_id="recovering-worker",
        min_idle_time_ms=0,
        count=10,
    )
    assert len(claimed) == 1
    assert claimed[0].envelope.task_id == task_id
    await adapter.close()

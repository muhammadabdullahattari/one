from datetime import UTC, datetime
from uuid import uuid4

import pytest
from src.core.constants import TaskStatus
from src.domain.entities import IdempotencyKey, Task, Worker


def test_task_initialization_defaults() -> None:
    task = Task(task_type="send_email")
    assert task.status == TaskStatus.PENDING
    assert task.priority == 5
    assert task.max_attempts == 3
    assert task.attempt_count == 0
    assert task.version == 1
    assert task.queue == "default"


def test_valid_state_transitions() -> None:
    task = Task(task_type="process_payment")
    assert task.status == TaskStatus.PENDING
    task.transition_to(TaskStatus.QUEUED)
    assert task.status == TaskStatus.QUEUED
    assert task.version == 2
    task.transition_to(TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
    assert task.version == 3
    task.transition_to(TaskStatus.RETRY_WAIT, reason="Transient network error")
    assert task.status == TaskStatus.RETRY_WAIT
    assert task.status_reason == "Transient network error"
    assert task.version == 4
    task.transition_to(TaskStatus.QUEUED)
    assert task.status == TaskStatus.QUEUED
    task.transition_to(TaskStatus.RUNNING)
    assert task.status == TaskStatus.RUNNING
    task.transition_to(TaskStatus.SUCCEEDED)
    assert task.status == TaskStatus.SUCCEEDED


def test_illegal_state_transitions_raise_error() -> None:
    task = Task(task_type="process_order")
    assert task.status == TaskStatus.PENDING
    with pytest.raises(ValueError, match="Illegal task state transition"):
        task.transition_to(TaskStatus.SUCCEEDED)
    task.transition_to(TaskStatus.QUEUED)
    task.transition_to(TaskStatus.RUNNING)
    task.transition_to(TaskStatus.SUCCEEDED)
    with pytest.raises(ValueError, match="Illegal task state transition"):
        task.transition_to(TaskStatus.RUNNING)


def test_dead_letter_replay_transition() -> None:
    task = Task(task_type="sync_inventory")
    task.transition_to(TaskStatus.QUEUED)
    task.transition_to(TaskStatus.RUNNING)
    task.transition_to(TaskStatus.FAILED)
    task.transition_to(TaskStatus.DEAD)
    assert task.status == TaskStatus.DEAD
    with pytest.raises(ValueError, match="Illegal task state transition"):
        task.transition_to(TaskStatus.RUNNING)
    task.transition_to(TaskStatus.QUEUED, reason="Operator replay")
    assert task.status == TaskStatus.QUEUED
    assert task.status_reason == "Operator replay"


def test_worker_entity_heartbeat() -> None:
    worker = Worker(
        worker_id="worker-node-1", hostname="worker-host.local", process_id=12345, concurrency=10
    )
    assert worker.status == "active"
    assert worker.active_slots == 0
    assert worker.queues_json == ["default"]


def test_idempotency_key_entity() -> None:
    now = datetime.now(UTC)
    key = IdempotencyKey(
        scope="orders",
        idempotency_key="order-req-12345",
        task_id=uuid4(),
        request_hash="sha256-hash-abc",
        expires_at=now,
    )
    assert key.scope == "orders"
    assert key.idempotency_key == "order-req-12345"

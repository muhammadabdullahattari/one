from typing import Any, cast

import pytest
from src.domain.task_registry import TaskRegistry


def test_task_registration_and_lookup() -> None:
    registry = TaskRegistry()

    @registry.task(name="send_notification", queue="high_priority", priority=2, max_retries=5)
    async def sample_task(user_id: str, message: str) -> bool:
        return True

    task_def = registry.get("send_notification")
    assert task_def is not None
    assert task_def.name == "send_notification"
    assert task_def.queue == "high_priority"
    assert task_def.priority == 2
    assert task_def.max_retries == 5
    assert task_def.is_async is True


def test_unregistered_task_lookup_raises_error() -> None:
    registry = TaskRegistry()
    with pytest.raises(ValueError, match="Unregistered task_type 'malicious_code'"):
        registry.get_or_raise("malicious_code")


def test_synchronous_task_handler_registration() -> None:
    registry = TaskRegistry()

    @registry.task(name="sync_compute")
    def sync_task(data: list[int]) -> int:
        return sum(data)

    task_def = registry.get("sync_compute")
    assert task_def is not None
    assert task_def.is_async is False


def test_invalid_handler_raises_error() -> None:
    registry = TaskRegistry()
    with pytest.raises(ValueError, match="must be a callable"):
        registry.register("invalid_task", cast(Any, "not-a-callable"))

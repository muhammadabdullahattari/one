import pytest
from src.domain.task_registry import global_task_registry
from src.worker.executor import TaskExecutor

from task_engine import (
    AsyncResult,
    TaskContext,
    TaskEngine,
    TaskEngineClient,
    task,
)


@pytest.mark.asyncio
async def test_srs_quickstart_acceptance_sequence() -> None:
    engine = TaskEngine(direct_mode=True, tenant_id="quickstart_tenant")
    assert engine.client is not None

    @task(name="notifications.send_welcome", queue="notifications", priority=3, max_attempts=5)
    async def send_welcome(payload: dict[str, str], context: TaskContext) -> dict[str, str]:
        assert context.task_id is not None
        assert context.queue == "notifications"
        return {"status": "sent", "recipient": payload["email"]}

    assert send_welcome.name == "notifications.send_welcome"
    assert send_welcome.queue == "notifications"
    assert send_welcome.priority == 3
    assert send_welcome.max_attempts == 5

    direct_res = await send_welcome(
        {"email": "alice@company.com"},
        TaskContext(task_id="t-1", queue="notifications"),
    )
    assert direct_res == {"status": "sent", "recipient": "alice@company.com"}

    mock_client = TaskEngineClient(direct_mode=True, tenant_id="quickstart_tenant")

    result_promise = await mock_client.submit_async(
        task_type="notifications.send_welcome",
        payload={"email": "bob@company.com"},
        queue="notifications",
        priority=3,
        idempotency_key="user:bob:welcome",
    )

    assert isinstance(result_promise, AsyncResult)
    assert result_promise.task_id is not None
    assert result_promise.state in {"PENDING", "QUEUED"}

    task_data = await mock_client.get_task_async(result_promise.task_id)
    assert task_data["task_type"] == "notifications.send_welcome"
    assert task_data["queue"] == "notifications"
    assert task_data["payload"] == {"email": "bob@company.com"}

    executor = TaskExecutor(registry=global_task_registry)
    ctx = TaskContext(
        task_id=result_promise.task_id,
        idempotency_key="user:bob:welcome",
        queue="notifications",
        attempt=1,
    )
    exec_result = await executor.execute(
        task_type="notifications.send_welcome",
        payload=task_data["payload"],
        timeout_seconds=60,
        context=ctx,
    )

    assert exec_result.success is True
    assert exec_result.result == {"status": "sent", "recipient": "bob@company.com"}


def test_task_engine_decorator_bound_to_instance() -> None:
    engine = TaskEngine(base_url="http://mock-api:8000")

    @engine.task(queue="billing", priority=9, max_retries=2)
    def charge_customer(amount: int, currency: str = "USD") -> str:
        return f"{currency} {amount}"

    assert charge_customer.name == "charge_customer"
    assert charge_customer.queue == "billing"
    assert charge_customer.priority == 9
    assert charge_customer.max_attempts == 2
    assert charge_customer(100, "EUR") == "EUR 100"
    assert charge_customer.client == engine.client

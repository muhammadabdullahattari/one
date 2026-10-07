import uuid

import httpx
import pytest
from src.api.main import app
from src.domain.entities import Queue
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.session import session_scope

from task_engine import AsyncResult, TaskEngineClient, task


@pytest.mark.asyncio
async def test_sdk_client_asgi_integration() -> None:
    queue_name = f"sdk_test_q_{uuid.uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_http:
        client = TaskEngineClient(base_url="http://testserver", tenant_id="default")
        client._async_client = async_http

        result = await client.submit_async(
            task_type="sdk_integration_test",
            payload={"msg": "hello sdk", "amount": 42},
            queue=queue_name,
            priority=7,
        )

        assert isinstance(result, AsyncResult)
        assert result.task_id is not None
        assert result.state in {"PENDING", "QUEUED"}

        task_info = await client.get_task_async(result.task_id)
        assert task_info["task_id"] == result.task_id
        assert task_info["queue"] == queue_name
        assert task_info["priority"] == 7
        assert task_info["payload"] == {"msg": "hello sdk", "amount": 42}

        tasks_list = await client.list_tasks_async(queue=queue_name)
        assert any(t["task_id"] == result.task_id for t in tasks_list)

        sched_res = await client.register_schedule_async(
            name="test_schedule",
            cron_expression="0 12 * * *",
            task_type="sdk_integration_test",
            queue=queue_name,
        )
        assert sched_res["task_type"] == "sdk_integration_test"
        assert sched_res["cron"] == "0 12 * * *"

        cancel_res = await client.cancel_task_async(result.task_id)
        assert cancel_res["status"] == "CANCELLED"

        cancelled_info = await client.get_task_async(result.task_id)
        assert cancelled_info["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_sdk_decorator_integration_with_client() -> None:
    queue_name = f"sdk_dec_q_{uuid.uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    client = TaskEngineClient(direct_mode=True, tenant_id="default")

    @task(name="calc.square", queue=queue_name, priority=8, client=client)
    def square(n: int) -> int:
        return n * n

    assert square(5) == 25

    ar = square.delay(7)
    assert isinstance(ar, AsyncResult)
    assert ar.task_id is not None

    task_data = client.get_task(ar.task_id)
    assert task_data["task_id"] == ar.task_id
    assert task_data["queue"] == queue_name
    assert task_data["status"] in {"PENDING", "QUEUED"}

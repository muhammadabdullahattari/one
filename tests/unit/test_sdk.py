import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.domain.task_registry import TaskRegistry
from src.worker.executor import TaskExecutor
from task_engine.cli import app
from typer.testing import CliRunner

from task_engine import (
    AsyncResult,
    AuthenticationError,
    TaskCancelledError,
    TaskContext,
    TaskEngine,
    TaskEngineClient,
    TaskEngineError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskTimeoutError,
    get_current_context,
    task,
)

runner = CliRunner()


def test_task_engine_init_and_from_env() -> None:
    engine = TaskEngine(
        base_url="http://localhost:8000",
        api_key="test_key",
        tenant_id="tenant_alpha",
    )
    assert engine.client.base_url == "http://localhost:8000"
    assert engine.client.api_key == "test_key"
    assert engine.client.tenant_id == "tenant_alpha"

    with patch.dict(
        "os.environ",
        {
            "TASK_ENGINE_API_URL": "http://api.remote:8000",
            "TASK_ENGINE_API_KEY": "env_api_key",
            "TASK_ENGINE_TENANT_ID": "env_tenant",
        },
    ):
        env_engine = TaskEngine.from_env()
        assert env_engine.client.base_url == "http://api.remote:8000"
        assert env_engine.client.api_key == "env_api_key"
        assert env_engine.client.tenant_id == "env_tenant"


def test_task_decorator_registration_and_direct_call() -> None:
    @task(name="test.math_add", queue="math", priority=3, max_attempts=4, timeout_seconds=45)
    def add(a: int, b: int) -> int:
        return a + b

    assert add.name == "test.math_add"
    assert add.queue == "math"
    assert add.priority == 3
    assert add.max_attempts == 4
    assert add.timeout_seconds == 45
    assert not add.is_async

    result = add(10, 20)
    assert result == 30


@pytest.mark.asyncio
async def test_async_task_decorator_and_direct_call() -> None:
    @task(name="test.async_multiply", queue="math")
    async def multiply(x: int, y: int) -> int:
        return x * y

    assert multiply.is_async
    res = await multiply(6, 7)
    assert res == 42


def test_task_decorator_delay_and_apply_async() -> None:
    mock_client = MagicMock(spec=TaskEngineClient)
    mock_client.submit.return_value = AsyncResult(
        task_id="abc-123",
        client=mock_client,
        initial_data={"status": "QUEUED"},
    )

    @task(name="test.dispatch_job", queue="jobs", client=mock_client)
    def dispatch_job(title: str, count: int) -> str:
        return f"{title}:{count}"

    ar1 = dispatch_job.delay("Report", 5)
    assert ar1.task_id == "abc-123"
    mock_client.submit.assert_called_with(
        task_type="test.dispatch_job",
        payload={"args": ["Report", 5]},
        queue="jobs",
        priority=5,
        max_attempts=3,
        timeout_seconds=300,
        delay_seconds=None,
        idempotency_key=None,
        headers=None,
    )

    ar2 = dispatch_job.apply_async(
        kwargs={"title": "Audit", "count": 10},
        queue="audit_queue",
        priority=9,
        delay_seconds=30,
        idempotency_key="idemp_456",
    )
    assert ar2.task_id == "abc-123"
    mock_client.submit.assert_called_with(
        task_type="test.dispatch_job",
        payload={"title": "Audit", "count": 10},
        queue="audit_queue",
        priority=9,
        max_attempts=3,
        timeout_seconds=300,
        delay_seconds=30,
        idempotency_key="idemp_456",
        headers=None,
    )


def test_task_context_attributes_and_logger() -> None:
    ctx = TaskContext(
        task_id="task-999",
        idempotency_key="key-abc",
        attempt=2,
        queue="urgent",
        priority=8,
        headers={"X-Trace": "trace-123"},
        tenant_id="tenant-x",
    )
    assert ctx.task_id == "task-999"
    assert ctx.idempotency_key == "key-abc"
    assert ctx.attempt == 2
    assert ctx.queue == "urgent"
    assert ctx.priority == 8
    assert ctx.headers == {"X-Trace": "trace-123"}
    assert ctx.tenant_id == "tenant-x"
    assert ctx.logger is not None


@pytest.mark.asyncio
async def test_task_executor_with_srs_appendix_b_signature() -> None:
    registry = TaskRegistry()

    received_context: list[TaskContext] = []
    received_payload: list[dict[str, Any]] = []

    async def srs_handler(payload: dict[str, Any], context: TaskContext) -> dict[str, Any]:
        received_payload.append(payload)
        received_context.append(context)
        ambient_ctx = get_current_context()
        assert ambient_ctx is not None
        assert ambient_ctx.task_id == context.task_id
        return {"processed": True, "to": payload.get("to")}

    registry.register(name="srs.email", handler=srs_handler, is_async=True)

    executor = TaskExecutor(registry=registry)
    ctx = TaskContext(task_id="task-email-1", idempotency_key="welcome:123", attempt=1)

    result = await executor.execute(
        task_type="srs.email",
        payload={"to": "user@example.com"},
        timeout_seconds=10,
        context=ctx,
    )

    assert result.success is True
    assert result.result == {"processed": True, "to": "user@example.com"}
    assert len(received_payload) == 1
    assert received_payload[0] == {"to": "user@example.com"}
    assert len(received_context) == 1
    assert received_context[0].idempotency_key == "welcome:123"
    assert get_current_context() is None


@pytest.mark.asyncio
async def test_task_executor_sync_and_kwargs_unpacking() -> None:
    registry = TaskRegistry()

    def sync_calc(a: int, b: int, ctx: TaskContext) -> int:
        assert ctx.task_id == "task-sync-1"
        return a + b

    registry.register(name="sync.calc", handler=sync_calc, is_async=False)
    executor = TaskExecutor(registry=registry)

    ctx = TaskContext(task_id="task-sync-1")
    result = await executor.execute(
        task_type="sync.calc",
        payload={"a": 15, "b": 25},
        timeout_seconds=5,
        context=ctx,
    )
    assert result.success is True
    assert result.result == 40


@pytest.mark.asyncio
async def test_task_executor_error_and_timeout() -> None:
    registry = TaskRegistry()

    async def failing_task() -> None:
        raise ValueError("Invalid computational argument")

    async def hung_task() -> None:
        await asyncio.sleep(10)

    registry.register(name="failing", handler=failing_task, is_async=True)
    registry.register(name="hung", handler=hung_task, is_async=True)

    executor = TaskExecutor(registry=registry)

    fail_res = await executor.execute("failing", payload={})
    assert fail_res.success is False
    assert fail_res.error_class == "ValueError"
    assert "Invalid computational argument" in (fail_res.error_message or "")

    timeout_res = await executor.execute("hung", payload={}, timeout_seconds=1)
    assert timeout_res.success is False
    assert timeout_res.error_class == "TaskTimeoutError"

    unreg_res = await executor.execute("not_exists", payload={})
    assert unreg_res.success is False
    assert unreg_res.error_class == "UnregisteredTaskError"


def test_async_result_states_and_retrieval() -> None:
    mock_client = MagicMock(spec=TaskEngineClient)
    mock_client.is_terminal_status.side_effect = lambda s: s in {"SUCCEEDED", "FAILED", "CANCELLED"}

    ar = AsyncResult(task_id="task-001", client=mock_client, initial_data={"status": "QUEUED"})
    assert ar.id == "task-001"
    assert ar.state == "QUEUED"
    assert not ar.ready()
    assert not ar.successful()
    assert not ar.failed()

    mock_client.get_task.return_value = {
        "task_id": "task-001",
        "status": "SUCCEEDED",
        "result": {"output": "ok"},
    }
    mock_client.get_result.return_value = {"result_data": {"output": "ok"}}

    res = ar.get(timeout=1.0, interval=0.01)
    assert res == {"output": "ok"}
    assert ar.ready()
    assert ar.successful()

    ar_fail = AsyncResult(task_id="task-002", client=mock_client)
    mock_client.get_task.return_value = {
        "task_id": "task-002",
        "status": "FAILED",
        "error_message": "Network timeout to vendor",
    }
    with pytest.raises(TaskExecutionError) as exc_info:
        ar_fail.get(timeout=1.0, interval=0.01)
    assert "Network timeout to vendor" in str(exc_info.value)

    ar_cancel = AsyncResult(task_id="task-003", client=mock_client)
    mock_client.get_task.return_value = {"task_id": "task-003", "status": "CANCELLED"}
    with pytest.raises(TaskCancelledError):
        ar_cancel.get(timeout=1.0, interval=0.01)

    ar_timeout = AsyncResult(task_id="task-004", client=mock_client)
    mock_client.get_task.return_value = {"task_id": "task-004", "status": "RUNNING"}
    with pytest.raises(TaskTimeoutError):
        ar_timeout.get(timeout=0.05, interval=0.01)


@pytest.mark.asyncio
async def test_async_result_async_get() -> None:
    mock_client = MagicMock(spec=TaskEngineClient)
    mock_client.is_terminal_status.side_effect = lambda s: s in {"SUCCEEDED", "FAILED"}

    mock_client.get_task_async = AsyncMock(
        return_value={
            "task_id": "task-010",
            "status": "SUCCEEDED",
            "result": 12345,
        }
    )
    mock_client.get_result_async = AsyncMock(return_value={"result_data": 12345})

    ar = AsyncResult(task_id="task-010", client=mock_client)
    val = await ar.get_async(timeout=1.0, interval=0.01)
    assert val == 12345


def test_client_headers_and_error_handling() -> None:
    client = TaskEngineClient(
        base_url="http://test-server:9000",
        api_key="secret-token-123",
        tenant_id="custom-tenant",
    )
    headers = client._get_headers()
    assert headers["X-Tenant-Id"] == "custom-tenant"
    assert headers["X-API-Key"] == "secret-token-123"
    assert headers["Authorization"] == "Bearer secret-token-123"

    mock_resp_401 = MagicMock()
    mock_resp_401.status_code = 401
    mock_resp_401.text = "Unauthorized"
    with pytest.raises(AuthenticationError):
        client._handle_response(mock_resp_401)

    mock_resp_404 = MagicMock()
    mock_resp_404.status_code = 404
    mock_resp_404.text = "Not found"
    with pytest.raises(TaskNotFoundError):
        client._handle_response(mock_resp_404)

    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    mock_resp_500.text = "Internal error"
    with pytest.raises(TaskEngineError):
        client._handle_response(mock_resp_500)


def test_cli_subcommands_help() -> None:
    for cmd in ["ui", "migrate", "rollback", "shell", "submit", "status", "version"]:
        result = runner.invoke(app, [cmd, "--help"])
        assert result.exit_code == 0

    sub_result = runner.invoke(app, ["submit", "--help"])
    assert "--payload" in sub_result.output
    assert "--queue" in sub_result.output
    assert "--priority" in sub_result.output
    assert "--idempotency-key" in sub_result.output


def test_cli_worker_and_scheduler_subcommands() -> None:
    w_res = runner.invoke(app, ["worker", "--help"])
    assert w_res.exit_code == 0
    assert "--app" in w_res.output
    assert "--queues" in w_res.output
    assert "--concurrency" in w_res.output

    s_res = runner.invoke(app, ["scheduler", "--help"])
    assert s_res.exit_code == 0
    assert "--app" in s_res.output
    assert "--leader-lock-key" in s_res.output

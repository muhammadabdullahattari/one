import pytest
from src.observability.tracing import get_tracer, init_tracer, trace_span


@pytest.mark.asyncio
async def test_tracing_initialization_and_spans() -> None:
    tracer = init_tracer("test-service")
    assert tracer is not None
    assert get_tracer() == tracer

    async with trace_span(
        "test_task_execution",
        task_id="task-12345",
        attempt_id="att-67890",
        queue="critical",
        worker_id="worker-01",
        attributes={"custom.tag": "val"},
    ) as span:
        assert span is not None
        assert span.is_recording() is not None

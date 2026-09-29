import pytest
from pydantic import ValidationError
from src.api.schemas.common import ErrorDetail, ErrorResponse
from src.api.schemas.queues import QueueCreateRequest
from src.api.schemas.schedules import ScheduledJobCreateRequest
from src.api.schemas.tasks import TaskSubmitRequest
from src.core.constants import MisfirePolicy


def test_task_submit_request_valid() -> None:
    req = TaskSubmitRequest(
        task_type="process_order",
        payload={"order_id": 12345, "amount": 99.99},
        queue="payments",
        priority=8,
        max_attempts=5,
        timeout_seconds=600,
        delay_seconds=30,
        idempotency_key="order-12345-submit",
    )
    assert req.task_type == "process_order"
    assert req.priority == 8
    assert req.queue == "payments"
    assert req.delay_seconds == 30


def test_task_submit_request_priority_and_timeout_bounds() -> None:
    with pytest.raises(ValidationError):
        TaskSubmitRequest(task_type="test", priority=11)
    with pytest.raises(ValidationError):
        TaskSubmitRequest(task_type="test", priority=0)
    with pytest.raises(ValidationError):
        TaskSubmitRequest(task_type="test", timeout_seconds=0)


def test_scheduled_job_recurrence_validation() -> None:
    req_cron = ScheduledJobCreateRequest(
        task_type="generate_report", cron="0 0 * * *", misfire_policy=MisfirePolicy.COALESCING
    )
    assert req_cron.cron == "0 0 * * *"
    req_interval = ScheduledJobCreateRequest(task_type="health_check", interval_seconds=60)
    assert req_interval.interval_seconds == 60
    with pytest.raises(ValidationError):
        ScheduledJobCreateRequest(task_type="invalid")
    with pytest.raises(ValidationError):
        ScheduledJobCreateRequest(task_type="invalid", cron="0 0 * * *", interval_seconds=60)


def test_queue_create_request_validation() -> None:
    valid_q = QueueCreateRequest(
        queue_name="high-priority.us-east", max_concurrency=50, rate_limit_rps=200
    )
    assert valid_q.queue_name == "high-priority.us-east"
    with pytest.raises(ValidationError):
        QueueCreateRequest(queue_name="invalid queue with spaces!")


def test_standard_error_response_envelope() -> None:
    err = ErrorResponse(
        error=ErrorDetail(
            code="TASK_NOT_FOUND",
            message="Task with ID 123 does not exist.",
            details={"task_id": "123"},
            request_id="req-abc123456789",
        )
    )
    dumped = err.model_dump()
    assert "error" in dumped
    assert dumped["error"]["code"] == "TASK_NOT_FOUND"
    assert dumped["error"]["request_id"] == "req-abc123456789"
    assert dumped["error"]["details"] == {"task_id": "123"}

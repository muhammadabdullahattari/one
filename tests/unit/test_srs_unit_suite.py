from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from src.api.schemas.tasks import TaskSubmitRequest
from src.core.constants import TaskStatus
from src.domain.entities import IdempotencyKey, Task
from src.domain.task_registry import TaskRegistry
from src.observability.redaction import sanitize_error_message
from src.rate_limit.fairness import compute_effective_priority
from src.rate_limit.limiter import TokenBucketRateLimiter
from src.retry.policy import JitterStrategy, RetryPolicy
from src.scheduler.cron import compute_next_run


def test_ut_001_task_schema_accepts_valid_task() -> None:
    req = TaskSubmitRequest(
        task_type="process_payment",
        queue="payments",
        priority=7,
        payload={"amount": 99.99, "currency": "USD"},
        timeout_seconds=180,
        max_attempts=4,
    )
    assert req.task_type == "process_payment"
    assert req.queue == "payments"
    assert req.priority == 7
    assert req.timeout_seconds == 180
    assert req.max_attempts == 4


def test_ut_002_reject_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        TaskSubmitRequest(task_type="invalid_priority_low", priority=0)

    with pytest.raises(ValidationError):
        TaskSubmitRequest(task_type="invalid_priority_high", priority=11)


def test_ut_003_retry_classification() -> None:
    policy = RetryPolicy(max_attempts=3)
    assert policy.is_retryable(attempt=1, exception=TimeoutError("Gateway timed out")) is True
    assert policy.is_retryable(attempt=1, exception=ConnectionError("Connection reset")) is True
    assert (
        policy.is_retryable(attempt=1, exception=ValueError("Invalid syntax in payload")) is False
    )
    assert policy.is_retryable(attempt=1, exception=KeyError("missing_field")) is False
    assert policy.is_retryable(attempt=3, exception=TimeoutError("Max attempts reached")) is False


def test_ut_004_backoff_calculation() -> None:
    policy = RetryPolicy(
        initial_interval_seconds=1.0,
        max_interval_seconds=60.0,
        backoff_factor=2.0,
        jitter_strategy=JitterStrategy.NONE,
    )
    d1 = policy.compute_backoff_seconds(1)
    d2 = policy.compute_backoff_seconds(2)
    d3 = policy.compute_backoff_seconds(3)
    d10 = policy.compute_backoff_seconds(10)
    assert d1 == 1.0
    assert d2 == 2.0
    assert d3 == 4.0
    assert d10 <= 60.0


def test_ut_005_jitter_bounds() -> None:
    policy = RetryPolicy(
        initial_interval_seconds=2.0,
        max_interval_seconds=100.0,
        backoff_factor=2.0,
        jitter_strategy=JitterStrategy.FULL,
    )
    for _ in range(50):
        delay = policy.compute_backoff_seconds(attempt=2)
        assert 0.0 <= delay <= 4.0


def test_ut_006_priority_selection() -> None:
    t_low = Task(task_type="batch_export", priority=2)
    t_high = Task(task_type="security_alert", priority=9)
    assert t_high.priority > t_low.priority


def test_ut_007_aging_fairness() -> None:
    now = datetime.now(UTC)
    old_low = Task(
        task_type="background_sync",
        priority=8,
        created_at=now - timedelta(seconds=120),
    )
    fresh_high = Task(
        task_type="user_action",
        priority=5,
        created_at=now - timedelta(seconds=2),
    )
    eff_low = compute_effective_priority(
        base_priority=old_low.priority,
        created_at=old_low.created_at,
        aging_interval_seconds=30.0,
    )
    eff_high = compute_effective_priority(
        base_priority=fresh_high.priority,
        created_at=fresh_high.created_at,
        aging_interval_seconds=30.0,
    )
    assert eff_low <= eff_high


def test_ut_008_idempotency_key() -> None:
    tid = uuid4()
    now = datetime.now(UTC)
    key1 = IdempotencyKey(
        scope="tenant-1",
        idempotency_key="idemp-order-999",
        task_id=tid,
        request_hash="hash-1234",
        expires_at=now + timedelta(hours=1),
    )
    assert key1.idempotency_key == "idemp-order-999"
    assert key1.task_id == tid
    assert key1.expires_at > now


def test_ut_009_state_transition_guard() -> None:
    t = Task(task_type="state_task", status=TaskStatus.PENDING)
    t.transition_to(TaskStatus.QUEUED)
    assert t.status == TaskStatus.QUEUED

    t.transition_to(TaskStatus.RUNNING)
    assert t.status == TaskStatus.RUNNING

    t.transition_to(TaskStatus.SUCCEEDED)
    assert t.status == TaskStatus.SUCCEEDED

    with pytest.raises(ValueError):
        t.transition_to(TaskStatus.RUNNING)


def test_ut_010_error_sanitization() -> None:
    raw_error = (
        "FATAL: connection failed postgresql://user:super_secret_password_123@db.internal:5432/app"
    )
    sanitized = sanitize_error_message(raw_error)
    assert "super_secret_password_123" not in sanitized
    assert "***" in sanitized


@pytest.mark.asyncio
async def test_ut_011_rate_limiter() -> None:
    limiter = TokenBucketRateLimiter(fail_closed=False)
    for _ in range(5):
        allowed = await limiter.acquire("tenant-x", rate_limit_rps=10, burst_capacity=10)
        assert allowed is True


def test_ut_012_schedule_next_run() -> None:
    base_time = datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)
    next_run = compute_next_run("0 12 * * *", tz_name="UTC", base_time=base_time)
    assert next_run == datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)


def test_ut_013_timezone_conversion() -> None:
    base_time = datetime(2026, 9, 29, 10, 0, 0, tzinfo=UTC)
    next_run = compute_next_run("0 12 * * *", tz_name="America/New_York", base_time=base_time)
    assert next_run is not None
    assert next_run.tzinfo == UTC
    assert next_run.hour == 16


def test_ut_014_task_registry() -> None:
    reg = TaskRegistry()

    def sample_handler(x: int) -> int:
        return x * 2

    reg.register(name="calc_double", handler=sample_handler)
    resolved = reg.get("calc_double")
    assert resolved is not None
    assert resolved.name == "calc_double"

    with pytest.raises(ValueError):
        reg.get_or_raise("non_existent_task_type")


def test_ut_015_lease_expiration() -> None:
    now = datetime.now(UTC)
    expired_task = Task(
        task_type="leased_task",
        status=TaskStatus.RUNNING,
        lease_expires_at=now - timedelta(seconds=10),
    )
    assert expired_task.lease_expires_at is not None
    assert expired_task.lease_expires_at < now

    valid_task = Task(
        task_type="leased_task",
        status=TaskStatus.RUNNING,
        lease_expires_at=now + timedelta(seconds=300),
    )
    assert valid_task.lease_expires_at is not None
    assert valid_task.lease_expires_at > now

from src.retry.policy import JitterStrategy, RetryPolicy


def test_exponential_backoff_monotonic_increase() -> None:
    policy = RetryPolicy(
        initial_interval_seconds=2.0,
        backoff_factor=2.0,
        max_interval_seconds=60.0,
        jitter_strategy=JitterStrategy.NONE,
    )
    assert policy.compute_backoff_seconds(1) == 2.0
    assert policy.compute_backoff_seconds(2) == 4.0
    assert policy.compute_backoff_seconds(3) == 8.0
    assert policy.compute_backoff_seconds(4) == 16.0
    assert policy.compute_backoff_seconds(10) == 60.0


def test_full_jitter_bounds() -> None:
    policy = RetryPolicy(
        initial_interval_seconds=10.0, backoff_factor=2.0, jitter_strategy=JitterStrategy.FULL
    )
    for _ in range(50):
        val = policy.compute_backoff_seconds(attempt=2)
        assert 0.0 <= val <= 20.0


def test_failure_classification_fatal_vs_retryable() -> None:
    policy = RetryPolicy(max_attempts=3)
    assert policy.is_retryable(attempt=1, exception=ValueError("Invalid argument")) is False
    assert policy.is_retryable(attempt=1, exception=TypeError("Type mismatch")) is False
    assert policy.is_retryable(attempt=1, exception="SchemaValidationError") is False
    assert policy.is_retryable(attempt=1, exception=TimeoutError("Connection timed out")) is True
    assert policy.is_retryable(attempt=1, exception=ConnectionResetError("Connection lost")) is True
    assert policy.is_retryable(attempt=1, exception="DatabaseDeadlockException") is True
    assert policy.is_retryable(attempt=3, exception=TimeoutError("Connection timed out")) is False

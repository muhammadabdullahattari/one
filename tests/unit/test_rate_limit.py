from datetime import UTC, datetime, timedelta

from src.rate_limit.fairness import compute_effective_priority
from src.rate_limit.limiter import TokenBucketRateLimiter


def test_in_memory_token_bucket_rate_limiter() -> None:
    limiter = TokenBucketRateLimiter()
    now = 1000.0
    for _ in range(5):
        allowed = limiter._acquire_in_memory(
            key="test-in-mem", rate_limit_rps=5, capacity=5, cost=1, now=now
        )
        assert allowed is True
    rejected = limiter._acquire_in_memory(
        key="test-in-mem", rate_limit_rps=5, capacity=5, cost=1, now=now
    )
    assert rejected is False


def test_anti_starvation_priority_aging() -> None:
    now = datetime.now(UTC)
    p0 = compute_effective_priority(base_priority=8, created_at=now, aging_interval_seconds=30.0)
    assert p0 == 8
    created_35s_ago = now - timedelta(seconds=35)
    p1 = compute_effective_priority(
        base_priority=8, created_at=created_35s_ago, aging_interval_seconds=30.0
    )
    assert p1 == 7
    created_125s_ago = now - timedelta(seconds=125)
    p4 = compute_effective_priority(
        base_priority=8, created_at=created_125s_ago, aging_interval_seconds=30.0
    )
    assert p4 == 4

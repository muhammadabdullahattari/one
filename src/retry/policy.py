import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class JitterStrategy(StrEnum):
    NONE = "none"
    FULL = "full"
    EQUAL = "equal"
    DECORRELATED = "decorrelated"


FATAL_EXCEPTION_CLASSES = {
    "ValueError",
    "TypeError",
    "AttributeError",
    "KeyError",
    "NotImplementedError",
    "PermissionError",
    "AuthenticationError",
    "AuthorizationError",
    "SchemaValidationError",
    "TaskCancelledException",
}


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    initial_interval_seconds: float = 1.0
    max_interval_seconds: float = 300.0
    backoff_factor: float = 2.0
    jitter_strategy: JitterStrategy = JitterStrategy.FULL

    def compute_backoff_seconds(self, attempt: int) -> float:
        if attempt <= 0:
            return 0.0
        raw_backoff = self.initial_interval_seconds * self.backoff_factor ** (attempt - 1)
        bounded_backoff = min(self.max_interval_seconds, raw_backoff)
        if self.jitter_strategy == JitterStrategy.FULL:
            return random.uniform(0.0, bounded_backoff)
        elif self.jitter_strategy == JitterStrategy.EQUAL:
            half = bounded_backoff / 2.0
            return half + random.uniform(0.0, half)
        elif self.jitter_strategy == JitterStrategy.DECORRELATED:
            return min(
                self.max_interval_seconds,
                random.uniform(self.initial_interval_seconds, bounded_backoff * 3),
            )
        return bounded_backoff

    def compute_next_retry_time(self, attempt: int) -> datetime:
        delay = self.compute_backoff_seconds(attempt)
        return datetime.now(UTC) + timedelta(seconds=delay)

    def is_retryable(self, attempt: int, exception: Exception | str) -> bool:
        if attempt >= self.max_attempts:
            return False
        error_name = exception if isinstance(exception, str) else exception.__class__.__name__
        if error_name in FATAL_EXCEPTION_CLASSES:
            return False
        return True


default_retry_policy = RetryPolicy()

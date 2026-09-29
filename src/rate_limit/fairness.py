from datetime import UTC, datetime


def compute_effective_priority(
    base_priority: int,
    created_at: datetime,
    aging_interval_seconds: float = 30.0,
    max_boost: int = 4,
    min_priority_bound: int = 1,
) -> int:

    now = datetime.now(UTC)

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    age_seconds = max(0.0, (now - created_at).total_seconds())

    if aging_interval_seconds <= 0:
        return base_priority

    boost_steps = int(age_seconds // aging_interval_seconds)
    effective_boost = min(max_boost, boost_steps)
    effective_priority = max(min_priority_bound, base_priority - effective_boost)

    return effective_priority

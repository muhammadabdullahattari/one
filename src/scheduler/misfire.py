from datetime import UTC, datetime

from src.core.constants import MisfirePolicy
from src.scheduler.cron import compute_next_run


def evaluate_misfires(
    cron_expression: str | None,
    interval_seconds: int | None,
    timezone_name: str,
    scheduled_run_at: datetime,
    now_utc: datetime,
    misfire_policy: MisfirePolicy = MisfirePolicy.SKIP,
    misfire_grace_seconds: float = 60.0,
) -> tuple[list[datetime], datetime | None]:

    if scheduled_run_at.tzinfo is None:
        scheduled_run_at = scheduled_run_at.replace(tzinfo=UTC)

    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)

    if (now_utc - scheduled_run_at).total_seconds() <= misfire_grace_seconds:
        next_run = compute_next_run(
            cron_expression, interval_seconds, timezone_name, base_time=now_utc
        )
        return ([scheduled_run_at], next_run)
    if misfire_policy == MisfirePolicy.SKIP:
        next_run = compute_next_run(
            cron_expression, interval_seconds, timezone_name, base_time=now_utc
        )
        return ([], next_run)
    elif misfire_policy == MisfirePolicy.COALESCING:
        next_run = compute_next_run(
            cron_expression, interval_seconds, timezone_name, base_time=now_utc
        )
        return ([now_utc], next_run)
    elif misfire_policy == MisfirePolicy.CATCH_UP:
        runs: list[datetime] = [scheduled_run_at]
        curr = scheduled_run_at
        while True:
            nxt = compute_next_run(cron_expression, interval_seconds, timezone_name, base_time=curr)
            if nxt is None or nxt > now_utc:
                break
            runs.append(nxt)
            curr = nxt
        next_run = compute_next_run(
            cron_expression, interval_seconds, timezone_name, base_time=now_utc
        )
        return (runs, next_run)
    return (
        [],
        compute_next_run(cron_expression, interval_seconds, timezone_name, base_time=now_utc),
    )

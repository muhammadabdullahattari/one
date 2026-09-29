from datetime import UTC, datetime, timedelta

import pytz
from croniter import croniter


def compute_next_run(
    cron_expression: str | None = None,
    interval_seconds: int | None = None,
    tz_name: str = "UTC",
    base_time: datetime | None = None,
    tz_str: str | None = None,
) -> datetime | None:
    now_utc = base_time or datetime.now(UTC)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    timezone_str = tz_str or tz_name
    if interval_seconds and interval_seconds > 0:
        return now_utc + timedelta(seconds=interval_seconds)
    if cron_expression:
        try:
            user_tz = pytz.timezone(timezone_str)
        except Exception:
            user_tz = pytz.UTC
        local_time = now_utc.astimezone(user_tz)
        fields = cron_expression.strip().split()
        if len(fields) == 6:
            cron = croniter(
                cron_expression, local_time, ret_type=datetime, second_at_beginning=True
            )
        else:
            cron = croniter(cron_expression, local_time, ret_type=datetime)
        next_local: datetime = cron.get_next(datetime)
        return next_local.astimezone(UTC)
    return None


def calculate_next_run(
    cron_expression: str, base_time: datetime | None = None, tz_str: str = "UTC"
) -> datetime:
    result = compute_next_run(cron_expression=cron_expression, tz_name=tz_str, base_time=base_time)
    if result is None:
        raise ValueError(f"Could not calculate next run for cron: {cron_expression}")
    return result

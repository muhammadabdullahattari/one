from datetime import UTC, datetime

from src.core.constants import MisfirePolicy
from src.scheduler.cron import compute_next_run
from src.scheduler.misfire import evaluate_misfires


def test_standard_5_field_cron() -> None:
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    nxt = compute_next_run(cron_expression="*/15 * * * *", base_time=base)
    assert nxt == datetime(2026, 1, 1, 10, 15, 0, tzinfo=UTC)


def test_6_field_cron_with_seconds() -> None:
    base = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    nxt = compute_next_run(cron_expression="30 * * * * *", base_time=base)
    assert nxt == datetime(2026, 1, 1, 10, 0, 30, tzinfo=UTC)


def test_timezone_conversion_to_utc() -> None:
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    nxt = compute_next_run(cron_expression="0 9 * * *", tz_name="America/New_York", base_time=base)
    assert nxt is not None
    assert nxt.hour == 14
    assert nxt.minute == 0


def test_misfire_policy_skip() -> None:
    scheduled_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    now_utc = datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC)
    runs, next_run = evaluate_misfires(
        cron_expression="0 * * * *",
        interval_seconds=None,
        timezone_name="UTC",
        scheduled_run_at=scheduled_at,
        now_utc=now_utc,
        misfire_policy=MisfirePolicy.SKIP,
    )
    assert len(runs) == 0
    assert next_run == datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC)


def test_misfire_policy_coalescing() -> None:
    scheduled_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    now_utc = datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC)
    runs, next_run = evaluate_misfires(
        cron_expression="0 * * * *",
        interval_seconds=None,
        timezone_name="UTC",
        scheduled_run_at=scheduled_at,
        now_utc=now_utc,
        misfire_policy=MisfirePolicy.COALESCING,
    )
    assert len(runs) == 1
    assert runs[0] == now_utc
    assert next_run == datetime(2026, 1, 1, 14, 0, 0, tzinfo=UTC)


def test_misfire_policy_catch_up() -> None:
    scheduled_at = datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC)
    now_utc = datetime(2026, 1, 1, 12, 30, 0, tzinfo=UTC)
    runs, next_run = evaluate_misfires(
        cron_expression="0 * * * *",
        interval_seconds=None,
        timezone_name="UTC",
        scheduled_run_at=scheduled_at,
        now_utc=now_utc,
        misfire_policy=MisfirePolicy.CATCH_UP,
    )
    assert len(runs) == 3
    assert runs[0] == scheduled_at
    assert runs[1] == datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC)
    assert runs[2] == datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert next_run == datetime(2026, 1, 1, 13, 0, 0, tzinfo=UTC)

from src.observability.metrics import (
    API_REQUESTS_TOTAL,
    BROKER_STREAM_LENGTH,
    DATABASE_POOL_USAGE,
    QUEUE_DEPTH,
    QUEUE_OLDEST_TASK_AGE_SECONDS,
    RATE_LIMIT_ALLOWED_TOTAL,
    SCHEDULER_DUE_SCHEDULES,
    TASK_EXECUTION_DURATION_SECONDS,
    TASKS_DEAD_TOTAL,
    TASKS_FAILED_TOTAL,
    TASKS_RETRY_TOTAL,
    TASKS_RUNNING,
    TASKS_SUBMITTED_TOTAL,
    TASKS_SUCCEEDED_TOTAL,
    WORKERS_HEALTHY,
    WORKERS_STALE,
    generate_metrics_text,
    get_metrics_content_type,
)


def test_metrics_definitions_and_increments() -> None:
    API_REQUESTS_TOTAL.labels(method="POST", endpoint="/api/v1/tasks", status_code="201").inc()
    TASKS_SUBMITTED_TOTAL.labels(task_type="order_processing", queue="high-priority").inc()
    TASKS_SUCCEEDED_TOTAL.labels(task_type="order_processing", queue="high-priority").inc()
    TASKS_FAILED_TOTAL.labels(
        task_type="order_processing",
        queue="high-priority",
        error_class="ConnectionError",
    ).inc()
    TASKS_RETRY_TOTAL.labels(task_type="order_processing", queue="high-priority").inc()
    TASKS_DEAD_TOTAL.labels(task_type="order_processing", queue="high-priority").inc()

    QUEUE_DEPTH.labels(queue="high-priority").set(42)
    QUEUE_OLDEST_TASK_AGE_SECONDS.labels(queue="high-priority").set(15.5)

    TASKS_RUNNING.labels(queue="high-priority").set(5)
    TASK_EXECUTION_DURATION_SECONDS.labels(
        task_type="order_processing", queue="high-priority"
    ).observe(0.45)

    WORKERS_HEALTHY.set(8)
    WORKERS_STALE.set(1)

    SCHEDULER_DUE_SCHEDULES.set(3)

    BROKER_STREAM_LENGTH.labels(backend="redis", queue="high-priority").set(150)

    DATABASE_POOL_USAGE.set(0.65)

    RATE_LIMIT_ALLOWED_TOTAL.labels(tenant_id="tenant-1", queue="high-priority").inc()

    metrics_text = generate_metrics_text().decode("utf-8")
    assert "api_requests_total" in metrics_text
    assert "tasks_submitted_total" in metrics_text
    assert "queue_oldest_task_age_seconds" in metrics_text
    assert "workers_healthy" in metrics_text
    assert "broker_stream_length" in metrics_text
    assert "database_pool_usage_ratio" in metrics_text
    assert "rate_limit_allowed_total" in metrics_text
    assert "text/plain" in get_metrics_content_type()

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry(auto_describe=True)

API_REQUESTS_TOTAL = Counter(
    "api_requests_total",
    "Total number of HTTP API requests",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY,
)
API_ERRORS_TOTAL = Counter(
    "api_errors_total",
    "Total number of HTTP API errors",
    ["method", "endpoint", "error_type"],
    registry=REGISTRY,
)
API_REQUEST_DURATION_SECONDS = Histogram(
    "api_request_duration_seconds",
    "HTTP API request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=REGISTRY,
)
API_AUTH_FAILURES_TOTAL = Counter(
    "api_auth_failures_total",
    "Total number of authentication failures",
    ["auth_mode", "reason"],
    registry=REGISTRY,
)
API_RATE_LIMIT_REJECTIONS_TOTAL = Counter(
    "api_rate_limit_rejections_total",
    "Total number of requests rejected by rate limiting",
    ["tenant_id", "endpoint"],
    registry=REGISTRY,
)

TASKS_SUBMITTED_TOTAL = Counter(
    "tasks_submitted_total",
    "Total number of tasks submitted",
    ["task_type", "queue"],
    registry=REGISTRY,
)
TASKS_SUCCEEDED_TOTAL = Counter(
    "tasks_succeeded_total",
    "Total number of tasks successfully completed",
    ["task_type", "queue"],
    registry=REGISTRY,
)
TASKS_FAILED_TOTAL = Counter(
    "tasks_failed_total",
    "Total number of tasks that failed an execution attempt",
    ["task_type", "queue", "error_class"],
    registry=REGISTRY,
)
TASKS_RETRY_TOTAL = Counter(
    "tasks_retry_total",
    "Total number of task retry attempts scheduled",
    ["task_type", "queue"],
    registry=REGISTRY,
)
TASKS_DEAD_TOTAL = Counter(
    "tasks_dead_total",
    "Total number of tasks transitioned to DEAD (DLQ)",
    ["task_type", "queue"],
    registry=REGISTRY,
)
TASKS_CANCELLED_TOTAL = Counter(
    "tasks_cancelled_total",
    "Total number of tasks cancelled",
    ["task_type", "queue"],
    registry=REGISTRY,
)

QUEUE_DEPTH = Gauge(
    "queue_depth",
    "Current number of pending and queued tasks in queue",
    ["queue"],
    registry=REGISTRY,
)
QUEUE_OLDEST_TASK_AGE_SECONDS = Gauge(
    "queue_oldest_task_age_seconds",
    "Age in seconds of the oldest queued unexecuted task",
    ["queue"],
    registry=REGISTRY,
)
QUEUE_ENQUEUE_RATE = Counter(
    "queue_enqueue_total",
    "Total number of task enqueue events",
    ["queue"],
    registry=REGISTRY,
)
QUEUE_DEQUEUE_RATE = Counter(
    "queue_dequeue_total",
    "Total number of task dequeue events",
    ["queue"],
    registry=REGISTRY,
)
QUEUE_WAIT_DURATION_SECONDS = Histogram(
    "queue_wait_duration_seconds",
    "Time tasks spend waiting in queue before execution",
    ["queue"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
    registry=REGISTRY,
)

TASKS_RUNNING = Gauge(
    "tasks_running",
    "Number of tasks currently in RUNNING state",
    ["queue"],
    registry=REGISTRY,
)
TASK_EXECUTION_DURATION_SECONDS = Histogram(
    "task_execution_duration_seconds",
    "Execution duration of task handlers in seconds",
    ["task_type", "queue"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=REGISTRY,
)
TASKS_TIMEOUT_TOTAL = Counter(
    "tasks_timeout_total",
    "Total number of tasks timed out during execution",
    ["task_type", "queue"],
    registry=REGISTRY,
)
TASK_DUPLICATE_EXECUTION_TOTAL = Counter(
    "task_duplicate_execution_total",
    "Total duplicate execution attempts prevented or detected",
    ["task_type", "queue"],
    registry=REGISTRY,
)

WORKERS_HEALTHY = Gauge(
    "workers_healthy",
    "Current count of active and healthy worker nodes",
    registry=REGISTRY,
)
WORKERS_STALE = Gauge(
    "workers_stale",
    "Current count of stale/offline worker nodes",
    registry=REGISTRY,
)
WORKER_ACTIVE_SLOTS = Gauge(
    "worker_active_slots",
    "Current active execution slots per worker",
    ["worker_id"],
    registry=REGISTRY,
)
WORKER_UTILIZATION = Gauge(
    "worker_utilization_ratio",
    "Worker utilization ratio (active slots / max concurrency)",
    ["worker_id"],
    registry=REGISTRY,
)
WORKER_HEARTBEAT_AGE_SECONDS = Gauge(
    "worker_heartbeat_age_seconds",
    "Seconds elapsed since worker last emitted a heartbeat",
    ["worker_id"],
    registry=REGISTRY,
)

SCHEDULER_DUE_SCHEDULES = Gauge(
    "scheduler_due_schedules",
    "Number of schedules currently due for task emission",
    registry=REGISTRY,
)
SCHEDULER_LAG_SECONDS = Gauge(
    "scheduler_lag_seconds",
    "Lag in seconds between expected schedule time and emission",
    registry=REGISTRY,
)
SCHEDULER_ERRORS_TOTAL = Counter(
    "scheduler_errors_total",
    "Total errors encountered by scheduler leader tick loop",
    ["error_type"],
    registry=REGISTRY,
)
SCHEDULER_DUPLICATES_PREVENTED_TOTAL = Counter(
    "scheduler_duplicates_prevented_total",
    "Total duplicate schedule executions prevented",
    registry=REGISTRY,
)

BROKER_STREAM_LENGTH = Gauge(
    "broker_stream_length",
    "Total length of broker stream or message backlog",
    ["backend", "queue"],
    registry=REGISTRY,
)
BROKER_PENDING_ENTRIES = Gauge(
    "broker_pending_entries",
    "Number of unacknowledged entries in broker consumer groups",
    ["backend", "queue"],
    registry=REGISTRY,
)
BROKER_CLAIM_RECOVERY_TOTAL = Counter(
    "broker_claim_recovery_total",
    "Total messages reclaimed from stale workers",
    ["backend", "queue"],
    registry=REGISTRY,
)
BROKER_ERRORS_TOTAL = Counter(
    "broker_errors_total",
    "Total errors occurred in broker publish/consume operations",
    ["backend"],
    registry=REGISTRY,
)

DATABASE_POOL_USAGE = Gauge(
    "database_pool_usage_ratio",
    "Current ratio of active connections in database pool",
    registry=REGISTRY,
)
DATABASE_TRANSACTION_DURATION_SECONDS = Histogram(
    "database_transaction_duration_seconds",
    "Database transaction latency in seconds",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=REGISTRY,
)
DATABASE_QUERY_ERRORS_TOTAL = Counter(
    "database_query_errors_total",
    "Total database query errors encountered",
    ["error_code"],
    registry=REGISTRY,
)
OUTBOX_LAG_SECONDS = Gauge(
    "outbox_lag_seconds",
    "Age in seconds of the oldest unpublished outbox entry",
    registry=REGISTRY,
)

RATE_LIMIT_ALLOWED_TOTAL = Counter(
    "rate_limit_allowed_total",
    "Total requests allowed by rate limiting",
    ["tenant_id", "queue"],
    registry=REGISTRY,
)
RATE_LIMIT_DELAYED_TOTAL = Counter(
    "rate_limit_delayed_total",
    "Total requests delayed or queued for smoothing",
    ["tenant_id", "queue"],
    registry=REGISTRY,
)
RATE_LIMIT_REJECTED_TOTAL = Counter(
    "rate_limit_rejected_total",
    "Total requests rejected by rate limiting",
    ["tenant_id", "queue"],
    registry=REGISTRY,
)
RATE_LIMIT_TOKEN_BUCKET_LEVEL = Gauge(
    "rate_limit_token_bucket_level",
    "Current token level in token bucket rate limiter",
    ["tenant_id", "queue"],
    registry=REGISTRY,
)


def generate_metrics_text() -> bytes:
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST

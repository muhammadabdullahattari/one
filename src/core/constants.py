from enum import StrEnum


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class ApiAuthMode(StrEnum):
    JWT = "jwt"
    API_KEY = "api_key"
    BOTH = "both"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogFormat(StrEnum):
    JSON = "json"
    TEXT = "text"


class BrokerBackendType(StrEnum):
    NATIVE = "native"
    REDIS = "redis"
    RABBITMQ = "rabbitmq"
    NATS = "nats"
    SQS = "sqs"


class RateLimitBackendType(StrEnum):
    REDIS = "redis"
    POSTGRES = "postgres"


class MisfirePolicy(StrEnum):
    SKIP = "skip"
    CATCH_UP = "catch_up"
    COALESCING = "coalescing"


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    SCHEDULED = "SCHEDULED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    DEAD = "DEAD"


class TaskEventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_RETRY_SCHEDULED = "task.retry_scheduled"
    TASK_SUCCEEDED = "task.succeeded"
    TASK_FAILED = "task.failed"
    TASK_DEAD = "task.dead"
    TASK_CANCELLED = "task.cancelled"
    WORKER_REGISTERED = "worker.registered"
    WORKER_HEARTBEAT = "worker.heartbeat"


class HttpHeader(StrEnum):
    REQUEST_ID = "x-request-id"
    TRACE_ID = "x-trace-id"
    TENANT_ID = "x-tenant-id"
    API_KEY = "x-api-key"
    IDEMPOTENCY_KEY = "idempotency-key"


DEFAULT_QUEUE_NAME = "default"
DLQ_QUEUE_PREFIX = "dlq."
DEFAULT_MAX_PAYLOAD_BYTES = 65536
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_LEASE_SECONDS = 300
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30
DEFAULT_SCHEDULER_TICK_SECONDS = 5
DEFAULT_SCHEDULER_LOCK_TTL_SECONDS = 30
DEFAULT_RESULT_RETENTION_DAYS = 30
DEFAULT_TASK_EVENT_RETENTION_DAYS = 90
DEFAULT_DLQ_RETENTION_DAYS = 180
DEFAULT_WORKER_CONCURRENCY = 10
DEFAULT_RATE_LIMIT_RPS = 100

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.constants import (
    DEFAULT_DLQ_RETENTION_DAYS,
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DEFAULT_LEASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_MAX_PAYLOAD_BYTES,
    DEFAULT_RATE_LIMIT_RPS,
    DEFAULT_RESULT_RETENTION_DAYS,
    DEFAULT_SCHEDULER_LOCK_TTL_SECONDS,
    DEFAULT_SCHEDULER_TICK_SECONDS,
    DEFAULT_TASK_EVENT_RETENTION_DAYS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_WORKER_CONCURRENCY,
    ApiAuthMode,
    AppEnv,
    LogFormat,
    LogLevel,
    RateLimitBackendType,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE_PATH = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE_PATH, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    app_env: AppEnv = Field(
        default=AppEnv.DEVELOPMENT, description="Application runtime environment (SRS §19)."
    )
    app_version: str = Field(default="0.1.3", description="Application version string.")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/task_engine_dev",
        description="PostgreSQL async connection string (SRS §19 Required).",
    )
    database_url_sync: str | None = Field(
        default=None, description="PostgreSQL synchronous connection string for Alembic migrations."
    )
    db_pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of persistent connections in the async pool.",
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections allowed above db_pool_size.",
    )
    db_pool_timeout: float = Field(
        default=30.0,
        gt=0,
        description="Seconds to wait before timing out on acquiring a pool connection.",
    )
    db_pool_recycle: int = Field(
        default=1800, ge=60, description="Recycle connections older than this duration (seconds)."
    )
    db_pool_pre_ping: bool = Field(
        default=True, description="Validate connection health on checkout (pool_pre_ping)."
    )
    database_session_url: str | None = Field(
        default=None,
        description="Session-persistent DB URL for Scheduler leader election (advisory locks).",
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for Streams broker & rate limits (SRS §19 Required).",
    )
    redis_stream_maxlen: int = Field(
        default=100000,
        ge=1000,
        description="Approximate max stream length for Redis Streams (XADD MAXLEN ~).",
    )
    redis_max_connections: int = Field(
        default=50, ge=5, description="Maximum size of Redis async connection pool."
    )
    redis_socket_timeout: float = Field(
        default=5.0, gt=0, description="Redis socket timeout in seconds."
    )
    api_auth_mode: ApiAuthMode = Field(
        default=ApiAuthMode.JWT,
        description="Pluggable auth mode: jwt, api_key, or both (SRS §12, §19 Required).",
    )
    secret_key: str = Field(
        default="change-me-in-production-min-32-chars-long-secure-random-key",
        description="Secret key for JWT signing (HMAC-SHA256) (SRS §19 Required).",
    )
    algorithm: str = Field(default="HS256", description="JWT cryptographic signing algorithm.")
    access_token_expire_minutes: int = Field(
        default=30, ge=1, description="JWT Access token expiration duration in minutes."
    )
    refresh_token_expire_days: int = Field(
        default=7, ge=1, le=90, description="JWT Refresh token expiration duration in days."
    )
    api_key_salt: str = Field(
        default="task-engine-api-key-salt",
        description="Salt used when hashing external API keys before storing.",
    )
    task_max_payload_bytes: int = Field(
        default=DEFAULT_MAX_PAYLOAD_BYTES,
        ge=1024,
        le=10485760,
        description="Maximum allowable inline task payload in bytes (SRS §12, §19 Required).",
    )
    default_max_attempts: int = Field(
        default=DEFAULT_MAX_ATTEMPTS,
        ge=1,
        le=50,
        description="Default retry attempt ceiling for tasks (SRS §19 Required).",
    )
    default_timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        ge=1,
        le=86400,
        description="Default execution timeout in seconds (SRS §19 Required).",
    )
    lease_seconds: int = Field(
        default=DEFAULT_LEASE_SECONDS,
        ge=5,
        le=3600,
        description="Worker task lease ownership duration (SRS §15, §19 Required).",
    )
    heartbeat_interval_seconds: int = Field(
        default=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        ge=1,
        le=300,
        description="Worker heartbeat cadence in seconds (SRS §15, §19 Required).",
    )
    worker_concurrency: int = Field(
        default=DEFAULT_WORKER_CONCURRENCY,
        ge=1,
        le=500,
        description="Bounded concurrency per worker process (SRS §15, §19 Required).",
    )
    scheduler_tick_seconds: int = Field(
        default=DEFAULT_SCHEDULER_TICK_SECONDS,
        ge=1,
        le=60,
        description="Scheduler polling cadence for due jobs (SRS §14.1, §19 Required).",
    )
    scheduler_leader_lock_ttl_seconds: int = Field(
        default=DEFAULT_SCHEDULER_LOCK_TTL_SECONDS,
        ge=5,
        le=300,
        description="Leader lease TTL for pg_try_advisory_xact_lock (SRS §14.1).",
    )
    result_retention_days: int = Field(
        default=DEFAULT_RESULT_RETENTION_DAYS,
        ge=1,
        le=3650,
        description="Retention duration for task results in days (SRS §19 Required).",
    )
    task_event_retention_days: int = Field(
        default=DEFAULT_TASK_EVENT_RETENTION_DAYS,
        ge=1,
        le=3650,
        description="Retention duration for task event history in days (SRS §19 Required).",
    )
    dlq_retention_days: int = Field(
        default=DEFAULT_DLQ_RETENTION_DAYS,
        ge=1,
        le=3650,
        description="Retention duration for dead letter records in days (SRS §19 Required).",
    )
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus-compatible metrics collector (SRS §19 Required).",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO, description="Application runtime log level (SRS §19 Required)."
    )
    log_format: LogFormat = Field(
        default=LogFormat.JSON,
        description="Log output format (JSON structured logging per SRS §13).",
    )
    otel_exporter_endpoint: str | None = Field(
        default=None, description="OpenTelemetry OTLP gRPC/HTTP collector endpoint (SRS §19)."
    )
    rate_limit_backend: RateLimitBackendType = Field(
        default=RateLimitBackendType.REDIS,
        description="Backend for token bucket rate limiting: redis or postgres (SRS §14.3).",
    )
    default_rate_limit_rps: int = Field(
        default=DEFAULT_RATE_LIMIT_RPS,
        ge=1,
        description="Default requests per second quota per tenant/queue.",
    )
    supabase_url: str | None = Field(
        default=None, description="Supabase project URL (https://<project-id>.supabase.co)."
    )
    supabase_anon_key: str | None = Field(
        default=None, description="Supabase anonymous public key."
    )
    supabase_service_role_key: str | None = Field(
        default=None, description="Supabase service role secret key (backend only)."
    )
    s3_endpoint_url: str | None = Field(
        default=None, description="S3-compatible endpoint (e.g. Supabase Storage / AWS S3 / MinIO)."
    )
    s3_access_key_id: str | None = Field(
        default=None, description="Access key for S3-compatible storage."
    )
    s3_secret_access_key: str | None = Field(
        default=None, description="Secret key for S3-compatible storage."
    )
    s3_bucket_name: str = Field(
        default="task-payloads",
        description="S3 bucket name for offloading payloads > task_max_payload_bytes.",
    )
    s3_region: str = Field(default="us-east-1", description="S3 bucket region.")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql+asyncpg://", "postgres+asyncpg://")):
            if v.startswith("postgresql://") or v.startswith("postgres://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1).replace(
                    "postgres://", "postgresql+asyncpg://", 1
                )
            raise ValueError(
                "DATABASE_URL must start with 'postgresql+asyncpg://' for async database access."
            )
        return v

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError("REDIS_URL must start with 'redis://' or 'rediss://' (TLS).")
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        if not self.database_url_sync:
            self.database_url_sync = self.database_url.replace(
                "postgresql+asyncpg://", "postgresql://", 1
            ).replace("postgres+asyncpg://", "postgresql://", 1)
        if not self.database_session_url:
            self.database_session_url = self.database_url
        if self.app_env in (AppEnv.PRODUCTION, AppEnv.STAGING):
            if len(self.secret_key) < 32 or "change-me" in self.secret_key:
                raise ValueError(
                    f"In {self.app_env.value} environment, SECRET_KEY must be a cryptographically secure random string of at least 32 characters (SRS §12, NFR-010)."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == AppEnv.PRODUCTION

    @property
    def is_development(self) -> bool:
        return self.app_env == AppEnv.DEVELOPMENT

    @property
    def is_test(self) -> bool:
        return self.app_env == AppEnv.TEST

    @property
    def sync_database_url(self) -> str:
        if self.database_url_sync:
            return self.database_url_sync
        return self.database_url.replace("+asyncpg", "")

    def get_sanitized_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        secret_keys = {
            "secret_key",
            "supabase_anon_key",
            "supabase_service_role_key",
            "s3_secret_access_key",
            "api_key_salt",
        }
        for key in secret_keys:
            if key in data and data[key] is not None:
                data[key] = "[REDACTED]"
        for url_field in ("database_url", "database_url_sync", "database_session_url", "redis_url"):
            val = data.get(url_field)
            if val and isinstance(val, str):
                try:
                    parsed = urlparse(val)
                    if parsed.password:
                        data[url_field] = val.replace(f":{parsed.password}@", ":[REDACTED]@")
                except Exception:
                    data[url_field] = "[REDACTED_URL]"
        return data


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

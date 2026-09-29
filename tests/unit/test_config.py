import pytest
from pydantic import ValidationError
from src.core.config import Settings, get_settings
from src.core.constants import ApiAuthMode, AppEnv, LogFormat, LogLevel, RateLimitBackendType


def test_default_settings_instantiation() -> None:
    settings = Settings()
    assert settings.app_env in (AppEnv.DEVELOPMENT, AppEnv.TEST)
    assert settings.task_max_payload_bytes == 65536
    assert settings.default_max_attempts == 3
    assert settings.default_timeout_seconds == 300
    assert settings.lease_seconds == 300
    assert settings.heartbeat_interval_seconds == 30
    assert settings.worker_concurrency == 10
    assert settings.scheduler_tick_seconds == 5
    assert settings.scheduler_leader_lock_ttl_seconds == 30
    assert settings.result_retention_days == 30
    assert settings.task_event_retention_days == 90
    assert settings.dlq_retention_days == 180
    assert settings.metrics_enabled is True
    assert settings.rate_limit_backend == RateLimitBackendType.REDIS
    assert settings.log_level == LogLevel.INFO
    assert settings.log_format == LogFormat.JSON


def test_get_settings_cached_singleton() -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_database_url_validation_and_driver_upgrade() -> None:
    settings = Settings(
        database_url="postgresql://user:pass@localhost:5432/mydb", database_url_sync=None
    )
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    assert settings.sync_database_url == "postgresql://user:pass@localhost:5432/mydb"


def test_invalid_database_url_scheme() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="mysql://user:pass@localhost:3306/mydb")


def test_redis_url_validation() -> None:
    s_plain = Settings(redis_url="redis://localhost:6379/0")
    assert s_plain.redis_url == "redis://localhost:6379/0"
    s_tls = Settings(redis_url="rediss://localhost:6379/0")
    assert s_tls.redis_url == "rediss://localhost:6379/0"
    with pytest.raises(ValidationError):
        Settings(redis_url="http://localhost:6379")


def test_production_secret_key_length_validation() -> None:
    expected_msg = "SECRET_KEY must be a cryptographically secure random string"
    with pytest.raises(ValidationError, match=expected_msg):
        Settings(app_env=AppEnv.PRODUCTION, secret_key="too-short")
    with pytest.raises(ValidationError, match=expected_msg):
        Settings(
            app_env=AppEnv.PRODUCTION,
            secret_key="change-me-in-production-min-32-chars-long-secure-random-key",
        )
    valid_key = "super-secret-random-32-character-long-production-key-here"
    valid_prod_settings = Settings(app_env=AppEnv.PRODUCTION, secret_key=valid_key)
    assert valid_prod_settings.secret_key == valid_key


def test_secret_redaction_for_logging() -> None:
    settings = Settings(
        secret_key="super-secret-key-12345678901234567890",
        database_url="postgresql+asyncpg://myuser:supersecretpass@db.supabase.co:5432/mydb",
        supabase_anon_key="anon-key-123",
        supabase_service_role_key="service-role-123",
        s3_secret_access_key="s3-secret-123",
    )
    sanitized = settings.get_sanitized_dict()
    assert sanitized["secret_key"] == "[REDACTED]"
    assert sanitized["supabase_anon_key"] == "[REDACTED]"
    assert sanitized["supabase_service_role_key"] == "[REDACTED]"
    assert sanitized["s3_secret_access_key"] == "[REDACTED]"
    assert "supersecretpass" not in sanitized["database_url"]
    assert "[REDACTED]" in sanitized["database_url"]


def test_computed_environment_properties() -> None:
    dev_settings = Settings(app_env=AppEnv.DEVELOPMENT)
    assert dev_settings.is_development is True
    assert dev_settings.is_production is False
    assert dev_settings.is_test is False
    prod_settings = Settings(app_env=AppEnv.PRODUCTION, secret_key="a" * 35)
    assert prod_settings.is_production is True
    assert prod_settings.is_development is False
    test_settings = Settings(app_env=AppEnv.TEST)
    assert test_settings.is_test is True
    assert test_settings.is_production is False


def test_auth_mode_parsing() -> None:
    s_jwt = Settings(api_auth_mode=ApiAuthMode.JWT)
    assert s_jwt.api_auth_mode == ApiAuthMode.JWT
    s_key = Settings(api_auth_mode=ApiAuthMode.API_KEY)
    assert s_key.api_auth_mode == ApiAuthMode.API_KEY
    s_both = Settings(api_auth_mode=ApiAuthMode.BOTH)
    assert s_both.api_auth_mode == ApiAuthMode.BOTH
    with pytest.raises(ValidationError):
        Settings.model_validate({"api_auth_mode": "unsupported_auth"})


def test_database_pool_configuration() -> None:
    settings = Settings(
        db_pool_size=30, db_max_overflow=15, db_pool_timeout=45.0, db_pool_recycle=3600
    )
    assert settings.db_pool_size == 30
    assert settings.db_max_overflow == 15
    assert settings.db_pool_timeout == 45.0
    assert settings.db_pool_recycle == 3600

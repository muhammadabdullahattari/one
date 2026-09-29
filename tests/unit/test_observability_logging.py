from src.observability.logging import (
    configure_logging,
    ctx_request_id,
    ctx_task_id,
    get_logger,
)
from src.observability.redaction import (
    is_sensitive_key,
    sanitize_data,
    sanitize_error_message,
)


def test_sensitive_data_redaction() -> None:
    assert is_sensitive_key("password") is True
    assert is_sensitive_key("api_key") is True
    assert is_sensitive_key("auth_token") is True
    assert is_sensitive_key("user_name") is False

    raw_data = {
        "user": "alice",
        "password": "super_secret_password",
        "api_key": "tk_live_123456789",
        "metadata": {
            "token": "bearer_jwt_token",
            "normal_field": 42,
        },
    }
    sanitized = sanitize_data(raw_data)
    assert sanitized["user"] == "alice"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["metadata"]["token"] == "[REDACTED]"
    assert sanitized["metadata"]["normal_field"] == 42


def test_error_message_redaction() -> None:
    db_err = (
        "Failed to connect to postgresql+asyncpg://postgres:mysecretpass@localhost:5432/task_db"
    )
    redacted = sanitize_error_message(db_err)
    assert "mysecretpass" not in redacted
    assert "***" in redacted

    auth_err = "Authentication failed with token: eyJhbGciOiJIUzI1NiJ9.test"
    redacted_auth = sanitize_error_message(auth_err)
    assert "eyJhbGciOiJIUzI1NiJ9.test" not in redacted_auth
    assert "[REDACTED]" in redacted_auth


def test_structured_logger_configuration() -> None:
    configure_logging()
    logger = get_logger("test_module")
    assert logger is not None

    ctx_request_id.set("req-abc-123")
    ctx_task_id.set("task-xyz-789")
    logger.info("test log entry", extra_key="extra_value")

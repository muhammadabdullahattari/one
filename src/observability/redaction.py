import re
from typing import Any

SENSITIVE_KEY_PATTERNS = [
    re.compile(r"pass(word)?", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"auth(orization)?", re.IGNORECASE),
    re.compile(r"private[_-]?key", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
    re.compile(r"cookie", re.IGNORECASE),
]

DB_URL_PASSWORD_PATTERN = re.compile(r"(://[^:]+:)([^@]+)(@)")


def is_sensitive_key(key: str) -> bool:
    return any(p.search(key) for p in SENSITIVE_KEY_PATTERNS)


def redact_secrets_from_string(val: str) -> str:
    return DB_URL_PASSWORD_PATTERN.sub(r"\1***\3", val)


def sanitize_data(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            k_str = str(k)
            if is_sensitive_key(k_str):
                sanitized[k_str] = "[REDACTED]"
            else:
                sanitized[k_str] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str):
        return redact_secrets_from_string(data)
    return data


def sanitize_error_message(error_msg: str) -> str:
    redacted = redact_secrets_from_string(error_msg)
    for pattern in SENSITIVE_KEY_PATTERNS:
        redacted = re.sub(
            rf"({pattern.pattern}\s*[:=]\s*['\"]?)([^'\"\s,]+)(['\"]?)",
            r"\1[REDACTED]\3",
            redacted,
            flags=re.IGNORECASE,
        )
    return redacted

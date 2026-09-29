from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt

from src.core.config import get_settings


def create_access_token(
    subject: str,
    claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "nbf": int(now.timestamp()),
        "iss": "task-engine",
    }
    if claims:
        payload.update(claims)
    encoded_jwt = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return str(encoded_jwt)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        issuer="task-engine",
    )
    return dict(payload)


def create_refresh_token(
    subject: str,
    claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=7)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "nbf": int(now.timestamp()),
        "iss": "task-engine",
    }
    if claims:
        payload.update(claims)
    encoded_jwt = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return str(encoded_jwt)


def decode_refresh_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
        issuer="task-engine",
    )
    token_type = payload.get("type")
    if token_type and token_type != "refresh":
        raise ValueError("Invalid token type; expected refresh token")
    return dict(payload)

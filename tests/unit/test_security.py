from datetime import timedelta

import pytest
from jose import JWTError
from src.core.constants import ApiAuthMode
from src.security.api_keys import generate_api_key, hash_api_key, verify_api_key
from src.security.jwt import create_access_token, decode_access_token
from src.security.password import hash_password, verify_password
from src.security.principal import ANONYMOUS_PRINCIPAL, Principal


def test_password_hashing_and_verification() -> None:
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_jwt_token_generation_and_decoding() -> None:
    subject = "usr-12345"
    claims = {"role": "admin", "tenant_id": "tenant-corp", "scopes": ["tasks:write", "tasks:read"]}
    token = create_access_token(subject, claims=claims, expires_delta=timedelta(minutes=15))
    assert isinstance(token, str)
    assert len(token) > 20
    decoded = decode_access_token(token)
    assert decoded["sub"] == subject
    assert decoded["role"] == "admin"
    assert decoded["tenant_id"] == "tenant-corp"
    assert decoded["scopes"] == ["tasks:write", "tasks:read"]
    assert decoded["iss"] == "task-engine"
    assert "exp" in decoded
    assert "iat" in decoded


def test_jwt_token_invalid_signature_raises_error() -> None:
    token = create_access_token("usr-12345")
    corrupted_token = token[:-5] + "XXXXX"
    with pytest.raises(JWTError):
        decode_access_token(corrupted_token)


def test_api_key_generation_and_hashing() -> None:
    full_key, prefix, key_hash = generate_api_key(prefix="te_live_")
    assert full_key.startswith("te_live_")
    assert len(full_key) > 30
    assert prefix == full_key[:12] + "..."
    assert len(key_hash) == 64
    assert verify_api_key(full_key, key_hash) is True
    assert verify_api_key(full_key + "tampered", key_hash) is False
    assert hash_api_key(full_key) == key_hash


def test_principal_role_and_scope_checks() -> None:
    admin_principal = Principal(
        principal_id="admin-1", role="admin", scopes=["*"], auth_mode=ApiAuthMode.JWT
    )
    assert admin_principal.has_role("admin") is True
    assert admin_principal.has_role("operator") is True
    assert admin_principal.has_scope("any:action") is True
    operator_principal = Principal(
        principal_id="op-1",
        role="operator",
        scopes=["tasks:submit", "tasks:read"],
        auth_mode=ApiAuthMode.JWT,
    )
    assert operator_principal.has_role("operator") is True
    assert operator_principal.has_role("admin") is False
    assert operator_principal.has_scope("tasks:submit") is True
    assert operator_principal.has_scope("system:delete") is False
    assert ANONYMOUS_PRINCIPAL.is_authenticated is False

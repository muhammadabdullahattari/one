import hashlib
import hmac
import secrets

from src.core.config import get_settings


def generate_api_key(prefix: str = "te_live_") -> tuple[str, str, str]:
    random_part = secrets.token_urlsafe(32)
    full_key = f"{prefix}{random_part}"
    key_prefix = full_key[:12] + "..."
    key_hash = hash_api_key(full_key)
    return (full_key, key_prefix, key_hash)


def hash_api_key(plain_key: str) -> str:
    settings = get_settings()
    salt = settings.api_key_salt.encode("utf-8")
    key_bytes = plain_key.encode("utf-8")
    return hmac.new(salt, key_bytes, hashlib.sha256).hexdigest()


def verify_api_key(plain_key: str, expected_hash: str) -> bool:
    computed_hash = hash_api_key(plain_key)
    return hmac.compare_digest(computed_hash, expected_hash)

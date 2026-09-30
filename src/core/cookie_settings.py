from typing import Any

from src.core.config import Settings


class CookieSettings:
    ACCESS_TOKEN_COOKIE_NAME: str = "te_access_token"
    REFRESH_TOKEN_COOKIE_NAME: str = "te_refresh_token"
    SESSION_ID_COOKIE_NAME: str = "te_session_id"
    COOKIE_PATH: str = "/"

    @classmethod
    def get_access_token_cookie_options(
        cls, settings: Settings, cookie_domain: str | None = None
    ) -> dict[str, Any]:
        is_secure = not (settings.is_development or settings.is_test)
        return {
            "key": cls.ACCESS_TOKEN_COOKIE_NAME,
            "max_age": settings.access_token_expire_minutes * 60,
            "path": cls.COOKIE_PATH,
            "domain": cookie_domain,
            "secure": is_secure,
            "httponly": True,
            "samesite": "lax",
        }

    @classmethod
    def get_refresh_token_cookie_options(
        cls, settings: Settings, cookie_domain: str | None = None
    ) -> dict[str, Any]:
        is_secure = not (settings.is_development or settings.is_test)
        return {
            "key": cls.REFRESH_TOKEN_COOKIE_NAME,
            "max_age": settings.refresh_token_expire_days * 86400,
            "path": cls.COOKIE_PATH,
            "domain": cookie_domain,
            "secure": is_secure,
            "httponly": True,
            "samesite": "lax",
        }

    @classmethod
    def get_session_id_cookie_options(
        cls, settings: Settings, cookie_domain: str | None = None
    ) -> dict[str, Any]:
        is_secure = not (settings.is_development or settings.is_test)
        return {
            "key": cls.SESSION_ID_COOKIE_NAME,
            "max_age": settings.refresh_token_expire_days * 86400,
            "path": cls.COOKIE_PATH,
            "domain": cookie_domain,
            "secure": is_secure,
            "httponly": True,
            "samesite": "lax",
        }

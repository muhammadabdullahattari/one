from fastapi import Request, Response

from src.core.config import Settings
from src.core.cookie_settings import CookieSettings


class CookieManager:
    @staticmethod
    def set_access_token_cookie(
        response: Response,
        token: str,
        settings: Settings,
        cookie_domain: str | None = None,
    ) -> None:
        opts = CookieSettings.get_access_token_cookie_options(settings, cookie_domain)
        response.set_cookie(value=token, **opts)

    @staticmethod
    def set_refresh_token_cookie(
        response: Response,
        token: str,
        settings: Settings,
        cookie_domain: str | None = None,
    ) -> None:
        opts = CookieSettings.get_refresh_token_cookie_options(settings, cookie_domain)
        response.set_cookie(value=token, **opts)

    @staticmethod
    def set_session_id_cookie(
        response: Response,
        session_id: str,
        settings: Settings,
        cookie_domain: str | None = None,
    ) -> None:
        opts = CookieSettings.get_session_id_cookie_options(settings, cookie_domain)
        response.set_cookie(value=session_id, **opts)

    @staticmethod
    def clear_auth_cookies(
        response: Response,
        cookie_domain: str | None = None,
    ) -> None:
        response.delete_cookie(
            key=CookieSettings.ACCESS_TOKEN_COOKIE_NAME,
            path=CookieSettings.COOKIE_PATH,
            domain=cookie_domain,
        )
        response.delete_cookie(
            key=CookieSettings.REFRESH_TOKEN_COOKIE_NAME,
            path=CookieSettings.COOKIE_PATH,
            domain=cookie_domain,
        )
        response.delete_cookie(
            key=CookieSettings.SESSION_ID_COOKIE_NAME,
            path=CookieSettings.COOKIE_PATH,
            domain=cookie_domain,
        )

    @staticmethod
    def get_access_token_from_cookies(request: Request) -> str | None:
        return request.cookies.get(CookieSettings.ACCESS_TOKEN_COOKIE_NAME)

    @staticmethod
    def get_refresh_token_from_cookies(request: Request) -> str | None:
        return request.cookies.get(CookieSettings.REFRESH_TOKEN_COOKIE_NAME)

    @staticmethod
    def get_session_id_from_cookies(request: Request) -> str | None:
        return request.cookies.get(CookieSettings.SESSION_ID_COOKIE_NAME)

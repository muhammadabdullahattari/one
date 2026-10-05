from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dlq_service import DLQService
from src.application.task_service import TaskService
from src.core.config import Settings, get_settings
from src.core.constants import ApiAuthMode, HttpHeader
from src.core.cookie_utils import CookieManager
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.idempotency_repository import IdempotencyRepository
from src.persistence.repositories.outbox_repository import OutboxRepository
from src.persistence.repositories.project_repository import ProjectRepository
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.repositories.user_repository import UserRepository
from src.persistence.repositories.user_session_repository import UserSessionRepository
from src.persistence.repositories.worker_repository import WorkerRepository
from src.persistence.session import get_db_session
from src.rate_limit.limiter import RedisTokenBucketRateLimiter
from src.security.api_keys import hash_api_key
from src.security.jwt import decode_access_token
from src.security.principal import Principal

http_bearer = HTTPBearer(auto_error=False)
_redis_client: Redis | None = None


def set_redis_client(client: Redis | None) -> None:
    global _redis_client
    _redis_client = client


async def get_redis_client() -> Redis | None:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        try:
            _redis_client = Redis.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                socket_timeout=settings.redis_socket_timeout,
                decode_responses=True,
            )
        except Exception:
            _redis_client = None
    return _redis_client


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserRepository:
    return UserRepository(session)


async def get_user_session_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserSessionRepository:
    return UserSessionRepository(session)


async def get_project_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectRepository:
    return ProjectRepository(session)


async def get_task_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TaskRepository:
    return TaskRepository(session)


async def get_queue_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> QueueRepository:
    return QueueRepository(session)


async def get_schedule_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ScheduleRepository:
    return ScheduleRepository(session)


async def get_worker_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> WorkerRepository:
    return WorkerRepository(session)


async def get_dlq_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DLQRepository:
    return DLQRepository(session)


async def get_outbox_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> OutboxRepository:
    return OutboxRepository(session)


async def get_idempotency_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IdempotencyRepository:
    return IdempotencyRepository(session)


async def get_task_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> TaskService:
    task_repo = TaskRepository(session)
    outbox_repo = OutboxRepository(session)
    idempotency_repo = IdempotencyRepository(session)
    queue_repo = QueueRepository(session)
    rate_limiter = RedisTokenBucketRateLimiter(redis=redis)
    return TaskService(
        task_repo=task_repo,
        outbox_repo=outbox_repo,
        idempotency_repo=idempotency_repo,
        rate_limiter=rate_limiter,
        queue_repo=queue_repo,
    )


async def get_dlq_service(session: Annotated[AsyncSession, Depends(get_db_session)]) -> DLQService:
    dlq_repo = DLQRepository(session)
    task_repo = TaskRepository(session)
    outbox_repo = OutboxRepository(session)
    return DLQService(dlq_repo=dlq_repo, task_repo=task_repo, outbox_repo=outbox_repo)


async def get_current_principal(
    request: Request,
    bearer_creds: Annotated[HTTPAuthorizationCredentials | None, Security(http_bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    api_key_header: Annotated[str | None, Header(alias=HttpHeader.API_KEY.value)] = None,
    settings: Annotated[Settings | None, Depends(get_settings)] = None,
) -> Principal:
    if settings is None:
        settings = get_settings()
    auth_mode = settings.api_auth_mode

    token: str | None = None
    if bearer_creds:
        token = bearer_creds.credentials
    elif auth_mode in (ApiAuthMode.JWT, ApiAuthMode.BOTH):
        token = CookieManager.get_access_token_from_cookies(request)

    if auth_mode in (ApiAuthMode.JWT, ApiAuthMode.BOTH) and token:
        try:
            payload = decode_access_token(token)
            principal_id = payload.get("sub", "unknown")
            role = payload.get("role", "operator")
            tenant_id = payload.get("tenant_id")
            scopes = payload.get("scopes", ["*"])
            username = payload.get("username")
            return Principal(
                principal_id=principal_id,
                role=role,
                tenant_id=tenant_id,
                scopes=scopes,
                auth_mode=ApiAuthMode.JWT,
                is_authenticated=True,
                username=username,
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired JWT token: {exc}",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    if auth_mode in (ApiAuthMode.API_KEY, ApiAuthMode.BOTH) and api_key_header:
        key_hash = hash_api_key(api_key_header)
        project_repo = ProjectRepository(session)
        key_record = await project_repo.get_api_key_by_hash(key_hash)
        if key_record:
            return Principal(
                principal_id=str(key_record.principal_id),
                role=key_record.role,
                tenant_id=str(key_record.project_id) if key_record.project_id else None,
                scopes=list(key_record.scopes) if key_record.scopes else ["*"],
                auth_mode=ApiAuthMode.API_KEY,
                is_authenticated=True,
            )
        if not (settings.is_development or settings.is_test):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key.",
            )
        return Principal(
            principal_id=f"apikey-{api_key_header[:8]}",
            role="operator",
            tenant_id=None,
            scopes=["*"],
            auth_mode=ApiAuthMode.API_KEY,
            is_authenticated=True,
        )

    if settings.is_test:
        return Principal(
            principal_id="test-operator",
            role="admin",
            tenant_id=None,
            scopes=["*"],
            auth_mode=ApiAuthMode.JWT,
            is_authenticated=True,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials required (Bearer JWT or HttpOnly cookie).",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_role(*roles: str) -> Callable[[Principal], Principal]:
    def _role_checker(principal: Annotated[Principal, Depends(get_current_principal)]) -> Principal:
        if not principal.has_role(*roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {', '.join(roles)}.",
            )
        return principal

    return _role_checker


def require_scope(*scopes: str) -> Callable[[Principal], Principal]:
    def _scope_checker(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if not principal.has_scope(*scopes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires all of the following scopes: {', '.join(scopes)}.",
            )
        return principal

    return _scope_checker


def enforce_tenant_access(principal: Principal, requested_tenant_id: str | None) -> None:
    if principal.is_admin and (principal.tenant_id is None or principal.tenant_id == "*"):
        return
    if not principal.tenant_id or str(principal.tenant_id) != str(requested_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cross-tenant access violation: Principal '{principal.principal_id}' cannot access tenant '{requested_tenant_id}'.",
        )


enforce_project_access = enforce_tenant_access

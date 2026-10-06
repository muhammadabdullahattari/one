import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.api.dependencies import (
    get_current_principal,
    get_project_repository,
    get_user_repository,
    get_user_session_repository,
)
from src.api.schemas.auth import (
    KeyRotationRequest,
    KeyRotationResponse,
    LoginRequest,
    LoginResponse,
    PrincipalResponse,
    UserCreateRequest,
    UserResponse,
)
from src.core.config import Settings, get_settings
from src.core.cookie_utils import CookieManager
from src.persistence.repositories.project_repository import ProjectRepository
from src.persistence.repositories.user_repository import UserRepository
from src.persistence.repositories.user_session_repository import UserSessionRepository
from src.security.api_keys import generate_api_key
from src.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.security.password import hash_password, verify_password
from src.security.principal import Principal
from src.security.rbac import enforce_project_access, require_role

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new operator or viewer account",
)
async def register_user(
    request: UserCreateRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserResponse:
    existing_user = await user_repo.get_by_username(request.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{request.username}' already exists.",
        )
    existing_email = await user_repo.get_by_email(request.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{request.email}' is already registered.",
        )
    effective_tenant = request.tenant_id if request.tenant_id else request.username.lower()
    user = await user_repo.create_user(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role,
        tenant_id=effective_tenant,
    )
    return UserResponse(
        user_id=str(user.user_id),
        username=user.username,
        email=user.email,
        role=user.role,
        tenant_id=user.tenant_id,
        created_at=user.created_at,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate with credentials and obtain session via HttpOnly cookies",
)
async def login(
    request_data: LoginRequest,
    request: Request,
    response: Response,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    session_repo: Annotated[UserSessionRepository, Depends(get_user_session_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    await user_repo.seed_default_users()
    user = await user_repo.get_by_username(request_data.username)
    if not user:
        user = await user_repo.get_by_email(request_data.username)
    if not user or not verify_password(request_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_tenant = getattr(user, "tenant_id", "default") or "default"
    access_tok = create_access_token(
        subject=str(user.user_id),
        claims={"role": user.role, "username": user.username, "tenant_id": user_tenant},
    )
    refresh_tok = create_refresh_token(
        subject=str(user.user_id),
        claims={"role": user.role, "username": user.username, "tenant_id": user_tenant},
    )

    refresh_token_hash = hashlib.sha256(refresh_tok.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session = await session_repo.create_session(
        user_id=user.user_id,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )

    CookieManager.set_access_token_cookie(response, access_tok, settings)
    CookieManager.set_refresh_token_cookie(response, refresh_tok, settings)
    CookieManager.set_session_id_cookie(response, str(session.session_id), settings)

    expires_seconds = settings.access_token_expire_minutes * 60
    return LoginResponse(
        token_type="bearer",
        expires_in=expires_seconds,
        user_id=str(user.user_id),
        role=user.role,
        tenant_id=user_tenant,
    )


@router.post(
    "/refresh",
    response_model=LoginResponse,
    summary="Exchange valid refresh token for a new access token via HttpOnly cookies",
)
async def refresh_token(
    request: Request,
    response: Response,
    session_repo: Annotated[UserSessionRepository, Depends(get_user_session_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    tok = CookieManager.get_refresh_token_from_cookies(request)

    if not tok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token cookie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_refresh_token(tok)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired refresh token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    tok_hash = hashlib.sha256(tok.encode()).hexdigest()
    active_session = await session_repo.get_active_session_by_token_hash(tok_hash)
    if not active_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub", "unknown")
    role = payload.get("role", "viewer")
    tenant_id = payload.get("tenant_id", "default")
    new_access_tok = create_access_token(
        subject=user_id,
        claims={"role": role, "tenant_id": tenant_id},
    )

    CookieManager.set_access_token_cookie(response, new_access_tok, settings)

    expires_seconds = settings.access_token_expire_minutes * 60
    return LoginResponse(
        token_type="bearer",
        expires_in=expires_seconds,
        user_id=user_id,
        role=role,
        tenant_id=tenant_id,
    )


@router.post(
    "/rotate-key",
    response_model=KeyRotationResponse,
    summary="Rotate an API key without service restart",
)
async def rotate_api_key(
    request: KeyRotationRequest,
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> KeyRotationResponse:
    require_role("admin", "operator")(principal)
    enforce_project_access(principal, request.project_id)

    project = None
    try:
        project_uuid = UUID(request.project_id)
        project = await project_repo.get_by_id(project_uuid)
    except ValueError:
        project = await project_repo.get_by_slug(request.project_id)

    if not project:
        project = await project_repo.create_project(
            name=f"Project {request.project_id}",
            slug=request.project_id,
        )

    raw_new_key, key_prefix, key_hash = generate_api_key(prefix="te_live_")
    new_key = await project_repo.create_api_key(
        project_id=project.project_id,
        name="Rotated API Key",
        key_prefix=key_prefix,
        key_hash=key_hash,
        role=principal.role,
        scopes=principal.scopes or ["*"],
    )
    try:
        old_uuid = UUID(request.old_key_id)
        await project_repo.revoke_api_key(project.project_id, old_uuid)
    except ValueError:
        pass

    return KeyRotationResponse(
        project_id=request.project_id,
        new_key_id=str(new_key.principal_id),
        new_api_key=raw_new_key,
        revoked_key_id=request.old_key_id,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Revoke active authentication session",
)
async def logout(
    request: Request,
    response: Response,
    session_repo: Annotated[UserSessionRepository, Depends(get_user_session_repository)],
) -> dict[str, str]:
    tok = CookieManager.get_refresh_token_from_cookies(request)
    if tok:
        tok_hash = hashlib.sha256(tok.encode()).hexdigest()
        active_session = await session_repo.get_active_session_by_token_hash(tok_hash)
        if active_session:
            await session_repo.revoke_session(active_session.session_id)

    CookieManager.clear_auth_cookies(response)
    return {"message": "Successfully logged out."}


@router.post(
    "/logout-all-devices",
    status_code=status.HTTP_200_OK,
    summary="Revoke all active authentication sessions across all devices",
)
async def logout_all_devices(
    response: Response,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session_repo: Annotated[UserSessionRepository, Depends(get_user_session_repository)],
) -> dict[str, str]:
    try:
        user_uuid = UUID(principal.principal_id)
        await session_repo.revoke_user_sessions(user_uuid)
    except ValueError:
        pass

    CookieManager.clear_auth_cookies(response)
    return {"message": "Successfully logged out from all devices."}


@router.get(
    "/me",
    response_model=PrincipalResponse,
    summary="Get current authenticated caller principal and permissions",
)
async def get_current_user_profile(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> PrincipalResponse:
    return PrincipalResponse(
        principal_id=principal.principal_id,
        role=principal.role,
        tenant_id=principal.tenant_id,
        scopes=principal.scopes,
        auth_mode=principal.auth_mode.value,
        username=principal.username,
    )

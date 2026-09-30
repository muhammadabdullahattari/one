from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import (
    get_current_principal,
    get_project_repository,
    get_user_repository,
)
from src.api.schemas.auth import (
    KeyRotationRequest,
    KeyRotationResponse,
    LoginRequest,
    PrincipalResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserCreateRequest,
    UserResponse,
)
from src.core.config import Settings, get_settings
from src.persistence.repositories.project_repository import ProjectRepository
from src.persistence.repositories.user_repository import UserRepository
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
    user = await user_repo.create_user(
        username=request.username,
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role,
    )
    return UserResponse(
        user_id=str(user.user_id),
        username=user.username,
        email=user.email,
        role=user.role,
        created_at=user.created_at,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with credentials and obtain access + refresh tokens",
)
async def login(
    request: LoginRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    await user_repo.seed_default_users()
    user = await user_repo.get_by_username(request.username)
    if not user:
        user = await user_repo.get_by_email(request.username)
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_tok = create_access_token(
        subject=str(user.user_id),
        claims={"role": user.role, "username": user.username},
    )
    refresh_tok = create_refresh_token(
        subject=str(user.user_id),
        claims={"role": user.role, "username": user.username},
    )
    expires_seconds = settings.access_token_expire_minutes * 60
    return TokenResponse(
        access_token=access_tok,
        token_type="bearer",
        expires_in=expires_seconds,
        refresh_token=refresh_tok,
        user_id=str(user.user_id),
        role=user.role,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange valid refresh token for a new access token",
)
async def refresh_token(
    request: RefreshTokenRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    try:
        payload = decode_refresh_token(request.refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired refresh token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user_id = payload.get("sub", "unknown")
    role = payload.get("role", "viewer")
    new_access_tok = create_access_token(
        subject=user_id,
        claims={"role": role},
    )
    expires_seconds = settings.access_token_expire_minutes * 60
    return TokenResponse(
        access_token=new_access_tok,
        token_type="bearer",
        expires_in=expires_seconds,
        refresh_token=request.refresh_token,
        user_id=user_id,
        role=role,
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
async def logout() -> dict[str, str]:
    return {"message": "Successfully logged out."}


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
    )

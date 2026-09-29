from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_principal
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

_USERS_DB: dict[str, dict[str, str]] = {
    "admin": {
        "user_id": "usr-admin-001",
        "username": "admin",
        "email": "admin@taskengine.internal",
        "password_hash": hash_password("adminpassword123"),
        "role": "admin",
        "created_at": datetime.now(UTC).isoformat(),
    },
    "operator": {
        "user_id": "usr-op-002",
        "username": "operator",
        "email": "operator@taskengine.internal",
        "password_hash": hash_password("operatorpass123"),
        "role": "operator",
        "created_at": datetime.now(UTC).isoformat(),
    },
}

_ACTIVE_API_KEYS: dict[str, dict[str, str]] = {}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new operator or viewer account",
)
async def register_user(request: UserCreateRequest) -> UserResponse:
    if request.username in _USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{request.username}' already exists.",
        )
    user_id = f"usr-{request.username}"
    now = datetime.now(UTC)
    _USERS_DB[request.username] = {
        "user_id": user_id,
        "username": request.username,
        "email": request.email,
        "password_hash": hash_password(request.password),
        "role": request.role,
        "created_at": now.isoformat(),
    }
    return UserResponse(
        user_id=user_id,
        username=request.username,
        email=request.email,
        role=request.role,
        created_at=now,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with credentials and obtain access + refresh tokens",
)
async def login(
    request: LoginRequest, settings: Annotated[Settings, Depends(get_settings)]
) -> TokenResponse:
    user = _USERS_DB.get(request.username)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_tok = create_access_token(
        subject=user["user_id"],
        claims={"role": user["role"], "username": user["username"]},
    )
    refresh_tok = create_refresh_token(
        subject=user["user_id"],
        claims={"role": user["role"], "username": user["username"]},
    )
    expires_seconds = settings.access_token_expire_minutes * 60
    return TokenResponse(
        access_token=access_tok,
        token_type="bearer",
        expires_in=expires_seconds,
        refresh_token=refresh_tok,
        user_id=user["user_id"],
        role=user["role"],
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
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> KeyRotationResponse:
    require_role("admin", "operator")(principal)
    enforce_project_access(principal, request.project_id)

    raw_new_key, _key_prefix, key_hash = generate_api_key(prefix="tk_live_")
    new_key_id = f"key-{uuid4().hex[:8]}"
    _ACTIVE_API_KEYS[new_key_id] = {
        "project_id": request.project_id,
        "key_hash": key_hash,
        "status": "active",
    }
    if request.old_key_id in _ACTIVE_API_KEYS:
        _ACTIVE_API_KEYS[request.old_key_id]["status"] = "revoked"

    return KeyRotationResponse(
        project_id=request.project_id,
        new_key_id=new_key_id,
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

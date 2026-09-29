from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_principal, require_role
from src.api.schemas.projects import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyListResponse,
    ApiKeyResponse,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
)
from src.security.api_keys import generate_api_key
from src.security.principal import Principal

router = APIRouter(prefix="/projects", tags=["Projects & Tenancy"])
_PROJECTS: dict[UUID, dict[str, Any]] = {}
_API_KEYS: dict[UUID, dict[str, Any]] = {}


def _to_project_response(p: dict[str, Any]) -> ProjectResponse:
    return ProjectResponse(
        project_id=p["project_id"],
        name=p["name"],
        slug=p["slug"],
        description=p.get("description"),
        created_at=p["created_at"],
    )


def _to_api_key_response(k: dict[str, Any]) -> ApiKeyResponse:
    return ApiKeyResponse(
        key_id=k["key_id"],
        project_id=k["project_id"],
        name=k["name"],
        key_prefix=k["key_prefix"],
        role=k["role"],
        scopes=k["scopes"],
        created_at=k["created_at"],
        last_used_at=k.get("last_used_at"),
    )


@router.get("", response_model=ProjectListResponse, summary="List all tenant projects")
async def list_projects(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> ProjectListResponse:
    projects = list(_PROJECTS.values())
    return ProjectListResponse(
        items=[_to_project_response(p) for p in projects],
        total=len(projects),
        limit=len(projects) or 50,
        offset=0,
        has_more=False,
    )


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant project",
)
async def create_project(
    request: ProjectCreateRequest, principal: Annotated[Principal, Depends(require_role("admin"))]
) -> ProjectResponse:
    for p in _PROJECTS.values():
        if p["slug"] == request.slug:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Project with slug '{request.slug}' already exists.",
            )
    project_id = uuid4()
    now = datetime.now(UTC)
    project_data: dict[str, Any] = {
        "project_id": project_id,
        "name": request.name,
        "slug": request.slug,
        "description": request.description,
        "created_at": now,
    }
    _PROJECTS[project_id] = project_data
    return _to_project_response(project_data)


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project details")
async def get_project(
    project_id: UUID, principal: Annotated[Principal, Depends(get_current_principal)]
) -> ProjectResponse:
    p = _PROJECTS.get(project_id)
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found."
        )
    return _to_project_response(p)


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a tenant project"
)
async def delete_project(
    project_id: UUID, principal: Annotated[Principal, Depends(require_role("admin"))]
) -> None:
    if project_id not in _PROJECTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found."
        )
    del _PROJECTS[project_id]


@router.get(
    "/{project_id}/api-keys",
    response_model=ApiKeyListResponse,
    summary="List API keys for a project",
)
async def list_api_keys(
    project_id: UUID, principal: Annotated[Principal, Depends(require_role("admin", "operator"))]
) -> ApiKeyListResponse:
    keys = [k for k in _API_KEYS.values() if k["project_id"] == project_id]
    return ApiKeyListResponse(
        items=[_to_api_key_response(k) for k in keys],
        total=len(keys),
        limit=len(keys) or 50,
        offset=0,
        has_more=False,
    )


@router.post(
    "/{project_id}/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new API key for a project",
)
async def create_api_key(
    project_id: UUID,
    request: ApiKeyCreateRequest,
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> ApiKeyCreatedResponse:
    if project_id not in _PROJECTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found."
        )
    full_key, key_prefix, key_hash = generate_api_key()
    key_id = uuid4()
    now = datetime.now(UTC)
    key_record: dict[str, Any] = {
        "key_id": key_id,
        "project_id": project_id,
        "name": request.name,
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "role": request.role,
        "scopes": request.scopes,
        "created_at": now,
        "last_used_at": None,
    }
    _API_KEYS[key_id] = key_record
    return ApiKeyCreatedResponse(
        key_id=key_id,
        project_id=project_id,
        name=request.name,
        key_prefix=key_prefix,
        role=request.role,
        scopes=request.scopes,
        created_at=now,
        last_used_at=None,
        plain_key=full_key,
    )


@router.delete(
    "/{project_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_api_key(
    project_id: UUID, key_id: UUID, principal: Annotated[Principal, Depends(require_role("admin"))]
) -> None:
    if key_id not in _API_KEYS or _API_KEYS[key_id]["project_id"] != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key '{key_id}' not found in project '{project_id}'.",
        )
    del _API_KEYS[key_id]

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import (
    get_current_principal,
    get_project_repository,
    require_role,
)
from src.api.schemas.projects import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyListResponse,
    ApiKeyResponse,
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
)
from src.persistence.repositories.project_repository import ProjectRepository
from src.security.api_keys import generate_api_key
from src.security.principal import Principal

router = APIRouter(prefix="/projects", tags=["Projects & Tenancy"])


@router.get("", response_model=ProjectListResponse, summary="List all tenant projects")
async def list_projects(
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> ProjectListResponse:
    projects, total = await project_repo.list_projects()
    return ProjectListResponse(
        items=[
            ProjectResponse(
                project_id=p.project_id,
                name=p.name,
                slug=p.slug,
                description=p.description,
                created_at=p.created_at,
            )
            for p in projects
        ],
        total=total,
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
    request: ProjectCreateRequest,
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> ProjectResponse:
    existing = await project_repo.get_by_slug(request.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with slug '{request.slug}' already exists.",
        )
    p = await project_repo.create_project(
        name=request.name,
        slug=request.slug,
        description=request.description,
    )
    return ProjectResponse(
        project_id=p.project_id,
        name=p.name,
        slug=p.slug,
        description=p.description,
        created_at=p.created_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse, summary="Get project details")
async def get_project(
    project_id: UUID,
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> ProjectResponse:
    p = await project_repo.get_by_id(project_id)
    if not p:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found."
        )
    return ProjectResponse(
        project_id=p.project_id,
        name=p.name,
        slug=p.slug,
        description=p.description,
        created_at=p.created_at,
    )


@router.delete(
    "/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a tenant project"
)
async def delete_project(
    project_id: UUID,
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> None:
    deleted = await project_repo.delete_project(project_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found."
        )


@router.get(
    "/{project_id}/api-keys",
    response_model=ApiKeyListResponse,
    summary="List API keys for a project",
)
async def list_api_keys(
    project_id: UUID,
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> ApiKeyListResponse:
    keys = await project_repo.list_api_keys(project_id)
    return ApiKeyListResponse(
        items=[
            ApiKeyResponse(
                key_id=k.principal_id,
                project_id=k.project_id or project_id,
                name=k.name,
                key_prefix=k.key_prefix or "te_live_",
                role=k.role,
                scopes=k.scopes,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
            )
            for k in keys
        ],
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
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> ApiKeyCreatedResponse:
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found."
        )
    full_key, key_prefix, key_hash = generate_api_key()
    key = await project_repo.create_api_key(
        project_id=project_id,
        name=request.name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        role=request.role,
        scopes=request.scopes,
    )
    return ApiKeyCreatedResponse(
        key_id=key.principal_id,
        project_id=project_id,
        name=key.name,
        key_prefix=key_prefix,
        role=key.role,
        scopes=key.scopes,
        created_at=key.created_at,
        last_used_at=None,
        plain_key=full_key,
    )


@router.delete(
    "/{project_id}/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_api_key(
    project_id: UUID,
    key_id: UUID,
    project_repo: Annotated[ProjectRepository, Depends(get_project_repository)],
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> None:
    revoked = await project_repo.revoke_api_key(project_id, key_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key '{key_id}' not found in project '{project_id}'.",
        )

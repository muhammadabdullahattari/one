from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    enforce_tenant_access,
    get_current_principal,
    get_db_session,
    get_dlq_repository,
    get_dlq_service,
    require_role,
)
from src.api.schemas.dlq import (
    DLQBulkReplayRequest,
    DLQEntryResponse,
    DLQListResponse,
    DLQReplayRequest,
)
from src.application.dlq_service import DLQService
from src.persistence.models.task import TaskModel
from src.persistence.repositories.dlq_repository import DLQRepository
from src.security.principal import Principal

router = APIRouter(prefix="/dlq", tags=["DLQ"])


async def _task_queue(session: AsyncSession, task_id: UUID) -> str:
    res = await session.execute(select(TaskModel.queue).where(TaskModel.task_id == task_id))
    return res.scalar_one_or_none() or "default"


async def _task_queues(session: AsyncSession, task_ids: list[UUID]) -> dict[UUID, str]:
    if not task_ids:
        return {}
    res = await session.execute(
        select(TaskModel.task_id, TaskModel.queue).where(TaskModel.task_id.in_(task_ids))
    )
    return {row.task_id: row.queue for row in res.all()}


@router.get("", response_model=DLQListResponse, summary="List dead-lettered tasks in DLQ")
async def list_dlq(
    dlq_repo: Annotated[DLQRepository, Depends(get_dlq_repository)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    limit: int = Query(50, ge=1, le=1000, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    tenant_id: str | None = Query(None, description="Filter by tenant ID"),
) -> DLQListResponse:
    if principal.is_admin and principal.tenant_id is None:
        effective_tenant = tenant_id
    else:
        scoped_tenant = principal.tenant_id or principal.principal_id
        if tenant_id and tenant_id != scoped_tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-tenant access forbidden: Principal '{principal.principal_id}' cannot access tenant '{tenant_id}'.",
            )
        effective_tenant = scoped_tenant

    entries = await dlq_repo.list_entries(limit=limit, offset=offset, tenant_id=effective_tenant)
    total = await dlq_repo.count_entries(tenant_id=effective_tenant)
    queue_map = await _task_queues(session, [e.task_id for e in entries])
    return DLQListResponse(
        items=[
            DLQEntryResponse(
                dlq_id=e.dlq_id,
                tenant_id=e.tenant_id,
                task_id=e.task_id,
                final_attempt_id=e.final_attempt_id,
                queue=queue_map.get(e.task_id, "default"),
                reason=e.reason,
                error_class=e.error_class,
                payload_ref=e.payload_ref,
                dead_at=e.dead_at,
                replay_count=e.replay_count,
                last_replayed_at=e.last_replayed_at,
            )
            for e in entries
        ],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(entries) < total,
    )


@router.get(
    "/{dlq_id}",
    response_model=DLQEntryResponse,
    summary="Get details of a specific dead letter entry",
)
async def get_dlq_entry(
    dlq_id: UUID,
    dlq_repo: Annotated[DLQRepository, Depends(get_dlq_repository)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> DLQEntryResponse:
    entry = await dlq_repo.get_by_id(dlq_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"DLQ entry '{dlq_id}' not found."
        )
    enforce_tenant_access(principal, entry.tenant_id)
    queue = await _task_queue(session, entry.task_id)
    return DLQEntryResponse(
        dlq_id=entry.dlq_id,
        tenant_id=entry.tenant_id,
        task_id=entry.task_id,
        final_attempt_id=entry.final_attempt_id,
        queue=queue,
        reason=entry.reason,
        error_class=entry.error_class,
        payload_ref=entry.payload_ref,
        dead_at=entry.dead_at,
        replay_count=entry.replay_count,
        last_replayed_at=entry.last_replayed_at,
    )


@router.post(
    "/{dlq_id}/replay",
    status_code=status.HTTP_200_OK,
    summary="Replay a dead-lettered task back into active execution",
)
async def replay_dlq_entry(
    dlq_id: UUID,
    dlq_service: Annotated[DLQService, Depends(get_dlq_service)],
    dlq_repo: Annotated[DLQRepository, Depends(get_dlq_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
    request: DLQReplayRequest | None = None,
) -> dict[str, str]:
    entry = await dlq_repo.get_by_id(dlq_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLQ entry '{dlq_id}' not found.",
        )
    enforce_tenant_access(principal, entry.tenant_id)
    success = await dlq_service.replay(dlq_id, reset_attempts=True)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DLQ entry '{dlq_id}' not found or task already removed.",
        )
    return {"status": "replayed", "dlq_id": str(dlq_id)}


@router.post(
    "/replay/bulk", status_code=status.HTTP_200_OK, summary="Bulk replay dead-lettered tasks"
)
async def bulk_replay_dlq(
    request: DLQBulkReplayRequest,
    dlq_service: Annotated[DLQService, Depends(get_dlq_service)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> dict[str, int]:
    effective_tenant = (
        principal.tenant_id
        if (principal.tenant_id and not (principal.is_admin and principal.tenant_id is None))
        else None
    )
    replayed_count = await dlq_service.bulk_replay(
        dlq_ids=request.dlq_ids,
        limit=request.max_count,
        reset_attempts=True,
        tenant_id=effective_tenant,
    )
    return {"replayed_count": replayed_count}


@router.delete(
    "/{dlq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Discard / delete a dead letter entry",
)
async def discard_dlq_entry(
    dlq_id: UUID,
    dlq_repo: Annotated[DLQRepository, Depends(get_dlq_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> None:
    entry = await dlq_repo.get_by_id(dlq_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"DLQ entry '{dlq_id}' not found."
        )
    enforce_tenant_access(principal, entry.tenant_id)
    deleted = await dlq_repo.delete_entry(dlq_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"DLQ entry '{dlq_id}' not found."
        )

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_current_principal, get_worker_repository, require_role
from src.api.schemas.workers import WorkerListResponse, WorkerResponse
from src.domain.entities import Worker
from src.persistence.repositories.worker_repository import WorkerRepository
from src.security.principal import Principal

router = APIRouter(prefix="/workers", tags=["Workers"])


def _effective_tenant(principal: Principal) -> str | None:
    """Return the tenant_id that must be used for isolation.

    - Global admin with tenant_id=None → unscoped (sees all cluster workers).
    - All other users → strictly isolated to their own worker fleet.
    """
    if principal.is_admin and principal.tenant_id is None:
        return None
    return principal.tenant_id or principal.principal_id


def _to_response(w: Worker) -> WorkerResponse:
    queues = w.queues_json if isinstance(w.queues_json, list) else []
    caps = (
        {"capabilities": w.capabilities_json}
        if isinstance(w.capabilities_json, list)
        else w.capabilities_json or {}
    )
    return WorkerResponse(
        worker_id=w.worker_id,
        tenant_id=w.tenant_id,
        hostname=w.hostname,
        process_id=w.process_id,
        version=w.version,
        status=w.status,
        queues=queues,
        concurrency=w.concurrency,
        active_task_count=w.active_slots,
        capabilities=caps,
        last_heartbeat=w.last_heartbeat,
        registered_at=w.registered_at,
        drained_at=w.drained_at,
    )


@router.get("", response_model=WorkerListResponse, summary="List all registered worker nodes")
async def list_workers(
    worker_repo: Annotated[WorkerRepository, Depends(get_worker_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status (active, draining, offline)"
    ),
) -> WorkerListResponse:
    tenant = _effective_tenant(principal)
    workers = await worker_repo.list_workers(status=status_filter, tenant_id=tenant)
    return WorkerListResponse(
        items=[_to_response(w) for w in workers],
        total=len(workers),
        limit=len(workers) or 50,
        offset=0,
        has_more=False,
    )


@router.get(
    "/{worker_id}", response_model=WorkerResponse, summary="Get details for a specific worker node"
)
async def get_worker(
    worker_id: str,
    worker_repo: Annotated[WorkerRepository, Depends(get_worker_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> WorkerResponse:
    worker = await worker_repo.get_by_id(worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )
    # Enforce cross-tenant protection: a non-admin can only view their own tenant's workers
    tenant = _effective_tenant(principal)
    if tenant and worker.tenant_id != tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )
    return _to_response(worker)


@router.post(
    "/{worker_id}/drain",
    response_model=WorkerResponse,
    summary="Initiate graceful drain for a worker node",
)
async def drain_worker(
    worker_id: str,
    worker_repo: Annotated[WorkerRepository, Depends(get_worker_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> WorkerResponse:
    worker = await worker_repo.get_by_id(worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )
    tenant = _effective_tenant(principal)
    if tenant and worker.tenant_id != tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )
    await worker_repo.set_draining(worker_id)
    updated = await worker_repo.get_by_id(worker_id)
    resp = _to_response(updated or worker)
    try:
        import asyncio
        from src.api.routers.ws import ws_manager

        asyncio.create_task(
            ws_manager.broadcast(
                "workers",
                {"type": "worker.updated", "data": resp.model_dump(mode="json")},
            )
        )
    except Exception:
        pass
    return resp


@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deregister an offline or decommissioned worker node",
)
async def deregister_worker(
    worker_id: str,
    worker_repo: Annotated[WorkerRepository, Depends(get_worker_repository)],
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> None:
    worker = await worker_repo.get_by_id(worker_id)
    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )
    tenant = _effective_tenant(principal)
    if tenant and worker.tenant_id != tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )
    deleted = await worker_repo.delete_worker(worker_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )
    try:
        import asyncio
        from src.api.routers.ws import ws_manager

        asyncio.create_task(
            ws_manager.broadcast(
                "workers",
                {"type": "worker.deregistered", "data": {"worker_id": worker_id}},
            )
        )
    except Exception:
        pass

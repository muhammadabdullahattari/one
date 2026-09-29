from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_worker_repository, require_role
from src.api.schemas.workers import WorkerListResponse, WorkerResponse
from src.persistence.repositories.worker_repository import WorkerRepository
from src.security.principal import Principal

router = APIRouter(prefix="/workers", tags=["Workers"])


def _to_response(w) -> WorkerResponse:
    queues = w.queues_json if isinstance(w.queues_json, list) else []
    caps = (
        {"capabilities": w.capabilities_json}
        if isinstance(w.capabilities_json, list)
        else w.capabilities_json or {}
    )
    return WorkerResponse(
        worker_id=w.worker_id,
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
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status (active, draining, offline)"
    ),
) -> WorkerListResponse:
    workers = await worker_repo.list_workers(status=status_filter)
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
    worker_id: str, worker_repo: Annotated[WorkerRepository, Depends(get_worker_repository)]
) -> WorkerResponse:
    worker = await worker_repo.get_by_id(worker_id)
    if not worker:
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
    await worker_repo.set_draining(worker_id)
    updated = await worker_repo.get_by_id(worker_id)
    return _to_response(updated or worker)


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
    deleted = await worker_repo.delete_worker(worker_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Worker '{worker_id}' not found."
        )

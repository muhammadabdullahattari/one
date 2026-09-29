from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_queue_repository, get_task_repository, require_role
from src.api.schemas.queues import (
    QueueCreateRequest,
    QueueDepthResponse,
    QueueListResponse,
    QueueResponse,
    QueueUpdateRequest,
)
from src.api.schemas.tasks import TaskListResponse, TaskResponse
from src.domain.entities import Queue
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.task_repository import TaskRepository
from src.security.principal import Principal

router = APIRouter(prefix="/queues", tags=["Queues"])


@router.get("", response_model=QueueListResponse, summary="List all configured task queues")
async def list_queues(
    queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)],
) -> QueueListResponse:
    queues = await queue_repo.list_queues()
    return QueueListResponse(
        items=[QueueResponse.model_validate(q) for q in queues],
        total=len(queues),
        limit=len(queues) or 50,
        offset=0,
        has_more=False,
    )


@router.post(
    "",
    response_model=QueueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or register a new task queue",
)
async def create_queue(
    request: QueueCreateRequest,
    queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> QueueResponse:
    existing = await queue_repo.get_by_name(request.queue_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Queue '{request.queue_name}' already exists.",
        )
    queue = Queue(
        queue_name=request.queue_name,
        enabled=request.enabled,
        default_priority=request.default_priority,
        max_concurrency=request.max_concurrency,
        rate_limit_rps=request.rate_limit_rps if request.rate_limit_rps is not None else 100,
        broker_backend=request.broker_backend,
    )
    saved = await queue_repo.create_or_update_queue(queue)
    return QueueResponse.model_validate(saved)


@router.get("/{name}", response_model=QueueResponse, summary="Get queue configuration details")
async def get_queue(
    name: str, queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)]
) -> QueueResponse:
    queue = await queue_repo.get_by_name(name)
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Queue '{name}' not found."
        )
    return QueueResponse.model_validate(queue)


@router.put(
    "/{name}", response_model=QueueResponse, summary="Update an existing queue configuration"
)
async def update_queue(
    name: str,
    request: QueueUpdateRequest,
    queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> QueueResponse:
    existing = await queue_repo.get_by_name(name)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Queue '{name}' not found."
        )
    updated_queue = Queue(
        queue_name=name,
        enabled=request.enabled if request.enabled is not None else existing.enabled,
        default_priority=request.default_priority
        if request.default_priority is not None
        else existing.default_priority,
        max_concurrency=request.max_concurrency
        if request.max_concurrency is not None
        else existing.max_concurrency,
        rate_limit_rps=request.rate_limit_rps
        if request.rate_limit_rps is not None
        else existing.rate_limit_rps,
        broker_backend=request.broker_backend
        if request.broker_backend is not None
        else existing.broker_backend,
        created_at=existing.created_at,
    )
    saved = await queue_repo.create_or_update_queue(updated_queue)
    return QueueResponse.model_validate(saved)


@router.delete(
    "/{name}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a queue configuration"
)
async def delete_queue(
    name: str,
    queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)],
    principal: Annotated[Principal, Depends(require_role("admin"))],
) -> None:
    depth = await queue_repo.get_queue_depth(name)
    if depth > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete queue '{name}' because it contains {depth} pending tasks.",
        )
    deleted = await queue_repo.delete_queue(name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Queue '{name}' not found."
        )


@router.get(
    "/{name}/depth",
    response_model=QueueDepthResponse,
    summary="Get real-time queue depth and oldest task age",
)
async def get_queue_depth(
    name: str, queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)]
) -> QueueDepthResponse:
    depth = await queue_repo.get_queue_depth(name)
    oldest_age = await queue_repo.get_oldest_task_age(name)
    return QueueDepthResponse(queue_name=name, depth=depth, oldest_task_age_seconds=oldest_age)


@router.get(
    "/{name}/tasks",
    response_model=TaskListResponse,
    summary="List tasks currently in a specific queue",
)
async def get_queue_tasks(
    name: str,
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> TaskListResponse:
    tasks = await task_repo.list_tasks(queue=name, limit=limit, offset=offset)
    total = await task_repo.count_tasks(queue=name)
    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(tasks) < total,
    )

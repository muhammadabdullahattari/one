from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import (
    enforce_tenant_access,
    get_current_principal,
    get_task_repository,
    get_task_service,
    require_role,
)
from src.api.schemas.tasks import (
    TaskAttemptResponse,
    TaskCancelRequest,
    TaskDetailResponse,
    TaskEventResponse,
    TaskListResponse,
    TaskResponse,
    TaskRetryRequest,
    TaskSubmitRequest,
)
from src.application.task_service import TaskService
from src.core.constants import TaskStatus
from src.domain.exceptions import TaskNotFoundError
from src.persistence.repositories.task_repository import TaskRepository
from src.security.principal import Principal

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a task for asynchronous execution",
)
async def submit_task(
    request: TaskSubmitRequest,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> TaskResponse:
    if principal.tenant_id and not (principal.is_admin and principal.tenant_id is None):
        if request.tenant_id and request.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-tenant submission forbidden: Principal '{principal.principal_id}' cannot submit tasks for tenant '{request.tenant_id}'.",
            )
        tenant_id = principal.tenant_id
    else:
        tenant_id = request.tenant_id or principal.tenant_id or "default"

    task = await task_service.submit_task(
        task_type=request.task_type,
        payload=request.payload,
        queue=request.queue,
        priority=request.priority,
        max_attempts=request.max_attempts,
        timeout_seconds=request.timeout_seconds,
        idempotency_key=request.idempotency_key,
        delay_seconds=request.delay_seconds,
        tenant_id=tenant_id,
        metadata=request.metadata,
    )
    return TaskResponse.model_validate(task)


@router.get("", response_model=TaskListResponse, summary="List tasks with filtering and pagination")
async def list_tasks(
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    queue: Annotated[str | None, Query(description="Filter by queue name")] = None,
    status_filter: Annotated[
        TaskStatus | None, Query(alias="status", description="Filter by task status")
    ] = None,
    task_type: Annotated[str | None, Query(description="Filter by registered task type")] = None,
    tenant_id: Annotated[str | None, Query(description="Filter by tenant ID")] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Page limit")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> TaskListResponse:
    if principal.tenant_id and not (principal.is_admin and principal.tenant_id is None):
        if tenant_id and tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-tenant access forbidden: Principal '{principal.principal_id}' cannot access tenant '{tenant_id}'.",
            )
        effective_tenant = principal.tenant_id
    else:
        effective_tenant = tenant_id

    tasks = await task_repo.list_tasks(
        queue=queue,
        status=status_filter,
        task_type=task_type,
        tenant_id=effective_tenant,
        limit=limit,
        offset=offset,
    )
    total = await task_repo.count_tasks(
        queue=queue, status=status_filter, task_type=task_type, tenant_id=effective_tenant
    )
    has_more = offset + len(tasks) < total
    return TaskListResponse(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get(
    "/{task_id}",
    response_model=TaskDetailResponse,
    summary="Get detailed task state and execution results",
)
async def get_task(
    task_id: UUID,
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> TaskDetailResponse:
    task = await task_repo.get_task(task_id)
    if not task:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
    enforce_tenant_access(principal, task.tenant_id)
    return TaskDetailResponse.model_validate(task)


@router.delete(
    "/{task_id}", response_model=TaskResponse, summary="Cancel a pending, scheduled, or queued task"
)
async def cancel_task(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
    request: TaskCancelRequest | None = None,
) -> TaskResponse:
    task = await task_repo.get_task(task_id)
    if not task:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
    enforce_tenant_access(principal, task.tenant_id)
    reason = request.reason if request and request.reason else "User requested cancellation"
    cancelled = await task_service.cancel_task(task_id, reason=reason)
    return TaskResponse.model_validate(cancelled)


@router.post(
    "/{task_id}/retry",
    response_model=TaskResponse,
    summary="Manually trigger a retry for a failed or dead task",
)
async def retry_task(
    task_id: UUID,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
    request: TaskRetryRequest | None = None,
) -> TaskResponse:
    task = await task_repo.get_task(task_id)
    if not task:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
    enforce_tenant_access(principal, task.tenant_id)
    delay = request.delay_seconds if request else 0
    reset = request.reset_attempts if request else False
    retried = await task_service.retry_task(task_id, delay_seconds=delay, reset_attempts=reset)
    return TaskResponse.model_validate(retried)


@router.get(
    "/{task_id}/attempts",
    response_model=list[TaskAttemptResponse],
    summary="List all execution attempt records for a task",
)
async def get_task_attempts(
    task_id: UUID,
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> list[TaskAttemptResponse]:
    task = await task_repo.get_task(task_id)
    if not task:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
    enforce_tenant_access(principal, task.tenant_id)
    attempts = await task_repo.get_task_attempts(task_id)
    return [TaskAttemptResponse.model_validate(a) for a in attempts]


@router.get(
    "/{task_id}/events",
    response_model=list[TaskEventResponse],
    summary="List lifecycle audit timeline events for a task",
)
async def get_task_events(
    task_id: UUID,
    task_repo: Annotated[TaskRepository, Depends(get_task_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> list[TaskEventResponse]:
    task = await task_repo.get_task(task_id)
    if not task:
        raise TaskNotFoundError(f"Task with ID '{task_id}' not found.")
    enforce_tenant_access(principal, task.tenant_id)
    events = await task_repo.get_task_events(task_id)
    return [TaskEventResponse.model_validate(e) for e in events]


# @router.get("", response_model= TaskEventsData)
# def getevents( ) -> TaskEventsData :

#     result = get_task_repository.gettaskeventdata()

#     data = TaskEventsData(
#             task_id = result.task_id ,
#             tenant_id= result.tenant_id,
#             task_type= result.task_type,
#             status = result.status,
#             )

#     return  data

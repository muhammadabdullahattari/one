from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import (
    enforce_tenant_access,
    get_current_principal,
    get_schedule_repository,
    get_task_service,
    require_role,
)
from src.api.schemas.schedules import (
    ScheduledJobCreateRequest,
    ScheduledJobListResponse,
    ScheduledJobResponse,
    ScheduledJobUpdateRequest,
)
from src.api.schemas.tasks import TaskResponse
from src.application.task_service import TaskService
from src.domain.entities import Schedule
from src.persistence.repositories.schedule_repository import ScheduleRepository
from src.scheduler.cron import calculate_next_run
from src.security.principal import Principal

router = APIRouter(prefix="/schedules", tags=["Schedules"])


def _to_response(s: Schedule) -> ScheduledJobResponse:
    return ScheduledJobResponse(
        schedule_id=s.schedule_id,
        tenant_id=s.tenant_id,
        task_type=s.task_type,
        queue=s.queue,
        cron=s.cron_expression,
        interval_seconds=s.interval_seconds,
        timezone=s.timezone,
        misfire_policy=s.misfire_policy,
        enabled=s.enabled,
        payload=s.payload or {},
        next_run_at=s.next_run_at,
        last_run_at=s.last_run_at,
        total_run_count=s.version,
        created_at=s.created_at or datetime.now(UTC),
        updated_at=s.updated_at or datetime.now(UTC),
    )


@router.get(
    "", response_model=ScheduledJobListResponse, summary="List all recurring schedule definitions"
)
async def list_schedules(
    schedule_repo: Annotated[ScheduleRepository, Depends(get_schedule_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    enabled_only: bool = Query(False, description="Filter only enabled schedules"),
    tenant_id: str | None = Query(None, description="Filter by tenant ID"),
) -> ScheduledJobListResponse:
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

    schedules = await schedule_repo.list_schedules(
        enabled_only=enabled_only, tenant_id=effective_tenant
    )
    return ScheduledJobListResponse(
        items=[_to_response(s) for s in schedules],
        total=len(schedules),
        limit=len(schedules) or 50,
        offset=0,
        has_more=False,
    )


@router.post(
    "",
    response_model=ScheduledJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new recurring schedule definition",
)
async def create_schedule(
    request: ScheduledJobCreateRequest,
    schedule_repo: Annotated[ScheduleRepository, Depends(get_schedule_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> ScheduledJobResponse:
    now = datetime.now(UTC)
    next_run: datetime | None = None
    if request.cron:
        try:
            next_run = calculate_next_run(request.cron, now, tz_str=request.timezone)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid cron expression '{request.cron}': {exc}",
            ) from exc
    elif request.interval_seconds:
        next_run = now + timedelta(seconds=request.interval_seconds)

    if principal.tenant_id and not (principal.is_admin and principal.tenant_id is None):
        if request.tenant_id and request.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-tenant schedule creation forbidden: Principal '{principal.principal_id}' cannot create schedule for tenant '{request.tenant_id}'.",
            )
        tenant_id = principal.tenant_id
    else:
        tenant_id = request.tenant_id or principal.tenant_id or "default"

    schedule = Schedule(
        schedule_id=uuid4(),
        tenant_id=tenant_id,
        task_type=request.task_type,
        queue=request.queue,
        payload=request.payload or None,
        cron_expression=request.cron,
        interval_seconds=request.interval_seconds,
        timezone=request.timezone,
        misfire_policy=request.misfire_policy,
        enabled=request.enabled,
        next_run_at=next_run,
        last_run_at=None,
        created_at=now,
        updated_at=now,
    )
    saved = await schedule_repo.create_schedule(schedule)
    return _to_response(saved)


@router.get(
    "/{schedule_id}",
    response_model=ScheduledJobResponse,
    summary="Get details for a specific schedule",
)
async def get_schedule(
    schedule_id: UUID,
    schedule_repo: Annotated[ScheduleRepository, Depends(get_schedule_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> ScheduledJobResponse:
    schedule = await schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule '{schedule_id}' not found."
        )
    enforce_tenant_access(principal, schedule.tenant_id)
    return _to_response(schedule)


@router.put(
    "/{schedule_id}",
    response_model=ScheduledJobResponse,
    summary="Update a recurring schedule definition",
)
async def update_schedule(
    schedule_id: UUID,
    request: ScheduledJobUpdateRequest,
    schedule_repo: Annotated[ScheduleRepository, Depends(get_schedule_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> ScheduledJobResponse:
    schedule = await schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule '{schedule_id}' not found."
        )
    enforce_tenant_access(principal, schedule.tenant_id)
    now = datetime.now(UTC)
    cron_val = request.cron if request.cron is not None else schedule.cron_expression
    int_val = (
        request.interval_seconds
        if request.interval_seconds is not None
        else schedule.interval_seconds
    )
    tz_val = request.timezone if request.timezone is not None else schedule.timezone
    misfire_val = (
        request.misfire_policy if request.misfire_policy is not None else schedule.misfire_policy
    )
    enabled_val = request.enabled if request.enabled is not None else schedule.enabled
    next_run = schedule.next_run_at
    if cron_val:
        next_run = calculate_next_run(cron_val, now, tz_str=tz_val)
    elif int_val:
        next_run = now + timedelta(seconds=int_val)
    updated_schedule = Schedule(
        schedule_id=schedule_id,
        tenant_id=schedule.tenant_id,
        task_type=schedule.task_type,
        queue=schedule.queue,
        cron_expression=cron_val,
        interval_seconds=int_val,
        timezone=tz_val,
        misfire_policy=misfire_val,
        enabled=enabled_val,
        next_run_at=next_run,
        last_run_at=schedule.last_run_at,
        version=schedule.version,
        created_at=schedule.created_at,
        updated_at=now,
    )
    saved = await schedule_repo.update_schedule(updated_schedule)
    return _to_response(saved)


@router.delete(
    "/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a recurring schedule"
)
async def delete_schedule(
    schedule_id: UUID,
    schedule_repo: Annotated[ScheduleRepository, Depends(get_schedule_repository)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> None:
    schedule = await schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule '{schedule_id}' not found."
        )
    enforce_tenant_access(principal, schedule.tenant_id)
    deleted = await schedule_repo.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule '{schedule_id}' not found."
        )


@router.post(
    "/{schedule_id}/trigger",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Manually trigger immediate execution of a scheduled job",
)
async def trigger_schedule(
    schedule_id: UUID,
    schedule_repo: Annotated[ScheduleRepository, Depends(get_schedule_repository)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
    principal: Annotated[Principal, Depends(require_role("admin", "operator"))],
) -> TaskResponse:
    schedule = await schedule_repo.get_by_id(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule '{schedule_id}' not found."
        )
    enforce_tenant_access(principal, schedule.tenant_id)
    task = await task_service.submit_task(
        task_type=schedule.task_type,
        payload=schedule.payload,
        queue=schedule.queue,
        tenant_id=schedule.tenant_id,
        schedule_id=schedule.schedule_id,
        metadata={"triggered_by_schedule": str(schedule_id), "manual_trigger": True},
    )
    return TaskResponse.model_validate(task)

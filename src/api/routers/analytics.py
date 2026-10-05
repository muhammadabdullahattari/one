from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_current_principal,
    get_queue_repository,
    get_worker_repository,
)
from src.api.schemas.analytics import (
    BrokerHealthItem,
    BrokerStatsResponse,
    LatencyPercentiles,
    LatencyResponse,
    OldestTaskAgeItem,
    OldestTaskAgeResponse,
    QueueDepthPoint,
    QueueDepthTrendResponse,
    StatusDistributionItem,
    StatusDistributionResponse,
    TaskTypeStatItem,
    TaskTypeStatsResponse,
    ThroughputPoint,
    ThroughputResponse,
    WorkerUtilizationItem,
    WorkerUtilizationResponse,
)
from src.broker.registry import BrokerRegistry
from src.core.constants import TaskStatus
from src.observability.metrics import generate_metrics_text, get_metrics_content_type
from src.persistence.models.task import TaskModel
from src.persistence.models.task_attempt import TaskAttemptModel
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.repositories.worker_repository import WorkerRepository
from src.persistence.session import get_db_session
from src.security.principal import Principal

router = APIRouter(tags=["Analytics & Observability"])


def _effective_tenant(principal: Principal) -> str | None:
    """Return the tenant_id that must be used for isolation.

    - Global admin with tenant_id=None → unscoped (cluster-wide telemetry).
    - All other users → strictly isolated to their own tenant telemetry.
    """
    if principal.is_admin and principal.tenant_id is None:
        return None
    return principal.tenant_id or principal.principal_id


@router.get(
    "/analytics/throughput",
    response_model=ThroughputResponse,
    summary="Get dual-line chart data for incoming vs outgoing throughput",
)
async def get_throughput(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    hours: int = Query(24, ge=1, le=168, description="Time range in hours"),
) -> ThroughputResponse:
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=hours)
    tenant = _effective_tenant(principal)

    stmt = select(TaskModel.created_at, TaskModel.status).where(TaskModel.created_at >= cutoff)
    if tenant:
        stmt = stmt.where(TaskModel.tenant_id == tenant)
    res = await session.execute(stmt)
    rows = res.all()

    bucket_count = 12 if hours <= 2 else min(hours, 24)
    bucket_seconds = (hours * 3600) / bucket_count

    bucket_in = [0] * bucket_count
    bucket_out = [0] * bucket_count
    terminal_statuses = {
        TaskStatus.SUCCEEDED.value,
        TaskStatus.FAILED.value,
        TaskStatus.DEAD.value,
    }

    recent_cutoff = now - timedelta(minutes=15)
    recent_in = 0
    recent_out = 0

    for row in rows:
        created_at = row[0]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        offset_sec = (created_at - cutoff).total_seconds()
        idx = int(offset_sec // bucket_seconds)
        if 0 <= idx < bucket_count:
            bucket_in[idx] += 1
            if str(row[1]) in terminal_statuses:
                bucket_out[idx] += 1
        elif idx >= bucket_count:
            bucket_in[-1] += 1
            if str(row[1]) in terminal_statuses:
                bucket_out[-1] += 1

        if created_at >= recent_cutoff:
            recent_in += 1
            if str(row[1]) in terminal_statuses:
                recent_out += 1

    points: list[ThroughputPoint] = []
    for i in range(bucket_count):
        pt_time = cutoff + timedelta(seconds=(i + 1) * bucket_seconds)
        rate_in = round(bucket_in[i] / bucket_seconds, 2)
        rate_out = round(bucket_out[i] / bucket_seconds, 2)
        if bucket_in[i] > 0 and rate_in == 0.0:
            rate_in = round(bucket_in[i] / bucket_seconds, 3)
        if bucket_out[i] > 0 and rate_out == 0.0:
            rate_out = round(bucket_out[i] / bucket_seconds, 3)
        points.append(
            ThroughputPoint(timestamp=pt_time, incoming_rate=rate_in, outgoing_rate=rate_out)
        )

    # Current rate based on recent 15 minutes window, or overall window
    current_in_tps = (
        round(recent_in / 900.0, 2)
        if recent_in > 0
        else (round(len(rows) / (hours * 3600), 2) if rows else 0.0)
    )
    current_out_tps = round(recent_out / 900.0, 2) if recent_out > 0 else 0.0

    return ThroughputResponse(
        points=points, current_incoming_tps=current_in_tps, current_outgoing_tps=current_out_tps
    )


@router.get(
    "/analytics/status-distribution",
    response_model=StatusDistributionResponse,
    summary="Get task status breakdown distribution",
)
async def get_status_distribution(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    queue: str | None = Query(None, description="Optional queue filter"),
) -> StatusDistributionResponse:
    stmt = select(TaskModel.status, func.count(TaskModel.task_id))
    if queue:
        stmt = stmt.where(TaskModel.queue == queue)
    tenant = _effective_tenant(principal)
    if tenant:
        stmt = stmt.where(TaskModel.tenant_id == tenant)
    stmt = stmt.group_by(TaskModel.status)
    res = await session.execute(stmt)
    rows = res.all()
    total = sum(int(r[1]) for r in rows)
    distribution = [
        StatusDistributionItem(
            status=str(r[0]),
            count=int(r[1]),
            percentage=round(int(r[1]) / total * 100.0, 2) if total > 0 else 0.0,
        )
        for r in rows
    ]
    return StatusDistributionResponse(distribution=distribution, total_tasks=total)


@router.get(
    "/analytics/latency",
    response_model=LatencyResponse,
    summary="Get P50/P95/P99 latency for queue wait and execution",
)
async def get_latency(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    queue: str | None = Query(None, description="Optional queue filter"),
) -> LatencyResponse:
    exec_ms = (
        func.extract("epoch", TaskAttemptModel.finished_at - TaskAttemptModel.started_at) * 1000.0
    )
    wait_ms = func.extract("epoch", TaskAttemptModel.started_at - TaskModel.created_at) * 1000.0

    exec_stmt = (
        select(
            func.percentile_cont(0.50).within_group(exec_ms).label("p50"),
            func.percentile_cont(0.95).within_group(exec_ms).label("p95"),
            func.percentile_cont(0.99).within_group(exec_ms).label("p99"),
            func.avg(exec_ms).label("avg"),
        )
        .select_from(TaskAttemptModel)
        .join(TaskModel, TaskAttemptModel.task_id == TaskModel.task_id)
        .where(TaskAttemptModel.finished_at.isnot(None))
    )
    wait_stmt = (
        select(
            func.percentile_cont(0.50).within_group(wait_ms).label("p50"),
            func.percentile_cont(0.95).within_group(wait_ms).label("p95"),
            func.percentile_cont(0.99).within_group(wait_ms).label("p99"),
            func.avg(wait_ms).label("avg"),
        )
        .select_from(TaskAttemptModel)
        .join(TaskModel, TaskAttemptModel.task_id == TaskModel.task_id)
        .where(TaskAttemptModel.started_at.isnot(None))
    )
    if queue:
        exec_stmt = exec_stmt.where(TaskModel.queue == queue)
        wait_stmt = wait_stmt.where(TaskModel.queue == queue)
    tenant = _effective_tenant(principal)
    if tenant:
        exec_stmt = exec_stmt.where(TaskModel.tenant_id == tenant)
        wait_stmt = wait_stmt.where(TaskModel.tenant_id == tenant)

    exec_row = (await session.execute(exec_stmt)).one()
    wait_row = (await session.execute(wait_stmt)).one()

    def _ms(row: object, field: str) -> float:
        val = getattr(row, field, None)
        return round(float(val), 3) if val is not None else 0.0

    ep50, ep95, ep99, eavg = (
        _ms(exec_row, "p50"),
        _ms(exec_row, "p95"),
        _ms(exec_row, "p99"),
        _ms(exec_row, "avg"),
    )
    wp50, wp95, wp99, wavg = (
        _ms(wait_row, "p50"),
        _ms(wait_row, "p95"),
        _ms(wait_row, "p99"),
        _ms(wait_row, "avg"),
    )

    return LatencyResponse(
        queue_wait=LatencyPercentiles(p50_ms=wp50, p95_ms=wp95, p99_ms=wp99, avg_ms=wavg),
        execution_duration=LatencyPercentiles(p50_ms=ep50, p95_ms=ep95, p99_ms=ep99, avg_ms=eavg),
        e2e_duration=LatencyPercentiles(
            p50_ms=round(wp50 + ep50, 3),
            p95_ms=round(wp95 + ep95, 3),
            p99_ms=round(wp99 + ep99, 3),
            avg_ms=round(wavg + eavg, 3),
        ),
    )


@router.get(
    "/analytics/worker-utilization",
    response_model=WorkerUtilizationResponse,
    summary="Get worker capacity utilization",
)
async def get_worker_utilization(
    worker_repo: Annotated[WorkerRepository, Depends(get_worker_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> WorkerUtilizationResponse:
    effective_tenant = _effective_tenant(principal)
    workers = await worker_repo.list_workers(tenant_id=effective_tenant)
    items: list[WorkerUtilizationItem] = []
    total_util = 0.0
    for w in workers:
        util = round(w.active_slots / max(1, w.concurrency) * 100.0, 2)
        total_util += util
        items.append(
            WorkerUtilizationItem(
                worker_id=w.worker_id,
                hostname=w.hostname,
                active_slots=w.active_slots,
                total_concurrency=w.concurrency,
                utilization_percent=util,
                status=w.status,
            )
        )
    avg_util = round(total_util / len(workers), 2) if workers else 0.0
    return WorkerUtilizationResponse(workers=items, average_utilization_percent=avg_util)


@router.get(
    "/analytics/task-types",
    response_model=TaskTypeStatsResponse,
    summary="Get volume and success metrics by task_type",
)
async def get_task_type_stats(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> TaskTypeStatsResponse:
    durations_stmt = (
        select(
            TaskModel.task_type,
            func.avg(
                func.extract("epoch", TaskAttemptModel.finished_at - TaskAttemptModel.started_at)
                * 1000.0
            ),
        )
        .select_from(TaskAttemptModel)
        .join(TaskModel, TaskAttemptModel.task_id == TaskModel.task_id)
        .where(TaskAttemptModel.finished_at.isnot(None))
    )
    stmt = select(
        TaskModel.task_type,
        func.count(TaskModel.task_id).label("total"),
        func.count(TaskModel.task_id)
        .filter(TaskModel.status == TaskStatus.SUCCEEDED.value)
        .label("success"),
        func.count(TaskModel.task_id)
        .filter(TaskModel.status.in_([TaskStatus.FAILED.value, TaskStatus.DEAD.value]))
        .label("failed"),
    )
    tenant = _effective_tenant(principal)
    if tenant:
        durations_stmt = durations_stmt.where(TaskModel.tenant_id == tenant)
        stmt = stmt.where(TaskModel.tenant_id == tenant)

    durations_stmt = durations_stmt.group_by(TaskModel.task_type)
    durations_res = await session.execute(durations_stmt)
    avg_map = {str(row[0]): float(row[1]) for row in durations_res.all() if row[1] is not None}

    stmt = stmt.group_by(TaskModel.task_type)
    res = await session.execute(stmt)
    rows = res.all()
    stats = [
        TaskTypeStatItem(
            task_type=str(r.task_type),
            total_count=int(r.total),
            success_count=int(r.success or 0),
            failed_count=int(r.failed or 0),
            success_rate=round(int(r.success or 0) / int(r.total) * 100.0, 2)
            if int(r.total) > 0
            else 0.0,
            avg_duration_ms=round(avg_map.get(str(r.task_type), 0.0), 3),
        )
        for r in rows
    ]
    return TaskTypeStatsResponse(stats=stats)


@router.get(
    "/analytics/queue-depth",
    response_model=QueueDepthTrendResponse,
    summary="Get backlog trend across active queues",
)
async def get_queue_depth_trend(
    queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> QueueDepthTrendResponse:
    now = datetime.now(UTC)
    effective_tenant = _effective_tenant(principal)
    summary = await queue_repo.get_queue_backlog_summary(tenant_id=effective_tenant)
    points = [
        QueueDepthPoint(
            queue_name=q_name,
            depth=depth,
            oldest_task_age_seconds=oldest_age,
            timestamp=now,
        )
        for q_name, depth, oldest_age in summary
    ]
    return QueueDepthTrendResponse(queues=points)


@router.get(
    "/analytics/oldest-task-age",
    response_model=OldestTaskAgeResponse,
    summary="Expose oldest-task age per queue",
)
async def get_oldest_task_age_report(
    queue_repo: Annotated[QueueRepository, Depends(get_queue_repository)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> OldestTaskAgeResponse:
    effective_tenant = _effective_tenant(principal)
    queues = await queue_repo.list_queues(tenant_id=effective_tenant)
    oldest_stmt = select(TaskModel.task_id, TaskModel.queue, TaskModel.created_at).where(
        TaskModel.status.in_(
            [TaskStatus.PENDING.value, TaskStatus.QUEUED.value, TaskStatus.RETRY_WAIT.value]
        )
    )
    if effective_tenant:
        oldest_stmt = oldest_stmt.where(TaskModel.tenant_id == effective_tenant)
    oldest_stmt = oldest_stmt.distinct(TaskModel.queue).order_by(
        TaskModel.queue, TaskModel.created_at.asc()
    )
    res = await session.execute(oldest_stmt)
    oldest_by_queue = {row.queue: (row.task_id, row.created_at) for row in res.all()}
    now = datetime.now(UTC)
    items: list[OldestTaskAgeItem] = []
    for q in queues:
        task_info = oldest_by_queue.get(q.queue_name)
        oldest_id = task_info[0] if task_info else None
        oldest_created = task_info[1] if task_info else None
        age_seconds: float | None = None
        warning = False
        if oldest_created:
            if oldest_created.tzinfo is None:
                oldest_created = oldest_created.replace(tzinfo=UTC)
            age_seconds = max(0.0, (now - oldest_created).total_seconds())
            warning = age_seconds > 300.0
        items.append(
            OldestTaskAgeItem(
                queue_name=q.queue_name,
                oldest_task_id=oldest_id,
                oldest_task_age_seconds=age_seconds,
                threshold_warning=warning,
            )
        )
    return OldestTaskAgeResponse(queues=items)


@router.get(
    "/brokers",
    response_model=list[BrokerHealthItem],
    summary="List broker backends and health status",
)
async def list_broker_backends() -> list[BrokerHealthItem]:
    backends = BrokerRegistry.list_backends()
    items: list[BrokerHealthItem] = []
    for b in backends:
        items.append(
            BrokerHealthItem(
                backend=b, backend_type=b, connected=True, status="healthy", active_consumers=1
            )
        )
    return items


@router.get(
    "/brokers/{backend}/stats",
    response_model=BrokerStatsResponse,
    summary="Get separate load metrics for native vs Redis broker adapters",
)
async def get_broker_stats(
    backend: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> BrokerStatsResponse:
    stmt = select(
        func.count(TaskModel.task_id).label("total"),
        func.count(TaskModel.task_id)
        .filter(TaskModel.status.in_([TaskStatus.PENDING.value, TaskStatus.QUEUED.value]))
        .label("pending"),
        func.count(TaskModel.task_id)
        .filter(TaskModel.status == TaskStatus.DEAD.value)
        .label("dead"),
    )
    tenant = _effective_tenant(principal)
    if tenant:
        stmt = stmt.where(TaskModel.tenant_id == tenant)
    res = await session.execute(stmt)
    row = res.one()
    return BrokerStatsResponse(
        backend=backend,
        published_count=int(row.total or 0),
        consumed_count=int((row.total or 0) - (row.pending or 0)),
        pending_count=int(row.pending or 0),
        dead_letter_count=int(row.dead or 0),
    )


@router.get("/metrics", summary="Prometheus text-format scrape endpoint")
async def get_prometheus_metrics() -> Response:
    data = generate_metrics_text()
    return Response(content=data, media_type=get_metrics_content_type())

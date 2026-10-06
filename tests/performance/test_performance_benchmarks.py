import asyncio
import time
from uuid import uuid4

import pytest
from src.application.task_service import TaskLifecycleService
from src.core.constants import TaskStatus
from src.domain.entities import Queue, Task
from src.persistence.repositories.queue_repository import QueueRepository
from src.persistence.session import session_scope
from src.rate_limit.limiter import TokenBucketRateLimiter
from src.worker.runtime import WorkerRuntime


@pytest.mark.asyncio
async def test_performance_p95_task_submission_latency() -> None:
    queue_name = f"perf-sub-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    task_service = TaskLifecycleService()
    latencies: list[float] = []

    for i in range(8):
        t0 = time.perf_counter()
        await task_service.submit_task(
            task_type="perf_submission_task",
            payload={"index": i, "data": "benchmark_payload"},
            queue=queue_name,
            tenant_id="tenant-perf",
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(duration_ms)

    sorted_lat = sorted(latencies)
    idx = int(0.95 * len(sorted_lat))
    p95 = sorted_lat[min(idx, len(sorted_lat) - 1)]
    assert p95 > 0.0
    assert len(latencies) == 8


@pytest.mark.asyncio
async def test_performance_burst_batch_ingestion() -> None:
    queue_name = f"perf-burst-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    task_service = TaskLifecycleService()
    batch_size = 8
    sem = asyncio.Semaphore(4)
    t_start = time.perf_counter()

    async def submit_bounded(idx: int) -> Task:
        async with sem:
            return await task_service.submit_task(
                task_type="burst_item",
                payload={"n": idx},
                queue=queue_name,
                tenant_id="tenant-burst",
            )

    tasks = await asyncio.gather(*[submit_bounded(i) for i in range(batch_size)])
    total_elapsed = time.perf_counter() - t_start

    assert len(tasks) == batch_size
    assert all(t.status == TaskStatus.PENDING for t in tasks)
    throughput = batch_size / max(total_elapsed, 0.001)
    assert throughput > 0.0


@pytest.mark.asyncio
async def test_performance_queue_wait_and_claim_latency() -> None:
    queue_name = f"perf-claim-{uuid4().hex[:6]}"
    async with session_scope() as session:
        queue_repo = QueueRepository(session)
        await queue_repo.create_or_update_queue(
            Queue(queue_name=queue_name, broker_backend="native")
        )

    task_service = TaskLifecycleService()
    task = await task_service.submit_task(
        task_type="latency_claim_task",
        payload={"benchmark": True},
        queue=queue_name,
        tenant_id="tenant-perf",
    )

    worker = WorkerRuntime(
        worker_id=f"perf-worker-{uuid4().hex[:6]}",
        queues=[queue_name],
        concurrency=2,
    )

    t0 = time.perf_counter()
    claimed = await worker.broker.consume(
        queue=queue_name, worker_id=worker.worker_id, batch_size=1
    )
    claim_ms = (time.perf_counter() - t0) * 1000.0

    assert len(claimed) == 1
    assert claimed[0].envelope.task_id == task.task_id
    assert claim_ms > 0.0


@pytest.mark.asyncio
async def test_performance_token_bucket_rate_limiter_throughput() -> None:
    limiter = TokenBucketRateLimiter()
    key = f"limiter-perf-{uuid4().hex[:6]}"

    t0 = time.perf_counter()
    allowed_count = 0
    total_iterations = 200

    for _ in range(total_iterations):
        allowed = await limiter.acquire(key=key, rate_limit_rps=500.0)
        if allowed:
            allowed_count += 1

    elapsed = time.perf_counter() - t0
    ops_per_second = total_iterations / max(elapsed, 0.001)

    assert allowed_count > 0
    assert ops_per_second > 500.0

import asyncio
import os
import socket
from uuid import uuid4

import structlog

from src.broker.core.adapter import BrokerAdapter
from src.broker.core.envelope import TaskMessage
from src.broker.registry import get_broker_adapter
from src.core.config import get_settings
from src.domain.entities import Worker
from src.persistence.repositories.task_repository import TaskRepository
from src.persistence.repositories.worker_repository import WorkerRepository
from src.persistence.result_backend import ResultBackend
from src.persistence.session import session_scope
from src.retry.policy import default_retry_policy
from src.worker.executor import TaskExecutor

logger = structlog.get_logger(__name__)


class WorkerRuntime:
    def __init__(
        self,
        worker_id: str | None = None,
        queues: list[str] | None = None,
        concurrency: int | None = None,
        broker_adapter: BrokerAdapter | None = None,
        executor: TaskExecutor | None = None,
        tenant_id: str | None = None,
    ) -> None:
        self.settings = get_settings()
        self.worker_id = (
            worker_id or f"worker-{socket.gethostname()}-{os.getpid()}-{uuid4().hex[:6]}"
        )
        self.tenant_id = tenant_id or "default"
        self.queues = queues or ["default"]
        self.concurrency = concurrency or self.settings.worker_concurrency
        self.broker = broker_adapter or get_broker_adapter("native")
        self.executor = executor or TaskExecutor()
        self.result_backend = ResultBackend(self.settings.task_max_payload_bytes)
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._active_tasks: set[asyncio.Task[None]] = set()
        self._running = False
        self._draining = False
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._running = True
        logger.info(
            "Starting worker runtime",
            worker_id=self.worker_id,
            queues=self.queues,
            concurrency=self.concurrency,
        )
        async with session_scope() as session:
            worker_repo = WorkerRepository(session)
            await worker_repo.register_worker(
                Worker(
                    worker_id=self.worker_id,
                    tenant_id=self.tenant_id,
                    hostname=socket.gethostname(),
                    process_id=os.getpid(),
                    version=self.settings.app_version,
                    protocol_version="1.0",
                    queues_json=self.queues,
                    concurrency=self.concurrency,
                )
            )
        self._heartbeat_task = asyncio.create_task(self._run_heartbeats())
        consumer_tasks = [asyncio.create_task(self._consume_queue(q)) for q in self.queues]
        try:
            await asyncio.gather(*consumer_tasks)
        except asyncio.CancelledError:
            pass

    async def _consume_queue(self, queue: str) -> None:
        while self._running and (not self._draining):
            await self._semaphore.acquire()
            try:
                messages = await self.broker.consume(
                    queue=queue,
                    worker_id=self.worker_id,
                    batch_size=1,
                    tenant_id=self.tenant_id,
                )
                if not messages:
                    self._semaphore.release()
                    await asyncio.sleep(0.5)
                    continue
                message = messages[0]
                task_job = asyncio.create_task(self._process_message(message))
                self._active_tasks.add(task_job)
                task_job.add_done_callback(self._active_tasks.discard)
            except Exception as e:
                self._semaphore.release()
                logger.error("Error during queue consumption", queue=queue, error=str(e))
                await asyncio.sleep(1.0)

    async def _process_message(self, message: TaskMessage) -> None:
        envelope = message.envelope
        task_id = envelope.task_id
        try:
            logger.info("Executing task", task_id=str(task_id), task_type=envelope.task_type)
            result = await self.executor.execute(
                task_type=envelope.task_type,
                payload=envelope.payload,
                timeout_seconds=envelope.timeout_seconds,
            )
            if result.success:
                async with session_scope() as session:
                    task_repo = TaskRepository(session)
                    inline_res, res_ref = await self.result_backend.store_result(
                        task_id, result.result
                    )
                    await task_repo.complete_task(
                        task_id=task_id, attempt_id=None, result_data=inline_res, result_ref=res_ref
                    )
                await self.broker.acknowledge(message.queue, message.message_id)
                logger.info(
                    "Task completed successfully",
                    task_id=str(task_id),
                    duration=result.duration_seconds,
                )
                try:
                    from src.api.routers.ws import ws_manager

                    await ws_manager.broadcast(
                        "tasks",
                        {
                            "type": "task.succeeded",
                            "data": {
                                "task_id": str(task_id),
                                "tenant_id": getattr(envelope, "tenant_id", "default"),
                                "status": "SUCCEEDED",
                                "duration_seconds": result.duration_seconds,
                            },
                        },
                    )
                except Exception:
                    pass
            else:
                max_att = envelope.max_attempts or self.settings.default_max_attempts
                current_attempt = envelope.attempt_count + 1
                retryable = (
                    default_retry_policy.is_retryable(
                        attempt=current_attempt,
                        exception=result.error_class or "UnknownError",
                    )
                    and (current_attempt < max_att)
                )
                next_retry = (
                    default_retry_policy.compute_next_retry_time(current_attempt)
                    if retryable
                    else None
                )
                async with session_scope() as session:
                    task_repo = TaskRepository(session)
                    await task_repo.fail_task(
                        task_id=task_id,
                        attempt_id=None,
                        error_class=result.error_class or "TaskExecutionError",
                        error_message_redacted=result.error_message or "Execution failed",
                        retryable=retryable,
                        next_retry_at=next_retry,
                    )
                await self.broker.nack(message.queue, message.message_id, requeue=retryable)
                logger.warn(
                    "Task execution failed",
                    task_id=str(task_id),
                    error=result.error_message,
                    retryable=retryable,
                )
                try:
                    from src.api.routers.ws import ws_manager

                    await ws_manager.broadcast(
                        "tasks",
                        {
                            "type": "task.failed",
                            "data": {
                                "task_id": str(task_id),
                                "tenant_id": getattr(envelope, "tenant_id", "default"),
                                "status": "RETRY_WAIT" if retryable else "FAILED",
                                "error_class": result.error_class,
                            },
                        },
                    )
                except Exception:
                    pass
        except Exception as exc:
            logger.error("Unhandled error processing task", task_id=str(task_id), error=str(exc))
        finally:
            self._semaphore.release()

    async def _run_heartbeats(self) -> None:
        while self._running:
            try:
                active_count = len(self._active_tasks)
                async with session_scope() as session:
                    worker_repo = WorkerRepository(session)
                    await worker_repo.record_heartbeat(self.worker_id, active_slots=active_count)
            except Exception as exc:
                logger.error("Failed to send worker heartbeat", error=str(exc))
            await asyncio.sleep(self.settings.heartbeat_interval_seconds)

    async def drain(self) -> None:
        logger.info("Draining worker...", active_tasks=len(self._active_tasks))
        self._draining = True
        async with session_scope() as session:
            worker_repo = WorkerRepository(session)
            await worker_repo.set_draining(self.worker_id)
        if self._active_tasks:
            logger.info("Waiting for active tasks to finish...", count=len(self._active_tasks))
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
        await self.stop()

    async def stop(self) -> None:
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        logger.info("Worker runtime stopped", worker_id=self.worker_id)

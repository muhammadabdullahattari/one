from __future__ import annotations

import asyncio
import importlib
from typing import TYPE_CHECKING, Any

from src.broker.registry import get_broker_adapter

if TYPE_CHECKING:
    from src.worker.runtime import WorkerRuntime


class TaskEngineWorker:
    def __init__(
        self,
        app: str | Any | None = None,
        queues: list[str] | None = None,
        concurrency: int | None = None,
        worker_id: str | None = None,
        tenant_id: str | None = None,
        broker_type: str = "native",
    ) -> None:
        self.app = app
        self.queues = queues or ["default"]
        self.concurrency = concurrency
        self.worker_id = worker_id
        self.tenant_id = tenant_id or "default"
        self.broker_type = broker_type
        self._runtime: WorkerRuntime | None = None

        if self.app is not None:
            self._load_app(self.app)

    def _load_app(self, app_spec: str | Any) -> None:
        if isinstance(app_spec, str):
            if ":" in app_spec:
                module_name, _ = app_spec.split(":", 1)
                importlib.import_module(module_name)
            else:
                importlib.import_module(app_spec)

    def get_runtime(self) -> WorkerRuntime:
        if self._runtime is None:
            from src.worker.runtime import WorkerRuntime

            broker = get_broker_adapter(self.broker_type)
            self._runtime = WorkerRuntime(
                worker_id=self.worker_id,
                queues=self.queues,
                concurrency=self.concurrency,
                broker_adapter=broker,
                tenant_id=self.tenant_id,
            )
        return self._runtime

    async def start(self) -> None:
        runtime = self.get_runtime()
        await runtime.start()

    async def stop(self) -> None:
        if self._runtime is not None:
            await self._runtime.drain()

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        runtime = self.get_runtime()
        try:
            loop.run_until_complete(runtime.start())
        except KeyboardInterrupt, SystemExit:
            loop.run_until_complete(runtime.drain())
        finally:
            loop.close()

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from task_engine.exceptions import (
    TaskCancelledError,
    TaskExecutionError,
    TaskTimeoutError,
)

if TYPE_CHECKING:
    from task_engine.client import TaskEngineClient


class AsyncResult:
    def __init__(
        self,
        task_id: str,
        client: TaskEngineClient | None = None,
        initial_data: dict[str, Any] | None = None,
    ) -> None:
        self.task_id = task_id
        self.client = client
        self._data: dict[str, Any] = initial_data or {}

    @property
    def id(self) -> str:
        return self.task_id

    @property
    def state(self) -> str:
        return str(self._data.get("status", "QUEUED")).upper()

    @property
    def status(self) -> str:
        return self.state

    @property
    def info(self) -> dict[str, Any]:
        return self._data

    @property
    def result(self) -> Any:
        return self._data.get("result")

    @property
    def error(self) -> str | None:
        err = self._data.get("error_message") or self._data.get("error")
        return str(err) if err is not None else None

    @property
    def error_class(self) -> str | None:
        err_cls = self._data.get("error_class")
        return str(err_cls) if err_cls is not None else None

    def ready(self) -> bool:
        return self.state in {"SUCCEEDED", "FAILED", "CANCELLED", "DEAD_LETTERED"}

    def successful(self) -> bool:
        return self.state == "SUCCEEDED"

    def failed(self) -> bool:
        return self.state in {"FAILED", "DEAD_LETTERED"}

    def refresh(self) -> dict[str, Any]:
        if self.client is None:
            return self._data
        task_info = self.client.get_task(self.task_id)
        if self.client.is_terminal_status(task_info.get("status", "")):
            try:
                res_info = self.client.get_result(self.task_id)
                task_info["result"] = res_info.get("result_data")
            except Exception:
                pass
        self._data = task_info
        return self._data

    async def refresh_async(self) -> dict[str, Any]:
        if self.client is None:
            return self._data
        task_info = await self.client.get_task_async(self.task_id)
        if self.client.is_terminal_status(task_info.get("status", "")):
            try:
                res_info = await self.client.get_result_async(self.task_id)
                task_info["result"] = res_info.get("result_data")
            except Exception:
                pass
        self._data = task_info
        return self._data

    def get(
        self,
        timeout: float | None = None,
        interval: float = 0.5,
        propagate: bool = True,
    ) -> Any:
        start_time = time.monotonic()
        while True:
            self.refresh()
            if self.ready():
                if self.successful():
                    return self.result
                if self.state == "CANCELLED":
                    raise TaskCancelledError(self.task_id)
                if propagate:
                    raise TaskExecutionError(
                        message=self.error or f"Task {self.task_id} failed",
                        task_id=self.task_id,
                        error_class=self.error_class,
                    )
                return self.result
            if timeout is not None and (time.monotonic() - start_time) > timeout:
                raise TaskTimeoutError(self.task_id, timeout)
            time.sleep(interval)

    async def get_async(
        self,
        timeout: float | None = None,
        interval: float = 0.5,
        propagate: bool = True,
    ) -> Any:
        start_time = time.monotonic()
        while True:
            await self.refresh_async()
            if self.ready():
                if self.successful():
                    return self.result
                if self.state == "CANCELLED":
                    raise TaskCancelledError(self.task_id)
                if propagate:
                    raise TaskExecutionError(
                        message=self.error or f"Task {self.task_id} failed",
                        task_id=self.task_id,
                        error_class=self.error_class,
                    )
                return self.result
            if timeout is not None and (time.monotonic() - start_time) > timeout:
                raise TaskTimeoutError(self.task_id, timeout)
            await asyncio.sleep(interval)

    def cancel(self) -> bool:
        if self.client is None:
            return False
        res = self.client.cancel_task(self.task_id)
        self.refresh()
        return bool(res.get("status") in {"CANCELLED", "cancelling"})

    async def cancel_async(self) -> bool:
        if self.client is None:
            return False
        res = await self.client.cancel_task_async(self.task_id)
        await self.refresh_async()
        return bool(res.get("status") in {"CANCELLED", "cancelling"})

    def __repr__(self) -> str:
        return f"<AsyncResult: task_id={self.task_id}, state={self.state}>"

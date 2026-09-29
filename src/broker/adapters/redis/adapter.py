import json
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from src.broker.core.adapter import BrokerAdapter
from src.broker.core.envelope import BrokerStats, TaskEnvelope, TaskMessage
from src.core.config import get_settings


class RedisBrokerAdapter(BrokerAdapter):
    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        redis_url: str | None = None,
        stream_maxlen: int | None = None,
    ) -> None:
        self._settings = get_settings()
        self._url = redis_url or self._settings.redis_url
        self._stream_maxlen = stream_maxlen or self._settings.redis_stream_maxlen
        self._client: aioredis.Redis = redis_client or aioredis.from_url(
            self._url, decode_responses=False
        )

    @property
    def backend_name(self) -> str:
        return "redis"

    @property
    def client(self) -> aioredis.Redis:
        return self._client

    def _stream_key(self, queue: str) -> str:
        return f"task_engine:stream:{queue}"

    def _group_name(self, queue: str) -> str:
        return f"task_engine:cg:{queue}"

    def _dlq_stream_key(self, queue: str) -> str:
        return f"task_engine:dlq:{queue}"

    def _lease_key(self, message_id: str) -> str:
        return f"task_engine:lease:{message_id}"

    async def _ensure_consumer_group(self, queue: str) -> None:
        stream_key = self._stream_key(queue)
        group_name = self._group_name(queue)
        try:
            await self._client.xgroup_create(
                name=stream_key, groupname=group_name, id="0", mkstream=True
            )
        except ResponseError as err:
            if "BUSYGROUP" not in str(err):
                raise

    async def publish(self, queue: str, envelope: TaskEnvelope) -> str:
        stream_key = self._stream_key(queue)
        payload_data = envelope.model_dump_json()
        fields: dict[Any, Any] = {
            "envelope": payload_data,
            "task_id": str(envelope.task_id),
            "priority": str(envelope.priority),
        }
        raw_id: Any = await self._client.xadd(
            name=stream_key,
            fields=fields,
            maxlen=self._stream_maxlen,
            approximate=True,
        )
        return raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)

    async def consume(self, queue: str, worker_id: str, batch_size: int = 1) -> list[TaskMessage]:
        await self._ensure_consumer_group(queue)
        stream_key = self._stream_key(queue)
        group_name = self._group_name(queue)
        raw_response: Any = await self._client.xreadgroup(
            groupname=group_name,
            consumername=worker_id,
            streams={stream_key: ">"},
            count=batch_size,
            block=100,
        )
        if not raw_response:
            return []
        messages: list[TaskMessage] = []
        for _stream, stream_messages in raw_response:
            for raw_msg_id, fields in stream_messages:
                msg_id_str = (
                    raw_msg_id.decode("utf-8") if isinstance(raw_msg_id, bytes) else str(raw_msg_id)
                )
                raw_envelope_bytes = fields.get(b"envelope") or fields.get("envelope")
                if not raw_envelope_bytes:
                    continue
                if isinstance(raw_envelope_bytes, str):
                    raw_envelope_bytes = raw_envelope_bytes.encode("utf-8")
                envelope_dict = json.loads(raw_envelope_bytes.decode("utf-8"))
                envelope = TaskEnvelope.model_validate(envelope_dict)
                ts_ms = int(msg_id_str.split("-")[0])
                published_at = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
                message = TaskMessage(
                    message_id=msg_id_str,
                    queue=queue,
                    envelope=envelope,
                    delivery_count=envelope.attempt_count + 1,
                    published_at=published_at,
                )
                messages.append(message)
        return messages

    async def acknowledge(self, queue: str, message_id: str) -> None:
        stream_key = self._stream_key(queue)
        group_name = self._group_name(queue)
        await self._client.xack(stream_key, group_name, message_id)
        await self._client.delete(self._lease_key(message_id))

    async def nack(self, queue: str, message_id: str, requeue: bool = True) -> None:
        stream_key = self._stream_key(queue)
        group_name = self._group_name(queue)
        await self._client.xack(stream_key, group_name, message_id)
        await self._client.delete(self._lease_key(message_id))

    async def extend_lease(self, message_id: str, duration: int) -> None:
        lease_key = self._lease_key(message_id)
        await self._client.set(lease_key, "active", ex=duration)

    async def dead_letter(self, message_id: str, reason: str) -> None:
        dlq_stream = self._dlq_stream_key("default")
        now = datetime.now(UTC)
        fields: dict[Any, Any] = {
            "message_id": message_id,
            "reason": reason,
            "dead_at": now.isoformat(),
        }
        await self._client.xadd(name=dlq_stream, fields=fields)
        await self._client.delete(self._lease_key(message_id))

    async def claim_stale(
        self,
        queue: str,
        worker_id: str,
        min_idle_time_ms: int = 300000,
        count: int = 10,
    ) -> list[TaskMessage]:
        await self._ensure_consumer_group(queue)
        stream_key = self._stream_key(queue)
        group_name = self._group_name(queue)
        try:
            claim_res: Any = await self._client.xautoclaim(
                name=stream_key,
                groupname=group_name,
                consumername=worker_id,
                min_idle_time=min_idle_time_ms,
                start_id="0-0",
                count=count,
            )
        except Exception:
            return []
        if not claim_res or len(claim_res) < 2:
            return []
        raw_messages = claim_res[1]
        claimed: list[TaskMessage] = []
        for raw_msg_id, fields in raw_messages:
            msg_id_str = (
                raw_msg_id.decode("utf-8") if isinstance(raw_msg_id, bytes) else str(raw_msg_id)
            )
            raw_env = fields.get(b"envelope") or fields.get("envelope")
            if not raw_env:
                continue
            if isinstance(raw_env, str):
                raw_env = raw_env.encode("utf-8")
            env_dict = json.loads(raw_env.decode("utf-8"))
            env = TaskEnvelope.model_validate(env_dict)
            ts_ms = int(msg_id_str.split("-")[0])
            claimed.append(
                TaskMessage(
                    message_id=msg_id_str,
                    queue=queue,
                    envelope=env,
                    delivery_count=env.attempt_count + 1,
                    published_at=datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC),
                )
            )
        return claimed

    async def stats(self, queue: str) -> BrokerStats:
        stream_key = self._stream_key(queue)
        group_name = self._group_name(queue)
        try:
            depth = await self._client.xlen(stream_key)
        except Exception:
            depth = 0
        active_consumers = 0
        oldest_age = 0.0
        now_ts = datetime.now(UTC).timestamp()
        try:
            consumers_info = await self._client.xinfo_consumers(stream_key, group_name)
            active_consumers = len(consumers_info)
        except Exception:
            active_consumers = 0
        try:
            pending_summary = await self._client.xpending(stream_key, group_name)
            if pending_summary and isinstance(pending_summary, dict):
                min_id = pending_summary.get("min")
                if min_id and min_id != b"0-0" and min_id != "0-0":
                    min_id_str = (
                        min_id.decode("utf-8") if isinstance(min_id, bytes) else str(min_id)
                    )
                    ts_ms = int(min_id_str.split("-")[0])
                    oldest_age = max(0.0, now_ts - (ts_ms / 1000.0))
        except Exception:
            pass
        is_healthy = await self.health_check()
        return BrokerStats(
            backend_name="redis",
            queue=queue,
            depth=depth,
            active_consumers=active_consumers,
            oldest_task_age_seconds=oldest_age,
            is_healthy=is_healthy,
        )

    async def health_check(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass

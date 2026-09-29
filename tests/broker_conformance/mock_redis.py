import time
from typing import Any

from redis.exceptions import ResponseError


class MockRedisStreamsClient:
    def __init__(self) -> None:
        self.streams: dict[str, list[tuple[str, dict[bytes, bytes], float]]] = {}
        self.groups: dict[str, dict[str, Any]] = {}
        self.pel: dict[str, dict[str, dict[str, Any]]] = {}
        self.kv: dict[str, Any] = {}
        self.seq_counter: int = 0

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def set(self, name: str, value: Any, ex: int | None = None) -> bool:
        self.kv[name] = value
        return True

    async def get(self, name: str) -> Any:
        return self.kv.get(name)

    async def delete(self, *names: str) -> int:
        count = 0
        for n in names:
            if n in self.kv:
                del self.kv[n]
                count += 1
        return count

    async def xlen(self, name: str) -> int:
        return len(self.streams.get(name, []))

    async def xgroup_create(
        self, name: str, groupname: str, id: str = "0", mkstream: bool = True
    ) -> bool:
        if mkstream and name not in self.streams:
            self.streams[name] = []
        if name not in self.groups:
            self.groups[name] = {}
        if groupname in self.groups[name]:
            raise ResponseError("BUSYGROUP Consumer Group name already exists")
        self.groups[name][groupname] = {
            "last_id": id,
            "consumers": {},
        }
        self.pel[f"{name}:{groupname}"] = {}
        return True

    async def xadd(
        self,
        name: str,
        fields: dict[Any, Any],
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        if name not in self.streams:
            self.streams[name] = []
        self.seq_counter += 1
        ts_ms = int(time.time() * 1000)
        msg_id = f"{ts_ms}-{self.seq_counter}"
        encoded_fields: dict[bytes, bytes] = {}
        for k, v in fields.items():
            kb = k if isinstance(k, bytes) else str(k).encode("utf-8")
            vb = v if isinstance(v, bytes) else str(v).encode("utf-8")
            encoded_fields[kb] = vb
        self.streams[name].append((msg_id, encoded_fields, time.time()))
        if maxlen and len(self.streams[name]) > maxlen:
            self.streams[name] = self.streams[name][-maxlen:]
        return msg_id

    async def xreadgroup(
        self,
        groupname: str,
        consumername: str,
        streams: dict[str, str],
        count: int = 1,
        block: int | None = None,
    ) -> list[tuple[bytes, list[tuple[bytes, dict[bytes, bytes]]]]]:
        results: list[tuple[bytes, list[tuple[bytes, dict[bytes, bytes]]]]] = []
        for stream_name, read_id in streams.items():
            if stream_name not in self.streams:
                continue
            group_info = self.groups.get(stream_name, {}).get(groupname)
            if not group_info:
                continue
            group_info["consumers"][consumername] = time.time()
            pel_key = f"{stream_name}:{groupname}"
            stream_entries = self.streams[stream_name]
            collected: list[tuple[bytes, dict[bytes, bytes]]] = []
            if read_id == ">":
                last_delivered = group_info.get("last_delivered_idx", 0)
                available = stream_entries[last_delivered : last_delivered + count]
                group_info["last_delivered_idx"] = last_delivered + len(available)
                for mid, flds, _created_ts in available:
                    self.pel[pel_key][mid] = {
                        "consumer": consumername,
                        "idle_since": time.time(),
                        "delivery_count": self.pel[pel_key].get(mid, {}).get("delivery_count", 0)
                        + 1,
                        "fields": flds,
                    }
                    collected.append((mid.encode("utf-8"), flds))
            if collected:
                results.append((stream_name.encode("utf-8"), collected))
        return results

    async def xack(self, name: str, groupname: str, *ids: str) -> int:
        pel_key = f"{name}:{groupname}"
        count = 0
        if pel_key in self.pel:
            for mid in ids:
                if mid in self.pel[pel_key]:
                    del self.pel[pel_key][mid]
                    count += 1
        return count

    async def xpending(self, name: str, groupname: str) -> dict[str, Any]:
        pel_key = f"{name}:{groupname}"
        entries = self.pel.get(pel_key, {})
        if not entries:
            return {"pending": 0, "min": None, "max": None, "consumers": []}
        all_ids = sorted(entries.keys())
        return {
            "pending": len(entries),
            "min": all_ids[0].encode("utf-8"),
            "max": all_ids[-1].encode("utf-8"),
            "consumers": [],
        }

    async def xinfo_consumers(self, name: str, groupname: str) -> list[dict[str, Any]]:
        group_info = self.groups.get(name, {}).get(groupname, {})
        consumers = group_info.get("consumers", {})
        return [{"name": cname, "pending": 0, "idle": 0} for cname in consumers]

    async def xautoclaim(
        self,
        name: str,
        groupname: str,
        consumername: str,
        min_idle_time: int,
        start_id: str = "0-0",
        count: int = 10,
    ) -> tuple[str, list[tuple[bytes, dict[bytes, bytes]]]]:
        pel_key = f"{name}:{groupname}"
        entries = self.pel.get(pel_key, {})
        now = time.time()
        claimed: list[tuple[bytes, dict[bytes, bytes]]] = []
        for mid, data in list(entries.items()):
            idle_ms = (now - data.get("idle_since", now)) * 1000.0
            if idle_ms >= min_idle_time or min_idle_time == 0:
                data["consumer"] = consumername
                data["idle_since"] = now
                claimed.append((mid.encode("utf-8"), data["fields"]))
                if len(claimed) >= count:
                    break
        return "0-0", claimed

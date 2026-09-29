import time
from typing import Any

import redis.asyncio as aioredis

from src.core.config import get_settings

TOKEN_BUCKET_LUA = '\nlocal key = KEYS[1]\nlocal capacity = tonumber(ARGV[1])\nlocal refill_rate = tonumber(ARGV[2]) -- tokens per second\nlocal cost = tonumber(ARGV[3])\nlocal now = tonumber(ARGV[4])\n\n-- Retrieve current bucket state: [tokens, last_refill_timestamp]\nlocal data = redis.call("HMGET", key, "tokens", "last_refill")\nlocal tokens = tonumber(data[1])\nlocal last_refill = tonumber(data[2])\n\nif not tokens or not last_refill then\n    tokens = capacity\n    last_refill = now\nelse\n    -- Compute token refill based on elapsed time\n    local elapsed = math.max(0, now - last_refill)\n    tokens = math.min(capacity, tokens + (elapsed * refill_rate))\n    last_refill = now\nend\n\nif tokens >= cost then\n    tokens = tokens - cost\n    redis.call("HMSET", key, "tokens", tokens, "last_refill", last_refill)\n    redis.call("EXPIRE", key, math.ceil(capacity / refill_rate) + 60)\n    return {1, tokens} -- Allowed\nelse\n    redis.call("HMSET", key, "tokens", tokens, "last_refill", last_refill)\n    redis.call("EXPIRE", key, math.ceil(capacity / refill_rate) + 60)\n    return {0, tokens} -- Rejected\nend\n'


class TokenBucketRateLimiter:
    def __init__(
        self,
        redis_client: aioredis.Redis | None = None,
        redis: aioredis.Redis | None = None,
        fail_closed: bool = False,
    ) -> None:
        self._redis = redis or redis_client
        self.fail_closed = fail_closed
        self._in_memory_buckets: dict[str, tuple[float, float]] = {}

    def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            settings = get_settings()
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def acquire(
        self, key: str, rate_limit_rps: int = 100, burst_capacity: int | None = None, cost: int = 1
    ) -> bool:
        capacity = burst_capacity or rate_limit_rps
        now = time.time()
        bucket_key = f"rate_limit:{key}"
        try:
            r = self._get_redis()
            res: list[Any] = await r.eval(
                TOKEN_BUCKET_LUA, 1, bucket_key, capacity, rate_limit_rps, cost, now
            )
            allowed = bool(res[0] == 1)
            return allowed
        except Exception:
            if self.fail_closed:
                return False
            return self._acquire_in_memory(key, rate_limit_rps, capacity, cost, now)

    def _acquire_in_memory(
        self, key: str, rate_limit_rps: int, capacity: int, cost: int, now: float
    ) -> bool:
        tokens, last_refill = self._in_memory_buckets.get(key, (float(capacity), now))
        elapsed = max(0.0, now - last_refill)
        tokens = min(float(capacity), tokens + elapsed * rate_limit_rps)
        if tokens >= cost:
            tokens -= cost
            self._in_memory_buckets[key] = (tokens, now)
            return True
        self._in_memory_buckets[key] = (tokens, now)
        return False


RedisTokenBucketRateLimiter = TokenBucketRateLimiter

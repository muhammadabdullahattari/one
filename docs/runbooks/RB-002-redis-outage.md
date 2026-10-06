# Runbook RB-002: Redis Outage & Restart Procedure

- **Runbook ID:** RB-002
- **Target Subsystem:** Redis Streams Broker Adapter & Rate Limiter Cache
- **Default Severity:** SEV-1 (Critical)
- **Relevant SRS Sections:** SRS §9 (Broker Architecture), SRS §21.3 (Chaos Matrix), SRS §22.1

---

## 1. Incident Overview & Symptoms

Redis provides the low-latency message streaming layer and distributed token bucket cache. If Redis crashes, becomes unreachable, or enters read-only mode due to memory pressure (`OOM command not allowed`), task publication and consumer dispatch stall.

### Alerting Triggers
- Prometheus Alert: `RedisConnectionDown` (`task_engine_redis_connected == 0`)
- API Error Log Spike: `redis.exceptions.ConnectionError: Error connecting to redis`
- Healthcheck Endpoint: `GET /api/v1/health` reports `"redis": "unhealthy"`

---

## 2. Immediate Triage & Diagnostics

### Step 1: Check Redis Container & Process Status
```bash
# Verify container liveness
docker compose ps redis

# Test direct connection via redis-cli
docker compose exec redis redis-cli ping
```
*Expected Healthy Output:* `PONG`

### Step 2: Inspect Redis Error Logs
```bash
docker compose logs --tail=100 redis
```
Key patterns to watch for:
- `OOM command not allowed when used memory > 'maxmemory'` (Memory Exhaustion)
- `Bad file format reading the append only file` (Corrupted AOF)
- `Can't save in background: fork: Cannot allocate memory` (System Memory Exhaustion)

---

## 3. Mitigation & Recovery Procedure

### Scenario A: Redis Container Terminated / Unhealthy
```bash
# Restart the Redis service cleanly
docker compose restart redis

# Tail logs to confirm startup and AOF loading
docker compose logs -f redis
```

### Scenario B: Memory Exhaustion (OOM)
If Redis is refusing writes due to maxmemory limit:
```bash
# Inspect current memory usage
docker compose exec redis redis-cli info memory

# Adjust maxmemory dynamically or clear volatile keys
docker compose exec redis redis-cli config set maxmemory 2gb
docker compose exec redis redis-cli config set maxmemory-policy volatile-lru
```

### Scenario C: Corrupted Append-Only File (AOF)
If Redis fails to boot due to an interrupted write:
```bash
# 1. Stop container
docker compose stop redis

# 2. Run AOF repair utility inside a temporary container
docker run --rm -v task-engine_redis_data:/data redis:7-alpine redis-check-aof --fix /data/appendonlydir/appendonly.aof.manifest

# 3. Restart container
docker compose start redis
```

### Scenario D: Consumer Group Reconciliation
If consumer group offsets were disrupted during the restart:
```bash
# Verify consumer group status on primary stream
docker compose exec redis redis-cli XINFO GROUPS stream:queue:default

# If group missing, the worker will auto-recreate on restart:
docker compose restart worker
```

---

## 4. Post-Incident Verification
1. Verify Redis health via API health probe:
   ```bash
   curl -s http://localhost:8000/api/v1/health | jq .components.redis
   ```
   *Expected:* `{"status": "healthy"}`
2. Ensure task stream message processing has resumed:
   ```bash
   curl -s http://localhost:8000/api/v1/analytics/throughput | jq .
   ```
3. Check Outbox relay has drained pending messages to Redis (see [RB-007](file:///d:/One/task-engine/docs/runbooks/RB-007-outbox-backlog.md)).

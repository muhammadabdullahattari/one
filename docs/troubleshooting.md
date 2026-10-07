# Troubleshooting Guide

This guide details diagnostics, mitigation strategies, and recovery procedures for common operational issues across the Task Engine cluster.

---

## 1. Quick Diagnostic Health Check

Before troubleshooting individual components, run the following fast triage checks:

```bash
# 1. Check API Liveness and Readiness
curl -s http://localhost:8000/health/ready | jq .

# 2. Inspect registered workers and active task counts
curl -s http://localhost:8000/api/v1/workers | jq .

# 3. Inspect queue depths and backlog
curl -s http://localhost:8000/api/v1/queues | jq .

# 4. Check for unhandled exceptions in structured logs
grep -E '"level": "(ERROR|CRITICAL)"' /var/log/task-engine/*.log
```

---

## 2. Worker Crashes and Unresponsive Processes

### Symptoms
* Workers disappear from `GET /api/v1/workers`.
* Tasks remain in `RUNNING` status without progressing.
* Worker processes exit unexpectedly with code 137 (OOM Killer) or SIGSEGV.

### Root Causes & Diagnosis
1. **Out of Memory (OOM)**: Handlers buffering large files into memory instead of streaming or offloading to S3. Check kernel logs:
   ```bash
   dmesg -T | grep -i oom
   ```
2. **Event Loop Blocked**: A synchronous, CPU-heavy blocking loop executed in an async worker without delegating to an executor pool.
3. **Database Network Partition**: Worker lost connection to PostgreSQL while processing and could not renew heartbeat.

### Automated Recovery
* Each running task holds a lease expiring at `lease_expires_at` (`LEASE_SECONDS`, default 30s).
* The engine lease monitor periodically detects orphaned tasks whose `lease_expires_at < NOW()`.
* If `attempt_count < max_attempts`, the task status resets to `QUEUED` for another worker to pick up.
* If attempts are exhausted, the task transitions to `DEAD` and moves to the Dead Letter Queue (DLQ).

### Operational Actions
* For worker crash storms, see [Runbook: Worker Crash Storm](runbooks/RB-001-worker-crash-storm.md).
* Restart failed workers with isolated concurrency:
  ```bash
  task-engine worker -A tasks --queues default --concurrency 4
  ```

---

## 3. Broker Disconnection and Reconnects

### Symptoms
* Logs display `ConnectionError: Failed to connect to Redis at redis://localhost:6379`.
* Workers stop receiving new task notifications.
* APIs reject new task dispatches or degrade to synchronous fallback.

### Mitigation & Recovery
1. **Redis Streams Down**:
   - Check Redis cluster health:
     ```bash
     redis-cli -u $REDIS_URL ping
     ```
   - If Redis is down, switch queues to PostgreSQL Zero-Infra Broker by setting `RATE_LIMIT_BACKEND=postgres` and relying on transactional outbox.
   - Refer to [Runbook: Redis Outage](runbooks/RB-002-redis-outage.md).
2. **PostgreSQL Pool Saturation**:
   - Error: `QueuePool limit of size 20 overflow 10 reached, connection timed out`.
   - Check active database connections:
     ```sql
     SELECT count(*), state FROM pg_stat_activity WHERE datname = 'task_engine_dev' GROUP BY state;
     ```
   - Increase `DB_POOL_SIZE` or configure PgBouncer connection pooling.
   - Refer to [Runbook: Postgres Outage](runbooks/RB-003-postgres-outage.md).

---

## 4. Stuck Tasks & Expired Lease Recovery

### Symptoms
* Tasks remain in `RUNNING` state long past their execution window.

### Diagnosis
Query database for stale tasks:
```sql
SELECT task_id, task_type, queue, worker_id, lease_expires_at, attempt_count
FROM tasks
WHERE status = 'RUNNING' AND lease_expires_at < NOW() - INTERVAL '1 minute';
```

### Manual Recovery
1. **Retry / Re-queue via API**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/tasks/{task_id}/retry" \
     -H "Content-Type: application/json" \
     -d '{"delay_seconds": 0, "reset_attempts": false}'
   ```
2. **Retry via CLI**:
   ```bash
   task-engine status {task_id}
   ```
3. **Cancel Stale Task**:
   ```bash
   curl -X DELETE "http://localhost:8000/api/v1/tasks/{task_id}?reason=Stale+lease+cleanup"
   ```

---

## 5. Dead Letter Queue (DLQ) Management & Re-Driving

When a task exceeds `max_attempts` or suffers an unrecoverable non-retryable exception, it is moved to the Dead Letter Queue to prevent poison pill loops.

### Inspecting DLQ Items
```bash
# Query DLQ entries
curl -s "http://localhost:8000/api/v1/dlq?limit=20" | jq .
```

### Re-driving (Replaying) DLQ Messages
After deploying a bug fix to the task handler:

1. **Replay Single Task**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/dlq/{dlq_id}/replay"
   ```
2. **Replay Entire Queue**:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/dlq/replay-batch" \
     -H "Content-Type: application/json" \
     -d '{"queue": "notifications", "limit": 100}'
   ```
3. **Purge Poison Pills**:
   ```bash
   curl -X DELETE "http://localhost:8000/api/v1/dlq/{dlq_id}"
   ```
* Detailed step-by-step procedures: [Runbook: DLQ Replay](runbooks/RB-004-dlq-replay.md).

---

## 6. Queue Overload & Lag Spikes

### Symptoms
* `task_engine_queue_depth` spikes while processing rate drops.
* Latency percentiles (P95, P99) climb significantly.

### Remediation
1. **Scale Workers**: Spin up additional worker containers targeting the congested queue.
2. **Throttle Ingestion Rate**: Apply per-tenant or per-queue rate limits:
   ```bash
   curl -X PATCH "http://localhost:8000/api/v1/queues/{queue_name}" \
     -H "Content-Type: application/json" \
     -d '{"rate_limit_rps": 50}'
   ```
3. **Pause Non-Critical Queues**: Temporarily pause background queues to prioritize real-time traffic:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/queues/{queue_name}/pause"
   ```
4. Complete procedure: [Runbook: Queue Overload](runbooks/RB-005-queue-overload.md).

---

## 7. Scheduler Stalling

### Symptoms
* Scheduled cron tasks do not trigger at their designated execution timestamp.
* No scheduler leader is active.

### Remediation
1. Inspect scheduler heartbeat and election locks:
   ```sql
   SELECT * FROM scheduler_locks;
   ```
2. If a dead process retains a stale advisory lock, terminate the blocking backend connection:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE query ILIKE '%scheduler%';
   ```
3. Standby scheduler will acquire leadership within `SCHEDULER_LEADER_LOCK_TTL_SECONDS` (15s).
4. See [Runbook: Scheduler Stuck](runbooks/RB-006-scheduler-stuck.md).

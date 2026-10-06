# Runbook RB-007: Transactional Outbox Backlog Drain

- **Runbook ID:** RB-007
- **Target Subsystem:** Transactional Outbox Pattern & Broker Dispatcher
- **Default Severity:** SEV-2 (High)
- **Relevant SRS Sections:** SRS §8.2 (Transactional Outbox), SRS §9.3 (Broker Ingestion), SRS §22.1

---

## 1. Incident Overview & Symptoms

To guarantee atomic persistence without dual-write inconsistencies, tasks submitted to the API are committed to PostgreSQL along with a record in the `task_outbox` table. An asynchronous outbox relay process polls the table and publishes messages to Redis Streams. If this relay fails, tasks remain trapped in the database and never reach workers.

### Alerting Triggers
- Prometheus Alert: `OutboxBacklogAccumulating` (`task_engine_outbox_backlog_total > 500`)
- Tasks Stuck in Initial State: `count(tasks{status='PENDING'}) > 100`

---

## 2. Immediate Triage & Diagnostics

### Step 1: Check Outbox Table Depth & Age
```sql
SELECT status, count(*), min(created_at) as oldest_entry, max(created_at) as newest_entry
FROM task_outbox
GROUP BY status;
```

### Step 2: Check Recent Outbox Errors
```sql
SELECT id, task_id, queue, error, retry_count, updated_at
FROM task_outbox
WHERE status = 'FAILED' OR retry_count > 3
ORDER BY updated_at DESC
LIMIT 10;
```

### Step 3: Verify Broker Availability
Ensure Redis is accepting writes (refer to [RB-002](file:///d:/One/task-engine/docs/runbooks/RB-002-redis-outage.md)). If Redis was down, outbox entries intentionally buffer in PostgreSQL.

---

## 3. Mitigation & Recovery Procedure

### Step 1: Restart the Outbox Relay Service / API Process
```bash
docker compose restart api
docker compose logs --tail=100 api | grep -E "outbox|relay|dispatch"
```

### Step 2: Force Manual Outbox Drain via Batch SQL Script
If the background worker is backlogged and needs immediate batch dispatch:
```sql
-- Step 1: Reset failed outbox records back to PENDING for retry
UPDATE task_outbox
SET status = 'PENDING',
    retry_count = 0,
    error = NULL,
    updated_at = NOW()
WHERE status = 'FAILED'
  AND created_at > NOW() - INTERVAL '6 hours';

-- Step 2: Mark corresponding tasks as ready for immediate pick up
UPDATE tasks
SET status = 'QUEUED',
    updated_at = NOW()
WHERE id IN (
    SELECT task_id FROM task_outbox WHERE status = 'PENDING'
)
AND status = 'PENDING';
```

### Step 3: Run the CLI Outbox Relay Flush Command
```bash
# Execute outbox drain utility inside container
docker compose exec api python3 -c "
import asyncio
from src.persistence.session import session_scope
from src.persistence.repositories.outbox_repository import OutboxRepository
from src.broker.registry import get_broker_adapter

async def drain():
    broker = get_broker_adapter('redis')
    async with session_scope() as session:
        repo = OutboxRepository(session)
        pending = await repo.get_pending_outbox_items(limit=500)
        print(f'Draining {len(pending)} outbox items...')
        for item in pending:
            await broker.publish(item.queue, item.payload)
            await repo.mark_published(item.id)
        print('Drain complete.')

asyncio.run(drain())
"
```

---

## 4. Post-Incident Verification
1. Verify pending outbox count is zero:
   ```sql
   SELECT count(*) FROM task_outbox WHERE status = 'PENDING';
   ```
   *Expected:* `0`
2. Check that workers have begun executing the drained tasks:
   ```bash
   curl -s http://localhost:8000/api/v1/analytics/throughput | jq .
   ```

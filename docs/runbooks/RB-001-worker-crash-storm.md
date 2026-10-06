# Runbook RB-001: Worker Crash Storm Recovery

- **Runbook ID:** RB-001
- **Target Subsystem:** Worker Runtime Pool & Execution Engine
- **Default Severity:** SEV-1 (Cluster-wide) / SEV-2 (Single Queue)
- **Relevant SRS Sections:** SRS §15 (Worker Lifecycle), SRS §21.3 (Fault Matrix), SRS §22.1

---

## 1. Incident Overview & Symptoms

A **Worker Crash Storm** occurs when worker processes repeatedly terminate abruptly (SIGKILL/OOM, segfaults, unhandled process exits) immediately upon consuming tasks from a queue. This causes rapid container restart loops, CPU churn, and tasks becoming orphaned in `RUNNING` status.

### Alerting Triggers
- Prometheus Alert: `TaskEngineWorkerCrashRateHigh` (`rate(task_engine_worker_crashes_total[2m]) > 0.1`)
- Docker Alert: `container restart count > 5 within 5 minutes`
- Stale Task Ratio: `count(tasks{status='RUNNING', updated_at < now() - interval '5 min'}) > 20`

---

## 2. Immediate Triage & Diagnostics

### Step 1: Identify Crashing Worker Containers
```bash
# Check container status and exit codes
docker compose ps worker

# Inspect recent crash logs and kernel OOM signals
docker compose logs --tail=200 worker | grep -E "OOM|Killed|Error|Traceback|Panic"
dmesg -T | grep -E -i "oom|out of memory|killed process"
```

### Step 2: Identify the Poison Pill Tasks
Find tasks currently in `RUNNING` that were assigned to crashed workers:
```sql
-- Connect to database
SELECT id, task_type, queue, payload, attempt_count, updated_at
FROM tasks
WHERE status = 'RUNNING'
  AND updated_at < NOW() - INTERVAL '5 minutes'
ORDER BY updated_at ASC
LIMIT 10;
```

---

## 3. Mitigation & Recovery Procedure

### Step 1: Pause Ingestion on the Affected Queue
Prevent workers from consuming more potentially destructive payloads:
```bash
# Pause queue via API
curl -X POST "http://localhost:8000/api/v1/queues/{queue_name}/pause" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json"
```

### Step 2: Quarantine Poison Tasks to DLQ
Move the offending task(s) directly to the Dead Letter Queue so workers do not crash when restarted:
```sql
UPDATE tasks
SET status = 'DEAD_LETTER',
    error_class = 'WorkerCrashPoisonPill',
    error_message_redacted = 'Terminated by operator due to worker crash storm',
    updated_at = NOW()
WHERE status = 'RUNNING'
  AND id IN ('<SUSPECT_TASK_UUID_1>', '<SUSPECT_TASK_UUID_2>');

-- Insert corresponding DLQ record
INSERT INTO dead_letter_tasks (id, original_task_id, queue, reason, error_class, failed_at)
SELECT gen_random_uuid(), id, queue, 'Quarantined during crash storm', 'WorkerCrashPoisonPill', NOW()
FROM tasks
WHERE id IN ('<SUSPECT_TASK_UUID_1>', '<SUSPECT_TASK_UUID_2>')
ON CONFLICT DO NOTHING;
```

### Step 3: Reclaim Any Remaining Stale Leases
Reset non-fatal tasks back to `QUEUED` so healthy workers can claim them:
```sql
UPDATE tasks
SET status = 'QUEUED',
    attempt_count = attempt_count + 1,
    updated_at = NOW()
WHERE status = 'RUNNING'
  AND updated_at < NOW() - INTERVAL '5 minutes';
```

### Step 4: Increase Worker Memory & Restart Fleet
If crashes were caused by OOM (Out Of Memory):
```bash
# Temporarily restart worker with increased resource limits
docker compose up -d --scale worker=4 worker
```

### Step 5: Resume the Queue
```bash
curl -X POST "http://localhost:8000/api/v1/queues/{queue_name}/resume" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json"
```

---

## 4. Post-Incident Verification
1. Verify workers are reporting steady heartbeats:
   ```bash
   curl -s http://localhost:8000/api/v1/workers | jq '.items[] | {id: .worker_id, status: .status, heartbeats: .last_heartbeat}'
   ```
2. Confirm task throughput has normalized:
   ```bash
   curl -s http://localhost:8000/api/v1/analytics/throughput | jq .
   ```
3. Check that the crash metric has returned to zero:
   ```bash
   curl -s http://localhost:8000/api/v1/metrics | grep task_engine_worker_crashes
   ```

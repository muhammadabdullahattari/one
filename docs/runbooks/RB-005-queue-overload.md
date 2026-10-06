# Runbook RB-005: Queue Overload & Backpressure Mitigation

- **Runbook ID:** RB-005
- **Target Subsystem:** Queue Subsystem, Rate Limiting & Flow Control
- **Default Severity:** SEV-2 (High)
- **Relevant SRS Sections:** SRS §13 (Rate Limiting & Anti-Starvation), SRS §17.4 (Queue Management), SRS §22.1

---

## 1. Incident Overview & Symptoms

A **Queue Overload** occurs when the task arrival rate significantly exceeds the cluster's consumption rate over an extended period. This leads to queue depth exceeding configured high-water marks, queue-to-start latency exceeding the 250ms p95 SLA, and potential broker storage exhaustion.

### Alerting Triggers
- Prometheus Alert: `QueueBacklogHigh` (`task_engine_queue_depth > 5000`)
- Latency SLA Breach: `task_engine_queue_time_seconds{quantile="0.95"} > 0.25`
- Oldest Task Age: `task_engine_oldest_task_age_seconds > 300` (5 minutes)

---

## 2. Immediate Triage & Diagnostics

### Step 1: Identify Which Queue Is Overloaded
```bash
# Query queue depths across the cluster
curl -s "http://localhost:8000/api/v1/queues" \
     -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.[] | {name: .name, depth: .depth, max_size: .max_size}'
```

### Step 2: Identify High-Volume Tenants / Task Types
```sql
SELECT tenant_id, task_type, count(*) as pending_count
FROM tasks
WHERE status = 'QUEUED'
GROUP BY tenant_id, task_type
ORDER BY pending_count DESC
LIMIT 10;
```

---

## 3. Mitigation & Recovery Procedure

### Step 1: Scale Out Worker Capacity Immediately
The most effective way to relieve backpressure is increasing processing capacity:
```bash
# Scale worker container replicas from 2 to 6
docker compose up -d --scale worker=6 worker
```

### Step 2: Apply Tenant-Level Rate Limiting
If a single noisy tenant is flooding the engine:
```bash
# Reduce burst allowance and refill rate for the offending tenant
curl -X PUT "http://localhost:8000/api/v1/projects/{project_id}/rate-limits" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "rate_limit_per_minute": 60,
       "burst_limit": 100
     }'
```

### Step 3: Enable Queue Flow Control / Pause Ingestion
If the queue is approaching the physical storage limit:
```bash
# Temporarily pause ingestion to allow workers to catch up
curl -X POST "http://localhost:8000/api/v1/queues/{queue_name}/pause" \
     -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Step 4: Priority Scheduling Rebalance
High priority tasks (`priority = 1` or `2`) will automatically be scheduled first due to anti-starvation age weighting. Ensure high-priority queues have dedicated workers:
```bash
# Start dedicated high-priority worker pool
docker compose run -d --name worker-high-priority worker \
    python3 -m src.sdk.cli worker start --queues high --concurrency 8
```

---

## 4. Post-Incident Verification
1. Verify queue depth is trending downward:
   ```bash
   curl -s http://localhost:8000/api/v1/analytics/oldest-task-age | jq .
   ```
2. Confirm p95 queue-to-start latency drops below 250ms:
   ```bash
   curl -s http://localhost:8000/api/v1/metrics | grep task_engine_queue_time_seconds
   ```
3. Resume normal rate limits once backlog drops below 500 items.

# Runbook RB-004: Dead Letter Queue (DLQ) Replay Procedure

- **Runbook ID:** RB-004
- **Target Subsystem:** Dead Letter Queue (DLQ) & Failure Recovery
- **Default Severity:** SEV-2 / SEV-3
- **Relevant SRS Sections:** SRS §11 (DLQ & Poison Pill Handling), SRS §17.7 (DLQ Inspection), SRS §22.1

---

## 1. Incident Overview & Symptoms

Tasks are routed to the **Dead Letter Queue (DLQ)** when they exhaust all retry attempts, encounter non-retryable fatal exceptions (e.g., bad payload data schema, invalid credentials), or are manually quarantined by operators. Once the root cause (such as an external service outage or bug) is resolved, the operator must replay dead tasks safely.

### Alerting Triggers
- Prometheus Alert: `DLQAccumulationHigh` (`task_engine_dlq_total > 50`)
- Frontend DLQ Badge: Red notification indicator on the DLQ navigation menu

---

## 2. Immediate Triage & Diagnostics

### Step 1: Inspect DLQ Backlog and Error Distribution
```bash
# Query DLQ entries via API
curl -s "http://localhost:8000/api/v1/dlq?limit=20" \
     -H "Authorization: Bearer $ADMIN_TOKEN" | jq .
```

### Step 2: Query Error Classes and Failure Patterns
```sql
SELECT error_class, count(*), min(failed_at) as earliest, max(failed_at) as latest
FROM dead_letter_tasks
GROUP BY error_class
ORDER BY count(*) DESC;
```

### Step 3: Verify Root Cause Is Resolved
Before replaying, verify that downstream services (payment gateways, external APIs, database tables) are operating nominally. Replaying prematurely will cause tasks to re-enter DLQ and waste compute resources.

---

## 3. Replay Execution Procedure

### Method A: Targeted Single-Task Replay (via REST API)
```bash
curl -X POST "http://localhost:8000/api/v1/dlq/{dlq_entry_id}/replay" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json"
```

### Method B: Batch Replay by Error Class / Queue (via Database)
To safely replay tasks in controlled increments of 100 without overwhelming workers:
```sql
-- Step 1: Identify and reset tasks for a specific error class
WITH replayed_batch AS (
    SELECT id, original_task_id, queue
    FROM dead_letter_tasks
    WHERE error_class = 'DownstreamService503Error'
      AND replayed_at IS NULL
    LIMIT 100
    FOR UPDATE SKIP LOCKED
)
UPDATE tasks t
SET status = 'QUEUED',
    attempt_count = 0,
    error_class = NULL,
    error_message_redacted = NULL,
    updated_at = NOW()
FROM replayed_batch rb
WHERE t.id = rb.original_task_id;

-- Step 2: Mark DLQ records as replayed
UPDATE dead_letter_tasks
SET replayed_at = NOW()
WHERE error_class = 'DownstreamService503Error'
  AND replayed_at IS NULL
  AND original_task_id IN (
      SELECT id FROM tasks WHERE status = 'QUEUED'
  );
```

### Method C: Replay via Frontend Console
1. Navigate to `/dlq` on the Web Console.
2. Filter by `Queue` and `Error Type`.
3. Select specific entries or click **"Replay All Visible"**.
4. Confirm the confirmation prompt modal.

---

## 4. Post-Incident Verification
1. Confirm DLQ count is decreasing:
   ```bash
   curl -s http://localhost:8000/api/v1/metrics | grep task_engine_dlq_total
   ```
2. Monitor task completions in real time:
   ```bash
   curl -s http://localhost:8000/api/v1/analytics/throughput | jq .
   ```
3. Verify no tasks from the replayed batch re-entered DLQ:
   ```sql
   SELECT count(*) FROM dead_letter_tasks WHERE failed_at > NOW() - INTERVAL '5 minutes';
   ```

# Runbook RB-006: Scheduler Stuck & Leader Election Reset

- **Runbook ID:** RB-006
- **Target Subsystem:** Distributed Cron Scheduler Daemon & Leader Election
- **Default Severity:** SEV-2 (High)
- **Relevant SRS Sections:** SRS §12 (Cron & Scheduled Tasks), SRS §17.6 (Schedule Console), SRS §22.1

---

## 1. Incident Overview & Symptoms

The Task Engine relies on a single active **Scheduler Leader** elected via a PostgreSQL session-level advisory lock (`key = 428912`). If the leader process freezes, experiences an unhandled loop hang, or terminates without releasing the advisory lock, cron tasks stop triggering.

### Alerting Triggers
- Prometheus Alert: `SchedulerHeartbeatMissing` (`time() - task_engine_scheduler_last_tick_timestamp > 60`)
- Schedules Overdue: `count(schedules{enabled=true, next_run_at < now() - interval '2 min'}) > 0`

---

## 2. Immediate Triage & Diagnostics

### Step 1: Check Scheduler Process & Logs
```bash
docker compose ps scheduler
docker compose logs --tail=100 scheduler
```
*Look for:* `Standing by as secondary scheduler instance` on all instances (indicating lock is held by a dead PID), or traceback in tick loop.

### Step 2: Query the Advisory Lock in PostgreSQL
```sql
SELECT pid, locktype, mode, granted
FROM pg_locks
WHERE locktype = 'advisory'
  AND (classid::bigint = 428912 OR objid::bigint = 428912);
```

### Step 3: Check Current Due Schedules
```sql
SELECT id, name, cron_expression, next_run_at, last_run_at, misfire_policy
FROM schedules
WHERE is_active = true
  AND next_run_at < NOW()
ORDER BY next_run_at ASC;
```

---

## 3. Mitigation & Recovery Procedure

### Step 1: Terminate the Zombie Lock Holder in PostgreSQL
If a previous scheduler crashed without releasing its connection:
```sql
-- Terminate the backend holding the advisory lock
SELECT pg_terminate_backend(pid)
FROM pg_locks
WHERE locktype = 'advisory'
  AND (classid::bigint = 428912 OR objid::bigint = 428912);
```

### Step 2: Restart the Scheduler Daemon
```bash
docker compose restart scheduler
docker compose logs -f scheduler
```
*Expected Log Output:*
`[info] Scheduler daemon starting tick_seconds=5`
`[info] Acquired scheduler leader election lock`
`[info] Evaluating due schedules count=X`

### Step 3: Misfire Reconciliation Check
The scheduler engine automatically evaluates misfires according to each job's configured policy:
- **`skip`**: Skips missed intervals and updates `next_run_at` to the next upcoming slot.
- **`coalesce`**: Executes exactly one run for the missed interval.
- **`catch_up`**: Spawns executions for all missed timestamps sequentially.

To force recalculation for any orphaned schedule:
```sql
UPDATE schedules
SET next_run_at = NOW()
WHERE is_active = true
  AND next_run_at < NOW() - INTERVAL '30 minutes';
```

---

## 4. Post-Incident Verification
1. Verify scheduler daemon is ticking every 5 seconds:
   ```bash
   docker compose logs --tail=20 scheduler | grep "Evaluating due schedules"
   ```
2. Verify overdue schedules count has dropped to zero:
   ```sql
   SELECT count(*) FROM schedules WHERE is_active = true AND next_run_at < NOW();
   ```
   *Expected:* `0`
3. Check generated tasks in the tasks table:
   ```sql
   SELECT id, task_type, created_at FROM tasks WHERE schedule_id IS NOT NULL ORDER BY created_at DESC LIMIT 5;
   ```

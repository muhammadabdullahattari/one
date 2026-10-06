# Runbook RB-003: PostgreSQL / Supabase Outage Procedure

- **Runbook ID:** RB-003
- **Target Subsystem:** PostgreSQL Database & Supabase Persistence Engine
- **Default Severity:** SEV-1 (Critical)
- **Relevant SRS Sections:** SRS §8 (Persistence Architecture), SRS §21.3 (Fault Matrix), SRS §22.1

---

## 1. Incident Overview & Symptoms

PostgreSQL is the durable **System of Record** for tasks, queues, schedules, users, and audit logs. A database outage, connection pool exhaustion, or network disconnect completely halts task transitions and API persistence.

### Alerting Triggers
- Prometheus Alert: `DatabaseConnectionExhausted` or `DatabaseConnectionDown`
- API Health Status: `GET /api/v1/health` returns `503 Service Unavailable`
- Log Signatures:
  - `asyncpg.exceptions.TooManyConnectionsError: remaining connection slots are reserved`
  - `sqlalchemy.exc.OperationalError: server closed the connection unexpectedly`

---

## 2. Immediate Triage & Diagnostics

### Step 1: Check Database Process & Connectivity
```bash
# If using containerized PostgreSQL:
docker compose ps postgres
docker compose exec postgres pg_isready -U postgres -d postgres

# Check container logs
docker compose logs --tail=100 postgres
```

### Step 2: Check Active Connections & Locks
Connect using `psql` to inspect connection count and blocking locks:
```sql
-- Check total connections vs max_connections
SELECT count(*), (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_conns
FROM pg_stat_activity;

-- Identify connections by application name / client IP
SELECT application_name, client_addr, state, count(*)
FROM pg_stat_activity
GROUP BY application_name, client_addr, state
ORDER BY count(*) DESC;

-- Identify long-running transactions (> 60s)
SELECT pid, now() - xact_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - xact_start) > interval '60 seconds'
  AND state != 'idle';
```

---

## 3. Mitigation & Recovery Procedure

### Scenario A: Connection Pool Exhaustion (Too Many Connections)
Terminate orphaned idle connections to restore connection capacity immediately:
```sql
-- Terminate all idle transactions older than 2 minutes
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state IN ('idle', 'idle in transaction')
  AND state_change < NOW() - INTERVAL '2 minutes'
  AND pid <> pg_backend_pid();
```

### Scenario B: Blocking Lock on Task Table
If a long-running transaction holds an exclusive table lock:
```sql
-- Find blocked and blocking queries
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Kill the blocker
SELECT pg_cancel_backend(<blocking_pid>);
-- If unresponsive:
SELECT pg_terminate_backend(<blocking_pid>);
```

### Scenario C: Supabase Managed Pooler Configuration
When operating against Supabase, verify the connection string mode:
- **Transaction Mode (Port 6543)**: Recommended for stateless API web requests and worker pools.
- **Session Mode (Port 5432)**: Required for Alembic schema migrations and PostgreSQL advisory locks.

If connection errors persist on Supabase:
1. Log in to the Supabase Cloud Dashboard.
2. Check `Database` -> `Connection Pooling` settings.
3. If pool size limit is reached, temporarily increase `Pool Size` or reduce `WORKER_CONCURRENCY` in `.env`.

### Scenario D: Local PostgreSQL Restart
```bash
docker compose restart postgres
docker compose logs -f postgres
```

---

## 4. Post-Incident Verification
1. Verify database responsiveness:
   ```bash
   curl -s http://localhost:8000/api/v1/health | jq .components.database
   ```
   *Expected:* `{"status": "healthy"}`
2. Verify workers re-established database connections without restart:
   ```bash
   docker compose logs --tail=50 worker | grep -E "database_connection|heartbeat"
   ```

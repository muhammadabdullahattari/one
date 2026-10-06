# Runbook RB-008: Database Migration Rollback Procedure

- **Runbook ID:** RB-008
- **Target Subsystem:** Alembic Database Schema Migrations & PostgreSQL DDL
- **Default Severity:** SEV-1 (Blocked Deployment) / SEV-2 (Degraded API)
- **Relevant SRS Sections:** SRS §8 (Persistence), SRS §16 (Deployment), SRS §22.1

---

## 1. Incident Overview & Symptoms

A failed or incompatible database migration causes column mismatch errors, unexpected locks on high-write tables (`tasks`, `workers`), or crashes in the API and worker runtimes. A clean, verified rollback must restore the previous stable schema revision without data corruption.

### Alerting Triggers
- Deployment Pipeline Failure during pre-deploy phase
- Database DDL Lock Contention (`pg_locks` showing exclusive access on `tasks`)
- API Error Logs: `sqlalchemy.exc.ProgrammingError: column "xyz" does not exist`

---

## 2. Immediate Triage & Diagnostics

### Step 1: Check Current Alembic Migration Version
```bash
# Check current database revision vs head
docker compose exec api alembic current
docker compose exec api alembic heads
```

### Step 2: Check for Blocking Schema Locks
Ensure no running queries are blocking DDL operations:
```sql
SELECT pid, query, state, age(clock_timestamp(), query_start)
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY age(clock_timestamp(), query_start) DESC;
```

---

## 3. Step-by-Step Rollback Procedure

### Step 1: Halt Application Ingestion
Prevent new tasks from being written during the schema rollback:
```bash
# Scale down API and workers temporarily
docker compose stop api worker scheduler
```

### Step 2: Identify Target Rollback Revision
Inspect the migration history to confirm the exact target revision hash:
```bash
docker compose run --rm api alembic history --verbose -n 5
```

### Step 3: Execute Rollback
Using the built-in CLI utility or Alembic directly:
```bash
# Method A: Using task-engine CLI
docker compose run --rm api python3 -m src.sdk.cli db rollback --steps 1

# Method B: Using alembic downgrade to specific revision
docker compose run --rm api alembic downgrade -1
# Or to a specific revision ID:
# docker compose run --rm api alembic downgrade 20261002_0006
```

### Step 4: Verify Schema State Post-Rollback
```sql
-- Check current migration stamp in alembic_version table
SELECT version_num FROM alembic_version;

-- Verify table schema structure
\d+ tasks
```

### Step 5: Roll Back Application Containers to Previous Release
Deploy the previous stable container image tag:
```bash
# Roll back container images to previous release tag (e.g., v0.1.0)
docker compose up -d
```

---

## 4. Post-Incident Verification
1. Run pre-deploy verification script to validate schema:
   ```bash
   docker compose exec api python3 scripts/deploy_migrate.py --config alembic.ini
   ```
2. Verify API boots cleanly:
   ```bash
   curl -s http://localhost:8000/api/v1/health | jq .
   ```
3. Run smoke test suite against rollback schema:
   ```bash
   docker compose exec api pytest tests/unit/test_health_readiness.py
   ```

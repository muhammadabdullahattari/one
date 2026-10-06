# Runbook RB-010: Disaster Recovery & Point-in-Time Restore

- **Runbook ID:** RB-010
- **Target Subsystem:** Full Engine Infrastructure & Persistent Data Recovery
- **Default Severity:** SEV-1 (Catastrophic Outage)
- **Relevant SRS Sections:** SRS §8 (Persistence), SRS §21.3 (Fault Injection), SRS §22.1

---

## 1. Incident Overview & Recovery Targets

This runbook guides recovery from total cluster loss, physical host failure, or catastrophic data corruption.

### Service Level Objectives
- **RPO (Recovery Point Objective):** $\le$ 15 minutes of transactional data
- **RTO (Recovery Time Objective):** $\le$ 30 minutes from incident declaration to traffic restoration

---

## 2. Recovery Prerequisites
1. Access to the backup storage archive (S3, external snapshot volume, or daily dumps).
2. Clean host or cloud VM with Docker & Docker Compose installed.
3. Decrypted master environment secrets (`.env.production`).

---

## 3. Step-by-Step Restoration Procedure

### Step 1: Initialize Clean Deployment Infrastructure
Clone repository and pull production images:
```bash
git clone https://github.com/muhammadabdullahattari/one.git /opt/task-engine
cd /opt/task-engine
cp /secure/backup/env.production .env
```

### Step 2: Start Persistence Services Only
```bash
# Start PostgreSQL and Redis without starting API or workers yet
docker compose up -d postgres redis
docker compose ps
```

### Step 3: Restore Database Snapshot
Locate the most recent database dump archive:
```bash
LATEST_BACKUP="/secure/backups/task_engine_db_$(date +%Y%m%d).sql.gz"

# Decompress and stream snapshot into PostgreSQL container
gunzip -c "$LATEST_BACKUP" | docker compose exec -T postgres psql -U postgres -d postgres
```

### Step 4: Verify Schema and Migrate to Latest Release
Run the automated migration and validation runner:
```bash
docker compose run --rm api python3 scripts/deploy_migrate.py --target head
```

### Step 5: Cleanse Stale In-Flight Leases
Tasks that were marked `RUNNING` at the time of disaster must be reset to `QUEUED`:
```sql
UPDATE tasks
SET status = 'QUEUED',
    attempt_count = attempt_count + 1,
    updated_at = NOW()
WHERE status = 'RUNNING';

-- Reset worker status to DEAD
UPDATE workers
SET status = 'DEAD',
    updated_at = NOW();
```

### Step 6: Start Application and Telemetry Fleet
```bash
# Start all containers in hardened production mode
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Step 7: Run End-to-End Smoke Test
Verify that tasks can be submitted, processed, and reported:
```bash
# Submit verification test task
TEST_RESP=$(curl -s -X POST "http://localhost:8000/api/v1/tasks" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{
       "task_type": "smoke.health_check",
       "queue": "default",
       "priority": 1,
       "payload": {"ping": "pong"}
     }')

TASK_ID=$(echo "$TEST_RESP" | jq -r .id)
echo "Submitted test task: $TASK_ID"

# Poll task state until SUCCEEDED
sleep 3
curl -s "http://localhost:8000/api/v1/tasks/$TASK_ID" \
     -H "Authorization: Bearer $ADMIN_TOKEN" | jq .status
```

---

## 4. Post-Incident Validation
- [ ] Database record counts match pre-incident estimates
- [ ] Redis Streams consumer groups established
- [ ] Worker pool reporting healthy heartbeats
- [ ] Web Console accessible at `http://<domain>:3000`
- [ ] Prometheus scraping and Grafana dashboards live

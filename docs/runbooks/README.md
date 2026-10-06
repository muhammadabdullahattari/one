# Task Engine Operational Runbooks Index

Welcome to the Task Engine Production Operations Runbook Repository. This library provides authoritative standard operating procedures (SOPs) for incident management, disaster recovery, capacity scaling, and system maintenance in accordance with **SRS §22.1** and **Implementation Plan Phase 13**.

---

## 1. Incident Severity Matrix & Response SLAs

| Severity | Definition | Target MTTD | Target MTTR | Escalation Trigger |
|---|---|---|---|---|
| **SEV-1 (Critical)** | Complete platform outage; total task processing halt; database/broker unreachable; active data loss risk | < 2 min | < 15 min | Immediate On-Call Page, Tech Lead, Engineering Director |
| **SEV-2 (High)** | Degradation of processing throughput (> 50% drop); queue backlog exceeding backpressure threshold; worker crash loops | < 5 min | < 30 min | Primary On-Call Page, Secondary On-Call notified |
| **SEV-3 (Moderate)** | Non-blocking failure; isolated DLQ accumulations; scheduler leader delay; single worker node degradation | < 15 min | < 2 hours | Slack `#task-engine-alerts` notification, next business rotation |

---

## 2. Master Runbook Directory (SRS §22.1)

| Runbook ID | Title | Target Subsystem | Default Severity | Document Link |
|---|---|---|---|---|
| **RB-001** | Worker Crash Storm Recovery | Worker Pool, Celery/Native Runtime | **SEV-1 / SEV-2** | [RB-001-worker-crash-storm.md](file:///d:/One/task-engine/docs/runbooks/RB-001-worker-crash-storm.md) |
| **RB-002** | Redis Outage & Restart Procedure | Redis Streams Broker | **SEV-1** | [RB-002-redis-outage.md](file:///d:/One/task-engine/docs/runbooks/RB-002-redis-outage.md) |
| **RB-003** | PostgreSQL / Supabase Outage Procedure | System of Record, Persistence | **SEV-1** | [RB-003-postgres-outage.md](file:///d:/One/task-engine/docs/runbooks/RB-003-postgres-outage.md) |
| **RB-004** | Dead Letter Queue (DLQ) Replay Procedure | DLQ & Error Classification | **SEV-2 / SEV-3** | [RB-004-dlq-replay.md](file:///d:/One/task-engine/docs/runbooks/RB-004-dlq-replay.md) |
| **RB-005** | Queue Overload & Backpressure Mitigation | Queues & Rate Limiting | **SEV-2** | [RB-005-queue-overload.md](file:///d:/One/task-engine/docs/runbooks/RB-005-queue-overload.md) |
| **RB-006** | Scheduler Stuck & Leader Election Reset | Cron Scheduler & Advisory Locks | **SEV-2** | [RB-006-scheduler-stuck.md](file:///d:/One/task-engine/docs/runbooks/RB-006-scheduler-stuck.md) |
| **RB-007** | Transactional Outbox Backlog Drain | Outbox Poller & Relay | **SEV-2** | [RB-007-outbox-backlog.md](file:///d:/One/task-engine/docs/runbooks/RB-007-outbox-backlog.md) |
| **RB-008** | Database Migration Rollback Procedure | Alembic & PostgreSQL Schema | **SEV-1 / SEV-2** | [RB-008-migration-rollback.md](file:///d:/One/task-engine/docs/runbooks/RB-008-migration-rollback.md) |
| **RB-009** | Zero-Downtime Credential Rotation | Secrets, JWT, Database & Redis | **SEV-2 / Maintenance** | [RB-009-credential-rotation.md](file:///d:/One/task-engine/docs/runbooks/RB-009-credential-rotation.md) |
| **RB-010** | Disaster Recovery & Point-in-Time Restore | Full Platform & Backups | **SEV-1** | [RB-010-disaster-recovery.md](file:///d:/One/task-engine/docs/runbooks/RB-010-disaster-recovery.md) |
| **RB-011** | Capacity Expansion (Horizontal Worker Scaling) | Worker Pool & Infrastructure | **SEV-3 / Operational** | [RB-011-capacity-expansion.md](file:///d:/One/task-engine/docs/runbooks/RB-011-capacity-expansion.md) |

---

## 3. High-Level Incident Triage Flowchart

```
                 [ Incoming Alert / Degradation ]
                               |
            +------------------+------------------+
            |                                     |
   [Infrastructure Down]                 [Processing Impaired]
            |                                     |
    +-------+-------+                     +-------+-------+
    |               |                     |               |
 [PostgreSQL]    [Redis]              [Worker Crash]  [Queue Lag / Backlog]
    |               |                     |               |
  RB-003          RB-002                RB-001          RB-005
                                                          |
                                                  +-------+-------+
                                                  |               |
                                              [DLQ Accum]   [Scheduler Stuck]
                                                  |               |
                                                RB-004          RB-006
```

---

## 4. Universal Diagnostic Toolkit

```bash
# 1. Check container health status across cluster
docker compose ps

# 2. Check API live health probe and component readiness
curl -s http://localhost:8000/api/v1/health | jq .

# 3. Stream centralized structured logs
docker compose logs --tail=100 -f api worker scheduler

# 4. Inspect real-time metrics
curl -s http://localhost:8000/api/v1/metrics | grep task_engine
```

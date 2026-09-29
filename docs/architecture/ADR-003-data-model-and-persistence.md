# ADR-003: Relational Data Model, Indexing Strategy, and Repository Pattern

**Date:** 2026-09-25  
**Status:** Accepted  
**Deciders:** Project Engineering Team  
**SRS Reference:** Section 7.1, Section 8, Section 10, Section 11 (Table 10), Section 14.1, Section 15.2

---

## Context

The Event-Driven Distributed Task Processing Engine requires high-throughput, low-latency persistence for concurrent task lifecycle transitions, transactional outbox publishing, worker heartbeat tracking, and leader-elected scheduling. Under peak load (up to 10,000 outstanding tasks per baseline deployment), the database must provide safe concurrent claims without table contention, deadlocks, or lost updates.

---

## Decision

1. **Relational Schema (12 Tables per SRS §11 Table 10):**
   - `tasks`: Primary durable task state, versioned for optimistic concurrency.
   - `task_attempts`: Per-execution audit log tracking worker IDs, execution windows, and redacted error messages.
   - `task_events`: Immutable event stream recording state changes (`task.created`, `task.started`, etc.).
   - `task_outbox`: Transactional outbox records ensuring at-least-once message delivery to brokers.
   - `queues`: Queue definitions, rate-limit thresholds, and broker backend routing (`FK -> broker_backends`).
   - `broker_backends`: Pluggable broker configurations (`native`, `redis`, `rabbitmq`, `nats`, `sqs`).
   - `workers`: Worker instance registration, concurrency limits, and liveness heartbeats.
   - `schedules`: Recurring cron and interval schedules with timezone and misfire policy support.
   - `idempotency_keys`: Unique scoped request deduplication records (`UNIQUE (scope, idempotency_key)`).
   - `dlq_entries`: Dead letter entries for permanently failed tasks with operator replay tracking.
   - `api_credentials`: Authentication principal records storing key hashes (never plain keys).
   - `audit_events`: Immutable operator and administrative audit trail.

2. **Hot-Path Indexing Strategy:**
   - **SKIP LOCKED Claim Index:** Compound index `(queue, status, priority, created_at)` on `tasks` enables $O(\log N)$ task claims using `SELECT ... FOR UPDATE SKIP LOCKED`.
   - **Outbox Polling Partial Index:** `ix_task_outbox_unpublished` on `created_at WHERE published_at IS NULL` ensures outbox pollers only scan uncommitted events.
   - **Reconciler Lease Expiry Partial Index:** `ix_tasks_running_lease_expiry` on `lease_expires_at WHERE status = 'RUNNING'` enables instant recovery of crashed worker leases.
   - **Schedule Polling Index:** `ix_schedules_due` on `(enabled, next_run_at)` guarantees sub-millisecond due-job lookups.

3. **Repository Pattern:**
   - Data access logic is strictly encapsulated within repository classes (`TaskRepository`, `OutboxRepository`, `ScheduleRepository`, etc.).
   - Atomic transactions: `TaskRepository.create_with_outbox()` commits task rows and outbox rows inside a single database transaction.

---

## Consequences

- Direct database operations are clean, fully decoupled from HTTP or worker layers, and unit/integration testable.
- High-concurrency worker fleets claim tasks concurrently without lock contention.
- Transactional outbox guarantees that no task is published to a message broker unless durably committed to PostgreSQL.

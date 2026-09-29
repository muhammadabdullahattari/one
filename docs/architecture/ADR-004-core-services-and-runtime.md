# ADR-004: Core Backend Services, Pluggable Broker Architecture, and Worker Runtime

**Date:** 2026-09-25  
**Status:** Accepted  
**Deciders:** Project Engineering Team  
**SRS Reference:** Section 7.2 (Components), Section 7.3 (Broker), Section 8 (Lifecycle), Section 14 (Scheduling & Fairness), Section 15 (Workers)

---

## Context

The engine requires a resilient, at-least-once task execution architecture that does not lose jobs during worker crashes, network interruptions, or broker restarts. Furthermore, the engine must support zero-infrastructure local setups (using native PostgreSQL `SKIP LOCKED`) while remaining pluggable to Redis Streams or cloud brokers without application code changes.

---

## Decision

1. **BrokerAdapter Interface (SRS §7.3.1):**
   - Standard 7-method contract: `publish`, `consume`, `acknowledge`, `nack`, `extend_lease`, `dead_letter`, and `stats`.
   - `NativeBrokerAdapter`: PostgreSQL-based zero-infra implementation utilizing `SKIP LOCKED` queries for concurrency-safe claims.

2. **Transactional Outbox & OutboxPublisher (SRS §7.1, §7.2):**
   - Every task submission creates a database task record and a transactional outbox entry in one atomic transaction.
   - `OutboxPublisher` background loop asynchronously dispatches committed outbox rows to the target queue broker.

3. **Reconciler Daemon (SRS §7.2, NFR-008):**
   - Background daemon dedicated to system self-healing.
   - Recovers tasks when a worker crashes mid-execution (lease expiry) or when outbox publication lags, guaranteeing at-least-once delivery.

4. **Task Registry Security Model (SRS §7.2, §15.2):**
   - Workers resolve handlers exclusively through the local in-process `TaskRegistry`.
   - Serialized payloads are strictly treated as data (JSON) and never executed as raw code.

5. **HA Scheduler & Misfire Handling (SRS §14.1):**
   - Self-built scheduling daemon powered by PostgreSQL `pg_try_advisory_xact_lock` leader election.
   - Full support for 5-field and 6-field (seconds) cron, IANA timezones (canonical UTC storage), and all 3 SRS misfire policies (`SKIP`, `CATCH_UP`, `COALESCING`).

6. **Rate Limiting & Anti-Starvation Fairness (SRS §14.2, §14.3):**
   - Token-bucket rate limiting backed by atomic Redis Lua scripts with fail-open fallback.
   - Dynamic anti-starvation priority aging formula boosting older low-priority jobs.

---

## Consequences

- Complete separation of concerns: API, Scheduler, OutboxPublisher, Reconciler, and Workers can run independently or in a single process.
- No third-party scheduler libraries (`apscheduler` / `celery`) are required.
- High availability with automated failover and zero message loss.

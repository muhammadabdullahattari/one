# Architectural Decision Records (ADR) Index

This document tracks all formal architectural decisions for the Task Engine architecture, runtime systems, persistence layers, and client interfaces.

---

## Index of Decisions

| ADR ID | Title | Date | Status | Summary |
|---|---|---|---|---|
| [ADR-001](ADR-001-project-structure.md) | Project Structure and Package Management | 2026-09-24 | Accepted | Single repository `src/` layout using `uv` for reproducible builds and byte-identical dependency lockfiles. |
| [ADR-002](ADR-002-configuration-and-secrets.md) | Configuration and Secrets Management | 2026-09-24 | Accepted | Pydantic Settings with strict production validation, secret redaction, and multi-tier precedence. |
| [ADR-003](ADR-003-data-model-and-persistence.md) | Data Model and Persistence Architecture | 2026-09-24 | Accepted | PostgreSQL with `asyncpg` as ACID source of truth, advisory locks for leader election, and Alembic migrations. |
| [ADR-004](ADR-004-core-services-and-runtime.md) | Core Services and Runtime Architecture | 2026-09-24 | Accepted | Asynchronous runtime architecture with decoupled workers, lease management, and heartbeat monitoring. |
| [ADR-005](ADR-005-api-surface-and-schemas.md) | API Surface and Schema Design | 2026-09-24 | Accepted | FastAPI REST API with OpenAPI 3.1 schema compliance, WebSocket live channels, and Pydantic v2 schemas. |
| [ADR-006](ADR-006-redis-streams-broker-adapter.md) | Redis Streams Broker Adapter | 2026-09-24 | Accepted | Redis Streams as primary broker with consumer groups (`XREADGROUP`), acknowledgment (`XACK`), and maxlen trimming. |
| [ADR-007](ADR-007-observability-metrics-tracing-and-logging.md) | Observability: Metrics, Tracing, and Logging | 2026-09-24 | Accepted | Structured JSON logging with trace context correlation, Prometheus metrics, and OpenTelemetry OTLP tracing. |
| [ADR-008](ADR-008-security-rbac-and-multitenancy.md) | Security, RBAC, and Multi-Tenancy | 2026-09-24 | Accepted | Pluggable JWT / API key authentication, tenant isolation via `X-Tenant-Id`, and role-based access control. |
| [ADR-009](ADR-009-test-strategy-and-api-validation.md) | Test Strategy and API Validation | 2026-09-24 | Accepted | Multi-tier test pyramid: unit, integration, simulated multi-app E2E microservices, and static analysis verification. |

---

## ADR Process

1. **Creating an ADR**: Copy the template below and save as `docs/architecture/ADR-XXX-<topic>.md`.
2. **Review & Acceptance**: Review with core team members. Once consensus is reached, mark status as `Accepted`.
3. **Superceding Decisions**: If a decision is superseded, update the status to `Deprecated` or `Superseded by ADR-YYY` with a reference link.

### Template

```markdown
# ADR-XXX: Title

**Date:** YYYY-MM-DD
**Status:** [Proposed | Accepted | Deprecated | Superseded]
**Deciders:** Team members

## Context
Describe the architectural context, business driver, or challenge being addressed.

## Decision
Describe the chosen solution and core mechanisms adopted.

## Consequences
Detail positive, negative, and neutral trade-offs resulting from this decision.
```

# ADR-007: Observability Architecture — Metrics, Tracing & Logging

## Status
Accepted

## Context
Production-grade distributed task engines require end-to-end observability across task submission, broker dispatch, worker execution, retries, and database persistence. Per SRS §13 (Table 12) and NFR-012, the engine must emit structured JSON logs, OpenTelemetry traces with standardized correlation IDs, and Prometheus metrics covering all 9 operational categories.

## Decisions
1. **Prometheus Metrics Hierarchy:**
   - Implemented all 9 metric categories from SRS Table 12 in `src/observability/metrics.py`: API, Tasks, Queue, Execution, Workers, Scheduler, Broker, Database, and Rate Limits.
   - Mandatory gauges including `queue_oldest_task_age_seconds` (SRS §14.4) and `queue_depth` are maintained for auto-scaling and SLA alerting.
   - Metrics are exposed at `/api/v1/metrics` in standard Prometheus text format.

2. **Distributed Tracing (OpenTelemetry):**
   - Configured OpenTelemetry SDK (`src/observability/tracing.py`) with service metadata and configurable OTLP exporter endpoints.
   - Enforced NFR-012 mandatory correlation attributes on all spans: `task.id`, `task.attempt_id`, `task.queue`, `worker.id`, and `trace_id`.

3. **Structured JSON Logging & Secret Redaction:**
   - Structured logging configured via `structlog` emitting machine-readable JSON logs with automatic context propagation (`request_id`, `trace_id`, `task_id`).
   - Integrated zero-leak secret redaction (`src/observability/redaction.py`) sanitizing passwords, API keys, JWT tokens, and database connection strings before emission (SRS §12 / UT-010).

4. **Health Probes:**
   - Liveness probe (`/api/v1/health` and `/health`) validates process vitality (HTTP 200).
   - Readiness probe (`/api/v1/health/ready` and `/ready`) validates database and Redis availability, returning HTTP 503 on dependency failures.

## Consequences
- Guarantees zero-leakage of credentials and sensitive payloads across logs and error envelopes.
- Enables seamless integration with Prometheus, Grafana, Datadog, and OpenTelemetry Collectors.

# Task Engine

> **Event-Driven Distributed Task Processing Engine**  
> Celery-like developer ergonomics with zero-extra-infrastructure on PostgreSQL, or enterprise-grade sub-millisecond throughput on Redis Streams.

[![Python Version](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/typescript-5.5%2B-blue.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Architecture](https://img.shields.io/badge/architecture-event--driven-orange.svg)](#architecture)

---

## Highlights

* **Zero-Extra-Infrastructure Mode**: Run background tasks, delayed jobs, and retries natively on PostgreSQL using ACID transactional guarantees and `FOR UPDATE SKIP LOCKED`. No Redis or RabbitMQ required for small-to-medium deployments.
* **Enterprise High-Throughput Broker**: Scale to millions of tasks with Redis Streams consumer groups (`XREADGROUP`, `XACK`) with sub-millisecond dispatch.
* **Dual Language SDKs**: Full-featured clients for Python (`task-engine`) and TypeScript / Node.js (`@task-engine/sdk`).
* **Celery-like Ergonomics**: Decorate functions with `@engine.task` or `@task`, dispatch with `.delay()` or `.apply_async()`, and track results via `AsyncResult`.
* **Distributed Cron & Scheduling**: Crontab and interval scheduling with automatic leader election via PostgreSQL advisory locks.
* **Resilience & Fault Tolerance**: Heartbeat leases (`lease_expires_at`), automatic re-queueing of crashed worker tasks, exponential backoff retries with jitter, and dead-letter queue (DLQ) re-driving.
* **Multi-Tenancy & Security**: First-class tenant isolation (`X-Tenant-Id`), JWT & API Key authentication, and token bucket rate limiting.
* **Full Observability**: Prometheus metrics (`/metrics`), OpenTelemetry distributed tracing, structured JSON logs, and real-time WebSocket event feeds.
* **Real-time Web Console**: Next.js 14 dashboard for queue monitoring, worker management, live metrics, and DLQ replay.

---

## Quickstart

### Python Quickstart (`task-engine`)

```bash
pip install task-engine
```

Define a background task in `tasks.py`:

```python
from task_engine import TaskEngine, TaskContext

engine = TaskEngine.from_env()


@engine.task(queue="notifications", priority=3, max_retries=3)
async def send_welcome_email(payload: dict, context: TaskContext) -> dict:
    print(f"Executing task {context.task_id} for tenant: {context.tenant_id}")
    return {"status": "sent", "email": payload["email"]}
```

Start the worker:
```bash
task-engine worker -A tasks --queues notifications --concurrency 4
```

Submit and await results programmatically:
```python
from tasks import send_welcome_email

result = send_welcome_email.delay({"email": "alice@example.com"})
print(f"Task ID: {result.id}")

output = result.get(timeout=30)
print(f"Task finished: {output}")
```

---

### TypeScript / Node.js Quickstart (`@task-engine/sdk`)

```bash
npm install @task-engine/sdk
# or
pnpm add @task-engine/sdk
```

Submit tasks and poll results with complete type safety:

```typescript
import { TaskEngine } from "@task-engine/sdk";

const engine = new TaskEngine({
  apiUrl: process.env.TASK_ENGINE_API_URL || "http://localhost:8000",
  apiKey: process.env.TASK_ENGINE_API_KEY,
  tenantId: "default",
});

async function run() {
  const result = await engine.submitTask({
    taskType: "notifications.send_welcome_email",
    payload: { email: "bob@example.com" },
    queue: "notifications",
  });

  console.log(`Submitted: ${result.id}`);
  const output = await result.get({ timeoutMs: 15000 });
  console.log("Result:", output);
}

run();
```

Subscribe to real-time events over WebSockets:

```typescript
import { TaskEngineWebSocket } from "@task-engine/sdk";

const ws = new TaskEngineWebSocket({
  apiUrl: "http://localhost:8000",
  channel: "tasks",
});

ws.on("task.completed", (event) => console.log("Completed:", event.data));
ws.connect();
```

---

### CLI Command Reference

```bash
# Start background worker process
task-engine worker -A tasks --queues default,notifications --concurrency 10

# Start distributed cron scheduler daemon
task-engine scheduler -A tasks

# Apply database migrations
task-engine migrate

# Start web dashboard and API server
task-engine ui --port 8000

# Submit ad-hoc tasks from terminal
task-engine submit notifications.send_welcome_email -p '{"email":"user@test.com"}'

# Query task lifecycle and execution output
task-engine status <task-id>
```

---

## Documentation Hub

Comprehensive engineering guides, specifications, and runbooks:

* **SDK Developer Guides**:
  * [Python SDK Guide](docs/sdk/python.md)
  * [TypeScript SDK Guide](docs/sdk/typescript.md)
  * [SDK Changelog](docs/sdk/CHANGELOG.md)
* **API Specifications**:
  * [OpenAPI 3.1 Schema (`openapi.json`)](docs/api/openapi.json)
  * [Postman v2.1 Collection (`postman_collection.json`)](docs/api/postman_collection.json)
* **Infrastructure & Operations**:
  * [Configuration Reference](docs/config.md)
  * [Cluster Operations Guide](docs/operations.md)
  * [Troubleshooting Guide](docs/troubleshooting.md)
* **Operational Runbooks**:
  * [Runbook Index](docs/runbooks/README.md)
  * [RB-001: Worker Crash Storm](docs/runbooks/RB-001-worker-crash-storm.md)
  * [RB-002: Redis Outage](docs/runbooks/RB-002-redis-outage.md)
  * [RB-003: Postgres Outage](docs/runbooks/RB-003-postgres-outage.md)
  * [RB-004: DLQ Replay](docs/runbooks/RB-004-dlq-replay.md)
  * [RB-005: Queue Overload](docs/runbooks/RB-005-queue-overload.md)
  * [RB-006: Scheduler Stuck](docs/runbooks/RB-006-scheduler-stuck.md)
  * [RB-007: Outbox Backlog](docs/runbooks/RB-007-outbox-backlog.md)
  * [RB-008: Migration Rollback](docs/runbooks/RB-008-migration-rollback.md)
  * [RB-009: Credential Rotation](docs/runbooks/RB-009-credential-rotation.md)
  * [RB-010: Disaster Recovery](docs/runbooks/RB-010-disaster-recovery.md)
  * [RB-011: Capacity Expansion](docs/runbooks/RB-011-capacity-expansion.md)
* **Architecture Decision Records**:
  * [ADR Index](docs/architecture/ADR_INDEX.md)
  * [ADR-001: Project Structure](docs/architecture/ADR-001-project-structure.md)
  * [ADR-002: Configuration & Secrets](docs/architecture/ADR-002-configuration-and-secrets.md)
  * [ADR-003: Data Model & Persistence](docs/architecture/ADR-003-data-model-and-persistence.md)
  * [ADR-004: Core Services & Runtime](docs/architecture/ADR-004-core-services-and-runtime.md)
  * [ADR-005: API Surface & Schemas](docs/architecture/ADR-005-api-surface-and-schemas.md)
  * [ADR-006: Redis Streams Broker Adapter](docs/architecture/ADR-006-redis-streams-broker-adapter.md)
  * [ADR-007: Observability (Metrics, Tracing, Logging)](docs/architecture/ADR-007-observability-metrics-tracing-and-logging.md)
  * [ADR-008: Security, RBAC & Multi-Tenancy](docs/architecture/ADR-008-security-rbac-and-multitenancy.md)
  * [ADR-009: Test Strategy & Validation](docs/architecture/ADR-009-test-strategy-and-api-validation.md)

---

## Verification & Testing

### Python Test Suite
```bash
uv run pytest tests/
uv run ruff check .
uv run mypy src/
```

### TypeScript SDK Suite
```bash
cd packages/sdk-ts
pnpm test
pnpm run typecheck
pnpm run build
```

---

## License

This project is licensed under the [MIT License](LICENSE).

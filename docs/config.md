# Configuration Reference

This document provides a comprehensive specification of all environment variables and configuration settings powering the Task Processing Engine across API instances, Worker nodes, Scheduler daemons, and SDKs.

---

## 1. Overview & Loading Precedence

Configuration is managed via Pydantic Settings and follows a strict hierarchy of precedence:

1. **System Environment Variables** (highest priority)
2. **Local Environment File** (`.env` in the project root)
3. **Application Defaults** (specified in `src/core/config.py` and `src/core/constants.py`)

Settings are case-insensitive. When deploying to production or container orchestrators (Kubernetes, Docker Swarm), inject settings directly via environment variables or secret mounts.

---

## 2. Core Application Settings

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_ENV` | `string` | `development` | Target runtime environment: `development`, `test`, `staging`, `production`. Production mode enforces minimum secret lengths and strict security guards. |
| `APP_VERSION` | `string` | `0.1.0` | Semantic version string reported in health probes and metrics. |
| `LOG_LEVEL` | `string` | `INFO` | Logging threshold: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_FORMAT` | `string` | `json` | Structured output formatting: `json` (production structured) or `text` (human-readable console). |
| `SECRET_KEY` | `string` | *(insecure dev key)* | Cryptographic HMAC-SHA256 secret key for signing tokens. In staging/production, must be >= 32 characters and cannot contain default placeholders. |

---

## 3. Database & Connection Pooling

The primary state store uses PostgreSQL with asynchronous I/O (`asyncpg`) and connection pooling.

| Variable | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | `string` | `postgresql+asyncpg://postgres:postgres@localhost:5432/task_engine_dev` | Asynchronous connection URL using the `asyncpg` driver. |
| `DATABASE_URL_SYNC` | `string` | *(auto-derived from DATABASE_URL)* | Synchronous connection URL using `psycopg2` or standard PostgreSQL driver for Alembic schema migrations. |
| `DATABASE_SESSION_URL` | `string` | *(auto-derived from DATABASE_URL)* | Dedicated connection URL used for session-level PostgreSQL advisory locks in scheduler leader election. |
| `DB_POOL_SIZE` | `integer` | `20` | Size of the persistent async connection pool (1–100). |
| `DB_MAX_OVERFLOW` | `integer` | `10` | Maximum temporary connections allowed beyond `DB_POOL_SIZE` during traffic bursts (0–50). |
| `DB_POOL_TIMEOUT` | `float` | `30.0` | Seconds to wait before timing out while acquiring a connection from the pool. |
| `DB_POOL_RECYCLE` | `integer` | `1800` | Connection recycling duration in seconds (30 minutes) to avoid stale socket drops behind load balancers. |
| `DB_POOL_PRE_PING` | `boolean` | `true` | Validates socket health before handing connections to queries. |

---

## 4. Message Broker (Redis Streams)

Redis provides low-latency queue transport, consumer groups, and distributed rate limiting.

| Variable | Type | Default | Description |
|---|---|---|---|
| `REDIS_URL` | `string` | `redis://localhost:6379/0` | Connection string for Redis. Supports `redis://`, `rediss://` (TLS encrypted), and `unix://` sockets. |
| `REDIS_STREAM_MAXLEN` | `integer` | `100000` | Approximate maximum stream length maintained via Redis Streams `XADD MAXLEN ~`. |
| `REDIS_MAX_CONNECTIONS`| `integer` | `50` | Maximum size of the asynchronous Redis connection pool. |
| `REDIS_SOCKET_TIMEOUT` | `float` | `5.0` | Socket timeout in seconds for broker operations. |

---

## 5. Worker & Task Execution Parameters

Controls task concurrency, heartbeat intervals, and failure detection.

| Variable | Type | Default | Description |
|---|---|---|---|
| `WORKER_CONCURRENCY` | `integer` | `10` | Maximum concurrent tasks executed per worker process (1–500). |
| `LEASE_SECONDS` | `integer` | `30` | Duration of task lease ownership. Leases expire if worker crashes without heartbeat renewal. |
| `HEARTBEAT_INTERVAL_SECONDS` | `integer` | `5` | Cadence at which workers pulse active leases and registry status. Must be strictly less than `LEASE_SECONDS`. |
| `DEFAULT_MAX_ATTEMPTS` | `integer` | `3` | Maximum execution retries assigned when not explicitly overridden by task definition. |
| `DEFAULT_TIMEOUT_SECONDS` | `integer` | `300` | Execution timeout in seconds (5 minutes) before a task attempt is considered timed out. |
| `TASK_MAX_PAYLOAD_BYTES` | `integer` | `1048576` | Maximum inline task payload size in bytes (1 MB). Larger payloads offload to object storage. |

---

## 6. Scheduler & Cron Subsystem

Powers distributed cron scheduling, interval recurring tasks, and leader election.

| Variable | Type | Default | Description |
|---|---|---|---|
| `SCHEDULER_TICK_SECONDS` | `integer` | `1` | Interval between scheduler sweeps checking for due cron or interval jobs (1–60s). |
| `SCHEDULER_LEADER_LOCK_TTL_SECONDS` | `integer` | `15` | Lease duration for distributed leader election lock (`pg_try_advisory_xact_lock` or Redis lock). |

---

## 7. Rate Limiting & Flow Control

Protects downstream APIs and downstream systems from queue burst storms.

| Variable | Type | Default | Description |
|---|---|---|---|
| `RATE_LIMIT_BACKEND` | `string` | `redis` | Backend storage for token bucket algorithms: `redis` (distributed cluster) or `postgres` (zero-infra fallback). |
| `DEFAULT_RATE_LIMIT_RPS` | `integer` | `100` | Default token refresh rate in requests per second per tenant/queue. |

---

## 8. Authentication & Multi-Tenancy

Controls access to API endpoints, CLI, and SDK connections.

| Variable | Type | Default | Description |
|---|---|---|---|
| `API_AUTH_MODE` | `string` | `jwt` | Authentication mode: `jwt`, `api_key`, or `both`. |
| `ALGORITHM` | `string` | `HS256` | Cryptographic algorithm for JWT verification. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `integer` | `30` | Lifespan of short-lived JWT access tokens. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `integer` | `7` | Lifespan of persistent refresh tokens. |
| `API_KEY_SALT` | `string` | `task-engine-api-key-salt` | Salt string used during cryptographic hashing of external API keys. |

---

## 9. Data Retention & Housekeeping

Governs automated vacuuming and purging of historic records.

| Variable | Type | Default | Description |
|---|---|---|---|
| `RESULT_RETENTION_DAYS` | `integer` | `7` | Days to retain completed task result data before automated pruning. |
| `TASK_EVENT_RETENTION_DAYS` | `integer` | `30` | Days to retain audit log events in `task_events` table. |
| `DLQ_RETENTION_DAYS` | `integer` | `90` | Days to retain exhausted or poisoned tasks in Dead Letter Queue storage. |

---

## 10. Observability & Telemetry

| Variable | Type | Default | Description |
|---|---|---|---|
| `METRICS_ENABLED` | `boolean` | `true` | Exposes `/metrics` endpoint formatted for Prometheus scrapers. |
| `OTEL_EXPORTER_ENDPOINT` | `string` | `None` | OpenTelemetry OTLP collector gRPC/HTTP endpoint for distributed traces and spans. |

---

## 11. Large Payload Storage (S3 & Supabase)

Required when task payloads or execution returns exceed `TASK_MAX_PAYLOAD_BYTES` (1 MB).

| Variable | Type | Default | Description |
|---|---|---|---|
| `S3_ENDPOINT_URL` | `string` | `None` | S3-compatible storage endpoint (e.g., MinIO, Supabase Storage, AWS). |
| `S3_ACCESS_KEY_ID` | `string` | `None` | Access key ID for object storage. |
| `S3_SECRET_ACCESS_KEY` | `string` | `None` | Secret access key for object storage. |
| `S3_BUCKET_NAME` | `string` | `task-payloads` | Target bucket name. |
| `S3_REGION` | `string` | `us-east-1` | Target storage region. |
| `SUPABASE_URL` | `string` | `None` | Supabase project URL (`https://<project>.supabase.co`). |
| `SUPABASE_ANON_KEY` | `string` | `None` | Supabase public anonymous key. |
| `SUPABASE_SERVICE_ROLE_KEY` | `string` | `None` | Supabase privileged service role key (backend operations). |

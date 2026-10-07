# Cluster Operations Guide

This guide details best practices for running, scaling, monitoring, and maintaining Task Engine clusters in production environments.

---

## 1. System Architecture

```
                    +-----------------------+
                    |    API Load Balancer  |
                    +-----------+-----------+
                                |
             +------------------+------------------+
             |                                     |
   +---------v---------+                 +---------v---------+
   |   API Instance 1  |                 |   API Instance 2  |
   +---------+---------+                 +---------+---------+
             |                                     |
             +------------------+------------------+
                                |
             +------------------+------------------+
             |                                     |
   +---------v---------+                 +---------v---------+
   |  PostgreSQL State |                 |   Redis Streams   |
   | (ACID Persistence)|                 |  (Message Broker) |
   +---------+---------+                 +---------+---------+
             ^                                     ^
             |                                     |
   +---------+---------+                 +---------+---------+
   | Worker Node Pool  |<----------------+   Scheduler Node  |
   | (Bounded Threads) |                 |  (Leader Election)|
   +-------------------+                 +-------------------+
```

The system comprises three independently scalable components:
1. **API Instances (Stateless)**: Ingests tasks, serves REST/WebSocket clients, authenticates users, and queries state. Horizontally scalable behind reverse proxies (Nginx, Traefik, AWS ALB).
2. **Worker Pool (Stateless Compute)**: Pulls tasks from broker queues, executes Python handlers, renews leases via heartbeats, and writes results. Scaled based on queue depth and processing latency.
3. **Scheduler Instances (Active-Passive)**: Evaluates cron expressions and interval schedules. Requires a distributed leader election lock so that only one leader emits scheduled tasks at any time.

---

## 2. Deployment Modes

### Mode A: Zero-Infrastructure Mode (PostgreSQL Only)
Suitable for small-to-medium workloads, single-region apps, or testing environments.
* Message broker tasks use PostgreSQL `FOR UPDATE SKIP LOCKED`.
* Rate limiting uses PostgreSQL token buckets.
* Eliminates need for Redis or external message brokers.

### Mode B: Enterprise Clustered Mode (PostgreSQL + Redis Streams)
Recommended for high-throughput, low-latency enterprise production.
* Redis Streams serves as sub-millisecond message transport with consumer groups (`XREADGROUP`, `XACK`).
* PostgreSQL acts as durable source of truth and audit log.
* Redis handles distributed token bucket rate limiting.

---

## 3. Health Checks & Probes

Configure orchestrator health checks against these endpoints:

### Liveness Probe (`/health/live`)
Returns HTTP 200 if the process event loop is responsive.
```bash
curl -f http://localhost:8000/health/live
```
**Kubernetes spec:**
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Readiness Probe (`/health/ready`)
Verifies active database connections, Redis broker availability, and migration state.
```bash
curl -f http://localhost:8000/health/ready
```
**Kubernetes spec:**
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

## 4. Scheduler Leader Election

The Scheduler supports running multiple replicas for high availability. One instance becomes the leader; standby instances monitor the leader lock and take over automatically if the leader terminates.

### Lock Mechanism
* **PostgreSQL Advisory Lock**: Acquired using session-level `pg_try_advisory_xact_lock` or persistent heartbeat tables.
* **Lease TTL**: Governed by `SCHEDULER_LEADER_LOCK_TTL_SECONDS` (default: 15 seconds).
* **Standby Behavior**: Standby schedulers poll every 1 second. If the leader fails to renew before the TTL expires, a standby claims leadership immediately with zero schedule interruption.

---

## 5. Scaling Workers & Queues

### Concurrency Tuning
The `WORKER_CONCURRENCY` parameter specifies concurrent async execution slots within a single worker process.
* **I/O-bound tasks** (HTTP requests, database exports, email sending): Concurrency 20–50 per worker.
* **CPU-bound tasks** (media processing, heavy calculation): Concurrency matching CPU core count (2–4 per worker) or separate multi-process workers.

### Queue Isolation
Separate critical workloads onto dedicated queues to prevent starvation:
```bash
# Critical high-priority worker
task-engine worker -A tasks --queues high,critical --concurrency 20

# Standard background worker
task-engine worker -A tasks --queues default,reports --concurrency 10
```

### Auto-Scaling Metrics
Scale worker replica counts dynamically based on:
1. `task_engine_queue_depth`: Number of pending and queued tasks.
2. `task_engine_task_latency_seconds_bucket`: P95 queue wait time.

---

## 6. Observability & Metrics

Prometheus metrics are exposed at `/metrics`:

| Metric Name | Type | Description |
|---|---|---|
| `task_engine_tasks_submitted_total` | Counter | Total tasks received by task type and queue. |
| `task_engine_tasks_completed_total` | Counter | Total tasks completed by status (`SUCCEEDED`, `FAILED`). |
| `task_engine_task_execution_duration_seconds` | Histogram | Execution time percentiles (P50, P95, P99). |
| `task_engine_queue_depth` | Gauge | Instantaneous number of messages queued per queue. |
| `task_engine_active_workers` | Gauge | Count of registered workers sending healthy heartbeats. |
| `task_engine_dlq_messages_total` | Counter | Tasks moved to Dead Letter Queue. |

---

## 7. Graceful Shutdown & Zero-Downtime Deployments

Workers implement strict POSIX signal handling:

1. **On `SIGTERM` / `SIGINT`**:
   - The worker unregisters from the broker consumer group to stop pulling new tasks.
   - It marks its status as `DRAINING` in the database.
   - Existing running tasks are allowed up to `LEASE_SECONDS` to complete cleanly.
   - Completed results are persisted to PostgreSQL before process exit.
2. **On Force Termination (`SIGKILL`)**:
   - Uncompleted task leases expire after `LEASE_SECONDS`.
   - The lease monitor automatically re-claims expired tasks and re-queues them for surviving workers.

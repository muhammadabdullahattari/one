# Runbook RB-011: Capacity Expansion (Horizontal Worker Scaling)

- **Runbook ID:** RB-011
- **Target Subsystem:** Worker Pool & Fleet Sizing
- **Default Severity:** SEV-3 / Operational Scaling
- **Relevant SRS Sections:** SRS §15 (Worker Lifecycle), SRS §21 (Performance Limits), SRS §22.1

---

## 1. Capacity Sizing Model

Before scaling worker containers, calculate required worker concurrency slots using Little's Law:

$$\text{Required Slots} = \lambda \times W$$

Where:
- $\lambda$ = Peak task arrival rate (tasks per second)
- $W$ = Average execution duration per task (seconds)

### Example Calculation:
For $500\text{ tasks/sec}$ with an average duration of $0.2\text{ seconds}$:
$$\text{Required Slots} = 500 \times 0.2 = 100\text{ concurrent slots}$$

With `--concurrency 4` per worker container:
$$\text{Required Worker Containers} = \frac{100}{4} = 25\text{ containers}$$

---

## 2. Horizontal Scaling via Docker Compose

### Step 1: Scale Worker Replicas
```bash
# Scale worker fleet dynamically to 10 instances
docker compose up -d --scale worker=10 --no-recreate worker
```

### Step 2: Verify Roster Registration
Inspect active workers registered in the platform database:
```bash
curl -s http://localhost:8000/api/v1/workers | jq '.items | length'
```
*Expected:* Matches the new replica count.

---

## 3. Dedicated Queue Worker Pools

To isolate heavy, long-running jobs (e.g., reports, image processing) from fast, low-latency jobs:

### Step 1: Start Dedicated Pool for "heavy" Queue
```bash
docker compose run -d \
  --name worker-pool-heavy \
  worker \
  python3 -m src.sdk.cli worker start --queues heavy --concurrency 2
```

### Step 2: Start High-Concurrency Pool for "default" Queue
```bash
docker compose run -d \
  --name worker-pool-fast \
  worker \
  python3 -m src.sdk.cli worker start --queues default --concurrency 16
```

---

## 4. Downstream Resource Considerations

When scaling workers up, ensure that downstream dependencies are sized appropriately:
1. **PostgreSQL Connections:** Each worker holds $\le 2$ persistent async connections. 25 workers = 50 connections. Verify `max_connections` in PostgreSQL:
   ```sql
   SHOW max_connections;
   ```
2. **Redis Client Connections:** Redis easily handles 10,000+ client sockets; verify Redis memory for consumer group state:
   ```bash
   docker compose exec redis redis-cli info clients
   ```

---

## 5. Graceful Downscaling Procedure

When the load spike subsides, scale workers down gracefully without terminating active jobs:
```bash
# 1. Trigger draining via API for targeted workers
curl -X POST "http://localhost:8000/api/v1/workers/{worker_id}/drain" \
     -H "Authorization: Bearer $ADMIN_TOKEN"

# 2. Once drained, safely reduce Compose replica count
docker compose up -d --scale worker=2 --no-recreate worker
```

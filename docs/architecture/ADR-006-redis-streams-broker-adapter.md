# ADR-006: Redis Streams Broker Adapter & Conformance Suite

## Status
Accepted

## Context
The task processing engine requires high-throughput message broker backends capable of sub-millisecond task dispatch and consumer coordination. In addition to the PostgreSQL native broker (`NativeBrokerAdapter`), the system requires a production-grade Redis Streams adapter (`RedisBrokerAdapter`) supporting consumer groups (`XREADGROUP`), automatic stream trimming (`MAXLEN ~`), dead-letter routing, and pending entry recovery (`XAUTOCLAIM`).

## Decisions
1. **Redis Streams Architecture:**
   - Tasks are published to queue-specific Redis Streams using `XADD` with approximate trimming (`MAXLEN ~`) to cap memory usage without stalling pipelines.
   - Worker fleets consume tasks through Redis consumer groups (`XREADGROUP`) with dedicated group identifiers per queue (`task_engine:cg:<queue>`).
   - Consumer group creation uses `MKSTREAM` and idempotently handles existing groups (`BUSYGROUP` exception absorption).

2. **At-Least-Once Delivery & ACK Protocol:**
   - Messages are acknowledged via `XACK` and released from the in-memory/KV lease tracking upon task completion or terminal failure.
   - Dead-lettered tasks are routed to dedicated DLQ streams (`task_engine:dlq:<queue>`) before ACK-ing the primary stream.
   - Stale in-flight tasks from failed worker processes are reclaimed via atomic `XAUTOCLAIM`.

3. **Pluggable Broker Interface & Conformance Suite:**
   - Both `NativeBrokerAdapter` and `RedisBrokerAdapter` strictly conform to the `BrokerAdapter` interface defined in `src/broker/core/adapter.py`.
   - A unified test suite in `tests/broker_conformance/test_conformance.py` validates identical lifecycle contracts across all supported broker backends.

## Consequences
- Enables linear scaling of task ingestion and consumption with minimal database lock contention.
- Guarantees broker backend portability across native PostgreSQL and Redis Streams environments.

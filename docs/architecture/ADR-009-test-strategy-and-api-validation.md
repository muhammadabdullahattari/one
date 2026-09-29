# ADR-009: Test Strategy, Conformance & API Validation

## Status
Accepted

## Context
Phase 8 represents the comprehensive testing gate validating the complete API surface, domain state guards, transactional persistence guarantees, broker portability, and operational error sanitization before any frontend UI construction. Per SRS §20 (Tables 21 & 22) and Appendix C, all 15 unit tests (`UT-001` to `UT-015`), 10 integration tests (`IT-001` to `IT-010`), and broker conformance suites must execute and pass cleanly.

## Decisions
1. **Explicit SRS Test Mapping:**
   - Implemented `tests/unit/test_srs_unit_suite.py` explicitly matching SRS Table 21 acceptance IDs `UT-001` through `UT-015`.
   - Implemented `tests/integration/test_srs_integration_suite.py` matching SRS Table 22 acceptance IDs `IT-001` through `IT-010`.

2. **Multi-Tier Test Architecture:**
   - **Unit Tests (`tests/unit/`):** Fast, isolated, deterministic evaluations of schemas, state machines, priority aging, jitter calculations, token bucket limiters, cron evaluations, and security hashing.
   - **Broker Conformance Tests (`tests/broker_conformance/`):** Unified test harness parameterized over `NativeBrokerAdapter` and `RedisBrokerAdapter` to guarantee identical runtime semantics.
   - **Integration Tests (`tests/integration/`):** End-to-end transactional testing with PostgreSQL, outbox publishing, worker heartbeat tracking, and result persistence.
   - **Regression Tests (`tests/regression/`):** Validation of crash failover recovery, schedule deduplication, and DLQ idempotent replays.

3. **FastAPI & Swagger UI Surface Validation:**
   - Validated all REST routes (`/api/v1/tasks`, `/api/v1/queues`, `/api/v1/workers`, `/api/v1/schedules`, `/api/v1/dlq`, `/api/v1/projects`, `/api/v1/auth`, `/api/v1/analytics`, `/api/v1/brokers`, `/api/v1/health`), WebSocket streaming channels, and SSE event endpoints.

## Consequences
- Guarantees 100% test verification across all core layers prior to frontend and SDK development.
- Provides immediate regression detection for future refactoring and scaling initiatives.

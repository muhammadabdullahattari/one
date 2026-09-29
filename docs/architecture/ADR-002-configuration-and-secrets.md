# ADR-002: Configuration Management, Environment Keys, and Secrets Handling

**Date:** 2026-09-24  
**Status:** Accepted  
**Deciders:** Project Engineering Team  
**SRS Reference:** Section 11, Section 12 (Security), Section 14, Section 19 (Table 20), NFR-010

---

## Context

The Event-Driven Distributed Task Processing Engine requires a robust, type-safe, and secure configuration system across its multiple runtime components (REST API service, distributed worker fleet, HA cron scheduler daemon, and Python SDK/CLI). The engine integrates with PostgreSQL (via Supabase), Redis Streams, and optional S3-compatible storage.

Improper configuration or leaked credentials would compromise multi-tenant isolation, data durability, and production security.

---

## Decision

1. **Pydantic Settings v2 (`pydantic-settings`):**
   - Central `Settings` class (`src/core/config.py`) encapsulates all 16 mandatory variables defined in SRS §19 Table 20.
   - All settings are strongly typed with validation bounds (e.g. `task_max_payload_bytes`, `default_max_attempts`, `lease_seconds`, `heartbeat_interval_seconds`).
   - Caching: Accessed through an `@lru_cache()` thread-safe singleton function `get_settings()`.

2. **Database Connection Strategy (SRS §11 & §23):**
   - Direct PostgreSQL asynchronous connection via `postgresql+asyncpg://` is the primary database driver for FastAPI and Worker runtimes.
   - Sync URL (`DATABASE_URL_SYNC`) is used strictly for Alembic database migrations.
   - Session-persistent connection (`database_session_url`) is reserved for the Scheduler process to maintain PostgreSQL session-level advisory locks (`pg_try_advisory_xact_lock`) without interference from transaction-level connection poolers.

3. **Production Security Guardrails (SRS §12, NFR-010):**
   - In `production` and `staging` environments, `SECRET_KEY` must be at least 32 characters and cannot use placeholder values.
   - `get_sanitized_dict()` method guarantees that all secrets, keys, and connection passwords in URLs are redacted before logging or diagnostic export.

4. **External Services & Storage:**
   - Supabase Python SDK is scoped exclusively for Supabase Auth and Supabase Storage integrations.
   - All database CRUD operations bypass the Supabase REST client and execute directly through SQLAlchemy 2.x AsyncIO + asyncpg.

---

## Consequences

- Configuration errors fail fast at application startup before any socket or database connection is accepted.
- Seamless compatibility with 12-factor application methodology (Docker, Kubernetes, CI/CD pipelines).
- Guaranteed protection against accidental credential exposure in logs or telemetry traces.

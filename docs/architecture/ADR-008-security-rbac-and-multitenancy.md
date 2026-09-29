# ADR-008: Security Architecture — RBAC, Token Refresh & Multi-Tenancy

## Status
Accepted

## Context
A distributed task engine executes asynchronous workloads, processes sensitive payloads, and coordinates shared worker fleets across multiple tenants and projects. To satisfy SRS §2.1, §9, §12, and §13, the security architecture must support role-based access control (RBAC), multi-tenancy project isolation, token refresh lifecycles, and hot API key rotation without server restart.

## Decisions
1. **Role-Based Access Control (RBAC):**
   - Canonical roles defined in `src/security/rbac.py`: `admin`, `developer`, `viewer`, `worker`.
   - Operations modifying queues, executing DLQ replays, or rotating credentials require `admin` or `operator` privileges.
   - Read-only inspection endpoints require `viewer` privileges.

2. **Multi-Tenancy & Project Scoping:**
   - Strict project isolation: Principals scoped to `project_id` cannot query, submit, or cancel tasks belonging to other projects.
   - Any cross-tenant access attempt raises an explicit HTTP 403 Forbidden exception. Superadmins (`role="admin"`) retain global cluster administration capabilities.

3. **Authentication & Token Lifecycle:**
   - Dual-token model: Access tokens (short-lived, 30m default) and refresh tokens (long-lived, 7d default) with cryptographic separation (`type="access"` vs `type="refresh"`).
   - `/api/v1/auth/refresh` exchanges a valid refresh token for a fresh access token without re-entering credentials.

4. **Dynamic API Key Rotation:**
   - `/api/v1/auth/rotate-key` generates a fresh cryptographically secure salted SHA-256 API key and revokes old keys dynamically without requiring daemon or worker fleet restarts.

5. **Safe Serialization & Error Sanitization:**
   - Pydantic and standard JSON serialization used exclusively across all API payloads and broker messages. `pickle` is prohibited across the codebase.
   - Sensitive credentials and connection passwords are automatically redacted from error envelopes and log records.

## Consequences
- Guarantees strict multi-tenant isolation and security compliance.
- Simplifies operational credential management and rolling key rotations.

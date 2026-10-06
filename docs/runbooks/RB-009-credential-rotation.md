# Runbook RB-009: Zero-Downtime Credential Rotation

- **Runbook ID:** RB-009
- **Target Subsystem:** Security, Secrets Management, JWT & Database Authentication
- **Default Severity:** SEV-2 / Operational Maintenance
- **Relevant SRS Sections:** SRS §14 (Security Architecture & Key Lifecycle), SRS §22.1

---

## 1. Incident Overview & Purpose

This runbook defines the procedures for rotating critical credentials without interrupting in-flight tasks or terminating active user sessions.
Credentials covered:
1. **JWT Secret Key (`SECRET_KEY`)**
2. **Database Master Password (`DATABASE_URL`)**
3. **Redis Broker Password (`REDIS_URL`)**
4. **Project API Keys (`x-api-key`)**

---

## 2. JWT Secret Key Zero-Downtime Rotation

To rotate JWT signing keys without logging out active users, use a **Dual-Verification Window**:

### Step 1: Add New Key as Primary, Old Key as Fallback
In `.env` / Secrets Manager:
```bash
# Old: SECRET_KEY="previous-super-secret-key"
# New setup:
SECRET_KEY="newly-generated-cryptographic-key-minimum-32-chars"
SECRET_KEY_FALLBACK="previous-super-secret-key"
```

### Step 2: Rolling Restart of API Services
```bash
# Update API container with rolling restart
docker compose up -d --no-deps api
```
- **New tokens issued:** Signed with `SECRET_KEY`.
- **Existing tokens:** Verified against `SECRET_KEY`; if signature invalid, verified against `SECRET_KEY_FALLBACK`.

### Step 3: Deprecate Fallback Key
After the token expiration window (e.g., 24 hours), remove `SECRET_KEY_FALLBACK` and reload:
```bash
docker compose up -d --no-deps api
```

---

## 3. Database Password Zero-Downtime Rotation

### Step 1: Create Secondary Database User with Equal Privileges
```sql
CREATE USER task_engine_app_v2 WITH PASSWORD '<NEW_STRONG_PASSWORD>';
GRANT ALL PRIVILEGES ON DATABASE postgres TO task_engine_app_v2;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO task_engine_app_v2;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO task_engine_app_v2;
```

### Step 2: Update Connection String in Environment
Update `DATABASE_URL` in `.env`:
```env
DATABASE_URL=postgresql+asyncpg://task_engine_app_v2:<NEW_STRONG_PASSWORD>@postgres:5432/postgres
```

### Step 3: Rolling Restart of All Services
```bash
docker compose up -d --no-deps api
docker compose up -d --no-deps worker
docker compose up -d --no-deps scheduler
```

### Step 4: Revoke and Drop Old User
After 24 hours of monitoring and zero errors from old user:
```sql
DROP USER task_engine_app_old;
```

---

## 4. Project API Key Rotation (SRS §14.3)

Each tenant/project can rotate their API key via the REST API with a grace period:
```bash
curl -X POST "http://localhost:8000/api/v1/projects/{project_id}/api-keys/rotate" \
     -H "Authorization: Bearer $ADMIN_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "grace_period_seconds": 86400
     }'
```
*Result:* Returns new API key. Both old and new keys remain valid for 86,400 seconds (24 hours).

---

## 5. Verification Checklist
- [ ] API liveness and readiness probes pass: `curl -f http://localhost:8000/api/v1/health`
- [ ] Test task submission succeeds with new API key / token
- [ ] Worker processes continue heartbeating with new database credentials
- [ ] No `401 Unauthorized` or `InvalidTokenError` spikes in Grafana

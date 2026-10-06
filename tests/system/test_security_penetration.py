from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from jose import JWTError, jwt
from src.api.dependencies import enforce_tenant_access, get_current_principal
from src.api.main import create_app
from src.application.task_service import TaskLifecycleService
from src.core.config import get_settings
from src.core.constants import ApiAuthMode
from src.persistence.result_backend import ResultBackend
from src.security.jwt import create_access_token, decode_access_token
from src.security.principal import Principal
from src.security.rbac import check_project_access, enforce_project_access, enforce_role


def test_jwt_tampered_signature_denial() -> None:
    token = create_access_token("valid-user", claims={"role": "operator"})
    parts = token.split(".")
    tampered_sig = parts[2][:-4] + "AAAA" if len(parts[2]) >= 4 else "AAAA"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"
    with pytest.raises(JWTError):
        decode_access_token(tampered_token)


def test_jwt_forged_secret_denial() -> None:
    payload = {
        "sub": "attacker",
        "role": "admin",
        "iss": "task-engine",
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    forged_token = jwt.encode(payload, "completely-wrong-secret-key-12345", algorithm="HS256")
    with pytest.raises(JWTError):
        decode_access_token(forged_token)


def test_jwt_expired_token_denial() -> None:
    expired_token = create_access_token("expired-user", expires_delta=timedelta(seconds=-60))
    with pytest.raises(JWTError):
        decode_access_token(expired_token)


def test_jwt_wrong_issuer_denial() -> None:
    settings = get_settings()
    payload = {
        "sub": "valid-user",
        "iss": "fake-issuer-service",
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    invalid_issuer_token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    with pytest.raises(JWTError):
        decode_access_token(invalid_issuer_token)


def test_jwt_malformed_string_denial() -> None:
    with pytest.raises(JWTError):
        decode_access_token("not-a-valid-jwt-token-at-all")


def test_rbac_direct_enforcement_boundaries() -> None:
    viewer = Principal(principal_id="viewer-1", role="viewer", auth_mode=ApiAuthMode.JWT)
    operator = Principal(principal_id="op-1", role="operator", auth_mode=ApiAuthMode.JWT)
    admin = Principal(principal_id="admin-1", role="admin", auth_mode=ApiAuthMode.JWT)

    enforce_role(admin, ("admin",))
    enforce_role(admin, ("operator",))
    enforce_role(admin, ("viewer",))

    enforce_role(operator, ("operator", "admin"))
    with pytest.raises(HTTPException) as exc_op:
        enforce_role(operator, ("admin",))
    assert exc_op.value.status_code == 403

    enforce_role(viewer, ("viewer", "operator"))
    with pytest.raises(HTTPException) as exc_v1:
        enforce_role(viewer, ("operator", "admin"))
    assert exc_v1.value.status_code == 403

    with pytest.raises(HTTPException) as exc_v2:
        enforce_role(viewer, ("admin",))
    assert exc_v2.value.status_code == 403


def test_tenant_direct_isolation_boundaries() -> None:
    tenant_a_user = Principal(
        principal_id="usr-a",
        role="developer",
        tenant_id="tenant-alpha",
        auth_mode=ApiAuthMode.JWT,
    )
    assert check_project_access(tenant_a_user, "tenant-alpha") is True
    assert check_project_access(tenant_a_user, "tenant-beta") is False
    assert check_project_access(tenant_a_user, None) is False

    enforce_project_access(tenant_a_user, "tenant-alpha")
    enforce_tenant_access(tenant_a_user, "tenant-alpha")

    with pytest.raises(HTTPException) as exc_beta:
        enforce_tenant_access(tenant_a_user, "tenant-beta")
    assert exc_beta.value.status_code == 403

    admin_unscoped = Principal(
        principal_id="admin-all",
        role="admin",
        tenant_id=None,
        auth_mode=ApiAuthMode.JWT,
    )
    assert check_project_access(admin_unscoped, "tenant-alpha") is True
    assert check_project_access(admin_unscoped, "tenant-beta") is True
    enforce_tenant_access(admin_unscoped, "tenant-alpha")
    enforce_tenant_access(admin_unscoped, "tenant-beta")


@pytest.mark.asyncio
async def test_api_tampered_jwt_rejected_at_gateway() -> None:
    app = create_app()
    token = create_access_token("usr-test", claims={"role": "operator"})
    corrupted_token = token[:-5] + "ZZZZZ"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {corrupted_token}"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_api_expired_jwt_rejected_at_gateway() -> None:
    app = create_app()
    expired_token = create_access_token("usr-test", expires_delta=timedelta(seconds=-120))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get(
            "/api/v1/tasks",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res.status_code == 401


@pytest.mark.asyncio
async def test_api_rbac_viewer_prevented_from_cancelling_task() -> None:
    app = create_app()
    viewer_principal = Principal(
        principal_id="viewer-restricted",
        role="viewer",
        tenant_id="tenant-restricted",
        auth_mode=ApiAuthMode.JWT,
    )
    app.dependency_overrides[get_current_principal] = lambda: viewer_principal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.delete(f"/api/v1/tasks/{uuid4()}")
        assert res.status_code == 403
        data = res.json()
        assert "requires one of the following roles" in str(data) or "INSUFFICIENT" in str(data)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_rbac_viewer_prevented_from_creating_queue() -> None:
    app = create_app()
    viewer_principal = Principal(
        principal_id="viewer-restricted",
        role="viewer",
        tenant_id="tenant-restricted",
        auth_mode=ApiAuthMode.JWT,
    )
    app.dependency_overrides[get_current_principal] = lambda: viewer_principal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/v1/queues",
            json={"queue_name": "restricted-queue-create"},
        )
        assert res.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_rbac_operator_prevented_from_creating_project() -> None:
    app = create_app()
    op_principal = Principal(
        principal_id="op-standard",
        role="operator",
        tenant_id="tenant-op",
        auth_mode=ApiAuthMode.JWT,
    )
    app.dependency_overrides[get_current_principal] = lambda: op_principal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/v1/projects",
            json={"name": "Forbidden Project", "slug": f"forbid-{uuid4().hex[:6]}"},
        )
        assert res.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_cross_tenant_submission_isolation() -> None:
    app = create_app()
    tenant_a_principal = Principal(
        principal_id="tenant-a-user",
        role="operator",
        tenant_id="tenant-alpha",
        auth_mode=ApiAuthMode.JWT,
    )
    app.dependency_overrides[get_current_principal] = lambda: tenant_a_principal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "some_task",
                "queue": "default",
                "tenant_id": "tenant-beta",
                "payload": {"key": "val"},
            },
        )
        assert res.status_code == 403
        assert "Cross-tenant submission forbidden" in str(res.json())
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_cross_tenant_query_isolation() -> None:
    app = create_app()
    tenant_a_principal = Principal(
        principal_id="tenant-a-user",
        role="operator",
        tenant_id="tenant-alpha",
        auth_mode=ApiAuthMode.JWT,
    )
    app.dependency_overrides[get_current_principal] = lambda: tenant_a_principal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get(
            "/api/v1/tasks",
            params={"tenant_id": "tenant-beta"},
        )
        assert res.status_code == 403
        assert "Cross-tenant access forbidden" in str(res.json())
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_payload_boundary_large_payload_handling() -> None:
    backend = ResultBackend(size_threshold_bytes=1024)
    small_data = {"key": "short_value"}
    stored_inline, ref = await backend.store_result(uuid4(), small_data)
    assert stored_inline == small_data
    assert ref is None

    large_data = {"chunk": "X" * 2048}
    stored_large, ref_large = await backend.store_result(uuid4(), large_data)
    assert stored_large == large_data or ref_large is not None


@pytest.mark.asyncio
async def test_payload_boundary_oversized_task_submission() -> None:
    service = TaskLifecycleService()
    huge_payload = {"data": "A" * 70000}
    task = await service.submit_task(
        task_type="oversized_payload_test",
        payload=huge_payload,
        queue="default",
        tenant_id="tenant-sec-test",
    )
    assert task.task_id is not None
    assert task.tenant_id == "tenant-sec-test"

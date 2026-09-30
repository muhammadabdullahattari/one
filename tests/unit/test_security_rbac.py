import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from src.api.dependencies import get_current_principal
from src.api.main import create_app
from src.core.constants import ApiAuthMode
from src.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.security.principal import Principal
from src.security.rbac import (
    check_project_access,
    enforce_project_access,
    enforce_role,
)


def test_rbac_role_enforcement() -> None:
    admin_principal = Principal(
        principal_id="p-admin",
        role="admin",
        auth_mode=ApiAuthMode.JWT,
    )
    enforce_role(admin_principal, ("admin", "developer"))

    viewer_principal = Principal(
        principal_id="p-viewer",
        role="viewer",
        auth_mode=ApiAuthMode.JWT,
    )
    with pytest.raises(HTTPException) as exc_info:
        enforce_role(viewer_principal, ("admin", "developer"))
    assert exc_info.value.status_code == 403


def test_cross_tenant_project_isolation() -> None:
    tenant_a_user = Principal(
        principal_id="usr-1",
        tenant_id="project-alpha",
        role="developer",
        auth_mode=ApiAuthMode.JWT,
    )
    assert check_project_access(tenant_a_user, "project-alpha") is True
    assert check_project_access(tenant_a_user, "project-beta") is False

    with pytest.raises(HTTPException) as exc_info:
        enforce_project_access(tenant_a_user, "project-beta")
    assert exc_info.value.status_code == 403

    admin_user = Principal(
        principal_id="usr-admin",
        role="admin",
        auth_mode=ApiAuthMode.JWT,
    )
    assert check_project_access(admin_user, "project-beta") is True


def test_refresh_token_generation_and_validation() -> None:
    tok = create_refresh_token("usr-123", claims={"role": "operator"})
    assert tok is not None
    payload = decode_refresh_token(tok)
    assert payload["sub"] == "usr-123"
    assert payload["role"] == "operator"
    assert payload["type"] == "refresh"

    access_tok = create_access_token("usr-123", claims={"role": "operator"})
    with pytest.raises(ValueError):
        decode_refresh_token(access_tok)


@pytest.mark.asyncio
async def test_auth_login_and_refresh_flow() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        ref_tok = data["refresh_token"]

        ref_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": ref_tok},
        )
        assert ref_res.status_code == 200
        new_data = ref_res.json()
        assert "access_token" in new_data
        assert new_data["user_id"] == data["user_id"]


@pytest.mark.asyncio
async def test_api_key_rotation_and_cross_tenant_denial() -> None:
    app = create_app()

    admin_principal = Principal(
        principal_id="usr-admin",
        role="admin",
        tenant_id="proj-100",
        auth_mode=ApiAuthMode.JWT,
    )
    app.dependency_overrides[get_current_principal] = lambda: admin_principal

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        rot_res = await client.post(
            "/api/v1/auth/rotate-key",
            json={"project_id": "proj-100", "old_key_id": "key-old-1"},
        )
        assert rot_res.status_code == 200
        data = rot_res.json()
        assert data["project_id"] == "proj-100"
        assert data["new_api_key"].startswith("te_live_")
        assert data["revoked_key_id"] == "key-old-1"

        tenant_principal = Principal(
            principal_id="usr-tenant-2",
            role="developer",
            tenant_id="proj-200",
            auth_mode=ApiAuthMode.JWT,
        )
        app.dependency_overrides[get_current_principal] = lambda: tenant_principal

        cross_res = await client.post(
            "/api/v1/auth/rotate-key",
            json={"project_id": "proj-100", "old_key_id": "key-old-1"},
        )
        assert cross_res.status_code == 403
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cookie_auth_and_silent_refresh_flow() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert login_res.status_code == 200
        assert "te_access_token" in login_res.cookies
        assert "te_refresh_token" in login_res.cookies
        assert "te_session_id" in login_res.cookies

        me_res = await client.get("/api/v1/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["role"] == "admin"

        refresh_res = await client.post("/api/v1/auth/refresh", json={})
        assert refresh_res.status_code == 200
        assert "access_token" in refresh_res.json()

        logout_res = await client.post("/api/v1/auth/logout")
        assert logout_res.status_code == 200

        after_logout_refresh = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": login_res.json()["refresh_token"]},
        )
        assert after_logout_refresh.status_code == 401


@pytest.mark.asyncio
async def test_logout_all_devices_flow() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login1 = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert login1.status_code == 200
        tok1 = login1.json()["refresh_token"]

        login2 = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "adminpassword123"},
        )
        assert login2.status_code == 200
        tok2 = login2.json()["refresh_token"]
        access_tok2 = login2.json()["access_token"]

        logout_all = await client.post(
            "/api/v1/auth/logout-all-devices",
            headers={"Authorization": f"Bearer {access_tok2}"},
        )
        assert logout_all.status_code == 200

        ref1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": tok1})
        assert ref1.status_code == 401

        ref2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": tok2})
        assert ref2.status_code == 401

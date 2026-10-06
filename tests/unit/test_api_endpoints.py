from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import create_app
from src.core.constants import HttpHeader


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def test_openapi_specification_contract(client: AsyncClient) -> None:
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    data = res.json()
    assert data["info"]["title"] == "Task Engine API"
    assert "components" in data
    assert "securitySchemes" in data["components"]
    assert "BearerAuth" in data["components"]["securitySchemes"]
    assert "ApiKeyAuth" in data["components"]["securitySchemes"]
    paths = data["paths"]
    assert "/api/v1/tasks" in paths
    assert "/api/v1/queues" in paths
    assert "/api/v1/workers" in paths
    assert "/api/v1/schedules" in paths
    assert "/api/v1/dlq" in paths
    assert "/api/v1/analytics/throughput" in paths
    assert "/api/v1/analytics/oldest-task-age" in paths
    assert "/api/v1/brokers" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/metrics" in paths


async def test_liveness_probe(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data
    assert HttpHeader.REQUEST_ID.value in res.headers
    assert HttpHeader.TRACE_ID.value in res.headers


async def test_prometheus_metrics_scrape_endpoint(client: AsyncClient) -> None:
    res = await client.get("/api/v1/metrics")
    assert res.status_code == 200
    assert "text/plain" in res.headers.get("content-type", "")


async def test_auth_login_and_me_lifecycle(client: AsyncClient) -> None:
    login_res = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "adminpassword123"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" not in token_data
    assert "refresh_token" not in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["role"] == "admin"
    assert "te_access_token" in login_res.cookies
    assert "te_refresh_token" in login_res.cookies

    me_res = await client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["role"] == "admin"
    assert me_data["principal_id"] == token_data["user_id"]

    cookie_token = login_res.cookies["te_access_token"]
    me_res_hdr = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {cookie_token}"}
    )
    assert me_res_hdr.status_code == 200

    refresh_res = await client.post("/api/v1/auth/refresh")
    assert refresh_res.status_code == 200
    ref_data = refresh_res.json()
    assert "access_token" not in ref_data
    assert "refresh_token" not in ref_data
    assert ref_data["user_id"] == token_data["user_id"]
    assert "te_access_token" in refresh_res.cookies


async def test_auth_invalid_credentials(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong_password"}
    )
    assert res.status_code == 401
    err = res.json()
    assert "error" in err
    assert err["error"]["code"] == "UNAUTHORIZED"


async def test_projects_and_api_keys_crud(client: AsyncClient) -> None:
    slug = f"test-tenant-{uuid4().hex[:6]}"
    proj_res = await client.post(
        "/api/v1/projects",
        json={"name": "Test Organization", "slug": slug, "description": "Tenant for testing"},
    )
    assert proj_res.status_code == 201
    project = proj_res.json()
    project_id = project["project_id"]
    assert project["slug"] == slug
    key_res = await client.post(
        f"/api/v1/projects/{project_id}/api-keys",
        json={"name": "Production Ingestion Key", "role": "operator", "scopes": ["tasks:write"]},
    )
    assert key_res.status_code == 201
    key_data = key_res.json()
    assert "plain_key" in key_data
    assert key_data["plain_key"].startswith("te_live_")
    assert "key_prefix" in key_data
    list_keys_res = await client.get(f"/api/v1/projects/{project_id}/api-keys")
    assert list_keys_res.status_code == 200
    keys_list = list_keys_res.json()
    assert keys_list["total"] >= 1
    assert "plain_key" not in keys_list["items"][0]


async def test_queues_list_and_create(client: AsyncClient) -> None:
    q_name = f"test-api-q-{uuid4().hex[:6]}"
    create_res = await client.post(
        "/api/v1/queues",
        json={
            "queue_name": q_name,
            "default_priority": 7,
            "max_concurrency": 25,
            "rate_limit_rps": 150,
            "broker_backend": "native",
        },
    )
    assert create_res.status_code == 201
    q = create_res.json()
    assert q["queue_name"] == q_name
    assert q["default_priority"] == 7
    assert q["max_concurrency"] == 25
    depth_res = await client.get(f"/api/v1/queues/{q_name}/depth")
    assert depth_res.status_code == 200
    depth_data = depth_res.json()
    assert depth_data["queue_name"] == q_name
    assert depth_data["depth"] == 0


async def test_queue_update_and_broker_backend_validation(client: AsyncClient) -> None:
    q_name = f"test-update-q-{uuid4().hex[:6]}"
    create_res = await client.post(
        "/api/v1/queues",
        json={
            "queue_name": q_name,
            "default_priority": 5,
            "max_concurrency": 50,
            "rate_limit_rps": 100,
            "broker_backend": "",
        },
    )
    assert create_res.status_code == 201
    assert create_res.json()["broker_backend"] == "native"

    update_res = await client.put(
        f"/api/v1/queues/{q_name}",
        json={
            "enabled": True,
            "default_priority": 2,
            "max_concurrency": 30,
            "rate_limit_rps": 60,
            "broker_backend": "",
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["default_priority"] == 2
    assert updated["broker_backend"] == "native"

    update_redis = await client.put(
        f"/api/v1/queues/{q_name}",
        json={"broker_backend": "redis"},
    )
    assert update_redis.status_code == 200
    assert update_redis.json()["broker_backend"] == "redis"

    update_invalid = await client.put(
        f"/api/v1/queues/{q_name}",
        json={"broker_backend": "unknown_broker"},
    )
    assert update_invalid.status_code == 400
    assert "not registered or supported" in update_invalid.json()["error"]["message"]

    create_invalid = await client.post(
        "/api/v1/queues",
        json={
            "queue_name": f"test-invalid-q-{uuid4().hex[:6]}",
            "broker_backend": "nonexistent_backend",
        },
    )
    assert create_invalid.status_code == 400
    assert "not registered or supported" in create_invalid.json()["error"]["message"]


async def test_queue_deletion_and_task_reference_handling(client: AsyncClient) -> None:
    del_default = await client.delete("/api/v1/queues/default")
    assert del_default.status_code == 400
    assert "default system queue cannot be deleted" in del_default.json()["error"]["message"]

    del_404 = await client.delete("/api/v1/queues/nonexistent-queue-xyz")
    assert del_404.status_code == 404

    q_name = f"test-del-q-{uuid4().hex[:6]}"
    create_res = await client.post(
        "/api/v1/queues",
        json={"queue_name": q_name, "broker_backend": "native"},
    )
    assert create_res.status_code == 201

    task_res = await client.post(
        "/api/v1/tasks",
        json={"task_type": "test_del_task", "queue": q_name, "payload": {"foo": "bar"}},
    )
    assert task_res.status_code == 202
    task_id = task_res.json()["task_id"]

    cancel_res = await client.delete(f"/api/v1/tasks/{task_id}")
    assert cancel_res.status_code == 200

    del_conflict = await client.delete(f"/api/v1/queues/{q_name}")
    assert del_conflict.status_code == 409
    assert "completed task(s)" in del_conflict.json()["error"]["message"]

    del_force = await client.delete(f"/api/v1/queues/{q_name}?force=true")
    assert del_force.status_code == 204

    get_gone = await client.get(f"/api/v1/queues/{q_name}")
    assert get_gone.status_code == 404


async def test_workers_list(client: AsyncClient) -> None:
    res = await client.get("/api/v1/workers")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data


async def test_schedules_crud(client: AsyncClient) -> None:
    sched_res = await client.post(
        "/api/v1/schedules",
        json={
            "task_type": "backup_database",
            "queue": "default",
            "cron": "0 2 * * *",
            "timezone": "UTC",
            "misfire_policy": "coalescing",
            "enabled": True,
        },
    )
    assert sched_res.status_code == 201
    sched_data = sched_res.json()
    assert sched_data["cron"] == "0 2 * * *"
    assert sched_data["misfire_policy"] == "coalescing"
    assert sched_data["next_run_at"] is not None
    sched_id = sched_data["schedule_id"]
    get_res = await client.get(f"/api/v1/schedules/{sched_id}")
    assert get_res.status_code == 200
    assert get_res.json()["schedule_id"] == sched_id


async def test_analytics_endpoints_contract(client: AsyncClient) -> None:
    t_res = await client.get("/api/v1/analytics/throughput?hours=12")
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert "points" in t_data
    assert "current_incoming_tps" in t_data
    assert "current_outgoing_tps" in t_data
    s_res = await client.get("/api/v1/analytics/status-distribution")
    assert s_res.status_code == 200
    s_data = s_res.json()
    assert "distribution" in s_data
    assert "total_tasks" in s_data
    l_res = await client.get("/api/v1/analytics/latency")
    assert l_res.status_code == 200
    l_data = l_res.json()
    assert "queue_wait" in l_data
    assert "execution_duration" in l_data
    assert "p50_ms" in l_data["queue_wait"]
    w_res = await client.get("/api/v1/analytics/worker-utilization")
    assert w_res.status_code == 200
    w_data = w_res.json()
    assert "workers" in w_data
    assert "average_utilization_percent" in w_data
    tt_res = await client.get("/api/v1/analytics/task-types")
    assert tt_res.status_code == 200
    assert "stats" in tt_res.json()
    qd_res = await client.get("/api/v1/analytics/queue-depth")
    assert qd_res.status_code == 200
    assert "queues" in qd_res.json()
    old_res = await client.get("/api/v1/analytics/oldest-task-age")
    assert old_res.status_code == 200
    assert "queues" in old_res.json()
    b_res = await client.get("/api/v1/brokers")
    assert b_res.status_code == 200
    b_data = b_res.json()
    assert len(b_data) >= 1
    bs_res = await client.get("/api/v1/brokers/native/stats")
    assert bs_res.status_code == 200
    bs_data = bs_res.json()
    assert bs_data["backend"] == "native"
    assert "published_count" in bs_data


async def test_validation_error_returns_standard_error_envelope(client: AsyncClient) -> None:
    res = await client.post("/api/v1/tasks", json={"priority": 99})
    assert res.status_code == 422
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "request_id" in data["error"]
    assert "timestamp" in data["error"]
    assert "details" in data["error"]


async def test_resource_not_found_returns_standard_error_envelope(client: AsyncClient) -> None:
    non_existent_id = uuid4()
    res = await client.get(f"/api/v1/tasks/{non_existent_id}")
    assert res.status_code == 404
    data = res.json()
    assert "error" in data
    assert data["error"]["code"] == "TASK_NOT_FOUND"

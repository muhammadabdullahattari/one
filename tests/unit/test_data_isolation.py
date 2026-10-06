from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import create_app
from src.core.constants import TaskStatus
from src.domain.entities import DLQEntry, Worker
from src.persistence.models.task import TaskModel
from src.persistence.repositories.dlq_repository import DLQRepository
from src.persistence.repositories.worker_repository import WorkerRepository
from src.persistence.session import session_scope
from src.security.jwt import create_access_token


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def token_tenant_a():
    return create_access_token("user-a", claims={"role": "operator", "tenant_id": "tenant-alpha"})


@pytest.fixture
def token_tenant_b():
    return create_access_token("user-b", claims={"role": "operator", "tenant_id": "tenant-beta"})


@pytest.fixture
def token_admin():
    return create_access_token("admin-user", claims={"role": "admin"})


@pytest.mark.asyncio
async def test_task_submission_and_query_tenant_isolation(
    app, token_tenant_a: str, token_tenant_b: str, token_admin: str
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        res_a = await client.post(
            "/api/v1/tasks",
            json={"task_type": "email.send", "payload": {"recipient": "a@example.com"}},
            headers=headers_a,
        )
        assert res_a.status_code == 202
        task_a = res_a.json()
        assert task_a["tenant_id"] == "tenant-alpha"
        task_a_id = task_a["task_id"]

        res_b = await client.post(
            "/api/v1/tasks",
            json={"task_type": "report.generate", "payload": {"report_id": 42}},
            headers=headers_b,
        )
        assert res_b.status_code == 202
        task_b = res_b.json()
        assert task_b["tenant_id"] == "tenant-beta"
        task_b_id = task_b["task_id"]

        list_a = await client.get("/api/v1/tasks", headers=headers_a)
        assert list_a.status_code == 200
        items_a = list_a.json()["items"]
        a_ids = [t["task_id"] for t in items_a]
        assert task_a_id in a_ids
        assert task_b_id not in a_ids

        list_b = await client.get("/api/v1/tasks", headers=headers_b)
        assert list_b.status_code == 200
        items_b = list_b.json()["items"]
        b_ids = [t["task_id"] for t in items_b]
        assert task_b_id in b_ids
        assert task_a_id not in b_ids

        list_admin = await client.get("/api/v1/tasks?limit=500", headers=headers_admin)
        assert list_admin.status_code == 200
        admin_ids = [t["task_id"] for t in list_admin.json()["items"]]
        assert task_a_id in admin_ids
        assert task_b_id in admin_ids


@pytest.mark.asyncio
async def test_task_cross_tenant_access_forbidden(
    app, token_tenant_a: str, token_tenant_b: str
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}

        res_b = await client.post(
            "/api/v1/tasks",
            json={"task_type": "payment.process", "payload": {"amount": 100}},
            headers=headers_b,
        )
        assert res_b.status_code == 202
        task_b_id = res_b.json()["task_id"]

        get_res = await client.get(f"/api/v1/tasks/{task_b_id}", headers=headers_a)
        assert get_res.status_code == 403

        cancel_res = await client.delete(f"/api/v1/tasks/{task_b_id}", headers=headers_a)
        assert cancel_res.status_code == 403

        retry_res = await client.post(f"/api/v1/tasks/{task_b_id}/retry", headers=headers_a)
        assert retry_res.status_code == 403

        attempts_res = await client.get(f"/api/v1/tasks/{task_b_id}/attempts", headers=headers_a)
        assert attempts_res.status_code == 403

        events_res = await client.get(f"/api/v1/tasks/{task_b_id}/events", headers=headers_a)
        assert events_res.status_code == 403

        spoof_res = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "email.send",
                "payload": {},
                "tenant_id": "tenant-beta",
            },
            headers=headers_a,
        )
        assert spoof_res.status_code == 403

        query_spoof_res = await client.get("/api/v1/tasks?tenant_id=tenant-beta", headers=headers_a)
        assert query_spoof_res.status_code == 403


@pytest.mark.asyncio
async def test_schedule_tenant_isolation(
    app, token_tenant_a: str, token_tenant_b: str, token_admin: str
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        create_a = await client.post(
            "/api/v1/schedules",
            json={"task_type": "cron.cleanup", "cron": "0 0 * * *"},
            headers=headers_a,
        )
        assert create_a.status_code == 201
        sched_a = create_a.json()
        assert sched_a["tenant_id"] == "tenant-alpha"
        sched_a_id = sched_a["schedule_id"]

        create_b = await client.post(
            "/api/v1/schedules",
            json={"task_type": "cron.sync", "cron": "*/15 * * * *"},
            headers=headers_b,
        )
        assert create_b.status_code == 201
        sched_b = create_b.json()
        assert sched_b["tenant_id"] == "tenant-beta"
        sched_b_id = sched_b["schedule_id"]

        list_a = await client.get("/api/v1/schedules", headers=headers_a)
        assert list_a.status_code == 200
        a_ids = [s["schedule_id"] for s in list_a.json()["items"]]
        assert sched_a_id in a_ids
        assert sched_b_id not in a_ids

        get_b = await client.get(f"/api/v1/schedules/{sched_b_id}", headers=headers_a)
        assert get_b.status_code == 403

        put_b = await client.put(
            f"/api/v1/schedules/{sched_b_id}", json={"enabled": False}, headers=headers_a
        )
        assert put_b.status_code == 403

        trig_b = await client.post(f"/api/v1/schedules/{sched_b_id}/trigger", headers=headers_a)
        assert trig_b.status_code == 403

        del_b = await client.delete(f"/api/v1/schedules/{sched_b_id}", headers=headers_a)
        assert del_b.status_code == 403

        spoof_sched = await client.post(
            "/api/v1/schedules",
            json={"task_type": "cron.fake", "cron": "0 1 * * *", "tenant_id": "tenant-beta"},
            headers=headers_a,
        )
        assert spoof_sched.status_code == 403

        del_res = await client.delete(f"/api/v1/schedules/{sched_b_id}", headers=headers_admin)
        assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_dlq_tenant_isolation(app, token_tenant_a: str, token_tenant_b: str) -> None:
    task_a_id = uuid4()
    task_b_id = uuid4()
    dlq_a_id = uuid4()
    dlq_b_id = uuid4()
    now = datetime.now(UTC)

    async with session_scope() as session:
        task_a_model = TaskModel(
            task_id=task_a_id,
            tenant_id="tenant-alpha",
            task_type="test.fail",
            queue="default",
            status=TaskStatus.DEAD.value,
            created_at=now,
            updated_at=now,
        )
        task_b_model = TaskModel(
            task_id=task_b_id,
            tenant_id="tenant-beta",
            task_type="test.fail",
            queue="default",
            status=TaskStatus.DEAD.value,
            created_at=now,
            updated_at=now,
        )
        session.add_all([task_a_model, task_b_model])
        await session.flush()

        dlq_repo = DLQRepository(session)
        await dlq_repo.create_entry(
            DLQEntry(
                dlq_id=dlq_a_id,
                task_id=task_a_id,
                tenant_id="tenant-alpha",
                reason="MAX_RETRIES_EXCEEDED",
                error_class="RuntimeError",
                dead_at=now,
            )
        )
        await dlq_repo.create_entry(
            DLQEntry(
                dlq_id=dlq_b_id,
                task_id=task_b_id,
                tenant_id="tenant-beta",
                reason="FATAL_ERROR",
                error_class="ValueError",
                dead_at=now,
            )
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}

        list_a = await client.get("/api/v1/dlq", headers=headers_a)
        assert list_a.status_code == 200
        dlq_items = list_a.json()["items"]
        item_ids = [d["dlq_id"] for d in dlq_items]
        assert str(dlq_a_id) in item_ids
        assert str(dlq_b_id) not in item_ids

        list_b = await client.get("/api/v1/dlq", headers=headers_b)
        assert list_b.status_code == 200
        dlq_items_b = list_b.json()["items"]
        item_ids_b = [d["dlq_id"] for d in dlq_items_b]
        assert str(dlq_b_id) in item_ids_b
        assert str(dlq_a_id) not in item_ids_b

        get_b = await client.get(f"/api/v1/dlq/{dlq_b_id}", headers=headers_a)
        assert get_b.status_code == 403

        replay_b = await client.post(f"/api/v1/dlq/{dlq_b_id}/replay", headers=headers_a)
        assert replay_b.status_code == 403

        del_b = await client.delete(f"/api/v1/dlq/{dlq_b_id}", headers=headers_a)
        assert del_b.status_code == 403


@pytest.mark.asyncio
async def test_analytics_and_queue_depth_tenant_isolation(
    app, token_tenant_a: str, token_tenant_b: str
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}

        await client.post(
            "/api/v1/tasks",
            json={"task_type": "analytics.test.a", "payload": {}},
            headers=headers_a,
        )
        await client.post(
            "/api/v1/tasks",
            json={"task_type": "analytics.test.b", "payload": {}},
            headers=headers_b,
        )

        dist_a = await client.get("/api/v1/analytics/status-distribution", headers=headers_a)
        assert dist_a.status_code == 200

        task_types_a = await client.get("/api/v1/analytics/task-types", headers=headers_a)
        assert task_types_a.status_code == 200
        types_a = [s["task_type"] for s in task_types_a.json()["stats"]]
        assert "analytics.test.a" in types_a
        assert "analytics.test.b" not in types_a

        depth_a = await client.get("/api/v1/queues/default/depth", headers=headers_a)
        assert depth_a.status_code == 200
        assert depth_a.json()["queue_name"] == "default"


@pytest.mark.asyncio
async def test_queue_tenant_isolation(
    app, token_tenant_a: str, token_tenant_b: str, token_admin: str
) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        q_a_name = f"queue-alpha-{uuid4().hex[:6]}"
        q_b_name = f"queue-beta-{uuid4().hex[:6]}"

        res_a = await client.post(
            "/api/v1/queues",
            json={"queue_name": q_a_name, "default_priority": 5},
            headers=headers_a,
        )
        assert res_a.status_code == 201
        assert res_a.json()["tenant_id"] == "tenant-alpha"

        res_b = await client.post(
            "/api/v1/queues",
            json={"queue_name": q_b_name, "default_priority": 3},
            headers=headers_b,
        )
        assert res_b.status_code == 201
        assert res_b.json()["tenant_id"] == "tenant-beta"

        list_a = await client.get("/api/v1/queues", headers=headers_a)
        assert list_a.status_code == 200
        q_names_a = [q["queue_name"] for q in list_a.json()["items"]]
        assert q_a_name in q_names_a
        assert q_b_name not in q_names_a

        list_b = await client.get("/api/v1/queues", headers=headers_b)
        assert list_b.status_code == 200
        q_names_b = [q["queue_name"] for q in list_b.json()["items"]]
        assert q_b_name in q_names_b
        assert q_a_name not in q_names_b

        get_b = await client.get(f"/api/v1/queues/{q_b_name}", headers=headers_a)
        assert get_b.status_code == 404

        put_b = await client.put(
            f"/api/v1/queues/{q_b_name}", json={"max_concurrency": 10}, headers=headers_a
        )
        assert put_b.status_code == 404

        del_b = await client.delete(f"/api/v1/queues/{q_b_name}", headers=headers_a)
        assert del_b.status_code in (403, 404)

        list_admin = await client.get("/api/v1/queues", headers=headers_admin)
        assert list_admin.status_code == 200
        admin_names = [q["queue_name"] for q in list_admin.json()["items"]]
        assert q_a_name in admin_names
        assert q_b_name in admin_names


@pytest.mark.asyncio
async def test_worker_tenant_isolation(
    app, token_tenant_a: str, token_tenant_b: str, token_admin: str
) -> None:
    worker_a_id = f"worker-a-{uuid4().hex[:6]}"
    worker_b_id = f"worker-b-{uuid4().hex[:6]}"

    async with session_scope() as session:
        worker_repo = WorkerRepository(session)
        await worker_repo.register_worker(
            Worker(
                worker_id=worker_a_id,
                tenant_id="tenant-alpha",
                hostname="host-a",
                process_id=1001,
            )
        )
        await worker_repo.register_worker(
            Worker(
                worker_id=worker_b_id,
                tenant_id="tenant-beta",
                hostname="host-b",
                process_id=1002,
            )
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}
        headers_admin = {"Authorization": f"Bearer {token_admin}"}

        list_a = await client.get("/api/v1/workers", headers=headers_a)
        assert list_a.status_code == 200
        w_ids_a = [w["worker_id"] for w in list_a.json()["items"]]
        assert worker_a_id in w_ids_a
        assert worker_b_id not in w_ids_a

        list_b = await client.get("/api/v1/workers", headers=headers_b)
        assert list_b.status_code == 200
        w_ids_b = [w["worker_id"] for w in list_b.json()["items"]]
        assert worker_b_id in w_ids_b
        assert worker_a_id not in w_ids_b

        get_b = await client.get(f"/api/v1/workers/{worker_b_id}", headers=headers_a)
        assert get_b.status_code == 404

        drain_b = await client.post(f"/api/v1/workers/{worker_b_id}/drain", headers=headers_a)
        assert drain_b.status_code == 404

        list_admin = await client.get("/api/v1/workers", headers=headers_admin)
        assert list_admin.status_code == 200
        admin_w_ids = [w["worker_id"] for w in list_admin.json()["items"]]
        assert worker_a_id in admin_w_ids
        assert worker_b_id in admin_w_ids


@pytest.mark.asyncio
async def test_registration_auto_assigns_isolated_tenant(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        username = f"user_{uuid4().hex[:8]}"
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "Password123!",
                "role": "operator",
            },
        )
        assert reg_res.status_code == 201
        data = reg_res.json()
        assert data["tenant_id"] == username.lower()
        assert data["tenant_id"] != "default"

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": "Password123!"},
        )
        assert login_res.status_code == 200
        assert "access_token" not in login_res.json()
        assert "refresh_token" not in login_res.json()
        assert login_res.json()["tenant_id"] == username.lower()
        assert "te_access_token" in login_res.cookies
        token = login_res.cookies["te_access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["tenant_id"] == username.lower()

        tasks_res = await client.get("/api/v1/tasks", headers=headers)
        assert tasks_res.status_code == 200
        assert len(tasks_res.json()["items"]) == 0

        queues_res = await client.get("/api/v1/queues", headers=headers)
        assert queues_res.status_code == 200
        assert len(queues_res.json()["items"]) == 0

        workers_res = await client.get("/api/v1/workers", headers=headers)
        assert workers_res.status_code == 200
        assert len(workers_res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_worker_task_claiming_celery_style_isolation(app, token_tenant_a: str) -> None:
    """Verify that a worker scoped to tenant-beta CANNOT claim tasks submitted by tenant-alpha,
    just like Celery workers only execute tasks belonging to their own application/project."""
    from src.broker.native.adapter import NativeBrokerAdapter

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}

        q_name = f"claim-q-{uuid4().hex[:6]}"
        create_q = await client.post(
            "/api/v1/queues",
            json={"queue_name": q_name},
            headers=headers_a,
        )
        assert create_q.status_code == 201

        submit_res = await client.post(
            "/api/v1/tasks",
            json={"task_type": "email.send", "queue": q_name, "payload": {"foo": "bar"}},
            headers=headers_a,
        )
        assert submit_res.status_code == 202
        task_id = submit_res.json()["task_id"]

        native_broker = NativeBrokerAdapter()
        messages_b = await native_broker.consume(
            queue=q_name, worker_id="worker-beta-1", batch_size=5, tenant_id="tenant-beta"
        )
        claimed_ids_b = [m.message_id for m in messages_b]
        assert task_id not in claimed_ids_b
        assert len(messages_b) == 0

        messages_a = await native_broker.consume(
            queue=q_name, worker_id="worker-alpha-1", batch_size=5, tenant_id="tenant-alpha"
        )
        claimed_ids_a = [m.message_id for m in messages_a]
        assert task_id in claimed_ids_a
        assert messages_a[0].envelope.tenant_id == "tenant-alpha"


@pytest.mark.asyncio
async def test_task_submission_auto_provisions_queue_with_tenant_isolation(
    app, token_tenant_a: str, token_tenant_b: str
) -> None:
    """Verify that submitting to a new/ad-hoc queue auto-provisions it for the caller's tenant
    without foreign key violations, and prevents cross-tenant submission to that queue."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        headers_a = {"Authorization": f"Bearer {token_tenant_a}"}
        headers_b = {"Authorization": f"Bearer {token_tenant_b}"}

        adhoc_q = f"adhoc-q-{uuid4().hex[:6]}"

        sub_a = await client.post(
            "/api/v1/tasks",
            json={"task_type": "order.process", "queue": adhoc_q, "payload": {"amount": 100}},
            headers=headers_a,
        )
        assert sub_a.status_code == 202
        task_data = sub_a.json()
        assert task_data["queue"] == adhoc_q
        assert task_data["tenant_id"] == "tenant-alpha"

        q_get = await client.get(f"/api/v1/queues/{adhoc_q}", headers=headers_a)
        assert q_get.status_code == 200
        assert q_get.json()["queue_name"] == adhoc_q
        assert q_get.json()["tenant_id"] == "tenant-alpha"

        list_b = await client.get("/api/v1/queues", headers=headers_b)
        assert list_b.status_code == 200
        q_names_b = [q["queue_name"] for q in list_b.json()["items"]]
        assert adhoc_q not in q_names_b

        sub_b_forbidden = await client.post(
            "/api/v1/tasks",
            json={"task_type": "order.process", "queue": adhoc_q, "payload": {"amount": 50}},
            headers=headers_b,
        )
        assert sub_b_forbidden.status_code == 403
        assert "belongs to tenant 'tenant-alpha'" in sub_b_forbidden.json()["error"]["message"]

        sub_b_default = await client.post(
            "/api/v1/tasks",
            json={"task_type": "order.process", "queue": "default", "payload": {"amount": 25}},
            headers=headers_b,
        )
        assert sub_b_default.status_code == 202
        assert sub_b_default.json()["tenant_id"] == "tenant-beta"

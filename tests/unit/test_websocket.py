import pytest
from fastapi.testclient import TestClient
from src.api.main import create_app
from src.api.routers.ws import ws_manager
from src.security.jwt import create_access_token


@pytest.fixture
def sync_client():
    app = create_app()
    with TestClient(app) as client:
        yield client


def test_websocket_connection_ack_and_default_tenant(sync_client: TestClient) -> None:
    with sync_client.websocket_connect("/ws/live") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection.ack"
        assert ack["channel"] == "live"
        assert ack["tenant_id"] == "default"


def test_websocket_query_tenant_id(sync_client: TestClient) -> None:
    with sync_client.websocket_connect("/ws/tasks?tenant_id=tenant-xyz") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection.ack"
        assert ack["channel"] == "tasks"
        assert ack["tenant_id"] == "tenant-xyz"


def test_websocket_jwt_auth_cookie(sync_client: TestClient) -> None:
    token = create_access_token(
        subject="user-123", claims={"role": "admin", "tenant_id": "tenant-corp"}
    )
    sync_client.cookies.set("te_access_token", token)
    with sync_client.websocket_connect("/ws/metrics") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection.ack"
        assert ack["channel"] == "metrics"
        assert ack["tenant_id"] == "tenant-corp"


def test_websocket_heartbeat_text_ping_pong(sync_client: TestClient) -> None:
    with sync_client.websocket_connect("/ws/workers") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection.ack"

        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"


def test_websocket_heartbeat_json_ping_pong(sync_client: TestClient) -> None:
    with sync_client.websocket_connect("/ws/queues") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection.ack"

        ws.send_json({"type": "ping"})
        response = ws.receive_json()
        assert response == {"type": "pong"}


@pytest.mark.asyncio
async def test_websocket_multi_tenant_isolation(sync_client: TestClient) -> None:
    with sync_client.websocket_connect("/ws/tasks?tenant_id=tenant-alpha") as ws_alpha:
        ack_alpha = ws_alpha.receive_json()
        assert ack_alpha["tenant_id"] == "tenant-alpha"

        with sync_client.websocket_connect("/ws/tasks?tenant_id=tenant-beta") as ws_beta:
            ack_beta = ws_beta.receive_json()
            assert ack_beta["tenant_id"] == "tenant-beta"

            msg = {
                "type": "task.created",
                "tenant_id": "tenant-alpha",
                "data": {"task_id": "alpha-task-001"},
            }
            await ws_manager.broadcast("tasks", msg)

            received = ws_alpha.receive_json()
            assert received["type"] == "task.created"
            assert received["tenant_id"] == "tenant-alpha"

            ws_beta.send_text("ping")
            beta_resp = ws_beta.receive_text()
            assert beta_resp == "pong"


def test_websocket_api_v1_prefix_compatibility(sync_client: TestClient) -> None:
    with sync_client.websocket_connect("/api/v1/ws/live") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection.ack"
        assert ack["channel"] == "live"


@pytest.mark.asyncio
async def test_websocket_global_admin_receives_cross_tenant_broadcast(
    sync_client: TestClient,
) -> None:
    admin_token = create_access_token(
        subject="admin-1", claims={"role": "admin", "tenant_id": "default"}
    )
    sync_client.cookies.set("te_access_token", admin_token)

    with sync_client.websocket_connect("/ws/live") as ws_admin:
        ack = ws_admin.receive_json()
        assert ack["channel"] == "live"

        msg = {
            "type": "task.created",
            "tenant_id": "tenant-custom-enterprise",
            "data": {"task_id": "enterprise-task-999"},
        }
        await ws_manager.broadcast("live", msg)

        received = ws_admin.receive_json()
        assert received["type"] == "task.created"
        assert received["tenant_id"] == "tenant-custom-enterprise"

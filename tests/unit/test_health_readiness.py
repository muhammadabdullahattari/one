from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.dependencies import get_redis_client
from src.api.main import create_app
from src.persistence.session import get_db_session


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.mark.asyncio
async def test_health_liveness(client: AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data


@pytest.mark.asyncio
async def test_health_readiness_healthy(client: AsyncClient, app) -> None:
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=None)
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_redis_client] = lambda: mock_redis

    res = await client.get("/api/v1/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["components"]["database"]["status"] == "healthy"
    assert data["components"]["redis"]["status"] == "healthy"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_readiness_db_failure_returns_503(client: AsyncClient, app) -> None:
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Database unreachable"))
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_redis_client] = lambda: mock_redis

    res = await client.get("/api/v1/health/ready")
    assert res.status_code == 503
    app.dependency_overrides.clear()

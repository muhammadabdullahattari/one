from collections.abc import AsyncGenerator

import pytest
from src.persistence.models.base import Base
from src.persistence.session import close_database_engine, get_engine


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def init_test_db() -> AsyncGenerator[None]:
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
async def cleanup_db_engine() -> AsyncGenerator[None]:
    yield
    await close_database_engine()

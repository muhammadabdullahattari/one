import os

os.environ["APP_ENV"] = "test"

from collections.abc import AsyncGenerator

import pytest
from src.core.config import get_settings
from src.persistence.session import close_database_engine

get_settings.cache_clear()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
async def cleanup_db_engine() -> AsyncGenerator[None]:
    yield
    await close_database_engine()

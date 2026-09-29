from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import get_settings

_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_async_engine() -> AsyncEngine:
    global _async_engine, _async_session_factory
    if _async_engine is None:
        settings = get_settings()
        engine_kwargs: dict[str, Any] = {
            "echo": False,
            "future": True,
            "pool_pre_ping": settings.db_pool_pre_ping,
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
            "pool_recycle": settings.db_pool_recycle,
        }
        _async_engine = create_async_engine(settings.database_url, **engine_kwargs)
        _async_session_factory = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    if _async_session_factory is None:
        get_async_engine()
        assert _async_session_factory is not None
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession]:
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession]:
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_database_engine() -> None:
    global _async_engine, _async_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None


get_engine = get_async_engine
get_db_session = get_async_session

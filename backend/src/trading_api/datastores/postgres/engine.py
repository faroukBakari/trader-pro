"""SQLAlchemy AsyncEngine factory for SQLModel integration.

[ARCHITECTURE] Wave 2B: Engine Management
Provides singleton pattern for engine/session factory to avoid
multiple connection pools in the same process.

Usage:
    session_factory = await AsyncEngineFactory.get_session_factory(url)
    async with session_factory() as session:
        result = await session.execute(select(User))
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    pass


class AsyncEngineFactory:
    """Singleton factory for async SQLAlchemy engine and session.

    Thread-safe via class-level attributes. Disposes old engine when
    URL changes, preventing connection pool leaks.
    """

    _engine: AsyncEngine | None = None
    _session_factory: async_sessionmaker[AsyncSession] | None = None
    _url: str | None = None

    @classmethod
    def _build_url(cls) -> str:
        """Build async database URL from environment."""
        dsn = os.environ.get("DATASTORE_POSTGRES_DSN")
        if dsn:
            # Convert postgresql:// to postgresql+psycopg://
            if dsn.startswith("postgresql://"):
                return dsn.replace("postgresql://", "postgresql+psycopg://", 1)
            return dsn

        user = os.environ.get("DATASTORE_POSTGRES_USER", "trader")
        password = os.environ.get("DATASTORE_POSTGRES_PASSWORD", "trader_dev")
        host = os.environ.get("DATASTORE_POSTGRES_HOST", "localhost")
        port = os.environ.get("DATASTORE_POSTGRES_PORT", "5433")
        db = os.environ.get("DATASTORE_POSTGRES_DB", "trader_bars")

        return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"

    @classmethod
    def _normalize_url(cls, url: str) -> str:
        """Ensure URL uses psycopg async driver."""
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        # Also handle legacy asyncpg URLs
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "+psycopg")
        return url

    @classmethod
    async def get_engine(cls, url: str | None = None) -> AsyncEngine:
        """Get or create async engine (singleton).

        Args:
            url: Database URL. If None, builds from environment.

        Returns:
            AsyncEngine instance (singleton per URL).
        """
        url = cls._normalize_url(url) if url else cls._build_url()

        if cls._engine is None or cls._url != url:
            if cls._engine is not None:
                await cls._engine.dispose()

            cls._engine = create_async_engine(
                url,
                echo=False,
                pool_size=5,
                max_overflow=10,
            )
            cls._url = url

        return cls._engine

    @classmethod
    async def get_session_factory(
        cls, url: str | None = None
    ) -> async_sessionmaker[AsyncSession]:
        """Get or create session factory (singleton).

        Args:
            url: Database URL. If None, builds from environment.

        Returns:
            Session factory for creating AsyncSession instances.
        """
        if cls._session_factory is None or (url and cls._url != url):
            engine = await cls.get_engine(url)
            cls._session_factory = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

        return cls._session_factory

    @classmethod
    async def dispose(cls) -> None:
        """Dispose engine and reset factory.

        Call this on application shutdown to cleanly close connections.
        Also useful in tests to reset state between test cases.
        """
        if cls._engine:
            await cls._engine.dispose()
            cls._engine = None
            cls._session_factory = None
            cls._url = None

"""SQLAlchemy AsyncEngine factory for SQLModel integration.

[ARCHITECTURE] Wave 2B: Engine Management
Provides singleton pattern for engine/session factory to avoid
multiple connection pools in the same process.

Configuration is centralized in Settings (config.py), which loads from .env.
This module delegates to settings.postgres_dsn for connection URL.

Usage:
    session_factory = await AsyncEngineFactory.get_session_factory(url)
    async with session_factory() as session:
        result = await session.execute(select(User))
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import psycopg
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from trading_api.models.exceptions import CommonException
from trading_api.shared.config import settings


class DatabaseNotFoundError(CommonException):
    """Raised when the configured database does not exist.

    Provides actionable remediation steps for the developer.
    """

    def __init__(self, db_name: str, host: str, port: int) -> None:
        message = (
            f"Database '{db_name}' does not exist on {host}:{port}.\n\n"
            f"To fix this, either:\n"
            f"  1. Recreate the Docker volume (loses data):\n"
            f"     make db-down && docker volume rm backend_postgres_data && make db-up\n\n"
            f"  2. Create the database manually (preserves existing data):\n"
            f"     docker-compose -f docker-compose.dev.yml exec postgres \\\n"
            f"       psql -U trader -d postgres -c 'CREATE DATABASE {db_name};'"
        )
        super().__init__(code="DATASTORE_DATABASE_NOT_FOUND", message=message)
        self.db_name = db_name
        self.host = host
        self.port = port


class ConnectionTimeoutError(CommonException):
    """Raised when database connection times out during startup.

    Indicates the database server may be down or unreachable.
    """

    def __init__(self, host: str, port: int, timeout: float) -> None:
        message = (
            f"Could not connect to PostgreSQL at {host}:{port} within {timeout}s.\n\n"
            f"Possible causes:\n"
            f"  1. Database server is not running:\n"
            f"     make db-up\n\n"
            f"  2. Wrong host/port configuration:\n"
            f"     Check DATASTORE_POSTGRES_HOST and DATASTORE_POSTGRES_PORT in .env"
        )
        super().__init__(code="DATASTORE_CONNECTION_TIMEOUT", message=message)
        self.host = host
        self.port = port
        self.timeout = timeout


def parse_dsn(dsn: str) -> tuple[str, str, str, int, str]:
    """Parse DSN into components: (user, password, host, port, dbname)."""
    # Strip driver suffix for parsing (e.g., postgresql+psycopg:// -> postgresql://)
    clean_dsn = re.sub(r"postgresql\+\w+://", "postgresql://", dsn)
    parsed = urlparse(clean_dsn)
    return (
        parsed.username or "trader",
        parsed.password or "",
        parsed.hostname or "localhost",
        parsed.port or 5432,
        parsed.path.lstrip("/") or "postgres",
    )


def check_database_exists(dsn: str) -> None:
    """Check if the target database exists, raise DatabaseNotFoundError if not.

    Connects to 'postgres' maintenance database to query pg_database.
    Uses synchronous psycopg for simplicity (one-time startup check).
    """

    user, password, host, port, db_name = parse_dsn(dsn)

    # Connect to maintenance database to check if target exists
    maintenance_dsn = f"postgresql://{user}:{password}@{host}:{port}/postgres"

    try:
        with psycopg.connect(maintenance_dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (db_name,),
                )
                if cur.fetchone() is None:
                    raise DatabaseNotFoundError(db_name, host, port)
    except psycopg.OperationalError:
        # Can't connect to maintenance DB - let the original connection attempt
        # fail with its own error (server down, auth failed, etc.)
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
        """Build async database URL from settings (which loads from .env)."""
        dsn = settings.postgres_dsn
        return cls._normalize_url(dsn)

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

        Raises:
            DatabaseNotFoundError: If the target database doesn't exist.
        """
        url = cls._normalize_url(url) if url else cls._build_url()

        if cls._engine is None or cls._url != url:
            if cls._engine is not None:
                await cls._engine.dispose()

            # Validate database exists before attempting connection
            check_database_exists(url)

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

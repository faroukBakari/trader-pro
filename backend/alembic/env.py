# backend/alembic/env.py
"""Alembic migration environment for async SQLModel.

[ARCHITECTURE] Wave 2B: SQLModel + Alembic integration
- Uses asyncpg driver for PostgreSQL
- Target metadata from SQLModel.metadata
- Environment-driven database URL
"""
import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from alembic import context
from trading_api.models.auth.token import RefreshTokenData  # table=True

# Import ALL table models to register metadata
# [CRITICAL]: Add new table models here as they're created
from trading_api.models.auth.user import User  # table=True

config = context.config

# Set sqlalchemy.url from environment
database_url = os.environ.get(
    "DATASTORE_POSTGRES_DSN",
    "postgresql+asyncpg://trader:trader_dev@localhost:5433/trader_pro",
)
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

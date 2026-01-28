"""SQLModel-based TableInterface implementation.

[ARCHITECTURE] Wave 2B: SQLModel Table
Replaces JSONB storage with typed columns using SQLModel ORM.
Used for tables with defined SQLModel classes (table=True).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import SQLModel

from trading_api.shared.datastore_interface import TableInterface

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

T = TypeVar("T", bound=SQLModel)


class SQLModelTable(TableInterface[T]):
    """TableInterface implementation using SQLModel + AsyncSession.

    Design:
    - Typed column storage (not JSONB)
    - Uses SQLModel class for schema definition
    - Supports upsert via PostgreSQL INSERT ... ON CONFLICT

    Usage:
        table = SQLModelTable(User, session_factory, primary_key="id")
        user = await table.get("user_123")
    """

    def __init__(
        self,
        model_class: type[T],
        session_factory: async_sessionmaker[AsyncSession],
        primary_key: str = "id",
    ) -> None:
        """Initialize SQLModelTable.

        Args:
            model_class: SQLModel class with table=True
            session_factory: Async session factory for database operations
            primary_key: Name of the primary key field
        """
        self._model = model_class
        self._session_factory = session_factory
        self._pk = primary_key
        self._pk_col = getattr(model_class, primary_key)

    async def get(self, key: str, index: str | None = None) -> T | None:
        """Get by primary key or indexed field."""
        async with self._session_factory() as session:
            if index is None:
                stmt = select(self._model).where(self._pk_col == key)
            else:
                idx_col = getattr(self._model, index)
                stmt = select(self._model).where(idx_col == key).limit(1)

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_all(self, key: str, index: str | None = None) -> list[T]:
        """Get all matching by primary key or indexed field."""
        async with self._session_factory() as session:
            if index is None:
                stmt = select(self._model).where(self._pk_col == key)
            else:
                idx_col = getattr(self._model, index)
                stmt = select(self._model).where(idx_col == key)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def set(self, key: str, value: BaseModel) -> None:
        """Upsert by key using INSERT ... ON CONFLICT."""
        async with self._session_factory() as session:
            # Ensure key is set on the model
            value_dict = value.model_dump()
            value_dict[self._pk] = key

            # PostgreSQL upsert
            stmt = pg_insert(self._model).values(**value_dict)
            stmt = stmt.on_conflict_do_update(
                index_elements=[self._pk],
                set_={k: v for k, v in value_dict.items() if k != self._pk},
            )

            await session.execute(stmt)
            await session.commit()

    async def delete(self, key: str, index: str | None = None) -> bool:
        """Delete by primary key or indexed field."""
        async with self._session_factory() as session:
            if index is None:
                stmt = delete(self._model).where(self._pk_col == key)
            else:
                idx_col = getattr(self._model, index)
                stmt = delete(self._model).where(idx_col == key)

            result = await session.execute(stmt)
            await session.commit()
            # Cast to CursorResult for DML statements
            cursor = cast(CursorResult[Any], result)
            return bool(cursor.rowcount and cursor.rowcount > 0)

    async def exists(self, key: str, index: str | None = None) -> bool:
        """Check existence by primary key or indexed field."""
        return await self.get(key, index) is not None

    async def keys(self, index: str | None = None) -> list[str]:
        """Get all primary keys or distinct indexed values."""
        async with self._session_factory() as session:
            if index is None:
                stmt = select(self._pk_col)
            else:
                idx_col = getattr(self._model, index)
                stmt = select(idx_col).distinct()

            result = await session.execute(stmt)
            return [str(row[0]) for row in result.all()]

    async def values(self) -> list[T]:
        """Get all records."""
        async with self._session_factory() as session:
            result = await session.execute(select(self._model))
            return list(result.scalars().all())

    async def clear(self) -> None:
        """Truncate table."""
        async with self._session_factory() as session:
            await session.execute(delete(self._model))
            await session.commit()

    async def count(self) -> int:
        """Count records."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(self._model)
            )
            return result.scalar() or 0

    async def iterate(self) -> AsyncIterator[tuple[str, T]]:
        """Iterate over (key, record) pairs."""
        async with self._session_factory() as session:
            result = await session.stream(select(self._model))
            async for row in result:
                record = row[0]
                key = str(getattr(record, self._pk))
                yield key, record

    async def create_index(self, field_name: str) -> None:
        """No-op: SQLModel defines indexes via Field(index=True)."""

    async def create_unique_index(self, field_name: str) -> None:
        """No-op: SQLModel defines unique constraints via Field(unique=True)."""

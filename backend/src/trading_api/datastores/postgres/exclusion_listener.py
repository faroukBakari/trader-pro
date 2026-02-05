"""SQLAlchemy event listener for automatic exclusion constraint creation.

[ARCHITECTURE] Declarative exclusion constraints via model metadata.
Models declare intent via __table_args__["info"]["exclusion"], and this
listener creates the actual PostgreSQL EXCLUDE USING GIST constraints
during schema creation.

This keeps PostgreSQL-specific DDL out of model definitions while allowing
models to declare their non-overlapping range requirements.

Usage (in models):
    class PendingRange(SQLModel, table=True):
        __table_args__ = {
            "info": {"exclusion": {"range_field": "time_range", "group": "lookup_key"}}
        }

The listener reads this metadata and creates:
    ALTER TABLE pending_ranges
    ADD CONSTRAINT pending_ranges_no_overlap
    EXCLUDE USING GIST (lookup_key WITH =, time_range WITH &&)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import event, text
from sqlmodel import SQLModel

from .sql_safe import validate_identifier

if TYPE_CHECKING:
    from sqlalchemy import MetaData, Table
    from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


def _create_exclusion_constraints(
    target: MetaData,
    connection: Connection,
    **kw: Any,
) -> None:
    """Event handler to create exclusion constraints from model metadata.

    Called after SQLModel.metadata.create_all() creates tables.
    Reads __table_args__["info"]["exclusion"] from each table and
    creates EXCLUDE USING GIST constraints if configured.

    Args:
        target: SQLAlchemy MetaData object
        connection: Database connection (sync, wrapped by run_sync)
        **kw: Additional event kwargs (unused)
    """
    # Only execute on PostgreSQL
    if connection.dialect.name != "postgresql":
        logger.debug("Skipping exclusion constraints (non-PostgreSQL dialect)")
        return

    # Ensure btree_gist extension is available (required for text column in GIST)
    try:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    except Exception as e:
        logger.warning(f"Could not create btree_gist extension: {e}")
        # Continue anyway - extension might already exist or user lacks privileges

    for table in target.tables.values():
        _process_table_exclusion(table, connection)


def _process_table_exclusion(table: Table, connection: Connection) -> None:
    """Process exclusion constraint for a single table.

    Args:
        table: SQLAlchemy Table object
        connection: Database connection
    """
    # Get exclusion config from table info if present
    exclusion_config = table.info.get("exclusion")
    if not exclusion_config:
        return

    table_name = table.name
    range_field = exclusion_config.get("range_field")
    group_field = exclusion_config.get("group", "lookup_key")

    if not range_field:
        logger.warning(
            f"Table {table_name} has exclusion config but missing range_field"
        )
        return

    # Validate identifiers for SQL safety (consistent with sqlmodel_table.add_exclusion)
    try:
        validate_identifier(range_field, "exclusion range_field")
        validate_identifier(group_field, "exclusion group field")
    except ValueError as e:
        logger.warning(f"Invalid exclusion config for {table_name}: {e}")
        return

    constraint_name = f"{table_name}_no_overlap"

    # Check if constraint already exists (idempotent)
    # Note: Using string formatting for table_name since ::regclass cast
    # conflicts with SQLAlchemy's :param syntax. Table name is safe (from metadata).
    check_sql = text(
        f"""
        SELECT 1 FROM pg_constraint
        WHERE conname = :constraint_name
        AND conrelid = '"{table_name}"'::regclass
        """
    )

    result = connection.execute(check_sql, {"constraint_name": constraint_name})

    if result.fetchone() is not None:
        logger.debug(f"Exclusion constraint {constraint_name} already exists")
        return

    # Create the exclusion constraint
    # Using raw SQL since SQLAlchemy doesn't have native EXCLUDE support
    create_sql = text(
        f"""
        ALTER TABLE "{table_name}"
        ADD CONSTRAINT "{constraint_name}"
        EXCLUDE USING GIST (
            ("{group_field}") WITH =,
            "{range_field}" WITH &&
        )
        """
    )

    try:
        connection.execute(create_sql)
        logger.info(
            f"Created exclusion constraint {constraint_name} on {table_name} "
            f"(group={group_field}, range={range_field})"
        )
    except Exception as e:
        # Log but don't fail - constraint may already exist from manual migration
        # or there may be data that violates the constraint
        logger.warning(f"Could not create exclusion constraint {constraint_name}: {e}")


def register_exclusion_listener(*, _registered_tracker: set[int] | None = None) -> None:
    """Register the SQLAlchemy event listener for exclusion constraints.

    Call this once before SQLModel.metadata.create_all().
    Safe to call multiple times (idempotent via tracker set).

    The listener fires after tables are created and reads
    __table_args__["info"]["exclusion"] from each table to create
    EXCLUDE USING GIST constraints.

    Args:
        _registered_tracker: Set to track registration state. Passed by
            PostgresDatastore to maintain registration state at class level
            rather than module level (improves test isolation).
    """
    # Use provided tracker or fall back to module-level for backward compat
    tracker = (
        _registered_tracker if _registered_tracker is not None else _default_tracker
    )
    listener_id = id(_create_exclusion_constraints)

    if listener_id in tracker:
        logger.debug("Exclusion listener already registered")
        return

    event.listen(
        SQLModel.metadata,
        "after_create",
        _create_exclusion_constraints,
    )

    tracker.add(listener_id)
    logger.debug("Registered exclusion constraint listener")


# Default tracker for backward compatibility (prefer passing tracker from PostgresDatastore)
_default_tracker: set[int] = set()

__all__ = ["register_exclusion_listener"]

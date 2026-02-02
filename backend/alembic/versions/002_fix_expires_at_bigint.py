"""Fix expires_at column type to BIGINT.

Revision ID: 002_fix_expires_at_bigint
Revises: 001_migrate_jsonb_to_typed
Create Date: 2026-02-01

The expires_at column stores Unix timestamps in milliseconds which exceed
INTEGER range (max ~2.1 billion). This migration converts it to BIGINT.
"""

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "002_fix_expires_at_bigint"
down_revision = "001_migrate_jsonb_to_typed"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    return table_name in inspector.get_table_names()


def _get_column_type(table_name: str, column_name: str) -> str | None:
    """Get the type name of a column."""
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    if table_name not in inspector.get_table_names():
        return None
    for col in inspector.get_columns(table_name):
        if col["name"] == column_name:
            return str(col["type"])
    return None


def upgrade() -> None:
    """Alter expires_at column to BIGINT if it exists as INTEGER."""
    if not _table_exists("pending_ranges"):
        return

    col_type = _get_column_type("pending_ranges", "expires_at")
    if col_type and "INT" in col_type.upper() and "BIGINT" not in col_type.upper():
        op.alter_column(
            "pending_ranges",
            "expires_at",
            type_=sa.BigInteger(),
            existing_type=sa.Integer(),
        )


def downgrade() -> None:
    """Revert expires_at to INTEGER (may cause data truncation)."""
    if not _table_exists("pending_ranges"):
        return

    op.alter_column(
        "pending_ranges",
        "expires_at",
        type_=sa.Integer(),
        existing_type=sa.BigInteger(),
    )

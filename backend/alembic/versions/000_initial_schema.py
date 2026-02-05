"""Initial schema - Create auth tables.

Revision ID: 000_initial_schema
Revises:
Create Date: 2026-01-29

[ARCHITECTURE] Wave 2B: Initial typed schema
Creates tables with typed columns matching SQLModel definitions.
This is the baseline schema for fresh databases.

Tables created:
- users: User accounts with Google OAuth integration
- refresh_tokens: JWT refresh token storage with device fingerprinting

For existing databases with JSONB schema (Wave 2A), the subsequent
001_migrate_jsonb_to_typed migration handles the data migration.
"""

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "000_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    inspector = sa_inspect(conn)
    if table_name not in inspector.get_table_names():
        return False
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    """Create initial schema if tables don't exist.

    This migration is idempotent:
    - Fresh database: Creates typed tables
    - Existing JSONB database: Skips (001_migrate handles conversion)
    - Existing typed database: Skips (already migrated)
    """
    # === USERS TABLE ===
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("google_id", sa.String(), nullable=False),
            sa.Column("full_name", sa.String(), nullable=True),
            sa.Column("picture", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_login", sa.DateTime(timezone=True), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        )
        # Create indexes
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)

    # === REFRESH_TOKENS TABLE ===
    if not _table_exists("refresh_tokens"):
        op.create_table(
            "refresh_tokens",
            sa.Column("token_hash", sa.String(), primary_key=True),
            sa.Column("token_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ip_address", sa.String(), nullable=False),
            sa.Column("user_agent", sa.String(), nullable=False),
            sa.Column("fingerprint", sa.String(), nullable=False),
        )
        # Create indexes
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])


def downgrade() -> None:
    """Drop auth tables.

    WARNING: This destroys all user data. Use with caution.
    """
    op.drop_table("refresh_tokens")
    op.drop_table("users")

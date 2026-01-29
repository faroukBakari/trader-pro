"""Migrate JSONB storage to typed columns.

Revision ID: 001_migrate_jsonb_to_typed
Revises: 000_initial_schema
Create Date: 2026-01-28

[ARCHITECTURE] Wave 2B: JSONB → Typed column migration
This migration transforms the JSONB-based schema (Wave 2A) to typed columns.

CONDITIONAL EXECUTION:
- Only runs if tables have JSONB "value" column (Wave 2A schema)
- Safely skips if tables already have typed schema (from 000_initial_schema)
- Safely skips if tables don't exist

Migration steps (when applicable):
1. Add typed columns (nullable initially)
2. Copy data from JSONB to typed columns
3. Set NOT NULL constraints
4. Create new indexes
5. Drop old JSONB indexes and columns
6. Rename primary key column

Reversible: downgrade recreates JSONB schema and copies data back.
"""

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "001_migrate_jsonb_to_typed"
down_revision = "000_initial_schema"
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


def _has_jsonb_schema(table_name: str) -> bool:
    """Check if table has JSONB schema (Wave 2A pattern).

    Wave 2A tables have: key, value (JSONB), created_at, updated_at
    Wave 2B tables have: typed columns matching SQLModel
    """
    return _column_exists(table_name, "value") and _column_exists(table_name, "key")


def upgrade() -> None:
    """Migrate JSONB tables to typed columns.

    CONDITIONAL: Only runs if JSONB schema detected.
    Safely no-ops for:
    - Fresh databases (typed tables from 000_initial_schema)
    - Already migrated databases
    """
    # === USERS TABLE ===
    if _table_exists("users") and _has_jsonb_schema("users"):
        _migrate_users_table()

    # === REFRESH_TOKENS TABLE ===
    if _table_exists("refresh_tokens") and _has_jsonb_schema("refresh_tokens"):
        _migrate_refresh_tokens_table()


def _migrate_users_table() -> None:
    """Migrate users table from JSONB to typed columns."""

    # Step 1: Add typed columns (nullable initially)
    op.add_column("users", sa.Column("email", sa.String(), nullable=True))
    op.add_column("users", sa.Column("google_id", sa.String(), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("picture", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("typed_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=True))

    # Step 2: Copy data from JSONB (safe even if table is empty)
    op.execute(
        """
        UPDATE users SET
            email = value->>'email',
            google_id = value->>'google_id',
            full_name = value->>'full_name',
            picture = value->>'picture',
            typed_created_at = COALESCE(
                (value->>'created_at')::timestamptz,
                created_at
            ),
            last_login = COALESCE(
                (value->>'last_login')::timestamptz,
                created_at
            ),
            is_active = COALESCE((value->>'is_active')::boolean, true)
        WHERE value IS NOT NULL
    """
    )

    # Step 3: Set NOT NULL constraints (only if we have data, otherwise defaults work)
    # For empty tables, we'll set defaults on the columns
    op.alter_column(
        "users",
        "email",
        nullable=False,
        server_default=sa.text("''"),  # Temporary default for empty tables
    )
    op.alter_column(
        "users",
        "google_id",
        nullable=False,
        server_default=sa.text("''"),
    )
    op.alter_column(
        "users",
        "typed_created_at",
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    op.alter_column(
        "users",
        "last_login",
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    op.alter_column(
        "users",
        "is_active",
        nullable=False,
        server_default=sa.text("true"),
    )

    # Remove temporary server defaults (not needed for SQLModel)
    op.alter_column("users", "email", server_default=None)
    op.alter_column("users", "google_id", server_default=None)
    op.alter_column("users", "typed_created_at", server_default=None)
    op.alter_column("users", "last_login", server_default=None)
    op.alter_column("users", "is_active", server_default=None)

    # Step 4: Create new indexes
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_id", "users", ["google_id"])

    # Step 5: Drop old JSONB indexes (use try/except pattern via execute)
    op.execute("DROP INDEX IF EXISTS idx_users_email")
    op.execute("DROP INDEX IF EXISTS uidx_users_email")
    op.execute("DROP INDEX IF EXISTS idx_users_google_id")
    op.execute("DROP INDEX IF EXISTS uidx_users_google_id")

    # Drop JSONB columns
    op.drop_column("users", "value")
    op.drop_column("users", "created_at")
    op.drop_column("users", "updated_at")

    # Step 6: Rename columns to match SQLModel schema
    op.alter_column("users", "key", new_column_name="id")
    op.alter_column("users", "typed_created_at", new_column_name="created_at")


def _migrate_refresh_tokens_table() -> None:
    """Migrate refresh_tokens table from JSONB to typed columns."""
    # Step 1: Add typed columns
    op.add_column("refresh_tokens", sa.Column("token_id", sa.String(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("user_id", sa.String(), nullable=True))
    op.add_column(
        "refresh_tokens",
        sa.Column("typed_created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("refresh_tokens", sa.Column("ip_address", sa.String(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("user_agent", sa.String(), nullable=True))
    op.add_column(
        "refresh_tokens", sa.Column("fingerprint", sa.String(), nullable=True)
    )

    # Step 2: Copy data from JSONB
    op.execute(
        """
        UPDATE refresh_tokens SET
            token_id = value->>'token_id',
            user_id = value->>'user_id',
            typed_created_at = COALESCE(
                (value->>'created_at')::timestamptz,
                created_at
            ),
            ip_address = value->>'ip_address',
            user_agent = value->>'user_agent',
            fingerprint = value->>'fingerprint'
        WHERE value IS NOT NULL
    """
    )

    # Step 3: Set NOT NULL constraints
    op.alter_column(
        "refresh_tokens",
        "token_id",
        nullable=False,
        server_default=sa.text("''"),
    )
    op.alter_column(
        "refresh_tokens",
        "user_id",
        nullable=False,
        server_default=sa.text("''"),
    )
    op.alter_column(
        "refresh_tokens",
        "typed_created_at",
        nullable=False,
        server_default=sa.text("NOW()"),
    )
    op.alter_column(
        "refresh_tokens",
        "ip_address",
        nullable=False,
        server_default=sa.text("''"),
    )
    op.alter_column(
        "refresh_tokens",
        "user_agent",
        nullable=False,
        server_default=sa.text("''"),
    )
    op.alter_column(
        "refresh_tokens",
        "fingerprint",
        nullable=False,
        server_default=sa.text("''"),
    )

    # Remove temporary server defaults
    op.alter_column("refresh_tokens", "token_id", server_default=None)
    op.alter_column("refresh_tokens", "user_id", server_default=None)
    op.alter_column("refresh_tokens", "typed_created_at", server_default=None)
    op.alter_column("refresh_tokens", "ip_address", server_default=None)
    op.alter_column("refresh_tokens", "user_agent", server_default=None)
    op.alter_column("refresh_tokens", "fingerprint", server_default=None)

    # Step 4: Create new indexes
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # Step 5: Drop old JSONB indexes and columns
    op.execute("DROP INDEX IF EXISTS idx_refresh_tokens_user_id")

    op.drop_column("refresh_tokens", "value")
    op.drop_column("refresh_tokens", "created_at")
    op.drop_column("refresh_tokens", "updated_at")

    # Step 6: Rename columns
    op.alter_column("refresh_tokens", "key", new_column_name="token_hash")
    op.alter_column("refresh_tokens", "typed_created_at", new_column_name="created_at")


def downgrade() -> None:
    """Revert typed columns back to JSONB schema.

    CONDITIONAL: Only runs if typed schema exists (id column for users).
    This handles the case where upgrade was a no-op.
    """
    # === REFRESH_TOKENS TABLE (reverse) ===
    if _table_exists("refresh_tokens") and _column_exists(
        "refresh_tokens", "token_hash"
    ):
        _downgrade_refresh_tokens_table()

    # === USERS TABLE (reverse) ===
    if _table_exists("users") and _column_exists("users", "id"):
        _downgrade_users_table()


def _downgrade_refresh_tokens_table() -> None:
    """Revert refresh_tokens table to JSONB schema."""

    # Rename columns back
    op.alter_column("refresh_tokens", "token_hash", new_column_name="key")
    op.alter_column("refresh_tokens", "created_at", new_column_name="typed_created_at")

    # Add JSONB columns
    op.add_column(
        "refresh_tokens", sa.Column("value", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")
        ),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")
        ),
    )

    # Copy data back to JSONB
    op.execute(
        """
        UPDATE refresh_tokens SET
            value = jsonb_build_object(
                'token_id', token_id,
                'user_id', user_id,
                'token_hash', key,
                'created_at', typed_created_at::text,
                'ip_address', ip_address,
                'user_agent', user_agent,
                'fingerprint', fingerprint
            ),
            created_at = typed_created_at,
            updated_at = NOW()
    """
    )

    # Set NOT NULL for JSONB column
    op.alter_column("refresh_tokens", "value", nullable=False)

    # Drop new indexes
    op.execute("DROP INDEX IF EXISTS ix_refresh_tokens_user_id")

    # Create old JSONB indexes
    op.execute(
        """
        CREATE INDEX idx_refresh_tokens_user_id
        ON refresh_tokens ((value->>'user_id'))
    """
    )

    # Drop typed columns
    op.drop_column("refresh_tokens", "token_id")
    op.drop_column("refresh_tokens", "user_id")
    op.drop_column("refresh_tokens", "typed_created_at")
    op.drop_column("refresh_tokens", "ip_address")
    op.drop_column("refresh_tokens", "user_agent")
    op.drop_column("refresh_tokens", "fingerprint")


def _downgrade_users_table() -> None:
    """Revert users table to JSONB schema."""
    # Rename columns back
    op.alter_column("users", "id", new_column_name="key")
    op.alter_column("users", "created_at", new_column_name="typed_created_at")

    # Add JSONB columns
    op.add_column("users", sa.Column("value", postgresql.JSONB(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")
        ),
    )

    # Copy data back to JSONB
    op.execute(
        """
        UPDATE users SET
            value = jsonb_build_object(
                'id', key,
                'email', email,
                'google_id', google_id,
                'full_name', full_name,
                'picture', picture,
                'created_at', typed_created_at::text,
                'last_login', last_login::text,
                'is_active', is_active
            ),
            created_at = typed_created_at,
            updated_at = NOW()
    """
    )

    # Set NOT NULL for JSONB column
    op.alter_column("users", "value", nullable=False)

    # Drop new indexes
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    op.execute("DROP INDEX IF EXISTS ix_users_google_id")

    # Create old JSONB indexes
    op.execute(
        """
        CREATE UNIQUE INDEX uidx_users_email
        ON users ((value->>'email'))
    """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uidx_users_google_id
        ON users ((value->>'google_id'))
    """
    )

    # Drop typed columns
    op.drop_column("users", "email")
    op.drop_column("users", "google_id")
    op.drop_column("users", "full_name")
    op.drop_column("users", "picture")
    op.drop_column("users", "typed_created_at")
    op.drop_column("users", "last_login")
    op.drop_column("users", "is_active")

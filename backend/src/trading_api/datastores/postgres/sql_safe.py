"""Safe SQL composition utilities for psycopg3.

This module provides wrappers around psycopg3's sql module for safe
dynamic SQL construction, eliminating SQL injection vulnerabilities.

Key components:
- sql.SQL(): Represents a SQL statement template
- sql.Identifier(): Safely quotes table/column names
- sql.Literal(): Safely escapes literal values in SQL

Usage:
    from .sql_safe import sql, identifier, literal

    # Safe table name interpolation
    query = sql.SQL("SELECT * FROM {}").format(identifier("user_data"))

    # Safe index field access in JSONB
    query = sql.SQL("SELECT value FROM {} WHERE value->>{} = %s").format(
        identifier(table_name),
        literal(field_name)
    )
"""

from __future__ import annotations

import re

from psycopg import sql

__all__ = ["sql", "identifier", "literal", "validate_identifier", "SafeSQL"]

# Regex for valid PostgreSQL identifiers (without quoting)
# Allows: letters, digits, underscores; must start with letter or underscore
_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Maximum identifier length in PostgreSQL
_MAX_IDENTIFIER_LENGTH = 63


def validate_identifier(name: str, context: str = "identifier") -> None:
    """Validate a SQL identifier for safety.

    While psycopg3's sql.Identifier() properly quotes identifiers,
    this provides an additional layer of defense-in-depth validation.

    Args:
        name: The identifier name to validate
        context: Description for error messages (e.g., "table name", "field name")

    Raises:
        ValueError: If the identifier is invalid
    """
    if not name:
        raise ValueError(f"Empty {context} not allowed")

    if len(name) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(
            f"{context} '{name}' exceeds maximum length of {_MAX_IDENTIFIER_LENGTH}"
        )

    # Allow valid PostgreSQL identifiers
    if not _IDENTIFIER_PATTERN.match(name):
        raise ValueError(
            f"Invalid {context} '{name}': must contain only letters, "
            "digits, and underscores, and start with a letter or underscore"
        )


def identifier(name: str, *, validate: bool = True) -> sql.Identifier:
    """Create a safe SQL identifier (table/column name).

    This wraps psycopg3's sql.Identifier with optional validation.

    Args:
        name: The identifier name (table name, column name, etc.)
        validate: Whether to validate the identifier format (default: True)

    Returns:
        sql.Identifier object safe for SQL composition

    Example:
        query = sql.SQL("SELECT * FROM {}").format(identifier("users"))
    """
    if validate:
        validate_identifier(name, "identifier")
    return sql.Identifier(name)


def literal(value: str) -> sql.Literal:
    """Create a safe SQL literal value.

    Use this for values that need to appear literally in SQL
    (not as parameters), such as JSONB field paths.

    Args:
        value: The literal value to embed in SQL

    Returns:
        sql.Literal object safe for SQL composition

    Example:
        # JSONB field access: value->>'field_name'
        query = sql.SQL("SELECT value FROM t WHERE value->>{} = %s").format(
            literal("email")
        )
    """
    return sql.Literal(value)


class SafeSQL:
    """Builder for complex SQL statements with safe composition.

    Provides a fluent interface for building SQL queries with
    automatic identifier quoting and parameter handling.

    Example:
        builder = SafeSQL.select("value").from_table("users")
        builder = builder.where_jsonb_eq("email", param_index=0)
        query, identifiers = builder.build()
    """

    def __init__(self) -> None:
        self._parts: list[str | sql.Composable] = []

    @classmethod
    def select(cls, *columns: str) -> SafeSQL:
        """Start a SELECT statement."""
        builder = cls()
        if columns:
            for col in columns:
                validate_identifier(col, "column")
            cols = sql.SQL(", ").join(sql.Identifier(c) for c in columns)
            builder._parts.append(sql.SQL("SELECT "))
            builder._parts.append(cols)
        else:
            builder._parts.append(sql.SQL("SELECT *"))
        return builder

    def from_table(self, table_name: str) -> SafeSQL:
        """Add FROM clause with safe table name."""
        validate_identifier(table_name, "table name")
        self._parts.append(sql.SQL(" FROM "))
        self._parts.append(sql.Identifier(table_name))
        return self

    def where_key_eq(self) -> SafeSQL:
        """Add WHERE key = %s clause."""
        self._parts.append(sql.SQL(" WHERE key = %s"))
        return self

    def where_jsonb_eq(self, field: str) -> SafeSQL:
        """Add WHERE value->>'field' = %s clause."""
        validate_identifier(field, "JSONB field")
        self._parts.append(sql.SQL(" WHERE value->>"))
        self._parts.append(sql.Literal(field))
        self._parts.append(sql.SQL(" = %s"))
        return self

    def limit(self, n: int) -> SafeSQL:
        """Add LIMIT clause.
        Args:
            n: Positive integer limit value
        """
        if n < 0:
            raise ValueError("LIMIT value must be non-negative")
        # Safe: n is an int, not user input
        self._parts.append(sql.SQL(" LIMIT ") + sql.Literal(n))
        return self

    def build(self) -> sql.Composed:
        """Build the final SQL query."""
        return sql.Composed(self._parts)

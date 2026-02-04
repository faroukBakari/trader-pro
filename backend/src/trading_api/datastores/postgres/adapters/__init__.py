"""PostgreSQL type adapters for custom domain types.

This package provides adapters for seamless conversion between
application domain types and PostgreSQL native types.

Note: Range type conversions are handled by SQLAlchemy TypeDecorators
in trading_api.types.range (Int8RangeType, TstzRangeType, DateRangeType).
No psycopg3 adapter registration is required for ORM operations.
"""

__all__: list[str] = []

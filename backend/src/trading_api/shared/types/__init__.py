"""Shared type definitions for trading_api.

This module provides Pydantic-compatible custom types for use across the codebase.

Types:
- TstzRange: PostgreSQL tstzrange type with Pydantic validators
"""

from .pg_range import TstzRange

__all__ = ["TstzRange"]

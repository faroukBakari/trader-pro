"""Shared utilities for datastore implementations."""

from __future__ import annotations

from pydantic import BaseModel


def extract_indexes(
    model_class: type[BaseModel],
) -> tuple[list[str], list[str], str | None]:
    """Extract index metadata from SQLModel/Pydantic Field() declarations.

    Reads index=True, unique=True, and primary_key=True from FieldInfo.
    Works for both SQLModel and Pydantic BaseModel classes.

    Returns:
        (indexes, unique_indexes, primary_key) tuple where:
        - indexes: Fields with index=True (non-unique secondary indexes)
        - unique_indexes: Fields with unique=True
        - primary_key: Field with primary_key=True (or None)
    """
    indexes: list[str] = []
    unique_indexes: list[str] = []
    primary_key: str | None = None

    for field_name, field_info in model_class.model_fields.items():
        if getattr(field_info, "primary_key", None) is True:
            primary_key = field_name

        if getattr(field_info, "unique", None) is True:
            unique_indexes.append(field_name)

        if (
            getattr(field_info, "index", None) is True
            and field_name not in unique_indexes
        ):
            indexes.append(field_name)

    return indexes, unique_indexes, primary_key

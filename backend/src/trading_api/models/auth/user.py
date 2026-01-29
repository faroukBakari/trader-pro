"""User models for authentication module.

[ARCHITECTURE] Wave 2B: SQLModel migration
- SQLModel enables single model for both API schema and database table
- User class has table=True for SQLAlchemy ORM integration
- UserBase/UserCreate are pure DTOs (no table=True)
"""

from datetime import datetime, timezone

from pydantic import EmailStr
from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


class UserBase(SQLModel):
    """Base user fields shared across create/read."""

    email: EmailStr
    full_name: str | None = None
    picture: str | None = None


class UserCreate(UserBase):
    """Input DTO for user creation."""

    google_id: str


class User(UserBase, table=True):
    """User model - unified API contract AND database table.

    [ARCHITECTURE]: SQLModel enables single model for both:
    - FastAPI request/response schemas (Pydantic validation)
    - SQLAlchemy ORM operations (database persistence)
    """

    __tablename__ = "users"  # pyright: ignore[reportAssignmentType]

    id: str = Field(primary_key=True, description="Unique user identifier")
    google_id: str = Field(index=True, unique=True)
    email: EmailStr = Field(index=True, unique=True)  # Override base to add index
    created_at: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    last_login: datetime = Field(
        default_factory=_utc_now, sa_column=Column(DateTime(timezone=True))
    )
    is_active: bool = Field(default=True)

    model_config = {"from_attributes": True}  # pyright: ignore[reportAssignmentType]


# [DELETED] UserInDB - redundant: User IS the DB model now

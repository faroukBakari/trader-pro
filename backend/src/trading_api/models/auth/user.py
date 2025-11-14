from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    picture: Optional[str] = None


class UserCreate(UserBase):
    google_id: str


class User(UserBase):
    id: str = Field(..., description="Unique user identifier")
    google_id: str
    created_at: datetime
    last_login: datetime
    is_active: bool = True

    model_config = {"from_attributes": True}


class UserInDB(User):
    """User model as stored in database"""

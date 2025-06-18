# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import uuid
from datetime import datetime

class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: bool = True
    # Add other common user fields if needed

class UserCreate(UserBase):
    supabase_user_id: str
    email: EmailStr

class UserUpdate(UserBase):
    pass

class User(UserBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    supabase_user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True # For SQLAlchemy compatibility if ever needed
        from_attributes = True # Pydantic V2

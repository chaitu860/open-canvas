# app/schemas/session.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime

class SessionBase(BaseModel):
    langgraph_thread_id: Optional[str] = None
    name: Optional[str] = None # Optional name for the session

class SessionCreate(SessionBase):
    user_id: uuid.UUID
    langgraph_thread_id: str

class SessionUpdate(SessionBase):
    name: Optional[str] = None

class Session(SessionBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        from_attributes = True

# For storing message context chunks related to a session
class SessionMessageChunkBase(BaseModel):
    content: str
    type: str # e.g., "human", "ai", "system"
    metadata: Optional[Dict[str, Any]] = None

class SessionMessageChunkCreate(SessionMessageChunkBase):
    session_id: uuid.UUID

class SessionMessageChunk(SessionMessageChunkBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        from_attributes = True

# For linking uploaded files to a session (references FileMetadata and FileVersion)
class SessionFileBase(BaseModel):
    file_id: uuid.UUID # Refers to FileMetadata.id
    version_id: uuid.UUID # Refers to FileVersion.id

class SessionFileCreate(SessionFileBase):
    session_id: uuid.UUID

class SessionFile(SessionFileBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    added_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        from_attributes = True

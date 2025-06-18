# app/schemas/metadata.py
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
from datetime import datetime

# --- FileChunk: Represents a chunk of a file version ---
class FileChunkBase(BaseModel):
    content: Optional[str] = None # Or bytes, depending on how it's stored/retrieved
    storage_reference: Optional[str] = None # e.g., path in a bucket, or part of a larger DB entry
    chunk_order: int = 0

class FileChunkCreate(FileChunkBase):
    file_version_id: uuid.UUID

class FileChunk(FileChunkBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    file_version_id: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        from_attributes = True

# --- FileVersion: Represents a specific version of a file ---
class FileVersionBase(BaseModel):
    version_number: int = 1
    notes: Optional[str] = None # Optional notes for this version

class FileVersionCreate(FileVersionBase):
    file_id: uuid.UUID

class FileVersion(FileVersionBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    file_id: uuid.UUID # Foreign key to FileMetadata
    # chunk_ids: List[uuid.UUID] = [] # If storing only IDs; alternative is relation from FileChunk
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        from_attributes = True

# --- FileMetadata: Represents the core metadata of a file ---
class FileMetadataBase(BaseModel):
    name: str
    type: Optional[str] = None # e.g., "pdf", "txt", "png"
    size: Optional[int] = None # Size in bytes

class FileMetadataCreate(FileMetadataBase):
    user_id: Optional[uuid.UUID] = None # Optional: if files are user-specific

class FileMetadata(FileMetadataBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # latest_version_id: Optional[uuid.UUID] = None # Could be useful

    class Config:
        orm_mode = True
        from_attributes = True

# app/schemas/artifact.py
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
import uuid
from datetime import datetime

# --- ArtifactChunk: Represents a chunk of an artifact version's content ---
class ArtifactChunkBase(BaseModel):
    content_chunk: str # The actual piece of content
    storage_reference: Optional[str] = None # If stored externally
    chunk_order: int = 0

class ArtifactChunkCreate(ArtifactChunkBase):
    artifact_version_id: uuid.UUID

class ArtifactChunk(ArtifactChunkBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    artifact_version_id: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        from_attributes = True

# --- ArtifactVersion: Represents a specific version of an artifact ---
class ArtifactVersionBase(BaseModel):
    version_number: int = 1
    langgraph_output_reference: Optional[Dict[str, Any]] = None # Reference to the LangGraph output that generated this
    notes: Optional[str] = None

class ArtifactVersionCreate(ArtifactVersionBase):
    artifact_id: uuid.UUID

class ArtifactVersion(ArtifactVersionBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    artifact_id: uuid.UUID # Foreign key to Artifact
    # chunk_ids: List[uuid.UUID] = [] # If storing only IDs
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        orm_mode = True
        from_attributes = True

# --- Artifact: Represents a generated artifact (e.g., canvas) ---
class ArtifactBase(BaseModel):
    name: str
    type: str # e.g., "canvas_state", "generated_code_block"

class ArtifactCreate(ArtifactBase):
    session_id: uuid.UUID
    # user_id: Optional[uuid.UUID] = None # Could be derived from session

class Artifact(ArtifactBase):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    # user_id: Optional[uuid.UUID] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # latest_version_id: Optional[uuid.UUID] = None # Could be useful

    class Config:
        orm_mode = True
        from_attributes = True

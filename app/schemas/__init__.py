# app/schemas/__init__.py
# This file makes 'schemas' a Python package

# Optional: You can make it easier to import models
from .user import User, UserCreate, UserUpdate
from .session import Session, SessionCreate, SessionUpdate, SessionMessageChunk, SessionMessageChunkCreate, SessionFile, SessionFileCreate
from .metadata import FileMetadata, FileMetadataCreate, FileVersion, FileVersionCreate, FileChunk, FileChunkCreate
from .artifact import Artifact, ArtifactCreate, ArtifactVersion, ArtifactVersionCreate, ArtifactChunk, ArtifactChunkCreate

# Or just leave it empty if you prefer direct imports like `from app.schemas.user import User`

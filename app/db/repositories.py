# app/db/repositories.py

from .base_repository import BaseRepository
from app.schemas.user import User, UserCreate, UserUpdate
from app.schemas.session import (
    Session, SessionCreate, SessionUpdate,
    SessionMessageChunk, SessionMessageChunkCreate,
    SessionFile, SessionFileCreate
)
from app.schemas.metadata import (
    FileMetadata, FileMetadataCreate,
    FileVersion, FileVersionCreate,
    FileChunk, FileChunkCreate
)
from app.schemas.artifact import (
    Artifact, ArtifactCreate,
    ArtifactVersion, ArtifactVersionCreate,
    ArtifactChunk, ArtifactChunkCreate
)
from pydantic import BaseModel  # For generic Update types where not specified

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self):
        super().__init__(model_class=User, table_name="users")

class SessionRepository(BaseRepository[Session, SessionCreate, SessionUpdate]):
    def __init__(self):
        super().__init__(model_class=Session, table_name="sessions")

class SessionMessageChunkRepository(BaseRepository[SessionMessageChunk, SessionMessageChunkCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=SessionMessageChunk, table_name="session_message_chunks")

class SessionFileRepository(BaseRepository[SessionFile, SessionFileCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=SessionFile, table_name="session_files")

class FileMetadataRepository(BaseRepository[FileMetadata, FileMetadataCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=FileMetadata, table_name="file_metadata")

class FileVersionRepository(BaseRepository[FileVersion, FileVersionCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=FileVersion, table_name="file_versions")

class FileChunkRepository(BaseRepository[FileChunk, FileChunkCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=FileChunk, table_name="file_chunks")

class ArtifactRepository(BaseRepository[Artifact, ArtifactCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=Artifact, table_name="artifacts")

class ArtifactVersionRepository(BaseRepository[ArtifactVersion, ArtifactVersionCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=ArtifactVersion, table_name="artifact_versions")

class ArtifactChunkRepository(BaseRepository[ArtifactChunk, ArtifactChunkCreate, BaseModel]):
    def __init__(self):
        super().__init__(model_class=ArtifactChunk, table_name="artifact_chunks")

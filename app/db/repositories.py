# app/db/repositories.py
from .base_repository import BaseRepository
from app.schemas.user import User, UserCreate, UserUpdate
from app.schemas.session import (
    Session, SessionCreate, SessionUpdate,
    SessionMessageChunk, SessionMessageChunkCreate, # UpdateSchema not defined, use BaseModel
    SessionFile, SessionFileCreate # UpdateSchema not defined, use BaseModel
)
from app.schemas.metadata import (
    FileMetadata, FileMetadataCreate, # UpdateSchema not defined, use BaseModel
    FileVersion, FileVersionCreate, # UpdateSchema not defined, use BaseModel
    FileChunk, FileChunkCreate # UpdateSchema not defined, use BaseModel
)
from app.schemas.artifact import (
    Artifact, ArtifactCreate, # UpdateSchema not defined, use BaseModel
    ArtifactVersion, ArtifactVersionCreate, # UpdateSchema not defined, use BaseModel
    ArtifactChunk, ArtifactChunkCreate # UpdateSchema not defined, use BaseModel
)
from supabase import Client # Changed from 'Any'
from pydantic import BaseModel # For generic Update types where not specified

class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    def __init__(self, supabase_client: Client):
        self.table_name = "users"
        super().__init__(supabase_client=supabase_client, model_class=User, table_name=self.table_name)

class SessionRepository(BaseRepository[Session, SessionCreate, SessionUpdate]):
    def __init__(self, supabase_client: Client):
        self.table_name = "sessions"
        super().__init__(supabase_client=supabase_client, model_class=Session, table_name=self.table_name)

class SessionMessageChunkRepository(BaseRepository[SessionMessageChunk, SessionMessageChunkCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "session_message_chunks"
        super().__init__(supabase_client=supabase_client, model_class=SessionMessageChunk, table_name=self.table_name)

class SessionFileRepository(BaseRepository[SessionFile, SessionFileCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "session_files"
        super().__init__(supabase_client=supabase_client, model_class=SessionFile, table_name=self.table_name)

class FileMetadataRepository(BaseRepository[FileMetadata, FileMetadataCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "file_metadata"
        super().__init__(supabase_client=supabase_client, model_class=FileMetadata, table_name=self.table_name)

class FileVersionRepository(BaseRepository[FileVersion, FileVersionCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "file_versions"
        super().__init__(supabase_client=supabase_client, model_class=FileVersion, table_name=self.table_name)

class FileChunkRepository(BaseRepository[FileChunk, FileChunkCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "file_chunks"
        super().__init__(supabase_client=supabase_client, model_class=FileChunk, table_name=self.table_name)

class ArtifactRepository(BaseRepository[Artifact, ArtifactCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "artifacts"
        super().__init__(supabase_client=supabase_client, model_class=Artifact, table_name=self.table_name)

class ArtifactVersionRepository(BaseRepository[ArtifactVersion, ArtifactVersionCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "artifact_versions"
        super().__init__(supabase_client=supabase_client, model_class=ArtifactVersion, table_name=self.table_name)

class ArtifactChunkRepository(BaseRepository[ArtifactChunk, ArtifactChunkCreate, BaseModel]):
    def __init__(self, supabase_client: Client):
        self.table_name = "artifact_chunks"
        super().__init__(supabase_client=supabase_client, model_class=ArtifactChunk, table_name=self.table_name)

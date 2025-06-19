# app/db/unit_of_work.py

from .repositories import (
    UserRepository,
    SessionRepository,
    SessionMessageChunkRepository,
    SessionFileRepository,
    FileMetadataRepository,
    FileVersionRepository,
    FileChunkRepository,
    ArtifactRepository,
    ArtifactVersionRepository,
    ArtifactChunkRepository,
)
from app.db.supabase_client import get_postgres_connection  # still using psycopg2 connection

class UnitOfWork:
    def __init__(self):
        self.conn = get_postgres_connection()
        self._init_repositories()

    def _init_repositories(self):
        # These repositories internally use get_postgres_connection()
        self.users = UserRepository()
        self.sessions = SessionRepository()
        self.session_message_chunks = SessionMessageChunkRepository()
        self.session_files = SessionFileRepository()
        self.file_metadata = FileMetadataRepository()
        self.file_versions = FileVersionRepository()
        self.file_chunks = FileChunkRepository()
        self.artifacts = ArtifactRepository()
        self.artifact_versions = ArtifactVersionRepository()
        self.artifact_chunks = ArtifactChunkRepository()

    async def __aenter__(self):
        # Start a transaction if needed
        self.conn.autocommit = False
        print("UoW: Transaction started")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        # Reset autocommit to avoid side effects outside UoW
        self.conn.autocommit = True

    async def commit(self):
        try:
            self.conn.commit()
            print("UoW: Commit successful")
        except Exception as e:
            print(f"UoW: Commit failed — {e}")
            await self.rollback()
            raise

    async def rollback(self):
        try:
            self.conn.rollback()
            print("UoW: Rollback successful")
        except Exception as e:
            print(f"UoW: Rollback failed — {e}")

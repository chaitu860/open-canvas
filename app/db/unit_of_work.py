# app/db/unit_of_work.py
from app.db.supabase_client import get_supabase_client, init_supabase_client # Added init for potential explicit call
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

# This will be replaced with the actual Supabase client later
# from app.db.supabase_client import get_supabase_client

class UnitOfWork:
    def __init__(self): # Removed supabase_client argument
        # Get the Supabase client instance
        # In a real app, ensure init_supabase_client() is called at app startup.
        # For robustness here, we can try to get it, which itself might try to init.
        self.client = get_supabase_client()

        # Initialize repositories with the actual client
        self.users = UserRepository(self.client)
        self.sessions = SessionRepository(self.client)
        # ... other repositories initialized similarly ...
        self.session_message_chunks = SessionMessageChunkRepository(self.client)
        self.session_files = SessionFileRepository(self.client)
        self.file_metadata = FileMetadataRepository(self.client)
        self.file_versions = FileVersionRepository(self.client)
        self.file_chunks = FileChunkRepository(self.client)
        self.artifacts = ArtifactRepository(self.client)
        self.artifact_versions = ArtifactVersionRepository(self.client)
        self.artifact_chunks = ArtifactChunkRepository(self.client)

    async def __aenter__(self):
        # This could be used to start a transaction if Supabase/Postgres supports it directly via the client
        # For now, it primarily ensures repositories are available.
        # self.transaction = await self.client.transaction() # Example if client supports
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # If an exception occurred, rollback. Otherwise, commit.
        if exc_type:
            await self.rollback()
        else:
            # For Supabase, explicit commit might not be needed per operation,
            # but this structure is good practice for managing a set of operations.
            # If batching, this is where it would be finalized.
            await self.commit()

    async def commit(self):
        # Placeholder: With Supabase, individual operations are often atomic.
        # If batching operations or using a specific transaction block,
        # this is where it would be finalized.
        # For now, this method signifies the successful completion of a unit of work.
        # await self.transaction.commit() # Example if client supports
        print("UoW: Commit called")
        pass

    async def rollback(self):
        # Placeholder: Rollback logic for Supabase.
        # This is complex without ORM-level transaction management or explicit db transaction blocks.
        # For now, it signifies an attempt to revert.
        # await self.transaction.rollback() # Example if client supports
        print("UoW: Rollback called")
        pass

# Example of how it might be used (actual client needed)
# async def some_service_function():
#     supabase_client = get_supabase_client() # Assume this function provides a client
#     async with UnitOfWork(supabase_client) as uow:
#         # Access repositories like uow.users, uow.sessions
#         user = await uow.users.create(...)
#         # await uow.commit() # Handled by __aexit__

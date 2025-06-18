# app/services/session_service.py
import uuid
from typing import Optional, List, Dict, Any
from app.db.unit_of_work import UnitOfWork
from app.schemas.session import (
    Session, SessionCreate, SessionUpdate,
    SessionMessageChunk, SessionMessageChunkCreate,
    SessionFile, SessionFileCreate
)
from app.schemas.artifact import (
    Artifact, ArtifactCreate,
    ArtifactVersion, ArtifactVersionCreate,
    ArtifactChunk, ArtifactChunkCreate
)
# Need to import schemas from metadata for type hinting if returning full objects
from app.schemas.metadata import FileMetadata, FileVersion

# Forward declare services if needed for type hinting, or import directly
# from .user_service import UserService # Assuming they are in the same directory or adjust path
# from .metadata_service import MetadataService

class SessionService:
    def __init__(self, uow: UnitOfWork): # Add other services if they are directly used
        self.uow = uow
        # self.user_service = user_service # To be injected if needed
        # self.metadata_service = metadata_service # To be injected if needed


    # Session Management
    async def create_session(
        self, *,
        user_id: uuid.UUID,
        langgraph_thread_id: str,
        name: Optional[str] = None
    ) -> Optional[Session]:
        '''Creates a new session for a user.'''
        async with self.uow:
            try:
                session_create = SessionCreate(
                    user_id=user_id,
                    langgraph_thread_id=langgraph_thread_id,
                    name=name
                )
                new_session = await self.uow.sessions.create(obj_in=session_create)
                return new_session
            except NotImplementedError:
                print("SessionService.create_session: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in SessionService.create_session: {e}")
                return None

    async def get_session_by_id(self, *, session_id: uuid.UUID) -> Optional[Session]:
        '''Retrieves a session by its ID.'''
        try:
            return await self.uow.sessions.get(id=session_id)
        except NotImplementedError:
            print("SessionService.get_session_by_id: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in SessionService.get_session_by_id: {e}")
            return None

    async def get_sessions_for_user(self, *, user_id: uuid.UUID) -> List[Session]:
        '''Retrieves all sessions for a given user ID.'''
        try:
            sessions = await self.uow.sessions.get_multi_by_attribute(attribute="user_id", value=user_id, limit=1000)
            return sessions if sessions else []
        except NotImplementedError:
            print("SessionService.get_sessions_for_user: Repository method not yet implemented.")
            return []
        except Exception as e:
            print(f"Error in SessionService.get_sessions_for_user: {e}")
            return []

    # Session Message Management
    async def add_message_to_session(
        self, *,
        session_id: uuid.UUID,
        content: str,
        type: str, # "human", "ai", "system"
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[SessionMessageChunk]:
        '''Adds a message chunk to a session.'''
        async with self.uow:
            try:
                msg_create = SessionMessageChunkCreate(
                    session_id=session_id,
                    content=content,
                    type=type,
                    metadata=metadata
                )
                new_msg = await self.uow.session_message_chunks.create(obj_in=msg_create)
                return new_msg
            except NotImplementedError:
                print("SessionService.add_message_to_session: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in SessionService.add_message_to_session: {e}")
                return None

    async def get_messages_for_session(self, *, session_id: uuid.UUID, limit: int = 100) -> List[SessionMessageChunk]:
        '''Retrieves messages for a session, ordered by creation time (implicitly by ID or add timestamp).'''
        try:
            # Assuming messages should be ordered by creation. If SessionMessageChunk has created_at:
            # messages = await self.uow.session_message_chunks.get_multi_by_attribute(attribute="session_id", value=session_id, limit=limit)
            # return sorted(messages, key=lambda m: m.created_at) if messages else []
            # For now, just fetching, order might depend on DB insertion order or need explicit sort column
            messages = await self.uow.session_message_chunks.get_multi_by_attribute(attribute="session_id", value=session_id, limit=limit)
            return messages if messages else []
        except NotImplementedError:
            print("SessionService.get_messages_for_session: Repository method not yet implemented.")
            return []
        except Exception as e:
            print(f"Error in SessionService.get_messages_for_session: {e}")
            return []

    # Session File Management
    async def link_file_to_session(
        self, *,
        session_id: uuid.UUID,
        file_id: uuid.UUID, # Refers to FileMetadata.id
        version_id: uuid.UUID # Refers to FileVersion.id
    ) -> Optional[SessionFile]:
        '''Links an existing file (and its specific version) to a session.'''
        async with self.uow:
            try:
                # Optional: Validate file_id and version_id exist using MetadataService if injected
                # file_meta = await self.metadata_service.get_file_metadata_by_id(file_id=file_id)
                # file_version = await self.metadata_service.get_file_version_by_id(version_id=version_id)
                # if not file_meta or not file_version or file_version.file_id != file_id:
                #     raise ValueError("Invalid file_id or version_id, or version does not belong to file.")

                session_file_create = SessionFileCreate(
                    session_id=session_id,
                    file_id=file_id,
                    version_id=version_id
                )
                new_session_file = await self.uow.session_files.create(obj_in=session_file_create)
                return new_session_file
            except NotImplementedError:
                print("SessionService.link_file_to_session: Repository method not yet implemented.")
                return None
            except ValueError as ve:
                print(f"Error in SessionService.link_file_to_session: {ve}")
                return None
            except Exception as e:
                print(f"Error in SessionService.link_file_to_session: {e}")
                return None

    async def get_linked_files_for_session(self, *, session_id: uuid.UUID) -> List[SessionFile]: # Could return List[Tuple[SessionFile, FileMetadata, FileVersion]]
        '''Retrieves files linked to a session.'''
        try:
            # This returns SessionFile objects. To get full details, you'd iterate and use MetadataService.
            session_files = await self.uow.session_files.get_multi_by_attribute(attribute="session_id", value=session_id, limit=100)
            return session_files if session_files else []
            # Example for richer data (if metadata_service is available):
            # rich_session_files = []
            # if session_files:
            #     for sf in session_files:
            #         meta = await self.metadata_service.get_file_metadata_by_id(file_id=sf.file_id)
            #         version = await self.metadata_service.get_file_version_by_id(version_id=sf.version_id)
            #         rich_session_files.append({"session_file": sf, "metadata": meta, "version": version})
            # return rich_session_files

        except NotImplementedError:
            print("SessionService.get_linked_files_for_session: Repository method not yet implemented.")
            return []
        except Exception as e:
            print(f"Error in SessionService.get_linked_files_for_session: {e}")
            return []


    # Artifact Management (within a session)
    async def create_artifact_for_session(
        self, *,
        session_id: uuid.UUID,
        name: str,
        type: str # e.g., "canvas_state", "code_block"
    ) -> Optional[Artifact]:
        '''Creates an artifact record associated with a session.'''
        async with self.uow:
            try:
                artifact_create = ArtifactCreate(session_id=session_id, name=name, type=type)
                new_artifact = await self.uow.artifacts.create(obj_in=artifact_create)
                return new_artifact
            except NotImplementedError:
                print("SessionService.create_artifact_for_session: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in SessionService.create_artifact_for_session: {e}")
                return None

    async def get_artifact_by_id(self, *, artifact_id: uuid.UUID) -> Optional[Artifact]:
        '''Retrieves an artifact by its ID.'''
        try:
            return await self.uow.artifacts.get(id=artifact_id)
        except NotImplementedError:
            print("SessionService.get_artifact_by_id: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in SessionService.get_artifact_by_id: {e}")
            return None

    async def create_artifact_version(
        self, *,
        artifact_id: uuid.UUID,
        langgraph_output_reference: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        version_number: Optional[int] = None # If None, logic to determine next version
    ) -> Optional[ArtifactVersion]:
        '''Creates a new version for an artifact.'''
        async with self.uow:
            try:
                if version_number is None:
                    existing_versions = await self.uow.artifact_versions.get_multi_by_attribute(attribute="artifact_id", value=artifact_id, limit=1000)
                    version_number = max(v.version_number for v in existing_versions) + 1 if existing_versions else 1

                version_create = ArtifactVersionCreate(
                    artifact_id=artifact_id,
                    langgraph_output_reference=langgraph_output_reference,
                    notes=notes,
                    version_number=version_number
                )
                new_version = await self.uow.artifact_versions.create(obj_in=version_create)
                return new_version
            except NotImplementedError:
                print("SessionService.create_artifact_version: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in SessionService.create_artifact_version: {e}")
                return None

    async def get_artifact_version_by_id(self, *, artifact_version_id: uuid.UUID) -> Optional[ArtifactVersion]:
        '''Retrieves a specific artifact version by its ID.'''
        try:
            return await self.uow.artifact_versions.get(id=artifact_version_id)
        except NotImplementedError:
            print("SessionService.get_artifact_version_by_id: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in SessionService.get_artifact_version_by_id: {e}")
            return None

    async def add_chunk_to_artifact_version(
        self, *,
        artifact_version_id: uuid.UUID,
        content_chunk: str,
        chunk_order: int,
        storage_reference: Optional[str] = None
    ) -> Optional[ArtifactChunk]:
        '''Adds a content chunk to a specific artifact version.'''
        async with self.uow:
            try:
                chunk_create = ArtifactChunkCreate(
                    artifact_version_id=artifact_version_id,
                    content_chunk=content_chunk,
                    chunk_order=chunk_order,
                    storage_reference=storage_reference
                )
                new_chunk = await self.uow.artifact_chunks.create(obj_in=chunk_create)
                return new_chunk
            except NotImplementedError:
                print("SessionService.add_chunk_to_artifact_version: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in SessionService.add_chunk_to_artifact_version: {e}")
                return None

    async def get_artifact_content_by_version(self, *, artifact_version_id: uuid.UUID) -> Optional[str]:
        '''Retrieves and concatenates all chunks for an artifact version.'''
        try:
            # First, get all chunks for the artifact version
            chunks = await self.uow.artifact_chunks.get_multi_by_attribute(
                attribute="artifact_version_id", value=artifact_version_id, limit=10000 # Large limit
            )
            if not chunks:
                # Check if the version itself exists, to differentiate "empty" from "non-existent"
                version_exists = await self.get_artifact_version_by_id(artifact_version_id=artifact_version_id)
                return "" if version_exists else None

            # Sort chunks by their order and join their content
            sorted_chunks = sorted(chunks, key=lambda c: c.chunk_order)
            return "".join(chunk.content_chunk for chunk in sorted_chunks if chunk.content_chunk)
        except NotImplementedError:
            print("SessionService.get_artifact_content_by_version: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in SessionService.get_artifact_content_by_version: {e}")
            return None

    async def get_artifact_versions(self, *, artifact_id: uuid.UUID) -> List[ArtifactVersion]:
        '''Retrieves all versions for a given artifact ID, sorted by version number.'''
        try:
            versions = await self.uow.artifact_versions.get_multi_by_attribute(attribute="artifact_id", value=artifact_id, limit=1000)
            return sorted(versions, key=lambda v: v.version_number) if versions else []
        except NotImplementedError:
            print("SessionService.get_artifact_versions: Repository method not yet implemented.")
            return []
        except Exception as e:
            print(f"Error in SessionService.get_artifact_versions: {e}")
            return []

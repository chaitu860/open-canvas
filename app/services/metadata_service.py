# app/services/metadata_service.py
import uuid
from typing import Optional, List
from app.db.unit_of_work import UnitOfWork
from app.schemas.metadata import (
    FileMetadata, FileMetadataCreate,
    FileVersion, FileVersionCreate,
    FileChunk, FileChunkCreate
)

class MetadataService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def create_file_metadata(
        self, *,
        name: str,
        type: Optional[str] = None,
        size: Optional[int] = None,
        user_id: Optional[uuid.UUID] = None
    ) -> Optional[FileMetadata]:
        '''Creates a new file metadata record.'''
        async with self.uow:
            try:
                file_meta_create = FileMetadataCreate(name=name, type=type, size=size, user_id=user_id)
                new_file_meta = await self.uow.file_metadata.create(obj_in=file_meta_create)
                return new_file_meta
            except NotImplementedError:
                print("MetadataService.create_file_metadata: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in MetadataService.create_file_metadata: {e}")
                return None

    async def get_file_metadata_by_id(self, *, file_id: uuid.UUID) -> Optional[FileMetadata]:
        '''Retrieves file metadata by its ID.'''
        try:
            return await self.uow.file_metadata.get(id=file_id)
        except NotImplementedError:
            print("MetadataService.get_file_metadata_by_id: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in MetadataService.get_file_metadata_by_id: {e}")
            return None

    async def create_file_version(
        self, *,
        file_id: uuid.UUID,
        notes: Optional[str] = None,
        version_number: Optional[int] = None # If None, logic to determine next version might be needed
    ) -> Optional[FileVersion]:
        '''Creates a new version for a file.'''
        async with self.uow:
            try:
                # Basic version increment logic (can be more sophisticated)
                if version_number is None:
                    existing_versions = await self.uow.file_versions.get_multi_by_attribute(attribute="file_id", value=file_id, limit=1000) # Assuming not too many versions for now
                    if existing_versions:
                        version_number = max(v.version_number for v in existing_versions) + 1
                    else:
                        version_number = 1

                version_create = FileVersionCreate(file_id=file_id, notes=notes, version_number=version_number)
                new_version = await self.uow.file_versions.create(obj_in=version_create)
                return new_version
            except NotImplementedError:
                print("MetadataService.create_file_version: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in MetadataService.create_file_version: {e}")
                return None

    async def get_file_version_by_id(self, *, version_id: uuid.UUID) -> Optional[FileVersion]:
        '''Retrieves a specific file version by its ID.'''
        try:
            return await self.uow.file_versions.get(id=version_id)
        except NotImplementedError:
            print("MetadataService.get_file_version_by_id: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in MetadataService.get_file_version_by_id: {e}")
            return None

    async def get_file_versions_for_file(self, *, file_id: uuid.UUID) -> List[FileVersion]:
        '''Retrieves all versions for a given file metadata ID.'''
        try:
            versions = await self.uow.file_versions.get_multi_by_attribute(attribute="file_id", value=file_id, limit=1000) # Adjust limit as needed
            return sorted(versions, key=lambda v: v.version_number) if versions else []
        except NotImplementedError:
            print("MetadataService.get_file_versions_for_file: Repository method not yet implemented.")
            return []
        except Exception as e:
            print(f"Error in MetadataService.get_file_versions_for_file: {e}")
            return []

    async def add_chunk_to_file_version(
        self, *,
        version_id: uuid.UUID,
        content: str, # Or bytes
        chunk_order: int,
        storage_reference: Optional[str] = None
    ) -> Optional[FileChunk]:
        '''Adds a content chunk to a specific file version.'''
        async with self.uow:
            try:
                chunk_create = FileChunkCreate(
                    file_version_id=version_id,
                    content=content,
                    chunk_order=chunk_order,
                    storage_reference=storage_reference
                )
                new_chunk = await self.uow.file_chunks.create(obj_in=chunk_create)
                return new_chunk
            except NotImplementedError:
                print("MetadataService.add_chunk_to_file_version: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in MetadataService.add_chunk_to_file_version: {e}")
                return None

    async def get_chunks_for_file_version(self, *, version_id: uuid.UUID) -> List[FileChunk]:
        '''Retrieves all chunks for a given file version, ordered by chunk_order.'''
        try:
            chunks = await self.uow.file_chunks.get_multi_by_attribute(attribute="file_version_id", value=version_id, limit=10000) # Adjust limit
            return sorted(chunks, key=lambda c: c.chunk_order) if chunks else []
        except NotImplementedError:
            print("MetadataService.get_chunks_for_file_version: Repository method not yet implemented.")
            return []
        except Exception as e:
            print(f"Error in MetadataService.get_chunks_for_file_version: {e}")
            return []

    async def get_file_content_by_version(self, *, version_id: uuid.UUID) -> Optional[str]:
        '''Retrieves and concatenates all chunks for a file version.'''
        try:
            chunks = await self.get_chunks_for_file_version(version_id=version_id)
            if not chunks:
                # Could be an empty file or version not found/no chunks
                file_version = await self.get_file_version_by_id(version_id=version_id)
                return "" if file_version else None # Return empty string for existing version with no chunks

            # Assuming content is string. If bytes, handle accordingly.
            return "".join(chunk.content for chunk in chunks if chunk.content)
        except NotImplementedError:
             print("MetadataService.get_file_content_by_version: Underlying repository method not yet implemented.")
             return None
        except Exception as e:
            print(f"Error in MetadataService.get_file_content_by_version: {e}")
            return None

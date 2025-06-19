# app/api/artifact_api.py
import uuid
from typing import Optional, List, Dict, Any, AsyncIterator
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, Request
from fastapi.responses import StreamingResponse
from app.schemas.artifact import (
    Artifact,
    ArtifactVersion,
    # We'll use this for the response of the stream upload
)
from app.schemas.user import User # Assuming user context might be needed, e.g. from auth
from app.services.session_service import SessionService
from app.api.dependencies import get_session_service # get_user_service if needed for auth
from pydantic import BaseModel # For the new response schema

# Define the response schema for the stream_content endpoint
class ArtifactStreamResponse(BaseModel):
    artifact_id: uuid.UUID
    artifact_version_id: uuid.UUID

router = APIRouter(
    prefix="/artifacts", # A common prefix for artifact related operations
    tags=["Artifacts"],
    responses={404: {"description": "Not found"}},
)

# Endpoint 1: Stream Artifact Content to Server
@router.post(
    "/sessions/{session_id}/stream_content",
    response_model=ArtifactStreamResponse,
    summary="Stream artifact content to the server",
    description="Accepts artifact metadata (name, type) as query parameters and streams artifact content from the request body. Stores content in chunks and returns artifact and version IDs."
)

async def stream_artifact_content_to_server(
    request: Request, # FastAPI's Request object to handle streaming
    session_id: uuid.UUID = Path(..., description="The ID of the session to associate the artifact with"),
    artifact_name: str = Query(..., description="The name of the artifact"),
    artifact_type: str = Query(..., description="The type of the artifact (e.g., 'canvas_state', 'generated_code_block')"),
    # user_id: uuid.UUID, # Assuming user_id will come from an auth dependency later
    version_notes: Optional[str] = Query(None, description="Optional notes for this artifact version"),
    session_service: SessionService = Depends(get_session_service)

):
    # For now, let's simulate a user_id. In a real app, this would come from an auth system.
    # This user_id should ideally be the one associated with the session_id.
    # We might need to fetch the session to get the user_id if not passed or from auth.
    temp_user_id_for_artifact_creation = uuid.uuid4() # Placeholder

    # First, get or create the artifact and its initial version
    # The user_id is passed to get_or_create_artifact_and_version as per its signature
    artifact_version_id = await session_service.get_or_create_artifact_and_version(
        session_id=session_id,
        artifact_name=artifact_name,
        artifact_type=artifact_type,
        user_id=temp_user_id_for_artifact_creation, # Pass the placeholder user_id
        version_notes=version_notes
    )

    if not artifact_version_id:
        raise HTTPException(status_code=500, detail="Could not create or retrieve artifact version")

    # Retrieve the artifact_id from the newly created/retrieved version for the response
    # This requires fetching the version, or modifying get_or_create_artifact_and_version to return both
    # For now, let's fetch the version.
    newly_created_version = await session_service.get_artifact_version_by_id(artifact_version_id=artifact_version_id)
    if not newly_created_version:
        raise HTTPException(status_code=500, detail="Failed to retrieve newly created artifact version details")

    artifact_id_for_response = newly_created_version.artifact_id

    chunk_order = 0
    try:
        async for chunk_bytes in request.stream():
            if chunk_bytes: # Ensure there's content
                content_chunk_str = chunk_bytes.decode('utf-8') # Assuming text content
                await session_service.add_chunk_to_artifact_version(
                    artifact_version_id=artifact_version_id,
                    content_chunk=content_chunk_str,
                    chunk_order=chunk_order
                )
                chunk_order += 1

        if chunk_order == 0: # No content was streamed
             # Optionally, handle this case: delete the version or artifact if it's empty?
             # For now, we allow empty artifacts if no content is streamed after metadata.
            print(f"Warning: No content chunks streamed for artifact_version_id: {artifact_version_id}")

    except Exception as e:
        # TODO: Consider cleanup if streaming fails mid-way (e.g., delete chunks or version)
        raise HTTPException(status_code=500, detail=f"Error streaming artifact content: {str(e)}")

    return ArtifactStreamResponse(
        artifact_id=artifact_id_for_response,
        artifact_version_id=artifact_version_id
    )

# Endpoint 2: Get All Artifact Versions for an Artifact in a Session
@router.get(
    "/users/{user_id}/sessions/{session_id}/artifacts/{artifact_id}/versions",
    response_model=List[ArtifactVersion],
    summary="Get all versions for a specific artifact",
    description="Retrieves a list of all versions associated with a given artifact ID, belonging to a specific user and session."
)
async def get_all_artifact_versions(
    user_id: uuid.UUID = Path(..., description="The ID of the user"), # Used for authorization/scoping
    session_id: uuid.UUID = Path(..., description="The ID of the session"), # Used for authorization/scoping
    artifact_id: uuid.UUID = Path(..., description="The ID of the artifact to get versions for"),
    session_service: SessionService = Depends(get_session_service)
):
    # Optional: Add validation here to ensure the session_id belongs to the user_id
    # and the artifact_id belongs to the session_id.
    # session = await session_service.get_session_by_id(session_id=session_id)
    # if not session or session.user_id != user_id:
    #     raise HTTPException(status_code=404, detail="Session not found or user mismatch")
    # artifact = await session_service.get_artifact_by_id(artifact_id=artifact_id)
    # if not artifact or artifact.session_id != session_id:
    #     raise HTTPException(status_code=404, detail="Artifact not found or session mismatch")

    versions = await session_service.get_artifact_versions(artifact_id=artifact_id)
    if not versions:
        # Return 200 with empty list if no versions, or 404 if artifact itself doesn't exist (current behavior is empty list)
        pass # Allow empty list to be returned
    return versions

# Endpoint 3: Stream Artifact Content from Server
@router.get(
    "/users/{user_id}/sessions/{session_id}/artifacts/versions/{version_id}/stream_content",
    summary="Stream artifact content from the server",
    description="Streams the content of a specific artifact version, chunk by chunk, for a given user and session.",
    response_class=StreamingResponse # Explicitly set for clarity, though FastAPI infers for async iterators
)
async def stream_artifact_content_from_server(
    user_id: uuid.UUID = Path(..., description="The ID of the user"), # Used for authorization/scoping
    session_id: uuid.UUID = Path(..., description="The ID of the session"), # Used for authorization/scoping
    version_id: uuid.UUID = Path(..., description="The ID of the artifact version to stream"),
    session_service: SessionService = Depends(get_session_service)
):
    # Optional: Add validation similar to Endpoint 2 to ensure entities are related correctly.
    # E.g., fetch version, then artifact, then session, and check IDs match up with path params.
    # artifact_version = await session_service.get_artifact_version_by_id(artifact_version_id=version_id)
    # if not artifact_version:
    #     raise HTTPException(status_code=404, detail="Artifact version not found")
    # ... further checks for artifact_id, session_id, user_id

    async def content_streamer():
        async for content_chunk in session_service.get_artifact_chunks_stream(artifact_version_id=version_id):
            yield content_chunk

    return StreamingResponse(content_streamer(), media_type="text/plain") # Adjust media_type if not plain text

# app/api/user_api.py
import uuid
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from app.schemas.user import User, UserCreate, UserUpdate
from app.services.user_service import UserService
from app.api.dependencies import get_user_service
from pydantic import EmailStr


router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={404: {"description": "Not found"}},
)

@router.post("/", response_model=User, status_code=201)
async def create_user_endpoint(
    user_in: UserCreate,
    user_service: UserService = Depends(get_user_service)
):
    '''
    Create a new user.
    This might be used by admin interfaces or specific backend processes.
    For user registration tied to Supabase Auth, prefer get_or_create_on_login_via_supabase_id.
    '''
    user = await user_service.create_user(user_in=user_in)
    if not user:
        # This condition might be hit if user_service.create_user returns None
        # e.g., due to repository error or if it finds an existing user and returns None (adjust service logic as needed)
        # For now, assuming if create_user returns None, it's an issue.
        # If create_user can return an existing user, the status code/response might change.
        raise HTTPException(status_code=400, detail="User could not be created or already exists with this Supabase ID.")
    return user

@router.get("/me", response_model=User)
async def read_users_me(
    # Here you would typically have a dependency that gets the current user
    # based on an auth token (e.g., from Supabase Auth).
    # For now, let's simulate it by requiring a supabase_user_id,
    # though this is NOT how actual "me" endpoints work with auth.
    # This is more like a "get_my_user_record_if_i_tell_you_my_supabase_id"
    supabase_user_id: str, # In a real app, this comes from decoded token
    email: Optional[str] = None, # Email might be needed if creating for the first time
    user_service: UserService = Depends(get_user_service)
):
    '''
    Simulates fetching the current authenticated user's details.
    In a real app, supabase_user_id would come from an auth token.
    This endpoint will try to get or create the user in the local DB.
    '''
    # This simulates a common pattern: on frontend login via Supabase,
    # the frontend gets a Supabase user ID. It then calls a backend endpoint like this
    # to ensure a corresponding user record exists in the application's database.
    user = await user_service.get_or_create_user_by_supabase_id(
        supabase_user_id=supabase_user_id,
        email=email # Provide email in case the user needs to be created
    )
    if not user:
        raise HTTPException(status_code=404, detail=f"User with Supabase ID {supabase_user_id} not found and could not be created. Email might be required if new.")
    return user

@router.get("/{user_id}", response_model=User)
async def get_user_by_id_endpoint(
    user_id: uuid.UUID,
    user_service: UserService = Depends(get_user_service)
):
    '''
    Retrieve a user by their internal application UUID.
    '''
    user = await user_service.get_user_by_id(user_id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.get("/supabase/{supabase_user_id}", response_model=User)
async def get_user_by_supabase_id_endpoint(
    supabase_user_id: str,
    user_service: UserService = Depends(get_user_service)
):
    '''
    Retrieve a user by their Supabase User ID. Does not create if not found.
    '''
    user = await user_service.get_user_by_supabase_id(supabase_user_id=supabase_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User with specified Supabase ID not found")
    return user

@router.put("/{user_id}", response_model=User)
async def update_user_endpoint(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    user_service: UserService = Depends(get_user_service)
):
    '''
    Update a user's details by their internal application UUID.
    '''
    user = await user_service.update_user(user_id=user_id, user_in=user_in)
    if not user:
        raise HTTPException(status_code=404, detail="User not found or update failed")
    return user

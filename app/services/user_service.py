# app/services/user_service.py
import uuid
from typing import Optional
from app.db.unit_of_work import UnitOfWork
from app.schemas.user import User, UserCreate, UserUpdate
from pydantic import EmailStr

class UserService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def get_user_by_id(self, *, user_id: uuid.UUID) -> Optional[User]:
        '''Retrieves a user by their internal ID.'''
        try:
            return await self.uow.users.get(id=user_id)
        except NotImplementedError:
            print("UserService.get_user_by_id: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in UserService.get_user_by_id: {e}")
            return None

    async def get_user_by_supabase_id(self, *, supabase_user_id: str) -> Optional[User]:
        '''Retrieves a user by their Supabase User ID.'''
        try:
            return await self.uow.users.get_by_attribute(attribute="supabase_user_id", value=supabase_user_id)
        except NotImplementedError:
            print("UserService.get_user_by_supabase_id: Repository method not yet implemented.")
            return None
        except Exception as e:
            print(f"Error in UserService.get_user_by_supabase_id: {e}")
            return None

    async def get_or_create_user_by_supabase_id(
        self, *, supabase_user_id: str, email: Optional[str] = None
    ) -> Optional[User]:
        '''Retrieves a user by their Supabase User ID, creating them if they don't exist.'''
        async with self.uow:
            try:
                user = await self.uow.users.get_by_attribute(attribute="supabase_user_id", value=supabase_user_id)
                if user:
                    return user

                if not email:
                    print("UserService.get_or_create_user_by_supabase_id: Email is required to create a new user if not found and email is part of UserCreate schema.")
                    raise ValueError("Email is required to create a new user under current schema assumptions.")

                user_create_data = UserCreate(supabase_user_id=supabase_user_id, email=email)
                new_user = await self.uow.users.create(obj_in=user_create_data)
                return new_user
            except NotImplementedError:
                print("UserService.get_or_create_user_by_supabase_id: Repository method not yet implemented.")
                return None
            except ValueError as ve:
                print(f"UserService.get_or_create_user_by_supabase_id: {ve}")
                return None
            except Exception as e:
                print(f"Error in UserService.get_or_create_user_by_supabase_id: {e}")
                return None

    async def update_user(self, *, user_id: uuid.UUID, user_in: UserUpdate) -> Optional[User]:
        '''Updates an existing user.'''
        async with self.uow:
            try:
                updated_user = await self.uow.users.update(id=user_id, obj_in=user_in)
                return updated_user
            except NotImplementedError:
                print("UserService.update_user: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in UserService.update_user: {e}")
                return None

    async def create_user(self, *, user_in: UserCreate) -> Optional[User]:
        '''
        Creates a new user.
        Generally, get_or_create_user_by_supabase_id is preferred if dealing with Supabase Auth.
        This provides a direct creation path if needed.
        '''
        async with self.uow:
            try:
                existing_user = await self.uow.users.get_by_attribute(attribute="supabase_user_id", value=user_in.supabase_user_id)
                if existing_user:
                    print(f"UserService.create_user: User with supabase_user_id {user_in.supabase_user_id} already exists.")
                    return existing_user

                new_user = await self.uow.users.create(obj_in=user_in)
                return new_user
            except NotImplementedError:
                print("UserService.create_user: Repository method not yet implemented.")
                return None
            except Exception as e:
                print(f"Error in UserService.create_user: {e}")
                return None

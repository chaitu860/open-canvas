# app/db/base_repository.py
from typing import TypeVar, Generic, List, Optional, Any, Dict
from pydantic import BaseModel
import uuid
from supabase import Client
from supabase.lib.client_options import ClientOptions # For type hinting if needed, though Client is primary
from postgrest import APIError # For catching Supabase errors

ModelType = TypeVar("ModelType", bound=BaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, supabase_client: Client, model_class: type[ModelType], table_name: str):
        self.client: Client = supabase_client
        self.model_class = model_class
        self.table_name = table_name
        self.table = self.client.table(table_name)

    async def create(self, *, obj_in: CreateSchemaType) -> Optional[ModelType]:
        try:
            data_to_insert = obj_in.model_dump()
            # Supabase expects UUIDs as strings
            for key, value in data_to_insert.items():
                if isinstance(value, uuid.UUID):
                    data_to_insert[key] = str(value)

            response = self.table.insert(data_to_insert).execute()
            if response.data:
                return self.model_class(**response.data[0])
            return None
        except APIError as e:
            print(f"Supabase API Error in create for table {self.table_name}: {e}")
            # Optionally re-raise or handle specific errors
            return None
        except Exception as e:
            print(f"Unexpected error in create for table {self.table_name}: {e}")
            return None

    async def get(self, *, id: uuid.UUID) -> Optional[ModelType]:
        try:
            response = self.table.select("*").eq("id", str(id)).execute()
            if response.data:
                return self.model_class(**response.data[0])
            return None
        except APIError as e:
            print(f"Supabase API Error in get for table {self.table_name} with id {id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in get for table {self.table_name} with id {id}: {e}")
            return None

    async def get_multi(
        self, *, skip: int = 0, limit: int = 100, filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        try:
            query = self.table.select("*")
            if filters:
                for key, value in filters.items():
                    # Handle UUIDs in filters
                    processed_value = str(value) if isinstance(value, uuid.UUID) else value
                    query = query.eq(key, processed_value)

            # Supabase uses range for pagination, not offset directly in this version of API
            # range is inclusive, so (skip, skip + limit - 1)
            response = query.range(skip, skip + limit - 1).execute()

            if response.data:
                return [self.model_class(**item) for item in response.data]
            return []
        except APIError as e:
            print(f"Supabase API Error in get_multi for table {self.table_name}: {e}")
            return []
        except Exception as e:
            print(f"Unexpected error in get_multi for table {self.table_name}: {e}")
            return []

    async def update(self, *, id: uuid.UUID, obj_in: UpdateSchemaType) -> Optional[ModelType]:
        try:
            data_to_update = obj_in.model_dump(exclude_unset=True)
            if not data_to_update:
                # If nothing to update after excluding unset, maybe return current object or error
                print(f"Warning: Update called for id {id} in {self.table_name} with no values to update.")
                return await self.get(id=id) # Or handle as an error/None

            # Supabase expects UUIDs as strings
            for key, value in data_to_update.items():
                if isinstance(value, uuid.UUID):
                    data_to_update[key] = str(value)

            response = self.table.update(data_to_update).eq("id", str(id)).execute()
            if response.data:
                return self.model_class(**response.data[0])
            return None # Or raise error if update affected 0 rows but expected 1
        except APIError as e:
            print(f"Supabase API Error in update for table {self.table_name} with id {id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in update for table {self.table_name} with id {id}: {e}")
            return None

    async def delete(self, *, id: uuid.UUID) -> Optional[ModelType]:
        try:
            # Optionally, first fetch the item to return it, as delete might not return the full object
            item_to_delete = await self.get(id=id)
            if not item_to_delete:
                return None # Item not found

            response = self.table.delete().eq("id", str(id)).execute()
            # Check response.data or response.status_code to confirm deletion
            # Supabase delete often returns the deleted records in response.data
            if response.data: # If Supabase returns the deleted record
                 return self.model_class(**response.data[0])
            # If not, but deletion was successful (e.g. check status or if item_to_delete existed)
            # and if Supabase doesn't return data on delete, we can return the fetched 'item_to_delete'
            # This part depends on the exact behavior of supabase-py delete version
            # For now, assuming response.data contains the deleted item if successful.
            return item_to_delete # Fallback, assuming successful if no APIError
        except APIError as e:
            print(f"Supabase API Error in delete for table {self.table_name} with id {id}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in delete for table {self.table_name} with id {id}: {e}")
            return None

    async def get_by_attribute(self, *, attribute: str, value: Any) -> Optional[ModelType]:
        try:
            processed_value = str(value) if isinstance(value, uuid.UUID) else value
            response = self.table.select("*").eq(attribute, processed_value).limit(1).execute() # Ensure only one record
            if response.data:
                return self.model_class(**response.data[0])
            return None
        except APIError as e:
            print(f"Supabase API Error in get_by_attribute for table {self.table_name} ({attribute}={value}): {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in get_by_attribute for table {self.table_name} ({attribute}={value}): {e}")
            return None

    async def get_multi_by_attribute(self, *, attribute: str, value: Any, skip: int = 0, limit: int = 100) -> List[ModelType]:
        try:
            processed_value = str(value) if isinstance(value, uuid.UUID) else value
            query = self.table.select("*").eq(attribute, processed_value)
            response = query.range(skip, skip + limit - 1).execute()
            if response.data:
                return [self.model_class(**item) for item in response.data]
            return []
        except APIError as e:
            print(f"Supabase API Error in get_multi_by_attribute for table {self.table_name} ({attribute}={value}): {e}")
            return []
        except Exception as e:
            print(f"Unexpected error in get_multi_by_attribute for table {self.table_name} ({attribute}={value}): {e}")
            return []

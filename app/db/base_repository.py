# app/db/base_repository.py

from typing import TypeVar, Generic, List, Optional, Any, Dict
from pydantic import BaseModel
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from app.db.supabase_client import get_postgres_connection  # renamed but same idea

ModelType = TypeVar("ModelType", bound=BaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model_class: type[ModelType], table_name: str):
        self.conn = get_postgres_connection()
        self.model_class = model_class
        self.table_name = table_name

    async def create(self, *, obj_in: CreateSchemaType) -> Optional[ModelType]:
        try:
            data = obj_in.model_dump()
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['%s'] * len(data))
            values = list(data.values())

            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders}) RETURNING *"
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                result = cur.fetchone()
                self.conn.commit()
                return self.model_class(**result) if result else None
        except Exception as e:
            print(f"Error in create: {e}")
            return None

    async def get(self, *, id: uuid.UUID) -> Optional[ModelType]:
        try:
            query = f"SELECT * FROM {self.table_name} WHERE id = %s"
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (str(id),))
                result = cur.fetchone()
                return self.model_class(**result) if result else None
        except Exception as e:
            print(f"Error in get: {e}")
            return None

    async def get_multi(
        self, *, skip: int = 0, limit: int = 100, filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        try:
            where_clause = ''
            values = []

            if filters:
                clauses = []
                for key, value in filters.items():
                    clauses.append(f"{key} = %s")
                    values.append(str(value) if isinstance(value, uuid.UUID) else value)
                where_clause = 'WHERE ' + ' AND '.join(clauses)

            query = f"""
                SELECT * FROM {self.table_name}
                {where_clause}
                OFFSET %s LIMIT %s
            """
            values.extend([skip, limit])

            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, tuple(values))
                results = cur.fetchall()
                return [self.model_class(**row) for row in results]
        except Exception as e:
            print(f"Error in get_multi: {e}")
            return []

    async def update(self, *, id: uuid.UUID, obj_in: UpdateSchemaType) -> Optional[ModelType]:
        try:
            data = obj_in.model_dump(exclude_unset=True)
            if not data:
                print("No values to update.")
                return await self.get(id=id)

            set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
            values = list(data.values()) + [str(id)]

            query = f"""
                UPDATE {self.table_name}
                SET {set_clause}
                WHERE id = %s
                RETURNING *
            """
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, values)
                result = cur.fetchone()
                self.conn.commit()
                return self.model_class(**result) if result else None
        except Exception as e:
            print(f"Error in update: {e}")
            return None

    async def delete(self, *, id: uuid.UUID) -> Optional[ModelType]:
        try:
            item = await self.get(id=id)
            if not item:
                return None

            query = f"DELETE FROM {self.table_name} WHERE id = %s RETURNING *"
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (str(id),))
                result = cur.fetchone()
                self.conn.commit()
                return self.model_class(**result) if result else item
        except Exception as e:
            print(f"Error in delete: {e}")
            return None

    async def get_by_attribute(self, *, attribute: str, value: Any) -> Optional[ModelType]:
        try:
            query = f"SELECT * FROM {self.table_name} WHERE {attribute} = %s LIMIT 1"
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (str(value) if isinstance(value, uuid.UUID) else value,))
                result = cur.fetchone()
                return self.model_class(**result) if result else None
        except Exception as e:
            print(f"Error in get_by_attribute: {e}")
            return None

    async def get_multi_by_attribute(
        self, *, attribute: str, value: Any, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        try:
            query = f"""
                SELECT * FROM {self.table_name}
                WHERE {attribute} = %s
                OFFSET %s LIMIT %s
            """
            values = [str(value) if isinstance(value, uuid.UUID) else value, skip, limit]
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, tuple(values))
                results = cur.fetchall()
                return [self.model_class(**row) for row in results]
        except Exception as e:
            print(f"Error in get_multi_by_attribute: {e}")
            return []

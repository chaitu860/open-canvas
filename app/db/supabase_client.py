# app/db/supabase_client.py

import os
import psycopg2
from psycopg2.extensions import connection as PGConnection
from typing import Optional
from app.config.settings import settings

postgres_connection: Optional[PGConnection] = None

def init_postgres_connection() -> PGConnection:
    '''
    Initializes a direct connection to Supabase Postgres.
    Raises ValueError if credentials are not set.
    '''
    global postgres_connection

    required = [
        settings.DB_HOST,
        settings.DB_NAME,
        settings.DB_USER,
        settings.DB_PASSWORD
    ]
    if not all(required):
        raise ValueError("Postgres connection details are not properly configured in settings.")

    try:
        postgres_connection = psycopg2.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT or 5432,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
        )
        print("Postgres connection initialized successfully.")
        return postgres_connection
    except Exception as e:
        print("Error connecting to Postgres:", e)
        raise ConnectionError(f"Failed to connect to Postgres: {e}")

def get_postgres_connection() -> PGConnection:
    '''
    Returns the initialized Postgres connection.
    Initializes it if it hasn't been already.
    '''
    global postgres_connection
    if postgres_connection is None:
        print("Postgres connection not initialized. Attempting to initialize now.")
        init_postgres_connection()

    if postgres_connection is None:
        raise ConnectionError("Postgres connection could not be initialized. Check configurations.")

    return postgres_connection

# app/db/supabase_client.py
import os
from supabase import create_client, Client
from app.config.settings import settings # Import your app settings
from typing import Optional # Added for Python < 3.9 compatibility with Optional[Client]

supabase_client: Optional[Client] = None

def init_supabase_client() -> Client:
    '''
    Initializes the Supabase client using credentials from settings.
    Raises ValueError if credentials are not set.
    '''
    global supabase_client
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        print("Supabase client initialized successfully.")
        return supabase_client
    else:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment variables / .env file.")
        raise ValueError("Supabase URL and Service Role Key not configured.")

def get_supabase_client() -> Client:
    '''
    Returns the initialized Supabase client.
    Initializes it if it hasn't been already.
    '''
    global supabase_client
    if supabase_client is None:
        # This ensures that if the client is not explicitly initialized at startup,
        # the first call to get_supabase_client will attempt to initialize it.
        # Depending on application structure, explicit initialization at startup might be preferred.
        print("Supabase client not initialized. Attempting to initialize now.")
        init_supabase_client()

    if supabase_client is None: # Check again after init attempt
        # This case should ideally not be reached if init_supabase_client raises ValueError
        # but as a safeguard:
        raise ConnectionError("Supabase client could not be initialized. Check configurations.")

    return supabase_client

# Optional: You might want to initialize the client when this module is loaded
# or explicitly call init_supabase_client() in your main application startup.
# For example, in app/main.py:
# from app.db.supabase_client import init_supabase_client
# @app.on_event("startup")
# async def startup_event():
#     init_supabase_client()

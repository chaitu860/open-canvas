# app/api/dependencies.py
from app.db.unit_of_work import UnitOfWork
from app.services.user_service import UserService
from app.services.metadata_service import MetadataService
from app.services.session_service import SessionService
from app.db.supabase_client import init_supabase_client, get_supabase_client

# Ensure Supabase client is initialized (ideally at app startup, but also on first use here)
# This is a simplified approach for dependency injection.
# In a larger app, you might use a more sophisticated DI framework or structure.

_supabase_client = None

def get_db_client():
    global _supabase_client
    if _supabase_client is None:
        try:
            _supabase_client = get_supabase_client() # get_supabase_client handles init if needed
        except ValueError as e: # Raised by init_supabase_client if config is missing
            print(f"Dependency Error: Supabase client could not be initialized: {e}")
            # Depending on how strict you want to be, you could re-raise or handle
            # For now, this will cause UoW to fail if client is None.
            raise RuntimeError(f"Supabase configuration error: {e}") from e
        except ConnectionError as e: # Raised by get_supabase_client if init fails
            print(f"Dependency Error: Supabase client connection error: {e}")
            raise RuntimeError(f"Supabase connection error: {e}") from e
    return _supabase_client

def get_unit_of_work() -> UnitOfWork:
    # This creates a new UoW instance for each request that needs it.
    # The UoW itself gets the Supabase client.
    # If Supabase client init fails in get_supabase_client(), it will raise an error here.
    return UnitOfWork() # UoW's __init__ now calls get_supabase_client()

async def get_user_service() -> UserService:
    # UoW is created per request effectively via this dependency structure.
    # Each service gets its own UoW instance.
    # If services needed to share a UoW for a single request, a different pattern would be needed
    # (e.g., a single UoW dependency passed to each service dependency).
    # For now, this is simple: each service method operates in its own UoW context.
    return UserService(uow=get_unit_of_work())

async def get_metadata_service() -> MetadataService:
    return MetadataService(uow=get_unit_of_work())

async def get_session_service() -> SessionService:
    # SessionService constructor currently only takes uow.
    # If it needed other services, they'd be resolved here too.
    # e.g., SessionService(uow=get_unit_of_work(), user_service=await get_user_service())
    return SessionService(uow=get_unit_of_work())

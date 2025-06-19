# app/api/dependencies.py
from app.db.unit_of_work import UnitOfWork
from app.services.user_service import UserService
from app.services.metadata_service import MetadataService
from app.services.session_service import SessionService

# Ensure Supabase client is initialized (ideally at app startup, but also on first use here)
# This is a simplified approach for dependency injection.
# In a larger app, you might use a more sophisticated DI framework or structure.



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

# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # Added
from app.api import user_api # Assuming user_api.py is in app/api/
from app.api import artifact_api # Import for the new artifact API
from app.db.supabase_client import init_postgres_connection # For explicit init at startup
from app.api.agent import router as agent_router


app = FastAPI(title="LangGraph Agent Server - Python Edition")

# ... FastAPI app initialization ...
# app = FastAPI(...)

@app.on_event("startup")
async def startup_event():
    print("Application startup: Initializing Supabase client...")
    try:
        init_postgres_connection()  # Initialize the Postgres connection
        print("Supabase client initialization successful from startup event.")
    except ValueError as e: # From init_supabase_client if config missing
        print(f"CRITICAL ERROR: Supabase client could not be initialized at startup: {e}")
        # Optionally, prevent app from starting or run in a degraded mode
    except Exception as e:
        print(f"CRITICAL ERROR: Unexpected error during Supabase client initialization at startup: {e}")

# --- CORS Configuration ---
# Adjust origins for production if needed.
# The Next.js frontend (apps/web) typically runs on http://localhost:3000 during development.
# The LangGraph TypeScript server was on port 54367.
# The FastAPI server might run on port 8000 by default with uvicorn.
origins = [
    "http://localhost:3000", # Typical Next.js dev port
    "http://localhost:54367",# Old LangGraph TS server port (if frontend still points there sometimes)
    "*" # Allow all for broad development, tighten for production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Allow cookies if your auth mechanism uses them
    allow_methods=["*"],    # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],    # Allow all headers
)
# --- End CORS Configuration ---

@app.get("/")
async def root():
    return {"message": "LangGraph Agent Server is running"}

app.include_router(agent_router, prefix="/api/agent")
app.include_router(user_api.router)
app.include_router(artifact_api.router) # Add the artifact API router
# Make sure agent_router is also included if it was there
# app.include_router(agent_router, prefix="/api/agent")

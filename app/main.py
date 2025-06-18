# app/main.py
from fastapi import FastAPI
from app.api.agent import router as agent_router # Modified import

app = FastAPI(title="LangGraph Agent Server")

@app.get("/")
async def root():
    return {"message": "LangGraph Agent Server is running"}

app.include_router(agent_router, prefix="/api/agent") # Modified to add /agent prefix

# app/agents/thread_title_graph/schemas.py
from pydantic import BaseModel, Field

class GenerateTitleToolSchema(BaseModel):
    title: str = Field(..., description="The generated concise and descriptive title for the conversation.")

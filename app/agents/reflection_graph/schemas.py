# app/agents/reflection_graph/schemas.py
from typing import List
from pydantic import BaseModel, Field

class GenerateReflectionsToolSchema(BaseModel):
    styleRules: List[str] = Field(..., description="The complete new list of style rules and guidelines for the user.")
    content: List[str] = Field(..., description="The complete new list of memories, facts, and insights about the user based on the conversation.")

class ReflectionsData(BaseModel):
    styleRules: List[str] = []
    content: List[str] = []

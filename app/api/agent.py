# app/api/agent.py
from fastapi import APIRouter, HTTPException, Path, Body
from app.schemas.agent import (
    AgentInvokeRequest,
    AgentInvokeResponse,
    AgentStatus,
    AgentHistory,
    AgentTools,
    ToolDefinition,
    Message,
    Configurable
)
from typing import Any, Dict, Optional
import uuid

router = APIRouter()

@router.post("/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(
    payload: AgentInvokeRequest = Body(...)
):
    # Placeholder: Actual agent invocation logic will go here
    print(f"Received input: {payload.input}")
    print(f"Received config: {payload.config}")
    # Example of accessing configurable fields
    if payload.config and 'configurable' in payload.config:
        configurable_data = payload.config['configurable']
        print(f"Supabase User ID: {configurable_data.get('supabase_user_id')}")
        print(f"Thread ID: {configurable_data.get('thread_id')}")

    run_id = str(uuid.uuid4())
    return AgentInvokeResponse(output={"message": "Agent invoked successfully", "input_received": payload.input}, run_id=run_id)

@router.get("/status/{run_id}", response_model=AgentStatus)
async def get_agent_status(
    run_id: str = Path(..., title="The ID of the agent run")
):
    # Placeholder: Actual status retrieval logic will go here
    print(f"Fetching status for run_id: {run_id}")
    # Simulate different statuses
    if run_id == "test_completed_id":
        return AgentStatus(run_id=run_id, status="completed", output={"result": "This is a completed result"})
    elif run_id == "test_running_id":
        return AgentStatus(run_id=run_id, status="running")
    else:
        return AgentStatus(run_id=run_id, status="unknown")


@router.get("/history/{workspace}", response_model=AgentHistory)
async def get_agent_history(
    workspace: str = Path(..., title="The workspace to fetch history from")
):
    # Placeholder: Actual history retrieval logic will go here
    print(f"Fetching history for workspace: {workspace}")
    return AgentHistory(
        workspace=workspace,
        history=[
            Message(type="human", content="Hello"),
            Message(type="ai", content="Hi there!"),
        ]
    )

@router.get("/tools", response_model=AgentTools)
async def get_agent_tools():
    # Placeholder: Actual tool listing logic will go here
    print("Fetching available tools")
    return AgentTools(
        tools=[
            ToolDefinition(name="search", description="Performs a web search."),
            ToolDefinition(name="calculator", description="Calculates mathematical expressions."),
        ]
    )

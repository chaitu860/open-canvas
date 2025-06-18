# app/api/agent.py
from fastapi import APIRouter, HTTPException, Path, Body
from schemas.agent import (
    AgentInvokeRequest,
    AgentInvokeResponse,
    AgentStatus,
    AgentHistory,
    AgentTools,
    ToolDefinition,
    Message,
    Configurable # Used in AgentInvokeRequest
)
from typing import Any, Dict, Optional
import uuid
from services.agent_service import AgentService # Import AgentService
from fastapi.responses import StreamingResponse
import json # For SSE streaming
from langchain_core.messages import HumanMessage # To create initial message for graph

router = APIRouter()
agent_service_instance = AgentService() # Instantiate the service

def serialize_event(obj):
    """
    Recursively convert LangChain message objects and other non-serializables to dicts.
    """
    if isinstance(obj, list):
        return [serialize_event(item) for item in obj]
    if hasattr(obj, "dict"):  # Pydantic or similar
        return obj.dict()
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        # For LangChain messages and similar
        d = obj.__dict__.copy()
        d["__type__"] = obj.__class__.__name__
        return {k: serialize_event(v) for k, v in d.items()}
    if isinstance(obj, dict):
        return {k: serialize_event(v) for k, v in obj.items()}
    return obj

# The response for streaming is different. We'll stream JSON events.
@router.post("/invoke")
async def invoke_agent(
    payload: AgentInvokeRequest = Body(...),
    # assistant_id and thread_id are now primarily derived from payload.config.configurable
    # or defaults if not provided there.
):
    # Default/placeholder values if not provided in request config's configurable section.
    # In a real app, assistant_id might be static or from env. thread_id from client if resuming.
    assistant_id = "default_assistant"
    # For a new conversation, a new thread_id is typically generated.
    # If resuming an existing conversation, the client would pass the thread_id.
    thread_id = str(uuid.uuid4())
    print(payload.config)
    configurable_payload_from_request: Optional[Dict[str, Any]] = None
    if payload.config and "configurable" in payload.config and isinstance(payload.config["configurable"], dict):
        configurable_payload_from_request = payload.config["configurable"]
        # Allow assistant_id and thread_id to be overridden by the request's config.configurable
        assistant_id = configurable_payload_from_request.get("assistant_id", assistant_id)
        thread_id = configurable_payload_from_request.get("thread_id", thread_id)
        print(f"API: Using assistant_id='{assistant_id}', thread_id='{thread_id}' from request config.")
    else:
        print(f"API: Using default assistant_id='{assistant_id}', generated thread_id='{thread_id}'.")


    # Prepare graph_invoke_payload for the service.
    # This includes the initial message and any other direct graph inputs from the payload.
    initial_messages = [HumanMessage(content=payload.input)]
    graph_invoke_payload: Dict[str, Any] = {"messages": initial_messages}

    # Pass other relevant parts of payload.config (excluding 'configurable' itself, which is handled separately)
    # These could be direct graph inputs or specific settings like 'modelConfig', 'systemPrompt'.
    if payload.config:
        # Handle direct graph inputs (e.g., for starting a specific flow)
        direct_graph_inputs_from_config_keys = [
            "customQuickActionId", "highlightedCode", "highlightedText",
            "language", "artifactLength", "regenerateWithEmojis",
            "readingLevel", "addComments", "addLogs", "portLanguage", "fixBugs",
            "webSearchEnabled"
        ]
        for key in direct_graph_inputs_from_config_keys:
            if key in payload.config and payload.config[key] is not None:
                graph_invoke_payload[key] = payload.config[key]

        # Handle 'modelConfig' and 'systemPrompt' if they are at the top level of payload.config
        # The AgentService expects these at the top level of its `input_payload`
        if "modelConfig" in payload.config:
            graph_invoke_payload["modelConfig"] = payload.config["modelConfig"]
        if "systemPrompt" in payload.config:
            graph_invoke_payload["systemPrompt"] = payload.config["systemPrompt"]

    async def event_publisher():
        async for event in agent_service_instance.invoke_agent_stream(
            graph_input_payload=graph_invoke_payload,
            assistant_id=assistant_id,
            thread_id=thread_id,
            request_config_extras=configurable_payload_from_request
        ):
            # Serialize event before yielding
            yield f"data: {json.dumps(serialize_event(event))}\n\n" # SSE format

    return StreamingResponse(event_publisher(), media_type="text/event-stream")

@router.get("/status/{run_id}", response_model=AgentStatus) # run_id here is more like a thread_id concept for state
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

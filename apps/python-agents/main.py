from fastapi import FastAPI, HTTPException
import uvicorn
import os
from dotenv import load_dotenv
from typing import Dict, Any, List

from .models import GraphInput, OpenCanvasGraphState, ArtifactV3 # Assuming models.py is in the same directory
# Import node functions as they are created, e.g.:
# from .agent_graph.generate_path import generate_path_node
# from .agent_graph.reply_to_general_input import reply_to_general_input_node
# ... other nodes

# Import utility functions that might be used directly in main orchestration
from .utils import get_model_config # Example

load_dotenv()

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Python Agents Server is Running"}

@app.post("/agent/invoke", response_model=OpenCanvasGraphState) # Or a more specific output model
async def invoke_agent_graph(graph_input: GraphInput, runnable_config: Dict[str, Any] = None):
    # runnable_config would simulate LangGraphRunnableConfig, passed via request or constructed
    # For now, let's assume it's part of the request or a default is created.
    # It should contain 'configurable' dict with 'assistant_id', 'customModelName', 'modelConfig', 'systemPrompt', 'supabase_session' etc.

    if runnable_config is None:
        # Create a default or example config. In real scenario, this should come from the request
        # or be properly initialized based on user session, environment, etc.
        # This is a simplified placeholder.
        runnable_config = {
            "configurable": {
                "assistant_id": "default_assistant",
                "customModelName": os.getenv("DEFAULT_MODEL_NAME", "gpt-3.5-turbo"), # Ensure a default
                "modelConfig": None, # Will be loaded by get_model_config if this is None
                                     # or should be an instance of CustomModelConfig from models.py
                "systemPrompt": None,
                "supabase_session": None, # Populated from auth if available
                # Potentially add 'reflections_data' and 'context_documents' here if they are global to the graph call
            }
        }
        # Example: Load actual model config if not provided
        # This is a bit of a chicken-and-egg, modelConfig should ideally be part of runnable_config.configurable
        # model_details = get_model_config(runnable_config) # get_model_config needs 'customModelName'
        # if model_details.get("modelConfig"):
        #    runnable_config["configurable"]["modelConfig"] = model_details["modelConfig"]


    # 1. Initialize state from GraphInput
    # messages in GraphInput are generic dicts, _messages in OpenCanvasGraphState are also List[Dict]
    # ArtifactV3 is compatible.
    current_state = OpenCanvasGraphState(
        messages=graph_input.messages if graph_input.messages is not None else [],
        _messages=graph_input.messages if graph_input.messages is not None else [], # Initial _messages often same as messages
        highlightedCode=graph_input.highlightedCode,
        highlightedText=graph_input.highlightedText,
        artifact=graph_input.artifact,
        next_node=graph_input.next_node, # 'next' in GraphInput, 'next_node' in OpenCanvasGraphState
        language=graph_input.language,
        artifactLength=graph_input.artifactLength,
        regenerateWithEmojis=graph_input.regenerateWithEmojis,
        readingLevel=graph_input.readingLevel,
        addComments=graph_input.addComments,
        addLogs=graph_input.addLogs,
        portLanguage=graph_input.portLanguage,
        fixBugs=graph_input.fixBugs,
        customQuickActionId=graph_input.customQuickActionId,
        webSearchEnabled=graph_input.webSearchEnabled,
        webSearchResults=graph_input.webSearchResults
    )

    # 2. Define the graph execution flow (simplified)
    # This will be a loop, calling node functions based on current_state.next_node
    # MAX_TURNS to prevent infinite loops
    MAX_TURNS = 15
    turns = 0

    # Entry point: if next_node is not set, it usually starts with "generatePath"
    if not current_state.next_node:
         current_state.next_node = "generatePath" # Matches START edge in LangGraph

    # These would be the actual imported node functions
    # For now, placeholders.
    node_functions = {
        # "generatePath": generate_path_node,
        # "replyToGeneralInput": reply_to_general_input_node,
        # ... etc.
    }

    print(f"Starting graph with initial state: {current_state.dict(exclude_none=True)}")
    print(f"Initial next_node: {current_state.next_node}")


    # Main graph loop
    while current_state.next_node and current_state.next_node != "END" and turns < MAX_TURNS:
        turns += 1
        current_node_name = current_state.next_node
        current_state.next_node = None # Consume the 'next' directive

        print(f"Turn {turns}: Executing node -> {current_node_name}")

        node_function = node_functions.get(current_node_name)
        if not node_function:
            # If no specific node function, assume it's a general purpose or needs routing.
            # For this mock, we'll just end if a specific node isn't in our small 'node_functions' map.
            # In a real graph, this might go to a generic handler or an error node.
            print(f"Node '{current_node_name}' not found in mock node_functions. Setting next_node to END.")
            update = {"next_node": "END", "_messages": current_state._messages + [{"role": "assistant", "content": f"Mock response: Node {current_node_name} not explicitly handled, ending."}]}
        else:
            # This block would be for nodes found in node_functions, but it's currently empty.
            # The mock logic below handles 'generatePath' as an example.
            # We should consolidate the mock logic.
            # For now, this path won't be hit if node_functions is empty.
            pass # Fall through to the mock logic further down if node_function was None (which it will be for now)


        # --- MOCK NODE EXECUTION (Consolidated) ---
        # This simulates a node being called, even if it's not in the empty node_functions map
        # current_node_name is the one we are trying to execute

        mock_update: Dict[str, Any] = {}
        if current_node_name == "generatePath":
             print(f"Mocking {current_node_name}. Setting next_node to replyToGeneralInput as an example.")
             mock_update = {"next_node": "replyToGeneralInput", "_messages": current_state._messages + [{"role": "assistant", "content": f"Mock response from {current_node_name}"}]}
        elif current_node_name == "replyToGeneralInput":
             print(f"Mocking {current_node_name}. Setting next_node to END.")
             mock_update = {"next_node": "END", "_messages": current_state._messages + [{"role": "assistant", "content": f"Mock response from {current_node_name}"}]}
        else: # Default for any other node not explicitly mocked above
             print(f"Mocking unspecific node {current_node_name}. Setting next_node to END.")
             mock_update = {"next_node": "END", "_messages": current_state._messages + [{"role": "assistant", "content": f"Mock response from unspecific node {current_node_name}"}]}
        # --- END MOCK NODE EXECUTION ---

        update_to_apply = mock_update # In real scenario, this would be: await node_function(current_state, runnable_config)

        print(f"Node {current_node_name} (mocked) produced update: {update_to_apply}")

        # Update the state (Simplified)
        for key, value in update_to_apply.items():
            if hasattr(current_state, key):
                if key == "_messages" and isinstance(getattr(current_state, key), list) and isinstance(value, list):
                    setattr(current_state, key, value) # Assume nodes provide full new list for _messages
                elif key == "messages" and isinstance(getattr(current_state, key), list) and isinstance(value, list):
                    setattr(current_state, key, value) # Assume nodes provide full new list for messages
                else:
                    setattr(current_state, key, value)
            else:
                print(f"Warning: Trying to update non-existent key '{key}' in state.")

        if "next_node" in update_to_apply and update_to_apply["next_node"] is not None:
             current_state.next_node = update_to_apply["next_node"]
        elif not current_state.next_node: # If node didn't set a next_node
             print(f"Node {current_node_name} did not set a next_node. Ending graph.")
             current_state.next_node = "END"


    if turns >= MAX_TURNS:
        print("Graph execution reached max turns.")
        # Potentially return current_state or an error state with appropriate message
        current_state.messages.append({
            "role": "assistant", # Or "system" / "error"
            "content": "Graph execution reached maximum turns. Returning current state."
        })


    print(f"Graph execution finished. Final state: {current_state.dict(exclude_none=True)}")
    return current_state


if __name__ == "__main__":
    port = int(os.getenv("PORT", "54367"))
    uvicorn.run(app, host="0.0.0.0", port=port)

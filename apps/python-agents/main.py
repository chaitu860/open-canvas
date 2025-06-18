from fastapi import FastAPI, HTTPException
import uvicorn
import os
from dotenv import load_dotenv
from typing import Dict, Any, List

from .models import GraphInput, OpenCanvasGraphState, ArtifactV3 # Assuming models.py is in the same directory
from .agent_graph.generate_path import generate_path_node
from .agent_graph.reply_to_general_input import reply_to_general_input_node
from .agent_graph.generate_artifact import generate_artifact_node
from .agent_graph.rewrite_artifact import rewrite_artifact_node
from .agent_graph.update_artifact import update_artifact_node
from .agent_graph.update_highlighted_text import update_highlighted_text_node
from .agent_graph.rewrite_artifact_theme import rewrite_artifact_theme_node
from langchain_core.messages import BaseMessage # For isinstance checks
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
                "modelConfig": None,
                "systemPrompt": None,
                "supabase_session": None,
            }
        }

    current_state = OpenCanvasGraphState(
        messages=graph_input.messages if graph_input.messages is not None else [],
        _messages=graph_input.messages if graph_input.messages is not None else [],
        highlightedCode=graph_input.highlightedCode,
        highlightedText=graph_input.highlightedText,
        artifact=graph_input.artifact,
        next_node=graph_input.next_node,
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

    MAX_TURNS = 15
    turns = 0

    if not current_state.next_node:
         current_state.next_node = "generatePath"

    node_functions = {
        "generatePath": generate_path_node,
        "replyToGeneralInput": reply_to_general_input_node,
        "generateArtifact": generate_artifact_node,
        "rewriteArtifact": rewrite_artifact_node,
        "updateArtifact": update_artifact_node,
        "updateHighlightedText": update_highlighted_text_node,
        "rewriteArtifactTheme": rewrite_artifact_theme_node,
        # ... other nodes will be added here
    }

    print(f"Starting graph with initial state: {current_state.dict(exclude_none=True)}")
    print(f"Initial next_node: {current_state.next_node}")

    while current_state.next_node and current_state.next_node != "END" and turns < MAX_TURNS:
        turns += 1
        current_node_name = current_state.next_node
        # current_state.next_node = None # Node should explicitly set next_node to None or "END" if it's terminal for that path

        print(f"Turn {turns}: Executing node -> {current_node_name}")

        node_function = node_functions.get(current_node_name)

        update: Dict[str, Any] = {} # Initialize update

        if not node_function:
            print(f"Node '{current_node_name}' not found in node_functions. Setting next_node to END.")
            # Ensure _messages is a list before appending
            if not isinstance(current_state._messages, list):
                current_state._messages = []
            update = {"next_node": "END", "_messages": current_state._messages + [{"role": "assistant", "content": f"Mock response: Node {current_node_name} not explicitly handled, ending."}]}
        else:
            try:
                # Call the actual node function
                update = await node_function(current_state, runnable_config)
            except Exception as e:
                print(f"Error executing node {current_node_name}: {e}")
                error_content = f"Error in node {current_node_name}: {str(e)}"
                if not isinstance(current_state._messages, list):
                    current_state._messages = []
                current_state._messages.append({"role": "assistant", "content": error_content, "type": "ai"})
                current_state.next_node = "END"
                if not isinstance(current_state.messages, list):
                    current_state.messages = []
                current_state.messages.append({"role": "assistant", "content": error_content, "type": "ai"})
                break


        print(f"Node {current_node_name} produced update: {update}")

        for key, value in update.items():
            if hasattr(current_state, key):
                if key == "_messages":
                    if isinstance(value, list):
                        current_state._messages = [m.dict() if isinstance(m, BaseMessage) else m for m in value]
                    else:
                        print(f"Warning: node returned non-list for _messages: {value}")
                elif key == "messages":
                    if isinstance(value, list):
                        current_state.messages = [m.dict() if isinstance(m, BaseMessage) else m for m in value]
                    else:
                        print(f"Warning: node returned non-list for messages: {value}")
                elif key == "next_node":
                    pass
                else:
                    setattr(current_state, key, value)
            else:
                print(f"Warning: Trying to update non-existent key '{key}' in state.")

        if "next_node" in update and update["next_node"] is not None:
            current_state.next_node = update["next_node"]
        elif current_node_name == current_state.next_node :
            print(f"Node {current_node_name} did not set a new next_node. Ending graph to prevent loop.")
            current_state.next_node = "END"
        elif "next_node" not in update: # If a node doesn't return a next_node, assume it's an end path for that node
            print(f"Node {current_node_name} did not return a 'next_node'. Assuming END for this path.")
            current_state.next_node = "END"


    if turns >= MAX_TURNS:
        print("Graph execution reached max turns.")
        if not isinstance(current_state.messages, list):
            current_state.messages = []
        current_state.messages.append({
            "role": "assistant",
            "content": "Graph execution reached maximum turns. Returning current state.",
            "type": "ai"
        })

    print(f"Graph execution finished. Final state: {current_state.dict(exclude_none=True)}")
    return current_state

if __name__ == "__main__":
    port = int(os.getenv("PORT", "54367"))
    uvicorn.run(app, host="0.0.0.0", port=port)

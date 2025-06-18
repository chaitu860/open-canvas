# app/agents/open_canvas.py
from langgraph.graph import StateGraph, END, START # Added START
from langgraph.checkpoint.sqlite import SqliteSaver
from app.utils.text_processing import get_string_from_content, extract_urls # Added
from .state import OpenCanvasState
from typing import Dict, Any, Literal, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import inspect

# Placeholder for DEFAULT_INPUTS equivalent in Python
DEFAULT_INPUTS_PYTHON = {
    "messages": [],
    "_messages": [],
    "highlightedCode": None,
    "highlightedText": None,
    "artifact": None,
    "next_node": None, # Renamed from 'next'
    "language": None,
    "artifactLength": None,
    "regenerateWithEmojis": None,
    "readingLevel": None,
    "addComments": None,
    "addLogs": None,
    "portLanguage": None,
    "fixBugs": None,
    "customQuickActionId": None,
    "webSearchEnabled": None,
    "webSearchResults": None,
}

async def generate_path(state: OpenCanvasState) -> Dict[str, Any]:
    print("Executing Node: generate_path (with imports for text processing)")

    _messages = state.get("messages", []) # Use .get for safety, default to empty list

    # Example usage of imported functions (actual logic will be more complex)
    if _messages:
        last_message = _messages[-1]
        # Ensure last_message has a 'content' attribute. BaseMessage does.
        if hasattr(last_message, 'content'):
            last_message_content_str = get_string_from_content(last_message.content)
            urls_in_last_message = extract_urls(last_message_content_str)
            print(f"Last message content: {last_message_content_str}")
            print(f"URLs in last message: {urls_in_last_message}")

            # For now, simplified routing based on placeholder:
            if isinstance(last_message, HumanMessage):
                content_lower = last_message_content_str.lower()
                if "generate artifact" in content_lower:
                    return {"next_node": "generateArtifact"}
                elif "update artifact" in content_lower:
                    return {"next_node": "updateArtifact"}
                else:
                    return {"next_node": "replyToGeneralInput"}
        else:
            # Handle cases where last_message might not have 'content' as expected
            print(f"Warning: Last message ({type(last_message)}) does not have a 'content' attribute.")
            return {"next_node": "replyToGeneralInput"} # Default fallback

    return {"next_node": "replyToGeneralInput"}


async def reply_to_general_input(state: OpenCanvasState) -> Dict[str, Any]:
    print("Executing Node: reply_to_general_input")
    return {"messages": [AIMessage(content="This is a general reply.")]}

async def generate_artifact(state: OpenCanvasState) -> Dict[str, Any]:
    print("Executing Node: generate_artifact")
    return {"messages": [AIMessage(content="Artifact generation placeholder.")]}

async def update_artifact(state: OpenCanvasState) -> Dict[str, Any]:
    print("Executing Node: update_artifact")
    return {"messages": [AIMessage(content="Artifact update placeholder.")]}

async def generate_followup(state: OpenCanvasState) -> Dict[str, Any]:
    print("Executing Node: generate_followup")
    return {"messages": [AIMessage(content="Follow-up placeholder.")]}

async def reflect_node(state: OpenCanvasState) -> Dict[str, Any]:
    print("Executing Node: reflect_node")
    return {}

async def clean_state_node(state: OpenCanvasState) -> Dict[str, Any]:
    print("Executing Node: clean_state")
    # Return a shallow copy, ensure nested structures like lists are copied if modified by nodes
    cleaned_state = {k: list(v) if isinstance(v, list) else v for k, v in DEFAULT_INPUTS_PYTHON.items()}
    return cleaned_state


def route_node(state: OpenCanvasState) -> Optional[str]:
    print(f"Executing Conditional Edge: route_node, next_node is {state.get('next_node')}")
    next_node = state.get("next_node")
    if not next_node:
        print("Warning: 'next_node' not set in route_node. Defaulting to replyToGeneralInput.")
        return "replyToGeneralInput"
    return next_node


def conditionally_generate_title(state: OpenCanvasState) -> Literal["generateTitle", "summarizer", END]: # type: ignore
    print("Executing Conditional Edge: conditionally_generate_title")
    current_messages = state.get("messages", [])
    if len(current_messages) <= 2:
         return "generateTitle"
    # Placeholder for simpleTokenCalculator logic
    # if sum(len(get_string_from_content(m.content)) for m in current_messages) > 1000: # Example condition
    #    return "summarizer"
    return END

# --- Graph Definition (Partial Sketch) ---
# workflow = StateGraph(OpenCanvasState)
# workflow.add_node("generatePath", generate_path)
# workflow.add_node("replyToGeneralInput", reply_to_general_input)
# workflow.add_node("generateArtifact", generate_artifact)
# workflow.add_node("updateArtifact", update_artifact)
# workflow.add_node("generateFollowup", generate_followup)
# workflow.add_node("reflectNode", reflect_node)
# workflow.add_node("cleanStateNode", clean_state_node)


# async def placeholder_node(state: OpenCanvasState, node_name: Optional[str] = None) -> Dict[str, Any]:
#    name_to_print = node_name or inspect.currentframe().f_code.co_name
#    print(f"Executing Placeholder Node: {name_to_print}")
#    return {}

# workflow.add_node("generateTitle", lambda state: placeholder_node(state, "generateTitle"))
# workflow.add_node("summarizer", lambda state: placeholder_node(state, "summarizer"))


# workflow.add_edge(START, "generatePath")

# workflow.add_conditional_edges(
#     "generatePath",
#     route_node,
#     {
#         "replyToGeneralInput": "replyToGeneralInput",
#         "generateArtifact": "generateArtifact",
#         "updateArtifact": "updateArtifact",
#         # "generateFollowup": "generateFollowup",
#         # "reflect": "reflectNode",
#     }
# )
# workflow.add_edge("replyToGeneralInput", "cleanStateNode")
# workflow.add_edge("generateArtifact", "cleanStateNode")
# workflow.add_edge("updateArtifact", "cleanStateNode")
# # workflow.add_edge("generateFollowup", "cleanStateNode")
# # workflow.add_edge("reflectNode", "cleanStateNode")


# workflow.add_conditional_edges("cleanStateNode", conditionally_generate_title, {
# "generateTitle": "generateTitle",
# "summarizer": "summarizer",
# END: END
# })
# workflow.add_edge("generateTitle", END)
# workflow.add_edge("summarizer", END)

# memory = SqliteSaver.from_conn_string(":memory:")
# app = workflow.compile(checkpointer=memory)
# print("Graph compiled (partially).")

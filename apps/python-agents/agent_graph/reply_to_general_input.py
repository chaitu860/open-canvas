from typing import Dict, Any, List, Optional

from ...models import OpenCanvasGraphState, Reflections as ReflectionsModel, ContextDocument # Added ContextDocument
from ...utils import (
    get_model_from_config,
    format_reflections,
    format_artifact_content_with_template,
    create_context_document_messages, # Utility to create formatted context messages
    is_using_o1_mini_model,
    get_artifact_content, # Utility to get current artifact content model
    get_string_from_content # To convert message content to string
)
from .prompts import CURRENT_ARTIFACT_PROMPT, NO_ARTIFACT_PROMPT
# It seems REPLY_TO_GENERAL_INPUT_PROMPT_TEMPLATE is defined locally, not imported. This is fine.

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage


async def reply_to_general_input_node(state: OpenCanvasGraphState, config: Dict[str, Any]) -> Dict[str, Any]:

    model = get_model_from_config(config)
    if not model:
        # Try to get a default model if specific one fails, or raise error
        # For now, raising error as per original get_model_from_config behavior
        raise ValueError("Failed to initialize model for reply_to_general_input")

    reflections_data_raw = config.get("configurable", {}).get("reflections_data")
    reflections_data_model: Optional[ReflectionsModel] = None
    if isinstance(reflections_data_raw, dict):
        reflections_data_model = ReflectionsModel.parse_obj(reflections_data_raw)
    elif isinstance(reflections_data_raw, ReflectionsModel): # If it's already the Pydantic model
        reflections_data_model = reflections_data_raw

    memories_as_string = "No reflections found."
    if reflections_data_model:
        memories_as_string = format_reflections(reflections_data_model) # Ensure format_reflections handles Pydantic model

    current_artifact_for_prompt_str = ""
    if state.artifact:
        try:
            artifact_content_model = get_artifact_content(state.artifact)
            current_artifact_for_prompt_str = format_artifact_content_with_template(
                CURRENT_ARTIFACT_PROMPT, artifact_content_model, shorten_content=True # Shorten for prompt context
            )
        except ValueError as e: # Handle cases where artifact might be present but content missing
            print(f"Warning: Could not get artifact content for prompt: {e}")
            current_artifact_for_prompt_str = NO_ARTIFACT_PROMPT
    else:
        current_artifact_for_prompt_str = NO_ARTIFACT_PROMPT

    # Local template string for this node
    REPLY_TO_GENERAL_INPUT_PROMPT_TEMPLATE = """You are an AI assistant tasked with responding to the users question.
Use the full chat history as context.
The user may have generated artifacts in the past. Use the following current artifact information as context when responding to the users question.

{currentArtifactPrompt}

You also have the following reflections on style guidelines and general memories/facts about the user to use when generating your response.
<reflections>
{reflections}
</reflections>
"""

    formatted_prompt_str = REPLY_TO_GENERAL_INPUT_PROMPT_TEMPLATE.format(
        reflections=memories_as_string,
        currentArtifactPrompt=current_artifact_for_prompt_str
    )

    # --- Context Document Handling ---
    # Attempt to retrieve context documents if passed in config or state.
    # This part was missing in the original provided snippet for this node.
    # Example: Get from config (if they were placed there by a preceding step or global config)
    context_documents_raw = config.get("configurable", {}).get("context_documents", [])
    context_document_obj_list: List[ContextDocument] = []
    if isinstance(context_documents_raw, list):
        for doc_data in context_documents_raw:
            if isinstance(doc_data, ContextDocument):
                context_document_obj_list.append(doc_data)
            elif isinstance(doc_data, dict):
                try:
                    context_document_obj_list.append(ContextDocument.parse_obj(doc_data))
                except Exception as e:
                    print(f"Warning: Could not parse context document dict: {e}")
            # else: skip if format is unknown

    context_messages_for_llm: List[BaseMessage] = []
    if context_document_obj_list:
        # create_context_document_messages expects the main runnable_config
        context_messages_for_llm = create_context_document_messages(config, context_document_obj_list)
    # --- End Context Document Handling ---

    llm_messages_input: List[BaseMessage] = []

    # System prompt handling
    # Based on original TS logic, is_using_o1_mini_model checks the model name from get_model_config(config)
    if is_using_o1_mini_model(config):
        # For o1-mini, the main prompt might be better as a HumanMessage to start if no other system prompt is defined
        # However, if a system prompt is explicitly set in config, that should be honored.
        system_prompt_from_config = config.get("configurable", {}).get("systemPrompt")
        if system_prompt_from_config:
            llm_messages_input.append(SystemMessage(content=system_prompt_from_config))
            llm_messages_input.append(HumanMessage(content=formatted_prompt_str)) # Main instruction as human message
        else: # No explicit system prompt, main instructions become the human message
            llm_messages_input.append(HumanMessage(content=formatted_prompt_str))
    else: # For other models
        system_prompt_from_config = config.get("configurable", {}).get("systemPrompt")
        # Combine system prompt from config with the node's specific instructions
        final_system_content = formatted_prompt_str # Default to node's main prompt
        if system_prompt_from_config:
            final_system_content = f"{system_prompt_from_config}\n\n{formatted_prompt_str}"
        llm_messages_input.append(SystemMessage(content=final_system_content))

    # Add context messages (if any) after system/initial human message
    llm_messages_input.extend(context_messages_for_llm)

    # Add chat history (state._messages)
    # Ensure state._messages is not None and convert dicts to BaseMessage instances
    internal_history_dicts = state._messages if state._messages is not None else []
    for msg_dict in internal_history_dicts:
        role = msg_dict.get("role") or msg_dict.get("type")
        content = msg_dict.get("content", "") # Ensure content is serializable
        name = msg_dict.get("name")

        # Convert content to string if it's not already suitable for BaseMessage
        # LangChain messages can handle List[Dict] for complex content.
        if not isinstance(content, (str, list)):
            content = str(content) # Fallback to string conversion

        if role in ["user", "human"]:
            llm_messages_input.append(HumanMessage(content=content, name=name))
        elif role in ["assistant", "ai"]:
            # Handle AIMessage specific fields like tool_calls if present
            tool_calls = msg_dict.get("tool_calls")
            invalid_tool_calls = msg_dict.get("invalid_tool_calls")
            if tool_calls or invalid_tool_calls:
                 llm_messages_input.append(AIMessage(content=content, name=name, tool_calls=tool_calls, invalid_tool_calls=invalid_tool_calls))
            else:
                 llm_messages_input.append(AIMessage(content=content, name=name))
        elif role == "system" and not is_using_o1_mini_model(config): # Avoid duplicate system messages if already added
            # Only add if it's not the initial system message already constructed
            if not (llm_messages_input and llm_messages_input[0].type == "system" and llm_messages_input[0].content == content):
                 llm_messages_input.append(SystemMessage(content=content, name=name))
        # Other types like ToolMessage could be handled here if necessary

    response_message = await model.ainvoke(llm_messages_input)
    response_dict = response_message.dict() # Convert BaseMessage to dict for state

    # Update user-facing messages: typically append the AI response.
    # The state.messages contains dicts.
    updated_user_facing_messages = (state.messages or []) + [response_dict]

    # Update internal messages: append the AI response to the existing internal history.
    updated_internal_messages = (state._messages or []) + [response_dict]

    return {
        "messages": updated_user_facing_messages,
        "_messages": updated_internal_messages,
        "next_node": "END" # This node typically ends the turn.
    }

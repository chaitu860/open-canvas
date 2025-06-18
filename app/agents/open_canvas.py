# app/agents/open_canvas.py
import inspect # For placeholder_node name
import copy # For deepcopy in clean_state_node

from langgraph.graph import StateGraph, END, START
# from langgraph.checkpoint.sqlite import SqliteSaver # Example checkpointer
from .state import OpenCanvasState
from typing import Dict, Any, Literal, Optional, List, Union

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage # type: ignore

from app.utils.text_processing import get_string_from_content, extract_urls
from app.agents.nodes.generate_path_helpers.documents import (
    convert_context_document_to_human_message,
    fix_misformatted_context_doc_message,
    RemoveMessage
)
from app.agents.nodes.generate_path_helpers.include_url_contents import include_url_contents_func
from app.agents.nodes.generate_path_helpers.dynamic_determine_path import dynamic_determine_path_func
    from app.utils.langchain_helpers import ( # Added for reply_to_general_input
        get_model_from_config,
        get_artifact_content,
        format_artifact_content_with_template,
        create_context_document_messages,
        is_using_o1_mini_model,
        # format_reflections, # Needs porting if reflections store is used
    )
    from app.agents.prompts import CURRENT_ARTIFACT_PROMPT, NO_ARTIFACT_PROMPT # Added
    # Imports for generate_artifact (already present from previous step, ensure they are correctly placed)
    from app.agents.nodes.generate_artifact_helpers.schemas import ArtifactToolSchema
    from app.agents.nodes.generate_artifact_helpers.utils import format_new_artifact_prompt, create_artifact_content
    from app.schemas.common import ArtifactV3, ArtifactType, ArtifactMarkdownV3, ArtifactCodeV3, ProgrammingLanguageOptions

    # Imports for rewrite_artifact
    from app.agents.nodes.rewrite_artifact_helpers.schemas import OptionallyUpdateArtifactMetaSchema
    from app.agents.nodes.rewrite_artifact_helpers.update_meta import optionally_update_artifact_meta
    from app.agents.nodes.rewrite_artifact_helpers.utils import (
        validate_state as validate_rewrite_state,
        build_prompt as build_rewrite_prompt,
        create_new_artifact_content as create_new_rewrite_artifact_content # Aliased
    )
    from app.utils.text_processing import is_thinking_model, extract_thinking_and_response_tokens # Added
    from app.utils.langchain_helpers import get_model_config # ensure get_model_config is available
    import uuid # Added for thinking message ID


# Placeholder for DEFAULT_INPUTS equivalent in Python
DEFAULT_INPUTS_PYTHON = {
    "messages": [],
    "_messages": [],
    "highlightedCode": None,
    "highlightedText": None,
    "artifact": None,
    "next_node": None,
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

async def generate_path(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: generate_path (Full Implementation Attempt)")
    if config is None:
        config = {}

    # Ensure 'configurable' key exists in config, as helpers might expect it.
    # The graph's `compile(checkpointer=memory, interrupt_before=["generate_path"])`
    # call will pass the full RunnableConfig, which has 'configurable'.
    # If calling this node directly in a test, ensure config is shaped like RunnableConfig.
    graph_config = config.get("configurable", {})


    # Messages to be added to the state's 'messages' key (user-facing or UI-hidden context)
    processed_messages_for_state: List[BaseMessage] = []
    # Internal messages list, potentially modified by URL scraping, for LLM calls.
    current_internal_messages: List[BaseMessage] = list(state.get("_messages", []))

    # 1. Document Handling (convertContextDocumentToHumanMessage)
    # Operates on current_internal_messages (which is state._messages)
    doc_message = await convert_context_document_to_human_message(current_internal_messages, graph_config)
    if doc_message:
        processed_messages_for_state.append(doc_message)

    # 2. Document Handling (fixMisFormattedContextDocMessage)
    ids_to_remove_from_internal_messages = set()
    messages_to_add_to_internal_messages = [] # For current_internal_messages
    messages_to_add_to_processed_for_state = [] # For processed_messages_for_state

    temp_current_internal_messages_for_fixing = list(current_internal_messages) # Iterate over a copy

    for i, msg_to_check in enumerate(temp_current_internal_messages_for_fixing):
        if isinstance(msg_to_check, HumanMessage) and msg_to_check.id: # Ensure message has an ID for removal
            fixed_msgs_result = await fix_misformatted_context_doc_message(msg_to_check, graph_config)
            if fixed_msgs_result:
                for f_msg in fixed_msgs_result:
                    if isinstance(f_msg, RemoveMessage) and f_msg.id_to_remove:
                        ids_to_remove_from_internal_messages.add(f_msg.id_to_remove)
                    elif isinstance(f_msg, HumanMessage):
                        messages_to_add_to_internal_messages.append(f_msg)
                        # If a message was fixed, the fixed version should also be in processed_messages_for_state
                        # if it's a UI-hidden context message.
                        if f_msg.additional_kwargs.get("oc_hide_from_ui"):
                             messages_to_add_to_processed_for_state.append(f_msg)

    if ids_to_remove_from_internal_messages:
        current_internal_messages = [m for m in current_internal_messages if m.id not in ids_to_remove_from_internal_messages]
        current_internal_messages.extend(messages_to_add_to_internal_messages)

        # Also update processed_messages_for_state if any of its messages were among those removed/fixed
        processed_messages_for_state = [m for m in processed_messages_for_state if m.id not in ids_to_remove_from_internal_messages]
        processed_messages_for_state.extend(messages_to_add_to_processed_for_state)


    # 3. Direct Routing based on State fields
    # Output of direct routing should be: {"next_node": "...", "messages": msgs_for_state_update_or_none}
    # Where messages is for the main 'messages' state key. _messages is not updated by direct routes.
    direct_route_messages_update = processed_messages_for_state or None # Use None if empty

    if state.get("highlightedCode"):
        return {"next_node": "updateArtifact", "messages": direct_route_messages_update}
    if state.get("highlightedText"):
        return {"next_node": "updateHighlightedText", "messages": direct_route_messages_update}
    if state.get("language") or state.get("artifactLength") or state.get("regenerateWithEmojis") or state.get("readingLevel"):
        return {"next_node": "rewriteArtifactTheme", "messages": direct_route_messages_update}
    if state.get("addComments") or state.get("addLogs") or state.get("portLanguage") or state.get("fixBugs"):
        return {"next_node": "rewriteCodeArtifactTheme", "messages": direct_route_messages_update}
    if state.get("customQuickActionId"):
        return {"next_node": "customAction", "messages": direct_route_messages_update}
    # webSearchEnabled is a trigger for the webSearch node.
    # If it's true, it means the user's query might need web search BEFORE normal routing.
    if state.get("webSearchEnabled"):
        # The webSearch node itself will handle search and then route to generateArtifact/rewriteArtifact.
        # It will also set webSearchEnabled to False.
        # processed_messages_for_state are passed along.
        return {"next_node": "webSearch", "messages": direct_route_messages_update}

    # 4. URL Extraction & Content Inclusion (operates on current_internal_messages)
    if current_internal_messages:
        last_internal_message = current_internal_messages[-1]
        if isinstance(last_internal_message, HumanMessage):
            last_message_content_str = get_string_from_content(last_internal_message.content)
            urls_in_last_message = extract_urls(last_message_content_str)
            if urls_in_last_message:
                # include_url_contents_func expects the 'configurable' part of the config
                updated_message_from_url_inclusion = await include_url_contents_func(last_internal_message, urls_in_last_message, graph_config)
                if updated_message_from_url_inclusion:
                    current_internal_messages = current_internal_messages[:-1] + [updated_message_from_url_inclusion]

    # 5. Dynamic Path Determination
    # Pass the original state, but dynamic_determine_path_func will use its own copy
    # and primarily relies on the _messages it's given (current_internal_messages here).
    # processed_messages_for_state are the "newly_processed_messages" for the routing LLM context.
    routing_result = await dynamic_determine_path_func(
        state, # Original state for other context (like artifact presence)
        processed_messages_for_state, # UI-hidden docs for routing LLM context
        graph_config # Pass 'configurable' part of config
    )

    route_name = routing_result.get("next_node", "replyToGeneralInput")


    # 6. Construct final return dictionary
    # 'messages' key for user-facing state.messages (UI hidden docs)
    # '_messages' key for internal LLM context state._messages (actual conversation + UI hidden docs)
    final_messages_for_main_state = processed_messages_for_state or None

    # Combine current_internal_messages (which might have been updated by URL inclusion)
    # with processed_messages_for_state (UI-hidden context docs) for the next LLM call's context.
    final_internal_messages_for_llm_context = current_internal_messages + (processed_messages_for_state if processed_messages_for_state else [])

    # Filter out any None values just in case, though lists should be empty not contain None
    final_internal_messages_for_llm_context = [m for m in final_internal_messages_for_llm_context if m is not None]


    return {
        "next_node": route_name,
        "messages": final_messages_for_main_state,
        "_messages": final_internal_messages_for_llm_context
    }

# --- Other Node Placeholders (Signatures updated to include config) ---
async def reply_to_general_input(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: reply_to_general_input")
    # graph_config = config.get("configurable", {}) if config else {}
    # llm = await get_model_from_config(graph_config)
    # response = await llm.ainvoke(state.get("_messages", []))
    # return {"messages": [response]} # This should update 'messages' for UI, and also '_messages' for history

    # Simplified placeholder return for now:
    # new_ai_message = AIMessage(content="This is a general reply from reply_to_general_input.")
    # return {
    #     "messages": [new_ai_message], # Adds to user-facing history
    #     "_messages": state.get("_messages", []) + [new_ai_message] # Adds to internal history
    # }
    print("Executing Node: reply_to_general_input")
    if config is None: config = {}
    # graph_config should be the 'configurable' part of the RunnableConfig
    graph_config = config.get("configurable", {})


    llm = await get_model_from_config(graph_config)

    # Placeholder for reflections - replace with actual store logic later
    # reflections_data = await get_reflections_from_store(graph_config) # Needs implementation
    # memories_as_string = format_reflections(reflections_data) if reflections_data else "No reflections available (placeholder)."
    memories_as_string = "No reflections available (placeholder)." # TS uses ensureStoreInConfig

    current_artifact_model = get_artifact_content(state.get("artifact"))
    current_artifact_prompt_str = ""
    if current_artifact_model:
        current_artifact_prompt_str = format_artifact_content_with_template(
            CURRENT_ARTIFACT_PROMPT, current_artifact_model, shorten_content=True, max_length=3000 # Keep it reasonably sized
        )
    else:
        current_artifact_prompt_str = NO_ARTIFACT_PROMPT

    # Define the prompt template here or import from prompts.py
    REPLY_TO_GENERAL_INPUT_PROMPT_TEMPLATE = """You are an AI assistant tasked with responding to the users question.
The user has generated artifacts in the past. Use the following artifacts as context when responding to the users question.
You also have the following reflections on style guidelines and general memories/facts about the user to use when generating your response.
<reflections>
{reflections}
</reflections>
{currentArtifactPrompt}"""

    formatted_prompt = REPLY_TO_GENERAL_INPUT_PROMPT_TEMPLATE.format(
        reflections=memories_as_string,
        currentArtifactPrompt=current_artifact_prompt_str
    )

    # Context documents from config (e.g. uploaded files if any were attached to the config for this run)
    # create_context_document_messages takes the 'configurable' part of the config
    context_document_llm_parts = await create_context_document_messages(graph_config)

    context_docs_messages_for_llm = []
    if context_document_llm_parts: # Ensure it's not an empty list
        # Wrap parts in a single HumanMessage, marked as hidden from UI
        context_docs_messages_for_llm.append(HumanMessage(
            content=context_document_llm_parts,
            additional_kwargs={"oc_hide_from_ui": True}
            ))

    # Determine role for the main system/user prompt based on model
    prompt_is_user_role = is_using_o1_mini_model(graph_config)

    llm_messages: List[BaseMessage] = []
    if prompt_is_user_role:
        llm_messages.append(HumanMessage(content=formatted_prompt))
    else:
        llm_messages.append(SystemMessage(content=formatted_prompt))

    llm_messages.extend(context_docs_messages_for_llm) # Add formatted context document message if any

    # Add chat history (_messages from state)
    # Filter out any None messages from state._messages just in case
    history_messages = [msg for msg in state.get("_messages", []) if msg is not None]
    llm_messages.extend(history_messages)

    response = await llm.ainvoke(llm_messages)

    # The TS code returns [response] for both 'messages' and '_messages'.
    # This implies the AI's response becomes the sole message in these lists for the next step.
    # This is correct if the graph's `OpenCanvasState` TypedDict uses a custom reducer for `_messages`
    # (like `self.new_messages + messages`) as seen in some LangGraph examples or the original TS.
    # If default reducer (overwrite) is used, then this is fine.
    # If additive reducer is used for _messages, then `state.get("_messages", []) + [response]` would be for _messages.
    # For 'messages' (UI), returning just [response] is usually what's desired for a new turn.
    return {
        "messages": [response],
        "_messages": [response] # Mirrored TS return. Assumes specific reducer for _messages if history is to be preserved AND appended.
                               # If OpenCanvasState._messages uses default TypedDict update (overwrite), this is the only message for next node.
                               # If it's like `operator.add` or a custom list extend, then it appends.
                               # The TS GraphState reducer for _messages is: `(left, right) => (right ?? []).concat(left ?? [])`
                               # which means new messages (right) are prepended. So [response] + state._messages would be closer.
                               # Or, if the meaning is "this is THE new list of messages", then [response] is correct.
                               # Given the name "_messages" often implies the whole history for the LLM, prepending/appending seems more likely.
                               # Let's adjust to append for _messages, as it's more common for history.
                               # messages: [response] -> for UI display of current turn
                               # _messages: state.get("_messages", []) + [response] -> for next LLM call context
                               # This seems more standard for many LangGraph examples.
                               # However, the TS code's OpenCanvasGraphState explicitly defines a reducer for _messages:
                               # `(left: BaseMessage[] | undefined, right: BaseMessage[] | undefined): BaseMessage[] => (right ?? []).concat(left ?? []);`
                               # This means `right` (the new message list from node output) is prepended to `left` (existing messages in state).
                               # So, if node returns `_messages: [response]`, then state becomes `[response] + existing_messages`.
                               # This is unusual. More typical is `existing_messages + [response]`.
                               # Sticking to the direct port of `_messages: [response]` for now as per prompt.
    }


# Placeholder for get_formatted_reflections - replace with actual store logic later
async def get_formatted_reflections(config: Dict[str, Any]) -> str:
    # graph_config is the 'configurable' part of RunnableConfig
    # Actual logic would involve config.store.get(...) or similar checkpoint interaction
    print("Warning: Using placeholder for get_formatted_reflections.")
    # Example: store = config.get("store") if config else None
    # if store: reflections = await store.mget("reflections_key") ...
    return "No specific user reflections available at this time (placeholder)."

# Placeholder/inline for optionally_get_system_prompt_from_config
def optionally_get_system_prompt_from_config(graph_config: Dict[str, Any]) -> Optional[str]:
    # graph_config is the 'configurable' part of RunnableConfig
    return graph_config.get("systemPrompt")


async def generate_artifact(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: generate_artifact")
    if config is None: config = {}
    graph_config = config.get("configurable", {}) # Extract 'configurable' part

    # Get model and its name, explicitly enabling tool calling
    # Temperature is set to 0.5 for this node in TS, pass as extra
    model_details = get_model_config(graph_config, extra={"isToolCalling": True}) # get_model_config needs 'configurable'
    model_name = model_details.get("model_name", "unknown_model")

    llm = await get_model_from_config(graph_config, extra={"temperature": 0.5, "isToolCalling": True})

    # Define the tool schema for artifact generation
    # from app.agents.nodes.generate_artifact_helpers.schemas import ArtifactToolSchema (already imported if at top)
    # from app.agents.nodes.generate_artifact_helpers.utils import format_new_artifact_prompt, create_artifact_content (already imported)
    # from app.schemas.common import ArtifactV3, ArtifactType (already imported)

    tool_payload = {
        "name": "generate_artifact", # Must match the tool call name expected by the LLM
        "description": "Generates an artifact which can be text or code based on the user's query and chat history.",
        "parameters": ArtifactToolSchema.schema()
    }

    llm_with_artifact_tool = llm.bind_tools(
        tools=[tool_payload],
        tool_choice="generate_artifact" # Force the LLM to use this tool
    )

    memories_as_string = await get_formatted_reflections(graph_config) # Placeholder
    formatted_prompt_str = format_new_artifact_prompt(memories_as_string, model_name)

    user_system_prompt = optionally_get_system_prompt_from_config(graph_config) # Pass 'configurable'
    # Combine system prompts if user_system_prompt exists
    full_system_prompt = f"{user_system_prompt}\n\n{formatted_prompt_str}" if user_system_prompt else formatted_prompt_str

    # Context documents (e.g. from file uploads)
    context_document_llm_parts = await create_context_document_messages(graph_config) # Pass 'configurable'
    context_docs_messages_for_llm = []
    if context_document_llm_parts:
        context_docs_messages_for_llm.append(HumanMessage(content=context_document_llm_parts, additional_kwargs={"oc_hide_from_ui": True}))

    # Determine role for the main system/user prompt based on model name
    prompt_is_user_role = is_using_o1_mini_model(graph_config) # Pass 'configurable'

    llm_messages_for_invoke: List[BaseMessage] = []
    if prompt_is_user_role:
        llm_messages_for_invoke.append(HumanMessage(content=full_system_prompt))
    else:
        llm_messages_for_invoke.append(SystemMessage(content=full_system_prompt))

    llm_messages_for_invoke.extend(context_docs_messages_for_llm)

    # Add chat history (_messages from state)
    history_messages = [msg for msg in state.get("_messages", []) if msg is not None]
    llm_messages_for_invoke.extend(history_messages)

    # Invoke the LLM with the prepared messages and tool choice
    # The run_name is for LangSmith tracing, can be omitted if not using LangSmith
    llm_response = await llm_with_artifact_tool.ainvoke(llm_messages_for_invoke, {"run_name": "generate_artifact_llm_call"})

    args_dict = None
    # Check for tool calls in the response
    if hasattr(llm_response, "tool_calls") and llm_response.tool_calls:
        # Assuming the first tool call is the one we want
        # In TS, it checks `if (response.tool_calls?.[0]?.name === "generateArtifact")`
        # Here, we forced tool_choice, so it should be "generate_artifact"
        first_tool_call = llm_response.tool_calls[0]
        if first_tool_call.get("name") == "generate_artifact":
            args_dict = first_tool_call.get("args")
        else:
            print(f"Warning: Expected tool 'generate_artifact' but got '{first_tool_call.get('name')}'")

    if not args_dict:
        print(f"Error: generate_artifact tool call did not return valid arguments. Response: {llm_response.content}")
        # Create a fallback text artifact indicating failure
        error_artifact_content = ArtifactMarkdownV3(
            index=0, type=ArtifactType.TEXT, title="Error Generating Artifact",
            fullMarkdown=f"I was unable to generate the artifact as requested. The model response was: {llm_response.content}"
        )
        error_artifact = ArtifactV3(currentIndex=0, contents=[error_artifact_content])
        # Also provide an AI message for the chat
        error_ai_message = AIMessage(content="I encountered an issue generating the artifact. Please try again or rephrase your request.")
        return {
            "artifact": error_artifact,
            "messages": [error_ai_message], # Update user-facing messages
            "_messages": state.get("_messages", []) + [error_ai_message] # Update internal history
        }

    try:
        # Validate and parse the arguments using the Pydantic schema
        parsed_args = ArtifactToolSchema(**args_dict)
    except Exception as e: # Catches Pydantic ValidationError
        print(f"Error parsing tool arguments for generate_artifact: {e}. Args: {args_dict}")
        error_artifact_content = ArtifactMarkdownV3(
            index=0, type=ArtifactType.TEXT, title="Error Parsing Artifact Data",
            fullMarkdown=f"There was an issue with the data format for the artifact: {e}. Received arguments: {args_dict}"
        )
        error_artifact = ArtifactV3(currentIndex=0, contents=[error_artifact_content])
        error_ai_message = AIMessage(content=f"I had trouble formatting the generated artifact due to: {e}.")
        return {
            "artifact": error_artifact,
            "messages": [error_ai_message],
            "_messages": state.get("_messages", []) + [error_ai_message]
        }

    # Create the actual artifact content object (ArtifactCodeV3 or ArtifactMarkdownV3)
    new_artifact_content = create_artifact_content(parsed_args)

    # Embed this content within an ArtifactV3 structure
    new_artifact_v3 = ArtifactV3(
        currentIndex=0, # New artifact, so current index is 0 (pointing to the first and only content)
        contents=[new_artifact_content]
    )

    # The TS node for generateArtifact ONLY returns the new artifact.
    # It does not directly add any AIMessage to the chat history.
    # Any user-facing message about the artifact generation would typically come from a subsequent node
    # or if the LLM itself (if not using tools) generated text like "Okay, here is your artifact: ...".
    # Since we are forcing a tool call, the LLM's response *is* the tool call, not a chat message.
    # If a chat message is desired *in addition* to the artifact, it needs to be constructed here.
    # For now, strictly adhering to the TS return signature for this node:
    return {"artifact": new_artifact_v3}


async def rewrite_artifact(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: rewrite_artifact")
    if config is None: config = {}
    # graph_config is the 'configurable' part of RunnableConfig
    graph_config = config.get("configurable", {})

    model_details = get_model_config(graph_config)
    model_name = model_details.get("model_name", "unknown_model")

    llm = await get_model_from_config(graph_config)

    memories_as_string = await get_formatted_reflections(graph_config)

    try:
        current_artifact_content_model, recent_human_message = validate_rewrite_state(state)
    except ValueError as e:
        print(f"Validation error in rewrite_artifact: {e}")
        error_message = AIMessage(content=f"Error: Could not rewrite artifact - {e}")
        return {
            "messages": [error_message],
            "_messages": state.get("_messages", []) + [error_message]
        }

    artifact_meta_update_schema: OptionallyUpdateArtifactMetaSchema = await optionally_update_artifact_meta(state, config) # Pass full config

    determined_artifact_type = artifact_meta_update_schema.type
    is_new_type = determined_artifact_type != current_artifact_content_model.type

    current_artifact_text_content = ""
    if is_artifact_code_content(current_artifact_content_model) and isinstance(current_artifact_content_model, ArtifactCodeV3):
        current_artifact_text_content = current_artifact_content_model.code
    elif isinstance(current_artifact_content_model, ArtifactMarkdownV3):
        current_artifact_text_content = current_artifact_content_model.fullMarkdown

    formatted_prompt_str = build_rewrite_prompt({
        "artifact_content_str": current_artifact_text_content,
        "memories_as_string": memories_as_string,
        "is_new_type": is_new_type,
        "artifact_meta_tool_call": artifact_meta_update_schema,
    })

    user_system_prompt = optionally_get_system_prompt_from_config(graph_config)
    full_system_prompt = f"{user_system_prompt}\n{formatted_prompt_str}" if user_system_prompt else formatted_prompt_str

    context_document_llm_parts = await create_context_document_messages(graph_config)
    context_docs_messages_for_llm = []
    if context_document_llm_parts:
        context_docs_messages_for_llm.append(HumanMessage(content=context_document_llm_parts, additional_kwargs={"oc_hide_from_ui": True}))

    prompt_is_user_role = is_using_o1_mini_model(graph_config)

    llm_messages_for_invoke: List[BaseMessage] = []
    if prompt_is_user_role:
        llm_messages_for_invoke.append(HumanMessage(content=full_system_prompt))
    else:
        llm_messages_for_invoke.append(SystemMessage(content=full_system_prompt))

    llm_messages_for_invoke.extend(context_docs_messages_for_llm)
    llm_messages_for_invoke.append(recent_human_message)

    response_ai_message = await llm.ainvoke(llm_messages_for_invoke, {"run_name": "rewrite_artifact_llm_call"})

    actual_artifact_text_response = response_ai_message.content
    if not isinstance(actual_artifact_text_response, str):
        actual_artifact_text_response = str(actual_artifact_text_response)

    thinking_message_for_state: Optional[AIMessage] = None
    if is_thinking_model(model_name):
        extracted_parts = extract_thinking_and_response_tokens(actual_artifact_text_response)
        if extracted_parts["thinking"]:
            thinking_message_for_state = AIMessage(
                id=f"thinking-{uuid.uuid4()}",
                content=extracted_parts["thinking"],
                additional_kwargs={"oc_hide_from_ui": True}
            )
        actual_artifact_text_response = extracted_parts["response"]

    new_artifact_content_item = create_new_rewrite_artifact_content(CreateNewArtifactContentArgs( # type: ignore
        artifact_type=determined_artifact_type,
        state=state,
        current_artifact_content_model=current_artifact_content_model,
        artifact_meta_tool_call=artifact_meta_update_schema,
        new_content_text=actual_artifact_text_response,
    ))

    existing_artifact_v3: Optional[ArtifactV3] = state.get("artifact")
    if not existing_artifact_v3:
         error_message = AIMessage(content="Critical error: Original artifact missing during rewrite.")
         return {"messages": [error_message], "_messages": state.get("_messages", []) + [error_message]}

    updated_artifact_contents = list(existing_artifact_v3.contents) + [new_artifact_content_item]

    final_artifact_v3 = ArtifactV3(
        currentIndex=len(updated_artifact_contents) - 1,
        contents=updated_artifact_contents
    )

    update_dict: Dict[str, Any] = {"artifact": final_artifact_v3}
    if thinking_message_for_state:
        update_dict["messages"] = [thinking_message_for_state]
        update_dict["_messages"] = [thinking_message_for_state]

    return update_dict


async def update_highlighted_text(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: update_highlighted_text")
    new_ai_message = AIMessage(content="Highlighted text update placeholder.")
    return {
        "messages": [new_ai_message],
        "_messages": state.get("_messages", []) + [new_ai_message],
        # "artifact": updated_artifact, "highlightedText": None
    }

async def rewrite_artifact_theme(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: rewrite_artifact_theme")
    new_ai_message = AIMessage(content="Artifact theme rewrite placeholder.")
    return {
        "messages": [new_ai_message],
        "_messages": state.get("_messages", []) + [new_ai_message],
        # "artifact": updated_artifact, "language": None, etc.
    }

async def rewrite_code_artifact_theme(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: rewrite_code_artifact_theme")
    new_ai_message = AIMessage(content="Code artifact theme rewrite placeholder.")
    return {
        "messages": [new_ai_message],
        "_messages": state.get("_messages", []) + [new_ai_message],
        # "artifact": updated_artifact, "addComments": None, etc.
    }

async def custom_action(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: custom_action")
    new_ai_message = AIMessage(content="Custom action placeholder.")
    return {
        "messages": [new_ai_message],
        "_messages": state.get("_messages", []) + [new_ai_message],
        # "artifact": updated_artifact, "customQuickActionId": None
    }

async def web_search_node(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: web_search_node (placeholder for webSearchGraph call)")
    # This node would typically:
    # 1. Get the actual user query from the last HumanMessage in state.get("_messages", [])
    # 2. Invoke a separate web search agent/graph with that query.
    # 3. The result of that sub-graph (list of SearchResult) comes back.
    # 4. Update the state with webSearchResults and webSearchEnabled=False.
    # It does NOT directly determine the next node for the main graph here.
    # That's done by routePostWebSearchNode.
    mock_search_results = [{"page_content": "Mock search result from web_search_node", "metadata": {"title": "Mock Site", "url":"http://mock.com"}}]
    return {
        "webSearchResults": mock_search_results,
        "webSearchEnabled": False # Critically, turn this off
    }

async def route_post_web_search_node(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: route_post_web_search_node")
    # This node decides where to go AFTER web_search_node has populated webSearchResults.
    # It also formats the webSearchResults into an AIMessage for the LLM.

    from app.schemas.common import SearchResult # For type hint
    web_results: Optional[List[SearchResult]] = state.get("webSearchResults")

    next_node_decision = "generateArtifact" if not state.get("artifact") else "rewriteArtifact"

    if not web_results: # Should not happen if web_search_node ran and found results
        print("Warning: No web search results found in route_post_web_search_node.")
        return {"next_node": next_node_decision} # No message to add about web results

    # Format web results into a message. This message goes into _messages for LLM context.
    # It does NOT go into the main 'messages' for UI display.
    # TODO: Port create_ai_message_from_web_results from TS if a complex format is needed.
    # For now, a simple concatenation:
    formatted_results_str = "\n".join(
        [f"Title: {res.get('metadata', {}).get('title', 'N/A')}\nURL: {res.get('metadata', {}).get('url', 'N/A')}\nContent Snippet: {res.get('page_content', '')[:200]}..."
         for res in web_results]
    )
    web_search_ai_message = AIMessage(
        content=f"Here are some web search results relevant to your query:\n{formatted_results_str}",
        additional_kwargs={"oc_hide_from_ui": True} # This message is for LLM context, not direct display
    )

    # Get current _messages, append the new web search AI message
    current_internal_messages = list(state.get("_messages", []))
    current_internal_messages.append(web_search_ai_message)

    return {
        "next_node": next_node_decision,
        "_messages": current_internal_messages, # Update _messages with the context from web search
        # webSearchEnabled should have been set to False by web_search_node
        # webSearchResults are kept for now, cleanStateNode might clear them later or they might be used by generate/rewrite.
    }


async def generate_followup(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: generate_followup")
    new_ai_message = AIMessage(content="Follow-up placeholder.")
    return {
        "messages": [new_ai_message],
        "_messages": state.get("_messages", []) + [new_ai_message]
    }

async def reflect_node(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: reflect_node")
    # This node might update 'reflections' in state based on state.get("messages")
    return {} # No direct message output, updates state fields like 'reflections'

async def clean_state_node(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: clean_state_node")
    # Returns a dictionary representing the fields to reset to their defaults.
    # LangGraph will merge this partial state into the main state.
    # It should only return fields that need to be reset.
    # For example, 'messages' and '_messages' are usually preserved by cleanState in TS.

    fields_to_reset = DEFAULT_INPUTS_PYTHON.copy()
    del fields_to_reset["messages"] # Don't clear conversation history
    del fields_to_reset["_messages"] # Don't clear internal message history
    del fields_to_reset["artifact"] # Don't clear artifact unless specified by logic

    # Specific logic from TS cleanState:
    # webSearchEnabled is reset.
    # webSearchResults are reset.
    # highlightedCode, highlightedText are reset.
    # customQuickActionId, language, artifactLength, etc. are reset.

    # This means DEFAULT_INPUTS_PYTHON should accurately reflect all clearable fields.
    return fields_to_reset


async def generate_title_node(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: generate_title_node")
    # This node would call an LLM to generate a title based on state.get("artifact") or state.get("messages")
    # It might update a 'title' field in the 'artifact' or a general 'conversation_title' in state.
    # For now, no message output, but could produce a SystemMessage with the title.
    return {}


async def summarizer_node(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    print("Executing Node: summarizer_node")
    # This node summarizes state.get("_messages", [])
    # The new summarized list becomes the new state._messages
    # Potentially, a summary message is also added to state.messages for UI.
    summarized_internal_history = [SystemMessage(content="The previous conversation has been summarized to save space.")]
    # Could also add a user-facing message:
    # summary_ui_message = SystemMessage(content="Conversation history has been summarized.")
    return {
        "_messages": summarized_internal_history,
        # "messages": state.get("messages", []) + [summary_ui_message] # Optional: inform user
    }


# --- Conditional Routing Functions (Updated signatures) ---
def route_node(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    # This conditional edge function receives the *entire current state* of the graph.
    # The preceding node (e.g., generate_path) must have updated the 'next_node' field in the state.
    print(f"Conditional Edge: route_node, current state's next_node is '{state.get('next_node')}'")
    next_node_val = state.get("next_node") # Read 'next_node' from the current graph state
    if not next_node_val:
        print("Warning: 'next_node' is not set in graph state for route_node. Defaulting to END.")
        return END
    return next_node_val


def conditionally_generate_title(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> Literal["generateTitleNode", "summarizerNode", END]: # type: ignore
    print("Conditional Edge: conditionally_generate_title")
    if len(state.get("messages", [])) <= 2: # User-facing messages count
         return "generateTitleNode"
    # Check if summarization is needed based on _messages length/tokens
    # This is where simple_token_calculator logic would effectively be.
    # Using CHARACTER_MAX from TS as an example.
    CHARACTER_MAX = 300000  # Example token/char count from TS
    current_total_chars = sum(len(get_string_from_content(m.content)) for m in state.get("_messages", []))
    if current_total_chars > CHARACTER_MAX:
        return "summarizerNode"
    return END

# simple_token_calculator is effectively merged into conditionally_generate_title's logic.
# No need for a separate conditional edge if conditionally_generate_title handles both paths.

def route_post_web_search_conditional(state: OpenCanvasState, config: Optional[Dict[str, Any]] = None) -> str:
    # This conditional edge follows 'route_post_web_search_node'.
    # That node should have set 'next_node' in its output, which updates the graph state.
    print(f"Conditional Edge: route_post_web_search_conditional, current state's next_node is '{state.get('next_node')}'")
    return state.get("next_node", END) # Read 'next_node' from graph state


# --- Graph Definition (Placeholders for node names, ensure they match .add_node calls) ---
# builder = StateGraph(OpenCanvasState)
# # Adding nodes (ensure names match strings in conditional edges)
# builder.add_node("generatePath", generate_path)
# builder.add_node("replyToGeneralInput", reply_to_general_input)
# builder.add_node("generateArtifact", generate_artifact)
# builder.add_node("updateArtifact", update_artifact)
# builder.add_node("updateHighlightedText", update_highlighted_text)
# builder.add_node("rewriteArtifactTheme", rewrite_artifact_theme)
# builder.add_node("rewriteCodeArtifactTheme", rewrite_code_artifact_theme)
# builder.add_node("customAction", custom_action)
# builder.add_node("webSearch", web_search_node)
# builder.add_node("routePostWebSearchNode", route_post_web_search_node) # Node before conditional edge
# builder.add_node("generateFollowup", generate_followup)
# builder.add_node("reflectNode", reflect_node) # Changed from "reflect" to match TS node name style
# builder.add_node("cleanStateNode", clean_state_node) # Changed from "cleanState"
# builder.add_node("generateTitleNode", generate_title_node)
# builder.add_node("summarizerNode", summarizer_node)

# builder.add_edge(START, "generatePath")

# # generatePath conditional routing using 'route_node' which reads 'next_node' from state
# builder.add_conditional_edges("generatePath", route_node, {
    # "updateArtifact": "updateArtifact",
    # "rewriteArtifactTheme": "rewriteArtifactTheme",
    # "rewriteCodeArtifactTheme": "rewriteCodeArtifactTheme",
    # "replyToGeneralInput": "replyToGeneralInput",
    # "generateArtifact": "generateArtifact",
    # # "rewriteArtifact": "updateArtifact", # Assuming 'rewriteArtifact' means general update, maps to 'updateArtifact' node
    # "customAction": "customAction",
    # "updateHighlightedText": "updateHighlightedText",
    # "webSearch": "webSearch",
    # END: END
# })

# # Edges from artifact modification/generation nodes to generateFollowup
# for node_name in ["generateArtifact", "updateArtifact", "updateHighlightedText",
#                   "rewriteArtifactTheme", "rewriteCodeArtifactTheme", "customAction"]:
#     builder.add_edge(node_name, "generateFollowup")

# builder.add_edge("webSearch", "routePostWebSearchNode")

# # Conditional routing after web search
# builder.add_conditional_edges("routePostWebSearchNode", route_post_web_search_conditional, {
    # "generateArtifact": "generateArtifact", # These are set by route_post_web_search_node
    # "updateArtifact": "updateArtifact",   # Assuming web search results feed into artifact update
    # END: END
# })

# builder.add_edge("replyToGeneralInput", "cleanStateNode")
# builder.add_edge("generateFollowup", "reflectNode")
# builder.add_edge("reflectNode", "cleanStateNode")

# # cleanStateNode conditional routing
# builder.add_conditional_edges("cleanStateNode", conditionally_generate_title, {
    # "generateTitleNode": "generateTitleNode",
    # "summarizerNode": "summarizerNode",
    # END: END
# })
# builder.add_edge("generateTitleNode", END)
# builder.add_edge("summarizerNode", END)

# # memory = SqliteSaver.from_conn_string(":memory:")
# # compiled_graph = builder.compile(checkpointer=memory)
# # print("Graph sketch compiled and ready for use.")

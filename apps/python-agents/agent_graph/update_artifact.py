from typing import Dict, Any, Optional, List, Union
import copy # For deepcopying state parts if necessary

from ...models import (
    OpenCanvasGraphState,
    ArtifactV3,
    ArtifactCodeV3,
    ArtifactMarkdownV3,
    Reflections as ReflectionsModel,
    CodeHighlight, # From models.py
    ContextDocument # Added for create_context_document_messages
)
from ...utils import (
    get_model_config as util_get_model_config, # Aliased
    get_model_from_config,
    create_context_document_messages,
    get_formatted_reflections,
    is_using_o1_mini_model,
    get_artifact_content,
    is_artifact_code_content
)
from .prompts import UPDATE_HIGHLIGHTED_ARTIFACT_PROMPT
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage


async def update_artifact_node(state: OpenCanvasGraphState, config: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Validate State
    if not state.artifact:
        raise ValueError("No artifact found in state for update_artifact_node.")

    current_artifact_version_model = get_artifact_content(state.artifact)

    if not is_artifact_code_content(current_artifact_version_model):
        raise ValueError("updateArtifact node can only operate on code artifacts.")

    current_code_content: ArtifactCodeV3 = current_artifact_version_model # type: ignore # Type assertion after check

    if not state.highlightedCode:
        raise ValueError("Cannot partially regenerate an artifact without a highlight (highlightedCode missing).")

    highlight_details: CodeHighlight = state.highlightedCode

    # 2. Model Selection Logic
    request_model_details = util_get_model_config(config)
    request_model_provider = request_model_details.get("modelProvider", "").lower()
    request_model_name = request_model_details.get("modelName", "").lower()

    llm_for_update: Any
    # Ensure gpt_4o_config is correctly formed for get_model_from_config
    gpt_4o_base_config = {
        "configurable": {
             "customModelName": "gpt-4o",
             # Potentially copy relevant parts from original config's 'configurable' if needed,
             # e.g., assistant_id, supabase_session, but avoid model-specific ones like azure details.
             "assistant_id": config.get("configurable", {}).get("assistant_id"),
             "supabase_session": config.get("configurable", {}).get("supabase_session"),
             # modelConfig for gpt-4o could be None or a generic one if applicable
             "modelConfig": None
        }
    }

    if "openai" in request_model_provider or "claude-3-5-sonnet" in request_model_name: # Corrected model name check
        llm_for_update = get_model_from_config(config, temperature=0)
    else:
        print(f"Defaulting to gpt-4o for partial code update, original model: {request_model_name}")
        llm_for_update = get_model_from_config(gpt_4o_base_config, temperature=0)


    if not llm_for_update:
        # If even gpt-4o fails, try the original config as a last resort if it wasn't already tried.
        if not ("openai" in request_model_provider or "claude-3-5-sonnet" in request_model_name):
            print(f"gpt-4o failed. Retrying with original model config: {request_model_name}")
            llm_for_update = get_model_from_config(config, temperature=0)

        if not llm_for_update: # If it still fails
            raise ValueError("Failed to initialize any suitable LLM for update_artifact_node")

    # 3. Prepare Prompt
    reflections_data_raw = config.get("configurable", {}).get("reflections_data")
    reflections_model_instance: Optional[ReflectionsModel] = None
    if isinstance(reflections_data_raw, dict):
        reflections_model_instance = ReflectionsModel.parse_obj(reflections_data_raw)
    elif isinstance(reflections_data_raw, ReflectionsModel):
        reflections_model_instance = reflections_data_raw
    memories_as_string = get_formatted_reflections(reflections_model_instance) if reflections_model_instance else "No reflections found."

    code_text = current_code_content.code
    start_char_idx = highlight_details.startCharIndex
    end_char_idx = highlight_details.endCharIndex

    context_start = max(0, start_char_idx - 500)
    context_end = min(len(code_text), end_char_idx + 500)

    text_before_highlight_in_window = code_text[context_start:start_char_idx]
    highlighted_text_segment = code_text[start_char_idx:end_char_idx]
    text_after_highlight_in_window = code_text[end_char_idx:context_end]

    formatted_prompt_str = UPDATE_HIGHLIGHTED_ARTIFACT_PROMPT.format(
        highlightedText=highlighted_text_segment,
        beforeHighlight=text_before_highlight_in_window,
        afterHighlight=text_after_highlight_in_window,
        reflections=memories_as_string
    )

    # 4. Prepare Messages for LLM
    internal_messages_history = state._messages if state._messages is not None else []
    recent_human_message_dict = next((msg for msg in reversed(internal_messages_history) if (msg.get("role") == "human" or msg.get("type") == "human")), None)
    if not recent_human_message_dict:
        raise ValueError("No recent human message found for update_artifact_node.")
    recent_human_message = HumanMessage(content=recent_human_message_dict.get("content",""))

    # Context Documents
    context_documents_input = config.get("configurable", {}).get("context_documents", [])
    parsed_context_docs: List[ContextDocument] = []
    if isinstance(context_documents_input, list):
        for doc_data in context_documents_input:
            if isinstance(doc_data, ContextDocument):
                parsed_context_docs.append(doc_data)
            elif isinstance(doc_data, dict):
                try:
                    parsed_context_docs.append(ContextDocument.parse_obj(doc_data))
                except Exception as e:
                    print(f"Skipping context document in update_artifact due to parsing error: {e}")

    context_llm_messages: List[BaseMessage] = create_context_document_messages(config, parsed_context_docs)

    llm_messages: List[BaseMessage] = []
    # Determine which config to use for is_using_o1_mini_model
    # If llm_for_update was defaulted to gpt-4o, use gpt_4o_config, otherwise original config
    active_config_for_o1_check = config
    if llm_for_update.model_name == "gpt-4o" and ("openai" not in request_model_provider and "claude-3-5-sonnet" not in request_model_name): # Check if it defaulted
        active_config_for_o1_check = gpt_4o_base_config

    if is_using_o1_mini_model(active_config_for_o1_check):
        llm_messages.append(HumanMessage(content=formatted_prompt_str))
    else:
        llm_messages.append(SystemMessage(content=formatted_prompt_str))

    llm_messages.extend(context_llm_messages)
    llm_messages.append(recent_human_message)

    # 5. Invoke LLM
    response_obj = await llm_for_update.ainvoke(llm_messages, config=config) # Pass original config for tracing etc.
    updated_artifact_segment: str = getattr(response_obj, 'content', '') if response_obj else ''
    if not isinstance(updated_artifact_segment, str):
        updated_artifact_segment = str(updated_artifact_segment)

    # 6. Reconstruct the full code content
    full_text_before_highlight = code_text[:start_char_idx]
    full_text_after_highlight = code_text[end_char_idx:]
    entire_updated_code = f"{full_text_before_highlight}{updated_artifact_segment}{full_text_after_highlight}"

    # 7. Create new artifact version
    if not state.artifact or not state.artifact.contents: # Should be caught by initial validation
        raise ValueError("Artifact or its contents are missing before creating new version.")

    new_artifact_code_obj = ArtifactCodeV3(
        index=len(state.artifact.contents) + 1,
        type="code",
        title=current_code_content.title,
        language=current_code_content.language,
        code=entire_updated_code
    )

    updated_artifact_contents = list(state.artifact.contents)
    updated_artifact_contents.append(new_artifact_code_obj)

    updated_artifact_v3 = ArtifactV3(
        currentIndex=new_artifact_code_obj.index,
        contents=updated_artifact_contents
    )

    # 8. Return State Update
    return {
        "artifact": updated_artifact_v3.dict(exclude_none=True),
        "next_node": "generateFollowup" # Or "END" if no followup after this type of update
    }

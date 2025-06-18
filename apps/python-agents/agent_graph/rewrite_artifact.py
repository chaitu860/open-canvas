from typing import Dict, Any, Optional, Union, List, Literal as TypingLiteral # Renamed to avoid clash
from pydantic import BaseModel, Field as PydanticField
import uuid

from ...models import (
    OpenCanvasGraphState,
    ArtifactV3,
    ArtifactCodeV3,
    ArtifactMarkdownV3,
    ProgrammingLanguageOptions,
    Reflections as ReflectionsModel,
    ContextDocument # Added ContextDocument for type hint
)
from ...utils import (
    get_model_config as util_get_model_config,
    get_model_from_config,
    create_context_document_messages,
    get_formatted_reflections,
    optionally_get_system_prompt_from_config,
    is_using_o1_mini_model,
    get_artifact_content,
    format_artifact_content,
    is_thinking_model,
    extract_thinking_and_response_tokens
)
from .prompts import (
    GET_TITLE_TYPE_REWRITE_ARTIFACT,
    OPTIONALLY_UPDATE_META_PROMPT,
    UPDATE_ENTIRE_ARTIFACT_PROMPT
)
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage

# --- Pydantic Schema for Meta Update Tool ---
class OptionallyUpdateArtifactMetaSchema(BaseModel):
    type: TypingLiteral["text", "code"] = PydanticField(description="The type of the artifact content.")
    title: Optional[str] = PydanticField(
        default=None,
        description="The new title to give the artifact. ONLY update this if the user is making a request which changes the subject/topic of the artifact."
    )
    language: Optional[ProgrammingLanguageOptions] = PydanticField(
        default=ProgrammingLanguageOptions.OTHER,
        description="The language of the code artifact. This should be populated with the programming language if the user is requesting code to be written, or 'other', in all other cases."
    )

# --- Helper: Optionally Update Artifact Meta ---
async def optionally_update_artifact_meta(
    state: OpenCanvasGraphState,
    config: Dict[str, Any]
) -> OptionallyUpdateArtifactMetaSchema:

    model_for_meta = get_model_from_config(config, temperature=0, is_tool_calling=True) # Temp 0 for deterministic meta update
    if not model_for_meta:
        raise ValueError("Failed to get model for optionally_update_artifact_meta")

    tool_calling_model = model_for_meta.with_structured_output(
        OptionallyUpdateArtifactMetaSchema,
        name="optionallyUpdateArtifactMeta"
    )

    reflections_data_raw = config.get("configurable", {}).get("reflections_data")
    reflections_model: Optional[ReflectionsModel] = None
    if isinstance(reflections_data_raw, dict):
        reflections_model = ReflectionsModel.parse_obj(reflections_data_raw)
    elif isinstance(reflections_data_raw, ReflectionsModel):
        reflections_model = reflections_data_raw

    memories_as_string = get_formatted_reflections(reflections_model) if reflections_model else "No reflections found."

    if not state.artifact: # Guard against None artifact
        raise ValueError("No artifact found in state for meta update (state.artifact is None).")
    current_artifact_content_model = get_artifact_content(state.artifact)
    if not current_artifact_content_model: # Should be caught by get_artifact_content if artifact.contents is empty
        raise ValueError("No artifact content found in state for meta update.")

    formatted_artifact_for_prompt = format_artifact_content(current_artifact_content_model, shorten_content=True)

    prompt_for_meta = GET_TITLE_TYPE_REWRITE_ARTIFACT.format(
        artifact=formatted_artifact_for_prompt,
        reflections=memories_as_string
    )

    # Ensure state._messages is not None before trying to iterate
    internal_messages_history = state._messages if state._messages is not None else []
    recent_human_message_dict = next((msg for msg in reversed(internal_messages_history) if (msg.get("role") == "human" or msg.get("type") == "human")), None)

    if not recent_human_message_dict: # If no human message, cannot proceed with this logic
        # Fallback: return current meta if no human message to guide the update
        print("Warning: No recent human message found for meta update. Returning current meta.")
        return OptionallyUpdateArtifactMetaSchema(
            type=current_artifact_content_model.type, # type: ignore # type: ignore because .type is Literal but Pydantic handles it
            title=current_artifact_content_model.title,
            language=getattr(current_artifact_content_model, 'language', ProgrammingLanguageOptions.OTHER)
        )

    recent_human_message = HumanMessage(content=recent_human_message_dict.get("content",""))

    llm_messages_for_meta: List[BaseMessage] = []
    sys_prompt_content = prompt_for_meta
    if is_using_o1_mini_model(config):
        llm_messages_for_meta.append(HumanMessage(content=sys_prompt_content))
    else:
        llm_messages_for_meta.append(SystemMessage(content=sys_prompt_content))
    llm_messages_for_meta.append(recent_human_message)

    try:
        response_meta_args: OptionallyUpdateArtifactMetaSchema = await tool_calling_model.ainvoke(llm_messages_for_meta, config=config)
        return response_meta_args
    except Exception as e:
        print(f"Error invoking LLM for artifact meta update: {e}")
        return OptionallyUpdateArtifactMetaSchema(
            type=current_artifact_content_model.type, # type: ignore
            title=current_artifact_content_model.title,
            language=getattr(current_artifact_content_model, 'language', ProgrammingLanguageOptions.OTHER)
        )

# --- Utilities ---
def validate_rewrite_state(state: OpenCanvasGraphState) -> Dict[str, Any]:
    if not state.artifact:
        raise ValueError("State artifact is None, cannot rewrite.")
    current_artifact_content_model = get_artifact_content(state.artifact)
    if not current_artifact_content_model:
        raise ValueError("No artifact content found in state for rewrite.")

    internal_messages_history = state._messages if state._messages is not None else []
    recent_human_message_dict = next((msg for msg in reversed(internal_messages_history) if (msg.get("role") == "human" or msg.get("type") == "human")), None)
    if not recent_human_message_dict:
        raise ValueError("No recent human message found for rewrite.")

    recent_human_message = HumanMessage(content=recent_human_message_dict.get("content",""))
    return {"current_artifact_content_model": current_artifact_content_model, "recent_human_message": recent_human_message}

def build_meta_prompt_for_rewrite(artifact_meta_tool_call: OptionallyUpdateArtifactMetaSchema) -> str:
    title_section = ""
    if artifact_meta_tool_call.title and artifact_meta_tool_call.type != "code":
        title_section = f"And its title is (do NOT include this in your response):\n{artifact_meta_tool_call.title}"

    return OPTIONALLY_UPDATE_META_PROMPT.format(
        artifactType=artifact_meta_tool_call.type,
        artifactTitle=title_section
    )

def build_main_rewrite_prompt(
    artifact_content_text: str,
    memories_as_string: str,
    is_new_type: bool,
    artifact_meta_tool_call: OptionallyUpdateArtifactMetaSchema
) -> str:
    meta_prompt_str = build_meta_prompt_for_rewrite(artifact_meta_tool_call) if is_new_type else ""

    return UPDATE_ENTIRE_ARTIFACT_PROMPT.format(
        artifactContent=artifact_content_text,
        reflections=memories_as_string,
        updateMetaPrompt=meta_prompt_str
    )

def get_language_for_rewritten_artifact(
    artifact_meta_tool_call: OptionallyUpdateArtifactMetaSchema,
    current_artifact_content_model: Union[ArtifactCodeV3, ArtifactMarkdownV3]
) -> ProgrammingLanguageOptions:
    if artifact_meta_tool_call.language and artifact_meta_tool_call.language != ProgrammingLanguageOptions.OTHER: # Prioritize if explicitly set and not default 'other'
        return artifact_meta_tool_call.language
    if isinstance(current_artifact_content_model, ArtifactCodeV3) and current_artifact_content_model.language:
        return current_artifact_content_model.language
    # If meta.language is OTHER and current is also OTHER or not code, return OTHER.
    # If meta.language is OTHER but current is specific, prefer current.
    return ProgrammingLanguageOptions.OTHER


def create_new_rewritten_artifact_content(
    artifact_type_str: TypingLiteral["text", "code"],
    state: OpenCanvasGraphState,
    current_artifact_content_model: Union[ArtifactCodeV3, ArtifactMarkdownV3],
    artifact_meta_tool_call: OptionallyUpdateArtifactMetaSchema,
    new_content_text: str
) -> Union[ArtifactCodeV3, ArtifactMarkdownV3]:

    new_index = len(state.artifact.contents) + 1 if state.artifact and state.artifact.contents else 1

    base_content_dict = {
        "index": new_index,
        "title": artifact_meta_tool_call.title or current_artifact_content_model.title # Fallback to old title
    }

    if artifact_type_str == "code":
        return ArtifactCodeV3(
            **base_content_dict,
            type="code",
            language=get_language_for_rewritten_artifact(artifact_meta_tool_call, current_artifact_content_model),
            code=new_content_text
        )
    else: # "text"
        return ArtifactMarkdownV3(
            **base_content_dict,
            type="text",
            fullMarkdown=new_content_text
        )

# --- Main Node: rewriteArtifact ---
async def rewrite_artifact_node(state: OpenCanvasGraphState, config: Dict[str, Any]) -> Dict[str, Any]:
    validated_data = validate_rewrite_state(state)
    current_artifact_content_model: Union[ArtifactCodeV3, ArtifactMarkdownV3] = validated_data["current_artifact_content_model"]
    recent_human_message: HumanMessage = validated_data["recent_human_message"]

    model_cfg_details = util_get_model_config(config)
    model_name = model_cfg_details.get("modelName", "unknown_model")

    artifact_meta_update_args = await optionally_update_artifact_meta(state, config)
    decided_artifact_type = artifact_meta_update_args.type
    is_new_type = decided_artifact_type != current_artifact_content_model.type

    reflections_data_raw = config.get("configurable", {}).get("reflections_data")
    reflections_model: Optional[ReflectionsModel] = None
    if isinstance(reflections_data_raw, dict):
        reflections_model = ReflectionsModel.parse_obj(reflections_data_raw)
    elif isinstance(reflections_data_raw, ReflectionsModel):
        reflections_model = reflections_data_raw
    memories_as_string = get_formatted_reflections(reflections_model) if reflections_model else "No reflections found."

    current_artifact_text = current_artifact_content_model.fullMarkdown if isinstance(current_artifact_content_model, ArtifactMarkdownV3) else current_artifact_content_model.code

    main_prompt_str = build_main_rewrite_prompt(
        artifact_content_text=current_artifact_text,
        memories_as_string=memories_as_string,
        is_new_type=is_new_type,
        artifact_meta_tool_call=artifact_meta_update_args
    )

    user_system_prompt = optionally_get_system_prompt_from_config(config)
    full_system_prompt_content = f"{user_system_prompt}\n{main_prompt_str}" if user_system_prompt else main_prompt_str

    rewrite_llm = get_model_from_config(config, temperature=0.3) # Slightly lower temp for rewrite
    if not rewrite_llm:
        raise ValueError("Failed to initialize LLM for rewrite_artifact_node")

    llm_messages_for_rewrite: List[BaseMessage] = []
    if is_using_o1_mini_model(config):
        llm_messages_for_rewrite.append(HumanMessage(content=full_system_prompt_content))
    else:
        llm_messages_for_rewrite.append(SystemMessage(content=full_system_prompt_content))

    # Context Documents: Check if they are List[ContextDocument] or need parsing
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
                    print(f"Skipping context document in rewrite_artifact due to parsing error: {e}")

    context_llm_messages: List[BaseMessage] = create_context_document_messages(config, parsed_context_docs)
    llm_messages_for_rewrite.extend(context_llm_messages)
    llm_messages_for_rewrite.append(recent_human_message)

    raw_artifact_response_obj = await rewrite_llm.ainvoke(llm_messages_for_rewrite, config=config)
    raw_artifact_response_content: str = getattr(raw_artifact_response_obj, 'content', '') if raw_artifact_response_obj else ''

    thinking_message_dict: Optional[Dict[str,Any]] = None
    final_artifact_text = raw_artifact_response_content

    if is_thinking_model(model_name):
        extracted = extract_thinking_and_response_tokens(raw_artifact_response_content)
        if extracted["thinking"]:
            thinking_ai_msg = AIMessage(id=f"thinking-{uuid.uuid4()}", content=extracted["thinking"])
            thinking_message_dict = thinking_ai_msg.dict()
        final_artifact_text = extracted["response"]

    new_artifact_content_obj = create_new_rewritten_artifact_content(
        artifact_type_str=decided_artifact_type,
        state=state,
        current_artifact_content_model=current_artifact_content_model,
        artifact_meta_tool_call=artifact_meta_update_args,
        new_content_text=final_artifact_text
    )

    if not state.artifact:
        raise ValueError("State artifact is None, cannot update contents list.") # Should be caught by validate

    updated_artifact_contents = list(state.artifact.contents)
    updated_artifact_contents.append(new_artifact_content_obj)

    updated_artifact = ArtifactV3(
        currentIndex=new_artifact_content_obj.index,
        contents=updated_artifact_contents
    )

    messages_to_add_to_ui: List[Dict[str,Any]] = [] # For user-facing messages
    # Thinking messages are typically not for UI, but for internal log (_messages)
    # If they were for UI, they'd be added to messages_to_add_to_ui

    updated_internal_history = list(state._messages if state._messages is not None else [])
    if thinking_message_dict:
        updated_internal_history.append(thinking_message_dict)

    return {
        "artifact": updated_artifact.dict(exclude_none=True),
        "messages": messages_to_add_to_ui,
        "_messages": updated_internal_history,
        "next_node": "generateFollowup" # Typically, after a rewrite, a followup is generated.
    }

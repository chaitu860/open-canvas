from typing import Dict, Any, Optional, List
import uuid # For thinking message ID

from ...models import (
    OpenCanvasGraphState,
    ArtifactV3,
    ArtifactMarkdownV3,
    Reflections as ReflectionsModel,
    LanguageOptions,
    ReadingLevelOptions,
    ArtifactLengthOptions
)
from ...utils import (
    get_model_config as util_get_model_config,
    get_model_from_config,
    get_formatted_reflections, # Corrected: this is the one that takes ReflectionsModel
    is_thinking_model,
    extract_thinking_and_response_tokens,
    get_artifact_content,
    is_artifact_markdown_content
)
from .prompts import (
    ADD_EMOJIS_TO_ARTIFACT_PROMPT,
    CHANGE_ARTIFACT_LANGUAGE_PROMPT,
    CHANGE_ARTIFACT_LENGTH_PROMPT,
    CHANGE_ARTIFACT_READING_LEVEL_PROMPT,
    CHANGE_ARTIFACT_TO_PIRATE_PROMPT
)
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

async def rewrite_artifact_theme_node(state: OpenCanvasGraphState, config: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Validate State and Get Current Content
    if not state.artifact:
        raise ValueError("No artifact found in state for rewrite_artifact_theme_node.")

    current_artifact_version_model = get_artifact_content(state.artifact)

    if not is_artifact_markdown_content(current_artifact_version_model):
        raise ValueError("rewriteArtifactTheme node can only operate on markdown artifacts.")

    current_markdown_content: ArtifactMarkdownV3 = current_artifact_version_model # type: ignore # Type assertion

    # 2. Determine Prompt based on State Flags
    formatted_prompt_str = ""
    prompt_template_vars = {"artifactContent": current_markdown_content.fullMarkdown, "reflections": ""} # reflections added later

    if state.language:
        prompt_template_vars["newLanguage"] = state.language.value
        formatted_prompt_str = CHANGE_ARTIFACT_LANGUAGE_PROMPT.format(**prompt_template_vars)
    elif state.readingLevel:
        if state.readingLevel == ReadingLevelOptions.PIRATE:
            formatted_prompt_str = CHANGE_ARTIFACT_TO_PIRATE_PROMPT.format(**prompt_template_vars)
        else:
            new_reading_level_text = ""
            if state.readingLevel == ReadingLevelOptions.CHILD:
                new_reading_level_text = "elementary school student"
            elif state.readingLevel == ReadingLevelOptions.TEENAGER:
                new_reading_level_text = "high school student"
            elif state.readingLevel == ReadingLevelOptions.COLLEGE:
                new_reading_level_text = "college student"
            elif state.readingLevel == ReadingLevelOptions.PHD:
                new_reading_level_text = "PhD student"
            else:
                raise ValueError(f"Unknown reading level: {state.readingLevel}")
            prompt_template_vars["newReadingLevel"] = new_reading_level_text
            formatted_prompt_str = CHANGE_ARTIFACT_READING_LEVEL_PROMPT.format(**prompt_template_vars)
    elif state.artifactLength:
        new_length_text = ""
        if state.artifactLength == ArtifactLengthOptions.SHORTEST:
            new_length_text = "much shorter than it currently is"
        elif state.artifactLength == ArtifactLengthOptions.SHORT:
            new_length_text = "slightly shorter than it currently is"
        elif state.artifactLength == ArtifactLengthOptions.LONG:
            new_length_text = "slightly longer than it currently is"
        elif state.artifactLength == ArtifactLengthOptions.LONGEST:
            new_length_text = "much longer than it currently is"
        else:
            raise ValueError(f"Unknown artifact length: {state.artifactLength}")
        prompt_template_vars["newLength"] = new_length_text
        formatted_prompt_str = CHANGE_ARTIFACT_LENGTH_PROMPT.format(**prompt_template_vars)
    elif state.regenerateWithEmojis is True:
        formatted_prompt_str = ADD_EMOJIS_TO_ARTIFACT_PROMPT.format(**prompt_template_vars)
    else:
        raise ValueError("No theme selected for rewriteArtifactTheme node.")

    # 3. Add Reflections to Prompt
    reflections_data_raw = config.get("configurable", {}).get("reflections_data")
    reflections_model_instance: Optional[ReflectionsModel] = None
    if isinstance(reflections_data_raw, dict):
        reflections_model_instance = ReflectionsModel.parse_obj(reflections_data_raw)
    elif isinstance(reflections_data_raw, ReflectionsModel):
        reflections_model_instance = reflections_data_raw

    memories_as_string = "No reflections found."
    if reflections_model_instance: # Check if it's not None
        memories_as_string = get_formatted_reflections(reflections_model_instance) # Ensure this util is correctly imported and used

    # Replace {reflections} placeholder in the chosen prompt string
    formatted_prompt_str = formatted_prompt_str.replace("{reflections}", memories_as_string)

    # 4. Get Model and Invoke
    model_details = util_get_model_config(config)
    model_name = model_details.get("modelName", "unknown_model")

    llm_model = get_model_from_config(config)
    if not llm_model:
        raise ValueError("Failed to initialize LLM for rewrite_artifact_theme_node")

    llm_messages: List[BaseMessage] = [HumanMessage(content=formatted_prompt_str)]

    raw_response_obj = await llm_model.ainvoke(llm_messages, config=config)
    rewritten_artifact_text: str = getattr(raw_response_obj, 'content', '') if raw_response_obj else ''
    if not isinstance(rewritten_artifact_text, str):
         rewritten_artifact_text = str(rewritten_artifact_text)

    # 5. Handle Thinking Model Logic
    thinking_message_dict: Optional[Dict[str,Any]] = None
    final_artifact_text_for_state = rewritten_artifact_text

    if is_thinking_model(model_name):
        extracted = extract_thinking_and_response_tokens(rewritten_artifact_text)
        if extracted["thinking"]:
            thinking_ai_msg = AIMessage(id=f"thinking-{uuid.uuid4()}", content=extracted["thinking"])
            thinking_message_dict = thinking_ai_msg.dict()
        final_artifact_text_for_state = extracted["response"]

    # 6. Create New Artifact Version
    if not state.artifact or not state.artifact.contents: # Should be caught by initial validation
        raise ValueError("Artifact or its contents are missing when creating new version.")

    new_artifact_markdown_obj = ArtifactMarkdownV3(
        index=len(state.artifact.contents) + 1,
        type="text",
        title=current_markdown_content.title,
        fullMarkdown=final_artifact_text_for_state
    )

    updated_artifact_contents = list(state.artifact.contents)
    updated_artifact_contents.append(new_artifact_markdown_obj)

    updated_artifact_v3 = ArtifactV3(
        currentIndex=new_artifact_markdown_obj.index,
        contents=updated_artifact_contents
    )

    # 7. Prepare State Update
    messages_to_add_to_ui: List[Dict[str,Any]] = []
    # if thinking_message_dict: # Typically thinking messages are not for UI
    #    messages_to_add_to_ui.append(thinking_message_dict)

    updated_internal_history = list(state._messages if state._messages is not None else [])
    if thinking_message_dict:
        updated_internal_history.append(thinking_message_dict)

    return {
        "artifact": updated_artifact_v3.dict(exclude_none=True),
        "messages": messages_to_add_to_ui, # Usually empty for this node, followup handles UI message
        "_messages": updated_internal_history,
        "next_node": "generateFollowup"
    }

from typing import Dict, Any, Optional, List
import copy # For deepcopying config

from ...models import (
    OpenCanvasGraphState,
    ArtifactV3,
    ArtifactMarkdownV3,
    TextHighlight, # From models.py
    ContextDocument # For create_context_document_messages
)
from ...utils import (
    get_model_config as util_get_model_config, # Aliased
    get_model_from_config,
    create_context_document_messages,
    is_using_o1_mini_model,
    get_artifact_content,
    is_artifact_markdown_content
)
# No specific prompts from prompts.py are used here, the prompt is local to this node.
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage

# Prompt specific to this node
UPDATE_HIGHLIGHTED_TEXT_NODE_PROMPT = """You are an expert AI writing assistant, tasked with rewriting some text a user has selected. The selected text is nested inside a larger 'block'. You should always respond with ONLY the updated text block in accordance with the user's request.
You should always respond with the full markdown text block, as it will simply replace the existing block in the artifact.
The blocks will be joined later on, so you do not need to worry about the formatting of the blocks, only make sure you keep the formatting and structure of the block you are updating.

# Selected text
{highlightedText}

# Text block
{textBlocks}

Your task is to rewrite the sourounding content to fulfill the users request. The selected text content you are provided above has had the markdown styling removed, so you can focus on the text itself.
However, ensure you ALWAYS respond with the full markdown text block, including any markdown syntax.
NEVER wrap your response in any additional markdown syntax, as this will be handled by the system. Do NOT include a triple backtick wrapping the text block, unless it was present in the original text block.
You should NOT change anything EXCEPT the selected text. The ONLY instance where you may update the sourounding text is if it is necessary to make the selected text make sense.
You should ALWAYS respond with the full, updated text block, including any formatting, e.g newlines, indents, markdown syntax, etc. NEVER add extra syntax or formatting unless the user has specifically requested it.
If you observe partial markdown, this is OKAY because you are only updating a partial piece of the text.

Ensure you reply with the FULL text block, including the updated selected text. NEVER include only the updated selected text, or additional prefixes or suffixes."""

async def update_highlighted_text_node(state: OpenCanvasGraphState, config: Dict[str, Any]) -> Dict[str, Any]:
    # 1. Validate State
    if not state.artifact:
        raise ValueError("No artifact found in state for update_highlighted_text_node.")

    current_artifact_version_model = get_artifact_content(state.artifact)

    if not is_artifact_markdown_content(current_artifact_version_model): # Ensures it's ArtifactMarkdownV3
        raise ValueError("updateHighlightedText node can only operate on markdown artifacts.")

    current_markdown_content: ArtifactMarkdownV3 = current_artifact_version_model # type: ignore # Type assertion

    if not state.highlightedText:
        raise ValueError("Cannot partially regenerate an artifact without a highlight (highlightedText missing).")

    highlight_details: TextHighlight = state.highlightedText

    # 2. Model Selection Logic
    request_model_details = util_get_model_config(config)
    request_model_provider = request_model_details.get("modelProvider", "").lower()
    request_model_name = request_model_details.get("modelName", "").lower()

    llm_for_update: Any
    gpt_4o_base_config = {
        "configurable": {
             "customModelName": "gpt-4o",
             "assistant_id": config.get("configurable", {}).get("assistant_id"),
             "supabase_session": config.get("configurable", {}).get("supabase_session"),
             "modelConfig": None
        }
    }
    active_config_for_o1_check = config # Default to original config for o1 check

    if "openai" in request_model_provider or "claude-3-5-sonnet" in request_model_name:
        llm_for_update = get_model_from_config(config, temperature=0)
    else:
        print(f"Defaulting to gpt-4o for highlighted text update, original model: {request_model_name}")
        llm_for_update = get_model_from_config(gpt_4o_base_config, temperature=0)
        active_config_for_o1_check = gpt_4o_base_config


    if not llm_for_update:
        if not ("openai" in request_model_provider or "claude-3-5-sonnet" in request_model_name):
            print(f"gpt-4o failed. Retrying with original model config: {request_model_name}")
            llm_for_update = get_model_from_config(config, temperature=0)
            active_config_for_o1_check = config # Revert o1 check config too

        if not llm_for_update:
            raise ValueError("Failed to initialize any suitable LLM for update_highlighted_text_node")

    llm_for_update = llm_for_update.with_config({"run_name": "update_highlighted_markdown"})

    # 3. Prepare Prompt
    formatted_prompt_str = UPDATE_HIGHLIGHTED_TEXT_NODE_PROMPT.format(
        highlightedText=highlight_details.selectedText,
        textBlocks=highlight_details.markdownBlock # This is 'markdownBlock' in TextHighlight model
    )

    # 4. Prepare Messages for LLM
    internal_messages_history = state._messages if state._messages is not None else []
    recent_human_message_dict = next((msg for msg in reversed(internal_messages_history) if (msg.get("role") == "human" or msg.get("type") == "human")), None)
    if not recent_human_message_dict:
        raise ValueError("No recent human message found for update_highlighted_text_node.")
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
                    print(f"Skipping context document in update_highlighted_text due to parsing error: {e}")

    context_llm_messages: List[BaseMessage] = create_context_document_messages(config, parsed_context_docs)

    llm_messages: List[BaseMessage] = []
    if is_using_o1_mini_model(active_config_for_o1_check):
        llm_messages.append(HumanMessage(content=formatted_prompt_str))
    else:
        llm_messages.append(SystemMessage(content=formatted_prompt_str))

    llm_messages.extend(context_llm_messages)
    llm_messages.append(recent_human_message)

    # 5. Invoke LLM
    response = await llm_for_update.ainvoke(llm_messages, config=config) # Pass original config for tracing
    updated_markdown_block_segment: str = getattr(response, 'content', '') if response else ''
    if not isinstance(updated_markdown_block_segment, str):
        updated_markdown_block_segment = str(updated_markdown_block_segment)

    # 6. Reconstruct the full markdown content
    original_full_markdown = current_markdown_content.fullMarkdown # Use current artifact content
    original_markdown_block_from_highlight = highlight_details.markdownBlock

    # Ensure the block to be replaced is actually part of the current artifact's full markdown
    if original_markdown_block_from_highlight not in original_full_markdown:
        # This indicates a potential mismatch or stale highlight data.
        # Attempt to find the block if it's just a whitespace/exact match issue, or error out.
        print(f"Warning: highlightedText.markdownBlock ('{original_markdown_block_from_highlight[:50]}...') not found verbatim in current artifact's fullMarkdown.")
        # As a fallback, if the content is small, we might assume the LLM returned the *full* new markdown.
        # However, the prompt asks it to return the *updated block*. This scenario needs careful handling.
        # For now, if not found, we might try replacing in highlight_details.fullMarkdown if it's different.
        if original_markdown_block_from_highlight in highlight_details.fullMarkdown:
             print("Replacing block in highlight_details.fullMarkdown as a fallback.")
             new_full_markdown_content = highlight_details.fullMarkdown.replace(original_markdown_block_from_highlight, updated_markdown_block_segment, 1)
        else:
             # If still not found, this is problematic. The safest might be to not change, or signal error.
             # Or, assume the LLM's output *is* the new full content if the block context is lost.
             # Given the prompt, the LLM returns the *block*, so replacing is key.
             raise ValueError("Markdown block from highlight details not found in current artifact or highlight's full markdown.")
    else:
        new_full_markdown_content = original_full_markdown.replace(original_markdown_block_from_highlight, updated_markdown_block_segment, 1)

    # 7. Create new artifact version
    if not state.artifact or not state.artifact.contents:
         raise ValueError("Artifact or its contents are missing when creating new version.")

    new_artifact_markdown_obj = ArtifactMarkdownV3(
        index=len(state.artifact.contents) + 1,
        type="text",
        title=current_markdown_content.title,
        fullMarkdown=new_full_markdown_content
    )

    updated_artifact_contents = list(state.artifact.contents)
    updated_artifact_contents.append(new_artifact_markdown_obj)

    updated_artifact_v3 = ArtifactV3(
        currentIndex=new_artifact_markdown_obj.index,
        contents=updated_artifact_contents
    )

    # 8. Return State Update
    return {
        "artifact": updated_artifact_v3.dict(exclude_none=True),
        "next_node": "generateFollowup" # Or "END"
    }

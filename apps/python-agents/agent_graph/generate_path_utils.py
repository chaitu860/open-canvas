import base64 # For include_url_contents if transforming prompt
from typing import Dict, Any, List, Optional, Union, Literal # Added Literal here
from pydantic import BaseModel, Field as PydanticField # To avoid conflict with Langchain Field
import uuid # For message IDs
import os # For FIRECRAWL_API_KEY

from ...models import OpenCanvasGraphState, ContextDocument, ProgrammingLanguageOptions # Relative import from parent
from ...utils import (
    get_model_from_config,
    create_context_document_messages,
    convert_pdf_to_text, # Used in fix_misformatted_context_doc_message
    get_model_config as util_get_model_config, # Renamed to avoid conflict if any
    get_string_from_content
)
from .prompts import (
    ROUTE_QUERY_PROMPT,
    ROUTE_QUERY_OPTIONS_HAS_ARTIFACTS,
    ROUTE_QUERY_OPTIONS_NO_ARTIFACTS,
    CURRENT_ARTIFACT_PROMPT,
    NO_ARTIFACT_PROMPT
)
from ...utils import format_artifact_content_with_template # from main utils

from langchain_core.messages import HumanMessage, BaseMessage, AIMessage, SystemMessage, MessageContent, RemoveMessage
from langchain_community.document_loaders import FireCrawlLoader # For include_url_contents

# Zod schemas from JS need to be Pydantic models for tool binding in LangChain Python
class RouteQuerySchema(BaseModel):
    route: str = PydanticField(description="The route to take based on the user's query.")

class DetermineIncludeUrlContentsSchema(BaseModel):
    shouldIncludeUrlContents: bool = PydanticField(description="Whether or not to include the contents of the URL in the prompt.")

# Moved DynamicRouteQuerySchema definition here, before it's used.
class DynamicRouteQuerySchema(BaseModel):
    route: Literal["replyToGeneralInput", "rewriteArtifact", "generateArtifact"] = PydanticField(description="The route to take based on the user's query.")


async def dynamic_determine_path_node(
    state: OpenCanvasGraphState,
    new_messages_from_path_logic: List[BaseMessage], # Messages added by generate_path before this call
    config: Dict[str, Any]
) -> Optional[Dict[str, str]]:
    # Equivalent of dynamicDeterminePathFunc

    current_artifact_content_model = None
    if state.artifact:
        from ...utils import get_artifact_content
        current_artifact_content_model = get_artifact_content(state.artifact)

    artifact_options_prompt = ROUTE_QUERY_OPTIONS_HAS_ARTIFACTS if current_artifact_content_model else ROUTE_QUERY_OPTIONS_NO_ARTIFACTS

    # Ensure state._messages is not None before slicing
    messages_to_join = state._messages if state._messages is not None else []
    recent_messages_str = "\n\n".join([f"{msg.get('type', 'unknown')}: {get_string_from_content(msg.get('content', ''))}"
                                         for msg in messages_to_join[-3:]])


    current_artifact_prompt_str = format_artifact_content_with_template(
        CURRENT_ARTIFACT_PROMPT, current_artifact_content_model
    ) if current_artifact_content_model else NO_ARTIFACT_PROMPT

    formatted_prompt = ROUTE_QUERY_PROMPT.format(
        artifactOptions=artifact_options_prompt,
        recentMessages=recent_messages_str,
        currentArtifactPrompt=current_artifact_prompt_str
    )

    # artifact_route_name = "rewriteArtifact" if current_artifact_content_model else "generateArtifact" # Not directly used in this func

    model = get_model_from_config(config, temperature=0, is_tool_calling=True)
    if not model:
        raise ValueError("Failed to initialize model for dynamic_determine_path")

    # Ensure DynamicRouteQuerySchema includes all possible routes the LLM might suggest,
    # even if the prompt guides it towards a subset based on artifact presence.
    # The provided schema is: Literal["replyToGeneralInput", "rewriteArtifact", "generateArtifact"]
    # This seems correct as these are the fundamental routing decisions.
    model_with_tool = model.with_structured_output(DynamicRouteQuerySchema, name="route_query")

    # context_docs_for_routing = [] # Placeholder from prompt, not used yet

    llm_messages_content: List[Union[BaseMessage, Dict[str, Any]]] = []
    # llm_messages_content.extend(context_docs_for_routing)
    llm_messages_content.extend(new_messages_from_path_logic)
    llm_messages_content.append(HumanMessage(content=formatted_prompt))

    # Ensure all elements are valid message types for ainvoke
    final_llm_messages_for_ainvoke: List[BaseMessage] = []
    for m_content in llm_messages_content:
        if isinstance(m_content, BaseMessage):
            final_llm_messages_for_ainvoke.append(m_content)
        elif isinstance(m_content, dict): # Attempt to convert dict to BaseMessage if necessary
            # This part is tricky; dicts aren't directly BaseMessages.
            # Assuming new_messages_from_path_logic are already BaseMessage objects.
            # If they were dicts, they'd need proper conversion based on 'role'/'type'.
            # For now, this will fail if m_content is a dict not parsable by the LLM.
            # Given the type hint of new_messages_from_path_logic is List[BaseMessage], this branch might not be needed.
            print(f"Warning: Attempting to use a dict as a message: {m_content}")
            # Potentially convert dict to a HumanMessage or AIMessage if structure is known
            # e.g. if m_content.get("role") == "user": final_llm_messages_for_ainvoke.append(HumanMessage(content=m_content.get("content","")))
            # This is simplified; robust conversion would be needed if dicts are expected here.
        else:
            print(f"Warning: Invalid type in messages for LLM: {type(m_content)}")


    try:
        result_structured = await model_with_tool.ainvoke(final_llm_messages_for_ainvoke)
        if result_structured and hasattr(result_structured, 'route'):
            # The schema for DynamicRouteQuerySchema has route: Literal["replyToGeneralInput", "rewriteArtifact", "generateArtifact"]
            # This means Pydantic already validated the output against these options.
            # No need for: if result_structured.route not in DynamicRouteQuerySchema.schema()["properties"]["route"]["enum"]
            return {"route": result_structured.route}
        else:
            print(f"Warning: LLM structured output for routing is missing 'route' or is None. Result: {result_structured}")
            # Defaulting if structure is not as expected
            return {"route": "replyToGeneralInput"}
    except Exception as e:
        print(f"Error in dynamic_determine_path LLM call: {e}")
    return {"route": "replyToGeneralInput"} # Default route on error


async def include_url_contents_node(
    message: HumanMessage,
    urls: List[str],
    config: Dict[str, Any]
) -> Optional[HumanMessage]:

    firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
    if not firecrawl_api_key and config.get("configurable", {}).get("firecrawl_api_key"):
        firecrawl_api_key = config["configurable"]["firecrawl_api_key"]

    if not firecrawl_api_key:
        print("WARN: FireCrawl API key not found. Cannot scrape URLs.")
        return None # Return None, not the original message, if scraping cannot proceed

    INCLUDE_URL_DECISION_PROMPT = """You're an advanced AI assistant.
You have been tasked with analyzing the user's message and determining if the user wants the contents of the URL included in their message included in their prompt.
You should ONLY answer 'true' if it is explicitly clear the user included the URL in their message so that its contents would be included in the prompt, otherwise, answer 'false'

Here is the user's message:
<message>
{message_content}
</message>

Now, given their message, determine whether or not they want the contents of that webpage to be included in the prompt."""

    temp_model_config_for_decision = {
        "configurable": {
            "customModelName": config.get("configurable",{}).get("url_decision_model", "gemini-1.5-flash-latest"),
            "modelConfig": None
        }
    }
    decision_model = get_model_from_config(temp_model_config_for_decision, temperature=0, is_tool_calling=True)
    if not decision_model:
        print("WARN: Could not initialize decision_model for include_url_contents.")
        return None

    decision_model_with_tool = decision_model.with_structured_output(DetermineIncludeUrlContentsSchema, name="determine_include_url_contents")

    prompt_content_str = get_string_from_content(message.content)
    formatted_decision_prompt = INCLUDE_URL_DECISION_PROMPT.format(message_content=prompt_content_str)

    should_include = False # Default to false
    try:
        decision_result = await decision_model_with_tool.ainvoke([HumanMessage(content=formatted_decision_prompt)])
        if decision_result and isinstance(decision_result, DetermineIncludeUrlContentsSchema):
            should_include = decision_result.shouldIncludeUrlContents
    except Exception as e:
        print(f"Error in include_url_contents decision LLM call: {e}")
        # should_include remains False

    if not should_include:
        return None # Return None if contents should not be included

    scraped_contents = []
    for url in urls:
        try:
            # Using FirecrawlLoader with await for aload
            loader = FireCrawlLoader(api_key=firecrawl_api_key, url=url, mode="scrape", params={"pageOptions": {"onlyMainContent": True}})
            docs = await loader.aload() # Use aload for async
            if docs:
                scraped_contents.append({"url": url, "pageContent": docs[0].page_content})
        except Exception as e:
            print(f"Error scraping URL {url} with FireCrawl: {e}")
            scraped_contents.append({"url": url, "pageContent": f"Error scraping URL: {url}. Could not retrieve content."}) # Informative error content

    transformed_prompt_str = prompt_content_str
    for item in scraped_contents:
        transformed_prompt_str = transformed_prompt_str.replace(
            item["url"],
            f"<page-contents url=\"{item['url']}\">\n{item['pageContent']}\n</page-contents>"
        )

    # Ensure message.id is a string or generate a new one.
    message_id = message.id if isinstance(message.id, str) else str(uuid.uuid4())
    return HumanMessage(content=transformed_prompt_str, id=message_id, additional_kwargs=message.additional_kwargs)


async def convert_context_document_to_human_message(
    messages: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> Optional[HumanMessage]:
    if not messages:
        return None

    last_message_dict = messages[-1]
    # Ensure additional_kwargs exists and is a dict before accessing "documents"
    additional_kwargs = last_message_dict.get("additional_kwargs")
    if not isinstance(additional_kwargs, dict):
        return None
    documents_raw = additional_kwargs.get("documents")


    if not documents_raw or not isinstance(documents_raw, list):
        return None

    try:
        # Ensure each item in documents_raw is a dictionary before parsing
        context_document_list = [ContextDocument.parse_obj(doc_dict) for doc_dict in documents_raw if isinstance(doc_dict, dict)]
    except Exception as e: # Catch Pydantic validation errors too
        print(f"Error parsing documents from last message: {e}")
        return None

    if not context_document_list:
        return None

    # Assuming create_context_document_messages is an async function if any underlying operations are async
    # Based on its current Python version, it's sync.
    formatted_content_messages: List[BaseMessage] = create_context_document_messages(config, context_document_list)

    if not formatted_content_messages:
        return None

    final_message_content: MessageContent = [] # This should be List[Union[str, Dict]]
    if formatted_content_messages:
        # Assuming the first message in the list is the one we want the content from
        msg_content_part = formatted_content_messages[0].content
        if isinstance(msg_content_part, str):
            final_message_content.append({"type": "text", "text": msg_content_part})
        elif isinstance(msg_content_part, list): # It's already List[Dict]
            final_message_content.extend(msg_content_part)

    if not final_message_content: # Check if anything was added
        return None

    OC_HIDE_FROM_UI_KEY_PY = "oc_hide_from_ui"

    return HumanMessage(
        content=final_message_content,
        id=str(uuid.uuid4()), # Always generate a new ID for this derived message
        additional_kwargs={OC_HIDE_FROM_UI_KEY_PY: True}
    )


async def fix_misformatted_context_doc_message(
    message: HumanMessage,
    config: Dict[str, Any]
) -> Optional[List[Union[RemoveMessage, HumanMessage]]]:
    if isinstance(message.content, str): # Only process if content is complex (list of parts)
        return None

    model_details = util_get_model_config(config) # util_get_model_config is already imported as such
    current_provider = model_details.get("modelProvider")

    new_content_parts: List[Dict[str, Any]] = []
    changes_made = False

    original_content_list = message.content if isinstance(message.content, list) else []

    for part in original_content_list:
        if not isinstance(part, dict):
            # If part is not a dict (e.g. a string), wrap it or skip, depending on desired handling
            if isinstance(part, str): # Example: wrap stray strings into text parts
                 new_content_parts.append({"type": "text", "text": part})
            # else: skip or raise error for unknown part types
            continue # Process next part

        part_type = part.get("type")

        # Logic for OpenAI: convert specific 'document' or 'application/pdf' types to 'text'
        if current_provider == "openai":
            if part_type == "document" and part.get("source", {}).get("type") == "base64":
                pdf_data = part.get("source", {}).get("data")
                media_type = part.get("source", {}).get("media_type")
                if pdf_data and media_type == "application/pdf": # Check it's a PDF
                    text = convert_pdf_to_text(pdf_data)
                    new_content_parts.append({"type": "text", "text": text})
                    changes_made = True
                    continue
            # Handle direct "application/pdf" part type if it exists (less common for OpenAI complex content)
            elif part_type == "application/pdf" and "data" in part:
                pdf_data = part.get("data")
                if pdf_data: # Assuming data is base64 encoded string
                    text = convert_pdf_to_text(pdf_data)
                    new_content_parts.append({"type": "text", "text": text})
                    changes_made = True
                    continue

        # Logic for Anthropic: ensure 'application/pdf' is wrapped in 'document' structure
        elif current_provider == "anthropic":
            if part_type == "application/pdf" and "data" in part: # If it's a direct PDF part
                new_content_parts.append({
                    "type": "document", # Wrap in Anthropic's expected document structure
                    "source": {
                        "type": "base64",
                        "media_type": part_type,
                        "data": part.get("data")
                    }
                })
                changes_made = True
                continue

        # Logic for Google GenAI: ensure 'document' (if from Anthropic-like source) becomes 'application/pdf' part
        elif current_provider == "google-genai":
            if part_type == "document" and part.get("source", {}).get("type") == "base64":
                media_type = part.get("source", {}).get("media_type")
                if media_type == "application/pdf": # If it was a PDF document
                    new_content_parts.append({
                        # "type": "application/pdf", # For Gemini, it's inline_data with mime_type
                        "inline_data": {
                             "mime_type": media_type,
                             "data": part.get("source", {}).get("data")
                        }
                    })
                    changes_made = True
                    continue

        new_content_parts.append(part) # Keep part as is if no transformation rule applies

    if changes_made:
        new_message_id = str(uuid.uuid4())
        msg_id_to_remove = message.id if isinstance(message.id, str) else "" # Ensure ID is string

        return [
            RemoveMessage(message_id=msg_id_to_remove), # LangChain RemoveMessage uses message_id
            HumanMessage(id=new_message_id, content=new_content_parts, name=message.name, additional_kwargs=message.additional_kwargs)
        ]

    return None

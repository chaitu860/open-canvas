from typing import Dict, Any, Optional, Union, List, Literal # Moved Literal here
from pydantic import BaseModel, Field as PydanticField

from ...models import ( # One level up for models
    OpenCanvasGraphState,
    ArtifactV3,
    ArtifactCodeV3,
    ArtifactMarkdownV3,
    ProgrammingLanguageOptions,
    Reflections as ReflectionsModel
)
from ...utils import ( # One level up for utils
    get_model_config as util_get_model_config, # Renamed to avoid conflict
    get_model_from_config,
    create_context_document_messages,
    get_formatted_reflections, # Expects ReflectionsModel
    optionally_get_system_prompt_from_config,
    is_using_o1_mini_model
)
from .prompts import NEW_ARTIFACT_PROMPT # Same level for prompts
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, AIMessage # Added AIMessage


# Pydantic model for ARTIFACT_TOOL_SCHEMA
class ArtifactToolSchema(BaseModel):
    type: Literal["code", "text"] = PydanticField(description="The content type of the artifact generated.")
    language: Optional[ProgrammingLanguageOptions] = PydanticField(
        default=None,
        description="The language/programming language of the artifact generated. If generating code, it should be one of the options, or 'other'. If not generating code, the language should ALWAYS be 'other' or null."
    )
    isValidReact: Optional[bool] = PydanticField(
        default=None,
        description="Whether or not the generated code is valid React code. Only populate this field if generating code."
    )
    artifact: str = PydanticField(description="The content of the artifact to generate.")
    title: str = PydanticField(description="A short title to give to the artifact. Should be less than 5 words.")

# --- Utilities ---
def format_new_artifact_prompt(memories_as_string: str, model_name: str) -> str:
    prompt = NEW_ARTIFACT_PROMPT.format(
        reflections=memories_as_string,
        disableChainOfThought=(
            "\n\nIMPORTANT: Do NOT preform chain of thought beforehand. Instead, go STRAIGHT to generating the tool response. This is VERY important."
            if "claude" in model_name.lower()
            else ""
        )
    )
    return prompt

def create_artifact_content_from_tool(tool_call_args: ArtifactToolSchema) -> Union[ArtifactCodeV3, ArtifactMarkdownV3]:
    artifact_type = tool_call_args.type

    if artifact_type == "code":
        return ArtifactCodeV3(
            index=1,
            type="code",
            title=tool_call_args.title,
            code=tool_call_args.artifact,
            language=tool_call_args.language if tool_call_args.language else ProgrammingLanguageOptions.OTHER
        )
    else: # type == "text"
        return ArtifactMarkdownV3(
            index=1,
            type="text",
            title=tool_call_args.title,
            fullMarkdown=tool_call_args.artifact
        )

# --- Main node function ---
async def generate_artifact_node(state: OpenCanvasGraphState, config: Dict[str, Any]) -> Dict[str, Any]:
    model_cfg_details = util_get_model_config(config, is_tool_calling=True)
    model_name = model_cfg_details.get("modelName", "unknown_model")

    llm_model = get_model_from_config(config, temperature=0.5, is_tool_calling=True)
    if not llm_model:
        raise ValueError("Failed to initialize LLM model for generate_artifact_node")

    model_with_artifact_tool = llm_model.with_structured_output(
        ArtifactToolSchema,
        name="generate_artifact"
    )

    reflections_data_raw = config.get("configurable", {}).get("reflections_data")
    reflections_data_model: Optional[ReflectionsModel] = None
    if isinstance(reflections_data_raw, dict):
        reflections_data_model = ReflectionsModel.parse_obj(reflections_data_raw)
    elif isinstance(reflections_data_raw, ReflectionsModel):
        reflections_data_model = reflections_data_raw

    memories_as_string = "No reflections found."
    if reflections_data_model:
        memories_as_string = get_formatted_reflections(reflections_data_model)

    formatted_new_artifact_prompt_str = format_new_artifact_prompt(memories_as_string, model_name)
    user_system_prompt = optionally_get_system_prompt_from_config(config)
    full_system_prompt_content = f"{user_system_prompt}\n{formatted_new_artifact_prompt_str}" if user_system_prompt else formatted_new_artifact_prompt_str

    llm_messages: List[BaseMessage] = []
    if is_using_o1_mini_model(config):
        llm_messages.append(HumanMessage(content=full_system_prompt_content))
    else:
        llm_messages.append(SystemMessage(content=full_system_prompt_content))

    context_document_obj_list: List = config.get("configurable", {}).get("context_documents", []) # Ensure it's a list
    # Ensure that context_document_obj_list is actually List[ContextDocument] if create_context_document_messages expects it.
    # For now, assuming it's correctly populated or create_context_document_messages handles various dicts.
    # The type hint for context_document_obj_list in the function signature of create_context_document_messages is List[ContextDocument].
    # A more robust way would be to parse here if they are dicts.
    parsed_context_docs = []
    if isinstance(context_document_obj_list, list):
        from ...models import ContextDocument # Local import for parsing
        for doc_data in context_document_obj_list:
            if isinstance(doc_data, ContextDocument):
                parsed_context_docs.append(doc_data)
            elif isinstance(doc_data, dict):
                try:
                    parsed_context_docs.append(ContextDocument.parse_obj(doc_data))
                except Exception as e:
                    print(f"Skipping context document due to parsing error: {e}")
            # else skip non-dict/non-ContextDocument items

    context_llm_messages: List[BaseMessage] = create_context_document_messages(config, parsed_context_docs)
    llm_messages.extend(context_llm_messages)

    internal_history_dicts = state._messages if state._messages is not None else []
    for msg_dict in internal_history_dicts:
        role = msg_dict.get("role") or msg_dict.get("type")
        content = msg_dict.get("content", "")
        name = msg_dict.get("name")
        if not isinstance(content, (str, list)):
            content = str(content)

        if role in ["user", "human"]:
            llm_messages.append(HumanMessage(content=content, name=name))
        elif role in ["assistant", "ai"]:
            tool_calls = msg_dict.get("tool_calls")
            invalid_tool_calls = msg_dict.get("invalid_tool_calls")
            if tool_calls or invalid_tool_calls:
                 llm_messages.append(AIMessage(content=content, name=name, tool_calls=tool_calls, invalid_tool_calls=invalid_tool_calls))
            else:
                 llm_messages.append(AIMessage(content=content, name=name))

    try:
        response_tool_args: ArtifactToolSchema = await model_with_artifact_tool.ainvoke(llm_messages, config=config)
    except Exception as e:
        print(f"Error invoking LLM with artifact tool: {e}")
        raise

    if not response_tool_args or not isinstance(response_tool_args, ArtifactToolSchema):
        print("Error: LLM did not return valid arguments for generate_artifact tool.")
        raise ValueError("LLM did not return valid arguments for generate_artifact tool.")

    new_artifact_content_obj = create_artifact_content_from_tool(response_tool_args)

    new_artifact = ArtifactV3(
        currentIndex=new_artifact_content_obj.index, # Should be 1 as per logic
        contents=[new_artifact_content_obj]
    )

    return {
        "artifact": new_artifact.dict(exclude_none=True)
    }

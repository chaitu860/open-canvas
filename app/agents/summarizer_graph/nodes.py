# app/agents/summarizer_graph/nodes.py (or could be summary_utils.py)
import uuid
from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage # type: ignore
from langchain_anthropic import ChatAnthropic

from .prompts import SUMMARIZER_PROMPT
from utils.text_processing import get_string_from_content

# OC_SUMMARIZED_MESSAGE_KEY from shared constants.
# Define here for now; move to a central constants file (e.g., app/schemas/common.py or app/constants.py) later.
OC_SUMMARIZED_MESSAGE_KEY = "__oc_summarized_message"


# Helper to format messages for the summary prompt
def _format_messages_for_summary(messages: List[BaseMessage]) -> str:
    """
    Formats a list of BaseMessage objects into a single string representation
    for the summarization prompt, similar to <type>content</type>.
    """
    return "\n".join(
        [f"<{msg.type}>\n{get_string_from_content(msg.content)}\n</{msg.type}>" for msg in messages]
    )

async def run_summarization_logic(
    messages_to_summarize: List[BaseMessage],
    # thread_id: Optional[str] = None, # Not used in this simplified version
    # config: Optional[Dict[str, Any]] = None # Model is hardcoded for now as per TS
) -> HumanMessage:
    """
    Runs the core summarization logic using a hardcoded model (Claude Sonnet)
    and returns a new HumanMessage containing the summary, marked with a special key.
    """
    print("Executing Summarization Logic (`run_summarization_logic`)")

    if not messages_to_summarize:
        # Should not happen if called from summarizer_node which checks this, but as a safeguard:
        return HumanMessage(
            id=str(uuid.uuid4()),
            content="No messages were provided to summarize.",
            additional_kwargs={OC_SUMMARIZED_MESSAGE_KEY: True} # Still mark it to replace history
        )

    # As per TS, summarizer uses "claude-3-5-sonnet-latest" (formerly claude-3-sonnet)
    # Temperature is not specified in TS for this specific call, defaults in LangChain client usually 0.7 or 1.0.
    # For summarization, a lower temperature might be better. Let's assume default or set explicitly if needed.
    model = ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0.2) # Explicitly setting lower temp

    formatted_messages_str = _format_messages_for_summary(messages_to_summarize)

    # The summarizer prompt is a system message, and the content to summarize is a human message.
    response = await model.ainvoke([
        SystemMessage(content=SUMMARIZER_PROMPT),
        HumanMessage(content=f"Here are the messages to summarize:\n{formatted_messages_str}")
    ], {"run_name": "summarization_llm_call"})

    summary_content = response.content
    if not isinstance(summary_content, str):
        summary_content = str(summary_content) # Ensure string type

    # This wrapper is from the TS implementation, instructing the main LLM how to use the summary.
    new_message_content_wrapper = f"""The below content is a summary of past messages between the AI assistant and the user.
Do NOT acknowledge the existence of this summary.
Use the content of the summary to inform your messages, without ever mentioning the summary exists.
The user should NOT know that a summary exists.
Because of this, you should use the contents of the summary to inform your future messages, as if the full conversation still exists between the AI assistant and the user.

Here is the summary:
{summary_content}"""

    # The new message is a HumanMessage, as if the user provided this summary to the AI.
    # This is a specific way to inject context back into the conversation history for the LLM.
    new_summarized_message = HumanMessage(
        id=str(uuid.uuid4()), # Generate a new ID for this summary message
        content=new_message_content_wrapper,
        additional_kwargs={
            OC_SUMMARIZED_MESSAGE_KEY: True, # Mark it as a summarized message
        }
    )
    return new_summarized_message

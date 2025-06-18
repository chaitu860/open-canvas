from typing import Dict, Any, List, Optional, Union
import uuid

from ...models import OpenCanvasGraphState
from ...utils import extract_urls, get_string_from_content
from .generate_path_utils import (
    dynamic_determine_path_node,
    include_url_contents_node,
    convert_context_document_to_human_message,
    fix_misformatted_context_doc_message # Added this import
)
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage, RemoveMessage # Added RemoveMessage


async def generate_path_node(state: OpenCanvasGraphState, config: Dict[str, Any]) -> Dict[str, Any]:

    _messages_dicts = state._messages if state._messages is not None else []
    # Convert internal message dicts to BaseMessage objects for processing
    # This is important because downstream functions like fix_misformatted_context_doc_message
    # might expect BaseMessage instances or specific types like HumanMessage.
    # However, convert_context_document_to_human_message takes List[Dict], so that's fine.
    # include_url_contents_node takes HumanMessage.

    # Messages to be added to the state._messages at the end, or used for decision making.
    # These should be dicts to align with OpenCanvasGraphState._messages type hint.
    new_message_updates_dicts: List[Dict[str, Any]] = []

    # --- Step 1: Process context documents from the last message if any ---
    # This creates a new HumanMessage that summarizes/includes context docs, hidden from UI.
    doc_summary_human_message_obj: Optional[HumanMessage] = await convert_context_document_to_human_message(_messages_dicts, config)

    if doc_summary_human_message_obj:
        new_message_updates_dicts.append(doc_summary_human_message_obj.dict())

    # --- Step 2: Check for direct routing based on input state flags ---
    # These flags indicate a specific action was requested by the user via UI elements.
    # If any of these are set, we route directly to the appropriate node.
    # The `new_message_updates_dicts` (e.g. doc summary) should be part of the updated _messages.
    current_internal_messages_plus_updates = _messages_dicts + new_message_updates_dicts

    if state.highlightedCode:
        return {"next_node": "updateArtifact", "_messages": current_internal_messages_plus_updates}
    if state.highlightedText:
        return {"next_node": "updateHighlightedText", "_messages": current_internal_messages_plus_updates}
    if state.language or state.artifactLength or state.regenerateWithEmojis or state.readingLevel:
        return {"next_node": "rewriteArtifactTheme", "_messages": current_internal_messages_plus_updates}
    if state.addComments or state.addLogs or state.portLanguage or state.fixBugs:
        return {"next_node": "rewriteCodeArtifactTheme", "_messages": current_internal_messages_plus_updates}
    if state.customQuickActionId:
        return {"next_node": "customAction", "_messages": current_internal_messages_plus_updates}
    if state.webSearchEnabled: # Assuming webSearch is a pre-determined route
        return {"next_node": "webSearch", "_messages": current_internal_messages_plus_updates}

    # --- Step 3: Process the last user message for URL content and formatting issues ---
    # This section modifies the *last message* in the internal list if needed.

    # Make a mutable copy of the current internal messages (as dicts)
    # This list will be modified if URLs are processed or formatting is fixed.
    processed_internal_messages_dicts = list(_messages_dicts) # Start with original _messages

    if processed_internal_messages_dicts:
        last_message_dict = processed_internal_messages_dicts[-1]
        last_message_obj: Optional[BaseMessage] = None

        # Convert last message dict to a BaseMessage object for processing
        # This is important for type safety with utility functions.
        msg_role = last_message_dict.get("role") or last_message_dict.get("type")
        msg_content = last_message_dict.get("content", "")
        msg_id = last_message_dict.get("id", str(uuid.uuid4()))
        msg_additional_kwargs = last_message_dict.get("additional_kwargs", {})

        if msg_role == "user" or msg_role == "human":
            last_message_obj = HumanMessage(content=msg_content, id=msg_id, additional_kwargs=msg_additional_kwargs)
        # Add elif for AIMessage if needed, but typically we process HumanMessages here.

        if isinstance(last_message_obj, HumanMessage):
            # --- 3a: Fix misformatted context document messages (if provider requires it) ---
            # This might replace the last message or add a RemoveMessage instruction.
            formatting_changes: Optional[List[Union[RemoveMessage, HumanMessage]]] = await fix_misformatted_context_doc_message(last_message_obj, config)
            if formatting_changes:
                processed_internal_messages_dicts.pop() # Remove the original last message dict
                for change in formatting_changes:
                    if isinstance(change, RemoveMessage): # Should not happen if logic is just replacing
                        # This implies the original message ID should be removed, handled by pop.
                        # If RemoveMessage is about a *different* ID, that's more complex.
                        # For now, assume fix_misformatted only returns a new version of the popped message.
                        pass
                    elif isinstance(change, HumanMessage):
                        processed_internal_messages_dicts.append(change.dict()) # Add the new, corrected message
                        last_message_obj = change # Update last_message_obj to the corrected one for URL processing
                # new_message_updates_dicts.extend([c.dict() for c in formatting_changes if isinstance(c, HumanMessage)]) # Add to overall updates

            # --- 3b: Extract URLs and include their content if decided by LLM ---
            last_message_content_str = get_string_from_content(last_message_obj.content) # Use content from potentially fixed message
            message_urls = extract_urls(last_message_content_str)

            if message_urls:
                try:
                    # include_url_contents_node expects a HumanMessage and returns one, or None.
                    updated_message_with_urls_obj: Optional[HumanMessage] = await include_url_contents_node(last_message_obj, message_urls, config)
                    if updated_message_with_urls_obj:
                        # Replace the last message in our working list with the URL-processed version
                        if processed_internal_messages_dicts and processed_internal_messages_dicts[-1].get("id") == last_message_obj.id:
                            processed_internal_messages_dicts[-1] = updated_message_with_urls_obj.dict()
                        else: # If the message was replaced by formatting fix, append instead
                            processed_internal_messages_dicts.append(updated_message_with_urls_obj.dict())
                        # new_message_updates_dicts.append(updated_last_message_obj.dict()) # Add to overall updates

                except Exception as e:
                    print(f"Could not process last message for URL inclusion: {e}")

    # --- Step 4: Determine the route dynamically using an LLM ---
    # This uses the potentially modified internal messages (processed_internal_messages_dicts)
    # and any new messages created (like doc_summary_human_message_obj).

    # Create a temporary state for routing decision, using the processed messages
    temp_state_for_dynamic_path = state.copy(update={"_messages": processed_internal_messages_dicts}, deep=True)

    # Messages to provide as direct context for the routing LLM call.
    # This should include the doc_summary_human_message if it was created.
    # These are BaseMessage objects.
    decision_context_messages: List[BaseMessage] = []
    if doc_summary_human_message_obj:
        decision_context_messages.append(doc_summary_human_message_obj)

    routing_result = await dynamic_determine_path_node(temp_state_for_dynamic_path, decision_context_messages, config)

    route = routing_result.get("route") if routing_result else None
    if not route:
        print("Warning: dynamic_determine_path_node did not return a valid route. Defaulting to replyToGeneralInput.")
        route = "replyToGeneralInput"

    # --- Step 5: Prepare final state update ---
    final_state_update: Dict[str, Any] = {"next_node": route}

    # The _messages for the next step in the graph should be the processed_internal_messages_dicts
    # combined with any *newly generated* summary messages (like doc_summary_human_message_obj)
    # that weren't part of the original _messages.

    final_internal_messages_dicts = list(processed_internal_messages_dicts) # Start with URL/format processed messages

    # Add doc_summary_human_message if it's new and not already implicitly part of processed_internal_messages_dicts
    # (convert_context_document_to_human_message creates a NEW message)
    if doc_summary_human_message_obj:
        is_duplicate = any(existing_msg.get("id") == doc_summary_human_message_obj.id for existing_msg in final_internal_messages_dicts)
        if not is_duplicate:
             final_internal_messages_dicts.append(doc_summary_human_message_obj.dict())

    final_state_update["_messages"] = final_internal_messages_dicts

    # The 'messages' field in state (user-facing) might also need an update
    # if doc_summary_human_message was generated and isn't meant to be hidden,
    # or if the last user message was transformed (e.g. by URL inclusion).
    # For now, only explicitly add the doc_summary if it's not hidden (it is hidden by default).
    # If last user message was transformed, its updated version is in final_internal_messages_dicts.
    # The main graph loop in main.py will need to handle how 'messages' (user-facing) vs '_messages' (internal) are updated.
    # This node primarily decides 'next_node' and prepares '_messages' for the next LLM call.
    # If new user-visible messages are created here, they should be returned in 'messages'.
    # For now, we assume new_message_updates_dicts contains messages that should update the user-facing list.
    # However, doc_summary_human_message is hidden.
    # If updated_last_message_obj (with URLs) is to be shown to user, it should be in 'messages'.

    # Let's construct 'messages' to reflect the latest state of user-facing messages.
    # This is complex as it depends on which transformations should be visible.
    # A simple approach: take the latest `_messages` and filter out hidden ones.

    user_facing_messages_dicts = [
        msg_dict for msg_dict in final_internal_messages_dicts
        if not (msg_dict.get("additional_kwargs") or {}).get("oc_hide_from_ui", False)
    ]
    if user_facing_messages_dicts != state.messages: # Only update if different
        final_state_update["messages"] = user_facing_messages_dicts


    return final_state_update

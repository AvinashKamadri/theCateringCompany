"""
Collect event date node
"""

from datetime import datetime, timedelta
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def collect_event_date_node(state: ConversationState) -> ConversationState:
    """
    Collect event date from message.
    
    Args:
        state: Current conversation state
        
    Returns:
        Updated conversation state
    """
    
    # Get last user message
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_message = msg.content
            break
    
    if not last_user_message:
        error_response = "When is your event?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Extract date
    extraction_prompt = f"""Extract the event date from: "{last_user_message}"

Convert to ISO format (YYYY-MM-DD). If you see "May 15th, 2026", respond with "2026-05-15".
If no date is found, respond with only "none".

Response (YYYY-MM-DD or "none"):"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Extract dates and convert to YYYY-MM-DD format."),
            HumanMessage(content=extraction_prompt)
        ])
        
        extracted_date = extraction_response.content.strip()
        
        # Check if extraction was successful
        if extracted_date and extracted_date.lower() not in ["none", "null", "n/a", ""]:
            # Update slot
            state["slots"]["event_date"] = {
                "value": extracted_date,
                "filled": True,
                "modified_at": datetime.now().isoformat(),
                "modification_history": []
            }
            
            # Generate response
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Thank the client for the date and ask if they want drop-off or on-site service in 1-2 sentences.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
        else:
            # Ask for clarification
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Ask for the event date. Keep it brief (1 sentence).")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        error_response = "When is your event?"
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Event date extraction error: {str(e)}"
    
    return state

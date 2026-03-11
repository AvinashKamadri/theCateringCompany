"""
Select event type node
"""

from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def select_event_type_node(state: ConversationState) -> ConversationState:
    """
    Select event type (Wedding, Corporate, Birthday, Social, Custom).
    
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
        error_response = "What type of event is this?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Extract event type
    extraction_prompt = f"""From this message: "{last_user_message}"

Determine the event type. Options: Wedding, Corporate, Birthday, Social, Custom

Respond with ONLY one of these words or "none" if unclear.

Response:"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Determine event type from: Wedding, Corporate, Birthday, Social, Custom."),
            HumanMessage(content=extraction_prompt)
        ])
        
        event_type = extraction_response.content.strip()
        
        if event_type in ["Wedding", "Corporate", "Birthday", "Social", "Custom"]:
            state["slots"]["event_type"] = {
                "value": event_type,
                "filled": True,
                "modified_at": datetime.now().isoformat(),
                "modification_history": []
            }
            
            # Generate event-type-aware response
            if event_type == "Wedding":
                response_prompt = "Acknowledge it's a wedding and ask for the venue location. Mention you'll help make their special day memorable. Keep it 1-2 sentences."
            elif event_type == "Birthday":
                response_prompt = "Acknowledge it's a birthday celebration and ask for the venue location. Keep it fun and celebratory. Keep it 1-2 sentences."
            elif event_type == "Corporate":
                response_prompt = "Acknowledge it's a corporate event and ask for the venue location. Keep it professional. Keep it 1-2 sentences."
            else:
                response_prompt = f"Acknowledge it's a {event_type} event and ask for the venue location. Keep it 1-2 sentences."
            
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content=response_prompt)
            ])
            
            state["messages"].append(AIMessage(content=response.content))
        else:
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Ask what type of event it is (Wedding, Corporate, Birthday, Social, or Custom). Keep it 1 sentence.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        error_response = "What type of event is this?"
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Event type extraction error: {str(e)}"
    
    return state

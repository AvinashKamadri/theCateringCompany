"""
Collect venue node
"""

from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def collect_venue_node(state: ConversationState) -> ConversationState:
    """
    Collect venue information.
    
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
        error_response = "Where is your event taking place?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Extract venue
    extraction_prompt = f"""Extract the venue/location from: "{last_user_message}"

If a venue or location is mentioned, respond with it.
If no venue is found, respond with "none".

Response (venue or "none"):"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Extract venue/location information."),
            HumanMessage(content=extraction_prompt)
        ])
        
        venue = extraction_response.content.strip()
        
        if venue and venue.lower() not in ["none", "null", "n/a", ""]:
            state["slots"]["venue"] = {
                "value": venue,
                "filled": True,
                "modified_at": datetime.now().isoformat(),
                "modification_history": []
            }
            
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Acknowledge the venue and ask how many guests they're expecting in 1-2 sentences.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
        else:
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Ask for the venue location. Keep it 1 sentence.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        error_response = "Where is your event taking place?"
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Venue extraction error: {str(e)}"
    
    return state

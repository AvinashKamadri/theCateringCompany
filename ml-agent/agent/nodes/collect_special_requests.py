"""
Collect special requests node
"""

from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def collect_special_requests_node(state: ConversationState) -> ConversationState:
    """
    Collect dietary restrictions and special requests.
    
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
        error_response = "Any dietary restrictions or special requests?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Extract special requests
    extraction_prompt = f"""Extract dietary restrictions or special requests from: "{last_user_message}"

If any are mentioned (halal, vegan, allergies, etc.), respond with them.
If they say "none" or "no restrictions", respond with "none".
If unclear, respond with "none".

Response:"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Extract dietary restrictions and special requests."),
            HumanMessage(content=extraction_prompt)
        ])
        
        special_requests = extraction_response.content.strip()
        
        # Always fill this slot (even with "none")
        state["slots"]["special_requests"] = {
            "value": special_requests if special_requests.lower() != "none" else "No special requests",
            "filled": True,
            "modified_at": datetime.now().isoformat(),
            "modification_history": []
        }
        
        # Generate final response
        response = await llm.ainvoke([
            SystemMessage(content="You are a friendly catering assistant."),
            HumanMessage(content="Thank the client and let them know you're preparing their catering proposal. Keep it 1-2 sentences and enthusiastic.")
        ])
        
        state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        # Even on error, fill the slot with default
        state["slots"]["special_requests"] = {
            "value": "No special requests",
            "filled": True,
            "modified_at": datetime.now().isoformat(),
            "modification_history": []
        }
        
        error_response = "Thank you! I'm preparing your catering proposal now."
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Special requests extraction error: {str(e)}"
    
    return state

"""
Collect guest count node
"""

from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def collect_guest_count_node(state: ConversationState) -> ConversationState:
    """
    Collect guest count.
    
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
        error_response = "How many guests are you expecting?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Extract guest count
    extraction_prompt = f"""Extract the number of guests from: "{last_user_message}"

If a number is mentioned, respond with ONLY the number.
If no number is found, respond with "none".

Response (number or "none"):"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Extract guest count as a number."),
            HumanMessage(content=extraction_prompt)
        ])
        
        guest_count_str = extraction_response.content.strip()
        
        if guest_count_str and guest_count_str.lower() not in ["none", "null", "n/a", ""]:
            try:
                guest_count = int(guest_count_str)
                
                state["slots"]["guest_count"] = {
                    "value": guest_count,
                    "filled": True,
                    "modified_at": datetime.now().isoformat(),
                    "modification_history": []
                }
                
                response = await llm.ainvoke([
                    SystemMessage(content="You are a friendly catering assistant."),
                    HumanMessage(content="Acknowledge the guest count and ask about dietary restrictions or special requests in 1-2 sentences.")
                ])
                
                state["messages"].append(AIMessage(content=response.content))
            except ValueError:
                response = await llm.ainvoke([
                    SystemMessage(content="You are a friendly catering assistant."),
                    HumanMessage(content="Ask for the number of guests as a number. Keep it 1 sentence.")
                ])
                
                state["messages"].append(AIMessage(content=response.content))
        else:
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Ask how many guests they're expecting. Keep it 1 sentence.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        error_response = "How many guests are you expecting?"
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Guest count extraction error: {str(e)}"
    
    return state

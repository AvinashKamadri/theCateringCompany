"""
Select service type node
"""

from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def select_service_type_node(state: ConversationState) -> ConversationState:
    """
    Select service type (drop-off or on-site).
    
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
        error_response = "Would you like drop-off or on-site service?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Extract service type
    extraction_prompt = f"""From this message: "{last_user_message}"

Determine if they want "drop-off" or "on-site" service.
- drop-off: delivery only
- on-site: staff stays to serve

Respond with ONLY "drop-off" or "on-site" or "none" if unclear.

Response:"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Determine service type: drop-off or on-site."),
            HumanMessage(content=extraction_prompt)
        ])
        
        service_type = extraction_response.content.strip().lower()
        
        if service_type in ["drop-off", "on-site"]:
            state["slots"]["service_type"] = {
                "value": service_type,
                "filled": True,
                "modified_at": datetime.now().isoformat(),
                "modification_history": []
            }
            
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Acknowledge the service type and ask what type of event it is (Wedding, Corporate, Birthday, Social, or Custom) in 1-2 sentences.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
        else:
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Ask if they want drop-off or on-site service. Explain briefly. Keep it 1-2 sentences.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        error_response = "Would you like drop-off or on-site service?"
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Service type extraction error: {str(e)}"
    
    return state

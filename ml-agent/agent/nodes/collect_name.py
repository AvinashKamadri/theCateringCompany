"""
Collect name node
"""

from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def collect_name_node(state: ConversationState) -> ConversationState:
    """
    Collect client name from message.
    
    Args:
        state: Current conversation state
        
    Returns:
        Updated conversation state
    """
    
    # Get last user message (skip AI messages)
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            last_user_message = msg.content
            break
    
    if not last_user_message:
        error_response = "Could you please share your name with me?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Simple extraction - ask LLM to extract name
    extraction_prompt = f"""Extract the person's name from this message: "{last_user_message}"

If a name is mentioned (like "I'm John", "My name is Sarah Smith", "Call me Mike"), respond with ONLY the name.
If no name is found, respond with only the word "none".

Response (name only or "none"):"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Extract names from messages. Respond with only the name or 'none'."),
            HumanMessage(content=extraction_prompt)
        ])
        
        extracted_name = extraction_response.content.strip()
        
        # Check if extraction was successful
        if extracted_name and extracted_name.lower() not in ["none", "null", "n/a", "no name", ""]:
            # Update slot
            state["slots"]["name"] = {
                "value": extracted_name,
                "filled": True,
                "modified_at": datetime.now().isoformat(),
                "modification_history": []
            }
            
            # Generate response
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content=f"The client said their name is {extracted_name}. Thank them briefly and ask for their phone number in 1-2 sentences.")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
        else:
            # Ask for clarification
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Ask the client for their name in a friendly way. Keep it brief (1 sentence).")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        error_response = "Could you please share your name with me?"
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Name extraction error: {str(e)}"
    
    return state

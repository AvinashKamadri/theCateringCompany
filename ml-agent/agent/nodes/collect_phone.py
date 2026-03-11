"""
Collect phone node
"""

import re
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm


async def collect_phone_node(state: ConversationState) -> ConversationState:
    """
    Collect and validate phone number from message.
    
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
        error_response = "Could you please provide your phone number?"
        state["messages"].append(AIMessage(content=error_response))
        return state
    
    # Extract phone number
    extraction_prompt = f"""Extract the phone number from this message: "{last_user_message}"

If a phone number is found, respond with ONLY the phone number.
If no phone number is found, respond with only the word "none".

Response (phone number only or "none"):"""
    
    try:
        extraction_response = await llm.ainvoke([
            SystemMessage(content="Extract phone numbers from messages. Respond with only the number or 'none'."),
            HumanMessage(content=extraction_prompt)
        ])
        
        extracted_phone = extraction_response.content.strip()
        
        # Check if extraction was successful
        if extracted_phone and extracted_phone.lower() not in ["none", "null", "n/a", ""]:
            # Normalize phone number
            phone_clean = re.sub(r'[^\d+]', '', extracted_phone)
            
            # Basic validation
            if len(phone_clean) >= 10:
                # Update slot
                state["slots"]["phone"] = {
                    "value": phone_clean if phone_clean.startswith('+') else f"+{phone_clean}",
                    "filled": True,
                    "modified_at": datetime.now().isoformat(),
                    "modification_history": []
                }
                
                # Generate response
                response = await llm.ainvoke([
                    SystemMessage(content="You are a friendly catering assistant."),
                    HumanMessage(content="Thank the client for their phone number and ask for their event date in 1-2 sentences.")
                ])
                
                state["messages"].append(AIMessage(content=response.content))
            else:
                # Invalid phone
                response = await llm.ainvoke([
                    SystemMessage(content="You are a friendly catering assistant."),
                    HumanMessage(content="The phone number seems incomplete. Ask them to provide a valid phone number. Keep it brief (1 sentence).")
                ])
                
                state["messages"].append(AIMessage(content=response.content))
        else:
            # Ask for clarification
            response = await llm.ainvoke([
                SystemMessage(content="You are a friendly catering assistant."),
                HumanMessage(content="Ask the client for their phone number in a friendly way. Keep it brief (1 sentence).")
            ])
            
            state["messages"].append(AIMessage(content=response.content))
            
    except Exception as e:
        error_response = "Could you please provide your phone number?"
        state["messages"].append(AIMessage(content=error_response))
        state["error"] = f"Phone extraction error: {str(e)}"
    
    return state

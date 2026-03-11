"""
Agent response schema for backend integration
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """
    Structured response from agent to backend.
    
    This is what the backend receives after each message.
    """
    # Message content
    content: str = Field(..., description="Agent's response message to display to user")
    
    # Conversation state
    current_node: str = Field(..., description="Current node in the conversation flow")
    slots_filled: int = Field(..., description="Number of slots filled so far")
    total_slots: int = Field(default=8, description="Total number of slots to fill")
    is_complete: bool = Field(..., description="Whether conversation is complete")
    
    # Conversation metadata
    conversation_id: str
    project_id: str
    thread_id: str
    
    # State for persistence
    conversation_state: Dict[str, Any] = Field(..., description="Full conversation state for backend to persist")
    
    # Contract data (only present when is_complete=True)
    contract_data: Optional[Dict[str, Any]] = Field(default=None, description="Contract data when conversation is complete")
    
    # Error handling
    error: Optional[str] = Field(default=None, description="Error message if something went wrong")
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Great to meet you, Sarah! Could you share your phone number?",
                "current_node": "collect_phone",
                "slots_filled": 1,
                "total_slots": 8,
                "is_complete": False,
                "conversation_id": "conv-123",
                "project_id": "proj-456",
                "thread_id": "thread-789",
                "conversation_state": {
                    "slots": {
                        "name": {
                            "value": "Sarah",
                            "filled": True,
                            "modified_at": "2026-03-08T10:30:00",
                            "modification_history": []
                        }
                    }
                },
                "contract_data": None,
                "error": None
            }
        }

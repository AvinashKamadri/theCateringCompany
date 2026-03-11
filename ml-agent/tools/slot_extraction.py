"""
Slot extraction tool using OpenAI function calling
"""

import os
from datetime import datetime
from typing import Any, Dict
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from agent.llm import llm
from pydantic import BaseModel, Field
import json


class SlotExtractionInput(BaseModel):
    """Input schema for slot extraction"""
    message: str = Field(description="User message to extract slot from")
    slot_name: str = Field(description="Name of slot to extract")
    slot_type: str = Field(description="Expected type: string, number, date, enum")


# Slot-specific extraction schemas for OpenAI function calling
SLOT_EXTRACTION_FUNCTIONS = {
    "name": {
        "name": "extract_name",
        "description": "Extract a person's name from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The person's full name"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["name", "confidence"]
        }
    },
    "phone": {
        "name": "extract_phone",
        "description": "Extract a phone number from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {
                    "type": "string",
                    "description": "The phone number in any format"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["phone", "confidence"]
        }
    },
    "event_date": {
        "name": "extract_event_date",
        "description": "Extract an event date from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "The event date in ISO format (YYYY-MM-DD) or natural language"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["date", "confidence"]
        }
    },
    "service_type": {
        "name": "extract_service_type",
        "description": "Extract service type (drop-off or on-site) from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "service_type": {
                    "type": "string",
                    "enum": ["drop-off", "on-site"],
                    "description": "The service type"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["service_type", "confidence"]
        }
    },
    "event_type": {
        "name": "extract_event_type",
        "description": "Extract event type from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "enum": ["Wedding", "Corporate", "Birthday", "Social", "Custom"],
                    "description": "The event type"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["event_type", "confidence"]
        }
    },
    "venue": {
        "name": "extract_venue",
        "description": "Extract venue details from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "venue": {
                    "type": "string",
                    "description": "Venue name, address, and any additional details"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["venue", "confidence"]
        }
    },
    "guest_count": {
        "name": "extract_guest_count",
        "description": "Extract the number of guests from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "guest_count": {
                    "type": "integer",
                    "description": "The number of expected guests"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["guest_count", "confidence"]
        }
    },
    "special_requests": {
        "name": "extract_special_requests",
        "description": "Extract dietary restrictions, allergies, or special requests from the message",
        "parameters": {
            "type": "object",
            "properties": {
                "special_requests": {
                    "type": "string",
                    "description": "Dietary restrictions, allergies, or special requests"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0 and 1",
                    "minimum": 0,
                    "maximum": 1
                }
            },
            "required": ["special_requests", "confidence"]
        }
    }
}


# Slot-specific extraction prompts
SLOT_EXTRACTION_PROMPTS = {
    "name": """Extract the person's name from the message. Look for:
- Direct statements: "My name is John", "I'm Sarah", "Call me Mike"
- Introductions: "This is David", "It's Jennifer"
Be lenient and extract the full name if provided.""",
    
    "phone": """Extract the phone number from the message. Accept any format:
- International: +917012345678, +1-555-123-4567
- Local: 7012345678, (555) 123-4567
- With spaces: +91 701 234 5678
Extract the complete number as provided.""",
    
    "event_date": """Extract the event date from the message. Accept:
- Specific dates: "April 15th", "15th April 2026", "04/15/2026"
- Relative dates: "next Saturday", "in two weeks"
- Natural language: "the 15th", "on the 20th"
Try to convert to ISO format (YYYY-MM-DD) if possible.""",
    
    "service_type": """Extract the service type from the message. Options:
- "drop-off": delivery only, client serves
- "on-site": staff stays to manage service
Look for keywords like "deliver", "drop off", "on-site", "full service", "staff".""",
    
    "event_type": """Extract the event type from the message. Options:
- Wedding: weddings, marriage ceremonies
- Corporate: business events, conferences, meetings
- Birthday: birthday parties, celebrations
- Social: social gatherings, parties
- Custom: any other type
Match to the closest category.""",
    
    "venue": """Extract venue details from the message. Include:
- Venue name
- Address or location
- Kitchen access information
- Load-in time or special instructions
Capture all venue-related information provided.""",
    
    "guest_count": """Extract the number of guests from the message. Look for:
- Direct numbers: "150 guests", "200 people"
- Approximate: "around 100", "about 75"
- Ranges: "between 50 and 75" (use midpoint)
Extract as an integer.""",
    
    "special_requests": """Extract dietary restrictions, allergies, or special requests. Look for:
- Dietary restrictions: vegetarian, vegan, halal, kosher
- Allergies: nut allergies, gluten-free, dairy-free
- Special requests: specific menu items, timing requirements
- "None" or "no restrictions" should be captured as such
Capture all relevant information."""
}


@tool
async def extract_slot_value(message: str, slot_name: str, slot_type: str) -> dict:
    """
    Extract a specific slot value from user message using OpenAI function calling.
    
    Args:
        message: User message text
        slot_name: Name of the slot to extract (name, phone, event_date, etc.)
        slot_type: Expected type (string, number, date, enum)
        
    Returns:
        {
            "success": bool,
            "value": any,
            "confidence": float,
            "raw_text": str
        }
    """
    try:
        # Get OpenAI API key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "success": False,
                "value": None,
                "confidence": 0.0,
                "raw_text": message,
                "error": "OPENAI_API_KEY not configured"
            }
        
        # Get slot-specific function schema
        if slot_name not in SLOT_EXTRACTION_FUNCTIONS:
            return {
                "success": False,
                "value": None,
                "confidence": 0.0,
                "raw_text": message,
                "error": f"Unknown slot name: {slot_name}"
            }
        
        function_schema = SLOT_EXTRACTION_FUNCTIONS[slot_name]
        extraction_prompt = SLOT_EXTRACTION_PROMPTS.get(slot_name, "")
        
        # Create messages for extraction
        system_message = SystemMessage(content=f"""You are a precise information extraction assistant.
{extraction_prompt}

If the information is not present in the message, return null for the value and 0 for confidence.
If the information is present, extract it accurately and provide a confidence score.""")
        
        user_message = HumanMessage(content=f"Extract {slot_name} from: {message}")
        
        # Call LLM with function calling
        response = await llm.ainvoke(
            [system_message, user_message],
            functions=[function_schema],
            function_call={"name": function_schema["name"]}
        )
        
        # Parse function call response
        if hasattr(response, 'additional_kwargs') and 'function_call' in response.additional_kwargs:
            function_call = response.additional_kwargs['function_call']
            arguments = json.loads(function_call['arguments'])
            
            # Extract value based on slot name
            value_key = slot_name if slot_name in arguments else list(arguments.keys())[0]
            extracted_value = arguments.get(value_key)
            confidence = arguments.get('confidence', 0.0)
            
            # Handle null/empty values
            if extracted_value is None or extracted_value == "":
                return {
                    "success": False,
                    "value": None,
                    "confidence": 0.0,
                    "raw_text": message
                }
            
            # Type conversion based on slot_type
            if slot_type == "number":
                try:
                    extracted_value = int(extracted_value)
                except (ValueError, TypeError):
                    return {
                        "success": False,
                        "value": None,
                        "confidence": 0.0,
                        "raw_text": message,
                        "error": f"Could not convert to number: {extracted_value}"
                    }
            
            return {
                "success": True,
                "value": extracted_value,
                "confidence": float(confidence),
                "raw_text": message
            }
        else:
            # No function call in response
            return {
                "success": False,
                "value": None,
                "confidence": 0.0,
                "raw_text": message,
                "error": "No function call in LLM response"
            }
            
    except Exception as e:
        return {
            "success": False,
            "value": None,
            "confidence": 0.0,
            "raw_text": message,
            "error": str(e)
        }

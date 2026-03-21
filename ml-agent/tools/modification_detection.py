"""
Modification detection tool for @AI mentions
"""

import os
import json
from datetime import date
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage
from agent.llm import llm
from pydantic import BaseModel, Field


class ModificationInput(BaseModel):
    """Input schema for modification detection"""
    message: str = Field(description="Message containing @AI mention")
    current_slots: dict = Field(description="Current slot values")


# Keyword mapping for slot identification
SLOT_KEYWORDS = {
    "name": ["name", "called", "call me"],
    "phone": ["phone", "number", "contact", "mobile"],
    "event_date": ["date", "when", "day", "schedule"],
    "guest_count": ["guest", "people", "count", "attendee", "guests"],
    "venue": ["venue", "location", "place", "address"],
    "service_type": ["service", "drop-off", "on-site"],
    "event_type": ["wedding", "corporate", "birthday", "event type"],
    "special_requests": ["dietary", "halal", "vegan", "allergy", "allergies", "restrictions"],
    "appetizers": ["appetizer", "hors d'oeuvres", "hors doeuvres", "starter", "starters"],
    "selected_dishes": ["dish", "dishes", "entree", "entrees", "main course", "main dish", "food selection"],
}


# OpenAI function for semantic slot identification
SLOT_IDENTIFICATION_FUNCTION = {
    "name": "identify_modification_target",
    "description": "Identify which booking detail the user wants to modify",
    "parameters": {
        "type": "object",
        "properties": {
            "target_slot": {
                "type": "string",
                "enum": ["name", "phone", "event_date", "service_type", "event_type", "venue", "guest_count", "special_requests", "appetizers", "selected_dishes"],
                "description": "The slot/field the user wants to modify"
            },
            "new_value": {
                "type": "string",
                "description": "The new value the user wants to set"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence score for the identification"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of why this slot was identified"
            }
        },
        "required": ["target_slot", "new_value", "confidence", "reasoning"]
    }
}


def keyword_match_slot(message: str) -> dict:
    """
    Layer 1: Keyword matching for quick slot identification.
    
    Args:
        message: User message (lowercased for matching)
        
    Returns:
        {
            "matches": dict[str, int],  # slot_name -> match_count
            "best_match": str | None,
            "confidence": float
        }
    """
    message_lower = message.lower()
    matches = {}
    
    # Count keyword matches for each slot
    for slot_name, keywords in SLOT_KEYWORDS.items():
        match_count = sum(1 for keyword in keywords if keyword in message_lower)
        if match_count > 0:
            matches[slot_name] = match_count
    
    if not matches:
        return {
            "matches": {},
            "best_match": None,
            "confidence": 0.0
        }
    
    # Find slot with most keyword matches
    best_match = max(matches.items(), key=lambda x: x[1])
    slot_name, match_count = best_match
    
    # Calculate confidence based on match count and uniqueness
    total_matches = sum(matches.values())
    confidence = match_count / total_matches if total_matches > 0 else 0.0
    
    # Boost confidence if only one slot matched
    if len(matches) == 1:
        confidence = min(confidence + 0.3, 1.0)
    
    return {
        "matches": matches,
        "best_match": slot_name,
        "confidence": confidence
    }


async def llm_identify_slot(message: str, current_slots: dict) -> dict:
    """
    Layer 2: Use OpenAI function calling for semantic slot identification.
    
    Args:
        message: User message
        current_slots: Current slot values for context
        
    Returns:
        {
            "target_slot": str | None,
            "new_value": str | None,
            "confidence": float,
            "reasoning": str
        }
    """
    try:
        # Build context about current slots
        slot_context = []
        for slot_name, slot_data in current_slots.items():
            if slot_data.get("filled"):
                value = slot_data.get("value")
                slot_context.append(f"- {slot_name}: {value}")
        
        context_str = "\n".join(slot_context) if slot_context else "No slots filled yet"
        
        # Create system prompt with today's date for relative date resolution
        today = date.today().isoformat()
        system_message = SystemMessage(content=f"""You are an expert at identifying which booking detail a user wants to modify.

Today's date is {today}. IMPORTANT: The current year is {date.today().year}.
When the user mentions relative dates like "next month", "25th of next month", "next Friday", etc.,
you MUST resolve them to absolute dates relative to today ({today}).
For example, if today is 2026-03-10 and the user says "25th of next month", the new_value should be "April 25, 2026".

Current booking details:
{context_str}

The user is trying to modify one of these fields:
- name: Client's name
- phone: Phone number
- event_date: Date of the event
- service_type: Service type (drop-off or on-site)
- event_type: Event category (Wedding, Corporate, Birthday, Social, Custom)
- venue: Venue details (address, location)
- guest_count: Number of guests
- special_requests: Dietary restrictions, allergies, special requests
- appetizers: Appetizer / hors d'oeuvres selections (add or remove specific items)
- selected_dishes: Main dish / entrée selections (add or remove specific items)

For appetizers and selected_dishes, the new_value should be a comma-separated list of the item names the user wants to ADD or the full instruction (e.g. "add Spanakopita" or "remove Chicken Satay").

Analyze the user's message and identify:
1. Which field they want to modify
2. What the new value should be (for dates, always resolve to an absolute date with the correct year)
3. Your confidence level (0.0 to 1.0)
4. Brief reasoning for your choice

Be precise and consider the context of already-filled slots.""")
        
        user_message = HumanMessage(content=f"User message: {message}")
        
        # Call LLM with function calling
        response = await llm.ainvoke(
            [system_message, user_message],
            functions=[SLOT_IDENTIFICATION_FUNCTION],
            function_call={"name": "identify_modification_target"}
        )
        
        # Parse function call response
        if hasattr(response, 'additional_kwargs') and 'function_call' in response.additional_kwargs:
            function_call = response.additional_kwargs['function_call']
            arguments = json.loads(function_call['arguments'])
            
            return {
                "target_slot": arguments.get("target_slot"),
                "new_value": arguments.get("new_value"),
                "confidence": float(arguments.get("confidence", 0.0)),
                "reasoning": arguments.get("reasoning", "")
            }
        else:
            return {
                "target_slot": None,
                "new_value": None,
                "confidence": 0.0,
                "reasoning": "No function call in LLM response"
            }
            
    except Exception as e:
        return {
            "target_slot": None,
            "new_value": None,
            "confidence": 0.0,
            "reasoning": f"Error: {str(e)}"
        }


@tool
async def detect_slot_modification(message: str, current_slots: dict) -> dict:
    """
    Detect which slot user wants to modify via @AI mention.
    
    Multi-layered disambiguation strategy:
    1. Keyword Matching: Check for explicit slot keywords
    2. OpenAI Function Calling: Use structured output to identify slot
    3. Combine keyword + LLM confidence scores
    4. Clarification Prompt: If confidence < 0.7, ask user to clarify
    
    Args:
        message: User message with @AI mention
        current_slots: Current slot values for context
        
    Returns:
        {
            "detected": bool,
            "target_slot": str | None,
            "new_value": any,
            "confidence": float,
            "clarification_needed": bool,
            "possible_slots": list[str]
        }
    """
    try:
        # Layer 1: Keyword matching
        keyword_result = keyword_match_slot(message)
        
        # Layer 2: LLM semantic identification
        llm_result = await llm_identify_slot(message, current_slots)
        
        # Layer 3: Combine confidence scores
        # If both agree, boost confidence
        if keyword_result["best_match"] == llm_result["target_slot"]:
            combined_confidence = min(
                (keyword_result["confidence"] + llm_result["confidence"]) / 2 + 0.2,
                1.0
            )
            target_slot = llm_result["target_slot"]
            new_value = llm_result["new_value"]
        else:
            # They disagree - use LLM result but lower confidence
            combined_confidence = llm_result["confidence"] * 0.8
            target_slot = llm_result["target_slot"]
            new_value = llm_result["new_value"]
        
        # Layer 4: Determine if clarification needed
        clarification_needed = combined_confidence < 0.7
        
        # Build possible_slots list for disambiguation
        possible_slots = []
        if clarification_needed:
            # Include keyword matches
            if keyword_result["matches"]:
                possible_slots.extend(keyword_result["matches"].keys())
            # Include LLM suggestion if not already there
            if target_slot and target_slot not in possible_slots:
                possible_slots.append(target_slot)
            # Remove duplicates and limit to top 3
            possible_slots = list(dict.fromkeys(possible_slots))[:3]
        
        # Determine if we detected a modification
        detected = target_slot is not None and new_value is not None
        
        return {
            "detected": detected,
            "target_slot": target_slot,
            "new_value": new_value,
            "confidence": combined_confidence,
            "clarification_needed": clarification_needed,
            "possible_slots": possible_slots
        }
        
    except Exception as e:
        return {
            "detected": False,
            "target_slot": None,
            "new_value": None,
            "confidence": 0.0,
            "clarification_needed": True,
            "possible_slots": [],
            "error": str(e)
        }

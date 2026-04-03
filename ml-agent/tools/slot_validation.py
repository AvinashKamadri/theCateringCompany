"""
Slot validation tool for business rules
"""

import re
from datetime import datetime
from dateutil import parser
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from config.business_rules import config


class ValidationInput(BaseModel):
    """Input schema for slot validation"""
    slot_name: str = Field(description="Slot to validate")
    value: str = Field(description="Value to validate")


def validate_phone(value: str) -> dict:
    """
    Validate phone number format.
    Accepts E.164 format (+917012345678) or local format (7012345678).
    
    Args:
        value: Phone number string
        
    Returns:
        Validation result with normalized value
    """
    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', value)
    
    # E.164 format: +[country code][number] (e.g., +917012345678)
    e164_pattern = r'^\+\d{10,15}$'
    
    # Local format: 10-15 digits
    local_pattern = r'^\d{10,15}$'
    
    if re.match(e164_pattern, cleaned):
        return {
            "valid": True,
            "normalized_value": cleaned,
            "error_message": None
        }
    elif re.match(local_pattern, cleaned):
        # Normalize to E.164 format (using configured country code for local numbers)
        # In production, you'd detect country from context
        if len(cleaned) == config.PHONE_MIN_LENGTH:
            normalized = f"{config.DEFAULT_COUNTRY_CODE}{cleaned}"
        else:
            normalized = f"+{cleaned}"
        return {
            "valid": True,
            "normalized_value": normalized,
            "error_message": None
        }
    else:
        return {
            "valid": False,
            "normalized_value": None,
            "error_message": "Phone number must be 10-15 digits. Example: +917012345678 or 7012345678"
        }


def _contains_relative_date(value: str) -> bool:
    """Check if the value contains relative date terms that dateutil can't parse."""
    relative_keywords = [
        "next month", "this month", "next week", "this week",
        "next year", "tomorrow", "next friday", "next saturday",
        "next sunday", "next monday", "next tuesday", "next wednesday",
        "next thursday", "coming", "upcoming",
    ]
    val_lower = value.lower()
    return any(kw in val_lower for kw in relative_keywords)


async def _resolve_relative_date(value: str) -> str:
    """Use LLM to resolve relative date phrases to absolute dates."""
    from agent.llm import llm
    from langchain_core.messages import SystemMessage, HumanMessage

    today = datetime.now().strftime("%Y-%m-%d")
    response = await llm.ainvoke([
        SystemMessage(content=(
            f"Today is {today}. Convert the following date expression to YYYY-MM-DD format. "
            f"Return ONLY the date in YYYY-MM-DD format, nothing else. "
            f"Example: if today is 2026-03-10 and input is '23rd next month', return 2026-04-23"
        )),
        HumanMessage(content=value),
    ])
    return response.content.strip()


def validate_event_date(value: str) -> dict:
    """
    Validate event date.
    Must be a future date. Accepts ISO dates and natural language.

    NOTE: Relative dates ("next month") should be resolved to absolute dates
    BEFORE calling this function. The caller (check_modifications_node) handles
    this via _resolve_relative_date(). This function only parses absolute dates.
    """
    try:
        now = datetime.now()
        parsed_date = parser.parse(value, fuzzy=True, default=now)

        # If parsed date is in the past and no year was explicitly mentioned,
        # bump to next year (handles "April 25" when it's already May)
        if parsed_date.date() <= now.date():
            import re as _re
            if not _re.search(r'\b20\d{2}\b', value):
                parsed_date = parsed_date.replace(year=parsed_date.year + 1)

        # Must be in the future
        if parsed_date.date() <= now.date():
            return {
                "valid": False,
                "normalized_value": None,
                "error_message": "Event date must be in the future"
            }

        normalized = parsed_date.date().isoformat()
        return {
            "valid": True,
            "normalized_value": normalized,
            "error_message": None
        }
    except (ValueError, parser.ParserError):
        return {
            "valid": False,
            "normalized_value": None,
            "error_message": "Could not parse date. Please provide a valid date (e.g., 'April 15, 2026' or '2026-04-15')"
        }


def validate_guest_count(value: str) -> dict:
    """
    Validate guest count.
    Must be a positive integer in reasonable range (10-10000).
    
    Args:
        value: Guest count string
        
    Returns:
        Validation result with normalized integer
    """
    try:
        # Convert to integer
        count = int(value)
        
        # Check range
        if count < 10:
            return {
                "valid": False,
                "normalized_value": None,
                "error_message": "Guest count must be at least 10"
            }
        elif count > 10000:
            return {
                "valid": False,
                "normalized_value": None,
                "error_message": "Guest count cannot exceed 10,000"
            }
        
        return {
            "valid": True,
            "normalized_value": count,
            "error_message": None
        }
    except ValueError:
        return {
            "valid": False,
            "normalized_value": None,
            "error_message": "Guest count must be a number (e.g., 150)"
        }


def validate_enum(value: str, allowed_values: list, field_name: str) -> dict:
    """
    Validate enum field against allowed values.
    Case-insensitive matching with normalization.
    
    Args:
        value: Value to validate
        allowed_values: List of allowed values
        field_name: Name of the field for error messages
        
    Returns:
        Validation result with normalized value
    """
    # Normalize input (lowercase, strip whitespace)
    normalized_input = value.strip().lower()
    
    # Create mapping of lowercase to original values
    value_map = {v.lower(): v for v in allowed_values}
    
    if normalized_input in value_map:
        return {
            "valid": True,
            "normalized_value": value_map[normalized_input],
            "error_message": None
        }
    else:
        return {
            "valid": False,
            "normalized_value": None,
            "error_message": f"{field_name} must be one of: {', '.join(allowed_values)}"
        }


@tool
async def validate_slot(slot_name: str, value: str) -> dict:
    """
    Validate slot value based on business rules.
    
    Validations:
    - phone: E.164 format or local format
    - event_date: Must be future date, parse natural language
    - guest_count: Positive integer, reasonable range (10-10000)
    - service_type: Must be in ['drop-off', 'on-site']
    - event_type: Must be in ['Wedding', 'Corporate', 'Birthday', 'Social', 'Custom']
    
    Args:
        slot_name: Name of the slot to validate
        value: Value to validate
        
    Returns:
        {
            "valid": bool,
            "normalized_value": any,
            "error_message": str | None
        }
    """
    # Handle None or empty values
    if value is None or (isinstance(value, str) and not value.strip()):
        return {
            "valid": False,
            "normalized_value": None,
            "error_message": f"{slot_name} cannot be empty"
        }
    
    # Route to appropriate validator
    if slot_name == "phone":
        return validate_phone(value)
    
    elif slot_name == "event_date":
        return validate_event_date(value)
    
    elif slot_name == "guest_count":
        return validate_guest_count(value)
    
    elif slot_name == "service_type":
        return validate_enum(
            value,
            allowed_values=['Drop-off', 'Onsite'],
            field_name="Service type"
        )
    
    elif slot_name == "event_type":
        return validate_enum(
            value,
            allowed_values=['Wedding', 'Corporate', 'Birthday', 'Social', 'Custom'],
            field_name="Event type"
        )
    
    elif slot_name == "buffet_or_plated":
        return validate_enum(
            value,
            allowed_values=['Buffet', 'Plated'],
            field_name="Buffet or plated"
        )

    elif slot_name == "tableware":
        return validate_enum(
            value,
            allowed_values=['Standard', 'Premium', 'China'],
            field_name="Tableware"
        )

    # Free-text slots — accept any non-empty value
    elif slot_name in [
        "name", "venue", "special_requests", "dietary_concerns",
        "fiance_name", "company_name", "birthday_person",
        "drinks", "bar_service", "labor_services", "desserts",
        "appetizers", "selected_dishes", "service_style",
        "rentals",
    ]:
        return {
            "valid": True,
            "normalized_value": value.strip(),
            "error_message": None
        }

    else:
        return {
            "valid": False,
            "normalized_value": None,
            "error_message": f"Unknown slot name: {slot_name}"
        }

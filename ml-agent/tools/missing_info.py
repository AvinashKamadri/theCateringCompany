"""
Missing info flagging tool
"""

from langchain_core.tools import tool


@tool
async def flag_missing_info(slots: dict, event_type: str) -> dict:
    """
    Detect incomplete or risky contract data before generation.
    
    Args:
        slots: Current slot values
        event_type: Type of event
        
    Returns:
        {
            "is_complete": bool,
            "missing_required": list[str],
            "missing_recommended": list[str],
            "risk_flags": list[dict]
        }
    """
    missing_required = []
    missing_recommended = []
    risk_flags = []
    
    # Check required fields
    required_fields = ["name", "phone", "event_date", "service_type", "event_type", "venue", "guest_count"]
    
    for field in required_fields:
        if not slots.get(field) or slots[field] is None:
            missing_required.append(field)
    
    # Check recommended fields based on event type
    if event_type == "Wedding":
        # Weddings should have detailed special requests
        special_requests = slots.get("special_requests", {})
        if not special_requests or (isinstance(special_requests, dict) and not special_requests.get("dietary_restrictions")):
            missing_recommended.append("dietary_restrictions - Important for wedding catering")
        
        # Check venue details
        venue = slots.get("venue", {})
        if isinstance(venue, dict):
            if not venue.get("kitchen_access"):
                missing_recommended.append("venue.kitchen_access - Critical for on-site wedding service")
            if not venue.get("load_in_time"):
                missing_recommended.append("venue.load_in_time - Important for wedding setup coordination")
    
    elif event_type == "Corporate":
        # Corporate events should specify AV needs
        special_requests = slots.get("special_requests", {})
        if not special_requests or (isinstance(special_requests, dict) and not special_requests.get("special_requests")):
            missing_recommended.append("av_requirements - Important for corporate events")
    
    # Detect risk factors
    guest_count = slots.get("guest_count", 0)
    service_type = slots.get("service_type", "")
    venue = slots.get("venue", {})
    special_requests = slots.get("special_requests", {})
    
    # Risk: Large guest count
    if guest_count and guest_count > 300:
        risk_flags.append({
            "type": "large_event",
            "severity": "high",
            "message": f"Large event with {guest_count} guests requires additional planning and resources",
            "recommendation": "Confirm adequate staffing and kitchen capacity"
        })
    
    # Risk: On-site service without kitchen access
    if service_type == "on-site" and isinstance(venue, dict):
        if not venue.get("kitchen_access") or venue.get("kitchen_access") == "none":
            risk_flags.append({
                "type": "no_kitchen_access",
                "severity": "high",
                "message": "On-site service requested but venue has no kitchen access",
                "recommendation": "Confirm mobile kitchen equipment needs and additional setup time"
            })
    
    # Risk: Outdoor venue (if mentioned in venue address)
    if isinstance(venue, dict) and venue.get("address"):
        address_lower = str(venue["address"]).lower()
        if any(word in address_lower for word in ["outdoor", "park", "garden", "beach", "field"]):
            risk_flags.append({
                "type": "outdoor_venue",
                "severity": "medium",
                "message": "Outdoor venue detected - weather contingency needed",
                "recommendation": "Confirm tent/shelter availability and backup plan"
            })
    
    # Risk: Alcohol service (if mentioned in special requests)
    if isinstance(special_requests, dict):
        special_text = str(special_requests.get("special_requests", "")).lower()
        if any(word in special_text for word in ["alcohol", "bar", "wine", "beer", "cocktail", "liquor"]):
            risk_flags.append({
                "type": "alcohol_service",
                "severity": "medium",
                "message": "Alcohol service mentioned - licensing and insurance required",
                "recommendation": "Verify liquor license and liability insurance coverage"
            })
    
    # Risk: Severe allergies
    if isinstance(special_requests, dict):
        allergies = special_requests.get("allergies", [])
        if allergies and len(allergies) > 0:
            severe_allergens = ["peanut", "tree nut", "shellfish", "fish"]
            if any(allergen.lower() in str(allergies).lower() for allergen in severe_allergens):
                risk_flags.append({
                    "type": "severe_allergies",
                    "severity": "high",
                    "message": "Severe food allergies detected",
                    "recommendation": "Implement strict cross-contamination protocols and staff training"
                })
    
    # Risk: Short notice (less than 2 weeks)
    from datetime import datetime, timedelta
    event_date_str = slots.get("event_date")
    if event_date_str:
        try:
            event_date = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
            days_until_event = (event_date - datetime.now()).days
            if days_until_event < 14:
                risk_flags.append({
                    "type": "short_notice",
                    "severity": "medium",
                    "message": f"Event is in {days_until_event} days - short planning window",
                    "recommendation": "Expedite vendor confirmations and menu planning"
                })
        except:
            pass
    
    # Determine if complete
    is_complete = len(missing_required) == 0
    
    return {
        "is_complete": is_complete,
        "missing_required": missing_required,
        "missing_recommended": missing_recommended,
        "risk_flags": risk_flags
    }

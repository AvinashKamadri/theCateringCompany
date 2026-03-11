"""
Staffing calculation tool
"""

from langchain_core.tools import tool
from config.business_rules import config


@tool
async def calculate_staffing(
    guest_count: int,
    service_type: str,
    event_type: str,
    event_duration_hours: float
) -> dict:
    """
    AI staffing recommendations based on industry standards.
    
    Args:
        guest_count: Number of guests
        service_type: Service type (drop-off, on-site)
        event_type: Type of event
        event_duration_hours: Duration of event in hours
        
    Returns:
        {
            "recommended_staff": dict,
            "total_labor_hours": float,
            "estimated_labor_cost": float,
            "reasoning": str
        }
    """
    if service_type.lower() == "drop-off":
        # Drop-off service requires minimal staff
        recommended_staff = {
            "delivery_drivers": config.MIN_DELIVERY_STAFF,
            "servers": 0,
            "bartenders": 0,
            "supervisors": 0,
        }
        
        total_labor_hours = config.MIN_DELIVERY_STAFF * config.DROPOFF_DELIVERY_HOURS
        estimated_labor_cost = total_labor_hours * config.DELIVERY_STAFF_HOURLY_RATE
        
        reasoning = (
            f"Drop-off service requires {config.MIN_DELIVERY_STAFF} delivery staff "
            f"for {config.DROPOFF_DELIVERY_HOURS} hour(s) to transport and set up food."
        )
        
    else:  # on-site service
        # Calculate staff based on guest count and business rules
        servers = max(config.MIN_SERVERS, (guest_count // config.GUESTS_PER_SERVER) + 1)
        bartenders = max(config.MIN_BARTENDERS, guest_count // config.GUESTS_PER_BARTENDER)
        
        # Add supervisor for larger events
        supervisors = 1 if guest_count > 100 else 0
        
        # Adjust for event type
        if event_type.lower() == "wedding":
            # Weddings typically need more attentive service
            servers += 1
            if guest_count > 150:
                supervisors = 1
        elif event_type.lower() == "corporate":
            # Corporate events may need fewer bartenders during business hours
            if guest_count < 100:
                bartenders = max(0, bartenders - 1)
        
        recommended_staff = {
            "servers": servers,
            "bartenders": bartenders,
            "supervisors": supervisors,
            "delivery_drivers": 0,
        }
        
        # Calculate labor hours and costs
        server_hours = servers * event_duration_hours
        bartender_hours = bartenders * event_duration_hours
        supervisor_hours = supervisors * event_duration_hours
        
        total_labor_hours = server_hours + bartender_hours + supervisor_hours
        
        server_cost = server_hours * config.SERVER_HOURLY_RATE
        bartender_cost = bartender_hours * config.BARTENDER_HOURLY_RATE
        supervisor_cost = supervisor_hours * config.SUPERVISOR_HOURLY_RATE
        
        estimated_labor_cost = server_cost + bartender_cost + supervisor_cost
        
        # Generate reasoning
        reasoning_parts = []
        reasoning_parts.append(f"{servers} server(s) for {guest_count} guests (1 per {config.GUESTS_PER_SERVER} guests)")
        
        if bartenders > 0:
            reasoning_parts.append(f"{bartenders} bartender(s) (1 per {config.GUESTS_PER_BARTENDER} guests)")
        
        if supervisors > 0:
            reasoning_parts.append(f"{supervisors} supervisor(s) for event coordination")
        
        reasoning_parts.append(f"Event duration: {event_duration_hours} hours")
        
        if event_type.lower() == "wedding":
            reasoning_parts.append("Wedding events require enhanced service levels")
        
        reasoning = ". ".join(reasoning_parts) + "."
    
    return {
        "recommended_staff": recommended_staff,
        "total_labor_hours": round(total_labor_hours, 1),
        "estimated_labor_cost": round(estimated_labor_cost, 2),
        "reasoning": reasoning,
        "staff_breakdown": {
            "servers_needed": recommended_staff.get("servers", 0),
            "bartenders_needed": recommended_staff.get("bartenders", 0),
            "supervisors_needed": recommended_staff.get("supervisors", 0),
            "delivery_drivers_needed": recommended_staff.get("delivery_drivers", 0),
        }
    }

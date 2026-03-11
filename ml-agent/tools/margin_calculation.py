"""
Margin calculation tool
"""

from langchain_core.tools import tool
from config.business_rules import config


@tool
async def calculate_margin(line_items: list[dict], guest_count: int, service_type: str) -> dict:
    """
    Real-time margin calculation with warnings.
    
    Args:
        line_items: List of line items with costs
        guest_count: Number of guests
        service_type: Service type (affects labor costs)
        
    Returns:
        {
            "total_revenue": float,
            "total_cost": float,
            "gross_margin": float,
            "margin_percentage": float,
            "warnings": list[str],
            "recommendations": list[str]
        }
    """
    # Calculate total revenue from line items
    total_revenue = sum(item.get("price", 0.0) for item in line_items)
    
    # Calculate food costs using business config
    food_cost = total_revenue * config.FOOD_COST_PERCENTAGE
    
    # Calculate labor costs based on service type using business config
    if service_type == "on-site":
        # On-site requires more staff
        servers_needed = max(config.MIN_SERVERS, (guest_count // config.GUESTS_PER_SERVER) + 1)
        bartenders_needed = max(config.MIN_BARTENDERS, guest_count // config.GUESTS_PER_BARTENDER)
        
        server_cost = servers_needed * config.DEFAULT_EVENT_DURATION_HOURS * config.SERVER_HOURLY_RATE
        bartender_cost = bartenders_needed * config.DEFAULT_EVENT_DURATION_HOURS * config.BARTENDER_HOURLY_RATE
        labor_cost = server_cost + bartender_cost
    else:  # drop-off
        # Drop-off requires minimal labor (delivery only)
        labor_cost = config.calculate_dropoff_labor_cost()
    
    # Calculate overhead using business config
    overhead_cost = total_revenue * config.OVERHEAD_PERCENTAGE
    
    # Total cost
    total_cost = food_cost + labor_cost + overhead_cost
    
    # Calculate margin
    gross_margin = total_revenue - total_cost
    margin_percentage = (gross_margin / total_revenue * 100) if total_revenue > 0 else 0
    
    # Generate warnings and recommendations using business config
    margin_status = config.get_margin_status(margin_percentage)
    warnings = margin_status["warnings"]
    recommendations = margin_status["recommendations"]
    
    # Service type specific recommendations
    if service_type == "on-site" and guest_count > 200:
        recommendations.append("Consider staffing efficiency for large on-site event")
    
    if guest_count < 50 and service_type == "drop-off":
        recommendations.append("Small drop-off events may have lower margins due to fixed costs")
    
    return {
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "food_cost": round(food_cost, 2),
        "labor_cost": round(labor_cost, 2),
        "overhead_cost": round(overhead_cost, 2),
        "gross_margin": round(gross_margin, 2),
        "margin_percentage": round(margin_percentage, 2),
        "warnings": warnings,
        "recommendations": recommendations
    }

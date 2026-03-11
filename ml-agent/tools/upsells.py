"""
AI upsell suggestion tool
"""

from langchain_core.tools import tool


@tool
async def suggest_upsells(event_type: str, guest_count: int, current_selections: dict) -> dict:
    """
    AI-powered upsell recommendations based on event details.
    
    Args:
        event_type: Type of event
        guest_count: Number of guests
        current_selections: Current selections made by client
        
    Returns:
        {
            "upsells": [
                {
                    "category": str,
                    "name": str,
                    "price": float,
                    "reasoning": str,
                    "priority": str
                }
            ],
            "total_potential_revenue": float
        }
    """
    upsells = []
    
    # Define upsell rules by event type
    if event_type == "Wedding":
        # Wedding-specific upsells
        upsells.append({
            "category": "Bar Service",
            "name": "Premium Open Bar Package",
            "price": guest_count * 45.0,
            "reasoning": "Weddings typically include bar service. Premium package includes top-shelf liquor and signature cocktails.",
            "priority": "high"
        })
        upsells.append({
            "category": "Staffing",
            "name": "Additional Service Staff",
            "price": 800.0,
            "reasoning": "Extra servers ensure seamless service during cocktail hour and reception.",
            "priority": "medium"
        })
        upsells.append({
            "category": "Rentals",
            "name": "Elegant Table Linens & China",
            "price": guest_count * 12.0,
            "reasoning": "Upgrade to premium linens and china for an elegant presentation.",
            "priority": "medium"
        })
        upsells.append({
            "category": "Food",
            "name": "Late Night Snack Station",
            "price": guest_count * 8.0,
            "reasoning": "Popular for weddings - keeps guests energized for dancing.",
            "priority": "low"
        })
        
    elif event_type == "Corporate":
        # Corporate-specific upsells
        upsells.append({
            "category": "Bar Service",
            "name": "Beer & Wine Bar",
            "price": guest_count * 18.0,
            "reasoning": "Professional networking events often include light bar service.",
            "priority": "high"
        })
        upsells.append({
            "category": "AV Equipment",
            "name": "Presentation Equipment Package",
            "price": 500.0,
            "reasoning": "Includes projector, screen, and sound system for presentations.",
            "priority": "medium"
        })
        upsells.append({
            "category": "Food",
            "name": "Coffee & Dessert Station",
            "price": guest_count * 6.0,
            "reasoning": "Keep attendees alert and engaged throughout the event.",
            "priority": "medium"
        })
        
    elif event_type == "Birthday":
        # Birthday-specific upsells
        upsells.append({
            "category": "Bar Service",
            "name": "Signature Cocktail Bar",
            "price": guest_count * 25.0,
            "reasoning": "Custom cocktails themed to the birthday celebration.",
            "priority": "high"
        })
        upsells.append({
            "category": "Dessert",
            "name": "Custom Cake & Dessert Display",
            "price": 350.0,
            "reasoning": "Professional cake cutting service and dessert presentation.",
            "priority": "high"
        })
        upsells.append({
            "category": "Entertainment",
            "name": "DJ & Dance Floor Setup",
            "price": 1200.0,
            "reasoning": "Complete entertainment package for a memorable celebration.",
            "priority": "medium"
        })
        
    elif event_type == "Social":
        # Social gathering upsells
        upsells.append({
            "category": "Bar Service",
            "name": "Beer & Wine Service",
            "price": guest_count * 15.0,
            "reasoning": "Casual bar service perfect for social gatherings.",
            "priority": "medium"
        })
        upsells.append({
            "category": "Food",
            "name": "Appetizer Station Upgrade",
            "price": guest_count * 10.0,
            "reasoning": "Variety of hot and cold appetizers for mingling guests.",
            "priority": "medium"
        })
        
    else:  # Custom
        # Generic upsells for custom events
        upsells.append({
            "category": "Bar Service",
            "name": "Full Bar Package",
            "price": guest_count * 30.0,
            "reasoning": "Complete bar service with beer, wine, and spirits.",
            "priority": "medium"
        })
        upsells.append({
            "category": "Staffing",
            "name": "Additional Service Staff",
            "price": 600.0,
            "reasoning": "Extra staff to ensure smooth service throughout your event.",
            "priority": "medium"
        })
    
    # Calculate guest count-based priorities
    if guest_count > 150:
        # Large events - recommend additional staffing
        if not any(u["category"] == "Staffing" for u in upsells):
            upsells.append({
                "category": "Staffing",
                "name": "Additional Service Staff",
                "price": 800.0,
                "reasoning": f"With {guest_count} guests, additional staff ensures excellent service.",
                "priority": "high"
            })
    
    # Calculate total potential revenue
    total_potential_revenue = sum(u["price"] for u in upsells)
    
    return {
        "upsells": upsells,
        "total_potential_revenue": total_potential_revenue
    }

"""
Generate contract node with detailed pricing and menu items
"""

import uuid
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.state import ConversationState
from agent.llm import llm
from tools.pricing import calculate_event_pricing


async def generate_contract_node(state: ConversationState) -> ConversationState:
    """
    Generate contract from filled slots.
    
    Args:
        state: Current conversation state
        
    Returns:
        Updated conversation state with contract data
    """
    
    # Verify all required slots are filled
    required_slots = ["name", "phone", "event_date", "service_type", "event_type", "venue", "guest_count", "special_requests"]
    missing_slots = [slot for slot in required_slots if not state["slots"].get(slot, {}).get("filled")]
    
    if missing_slots:
        error_message = f"Cannot generate contract. Missing: {', '.join(missing_slots)}"
        state["messages"].append(AIMessage(content=error_message))
        state["error"] = error_message
        return state
    
    try:
        print("[Contract] Starting contract generation...")

        # Extract slot values
        name = state["slots"]["name"].get("value", "")
        phone = state["slots"].get("phone", {}).get("value", "")
        email = state["slots"].get("email", {}).get("value", "")
        event_date = state["slots"]["event_date"]["value"]
        service_type = state["slots"]["service_type"]["value"]
        event_type = state["slots"]["event_type"]["value"]
        venue = state["slots"]["venue"]["value"]
        guest_count = int(state["slots"]["guest_count"]["value"])
        special_requests = state["slots"]["special_requests"]["value"]

        # Extract menu and add-ons
        selected_dishes = state["slots"].get("selected_dishes", {}).get("value", "")
        appetizers = state["slots"].get("appetizers", {}).get("value", "")
        desserts = state["slots"].get("desserts", {}).get("value", "")
        utensils = state["slots"].get("utensils", {}).get("value", "")
        rentals = state["slots"].get("rentals", {}).get("value", "")
        dietary_concerns = state["slots"].get("dietary_concerns", {}).get("value", "")

        print(f"[Contract] Extracted all slot values for {name}")

        # Calculate detailed pricing using pricing calculator
        print(f"[Contract] Calculating pricing for {guest_count} guests...")
        print(f"[Contract] Menu: dishes={selected_dishes}, appetizers={appetizers}, desserts={desserts}")

        pricing_data = await calculate_event_pricing(
            guest_count=guest_count,
            event_type=event_type,
            service_type=service_type,
            selected_dishes=selected_dishes,
            appetizers=appetizers,
            desserts=desserts,
            utensils=utensils,
            rentals=rentals,
        )

        print(f"[Contract] Total: ${pricing_data['grand_total']:,.2f}")
        print(f"[Contract] Menu items: {len(pricing_data['line_items'])}")

        # Generate contract number in format: CC-YYYYMMDD-XXXX
        now = datetime.now()
        contract_number = f"CC-{now:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"

        # Create detailed contract data
        state["contract_data"] = {
            # Contract metadata
            "contract_number": contract_number,
            "contract_id": f"contract-{uuid.uuid4()}",
            "issue_date": now.strftime("%B %d, %Y"),
            "status": "pending_staff_approval",
            "generated_at": now.isoformat(),

            # Client information
            "client_name": name,
            "client_email": email or "",
            "client_phone": phone,

            # Event details
            "event_type": event_type,
            "event_date": event_date,
            "venue_name": venue.split(",")[0].strip() if "," in venue else venue,
            "venue_address": venue,
            "guest_count": guest_count,
            "service_type": service_type,

            # Menu and pricing
            "package": pricing_data.get("package"),
            "menu_items": pricing_data["line_items"],
            "dietary_restrictions": dietary_concerns if dietary_concerns else None,
            "special_requests": special_requests,

            # Billing breakdown
            "billing": {
                "menu_subtotal": pricing_data["menu_total"],
                "service_charge": pricing_data["service_surcharge"],
                "subtotal_before_fees": pricing_data["subtotal_before_fees"],
                "tax": {
                    "amount": pricing_data["tax"],
                    "rate": pricing_data["tax_rate"],
                    "percentage": f"{pricing_data['tax_rate'] * 100}%"
                },
                "gratuity": {
                    "amount": pricing_data["gratuity"],
                    "rate": pricing_data["gratuity_rate"],
                    "percentage": f"{pricing_data['gratuity_rate'] * 100}%"
                },
                "grand_total": pricing_data["grand_total"],
                "deposit": {
                    "amount": pricing_data["deposit"],
                    "percentage": "50%",
                    "due": "at signing"
                },
                "balance": {
                    "amount": pricing_data["balance"],
                    "due": "21 days prior to event"
                },
                "currency": "USD"
            },

            # Policies (from business config)
            "policies": {
                "cancellation": {
                    "over_60_days": "$500 date freeze forfeited",
                    "30_60_days": "max 30% deposit refund minus $500 forfeited",
                    "under_30_days": "max 0% deposit refund minus Deposit forfeited",
                    "under_2_weeks": "max 0% deposit refund minus 100% forfeited"
                },
                "guest_count": "If counts drop 10% below original, prices may vary",
                "food_escalation": "Costs subject to change to match market value",
                "payment_fees": {
                    "credit_debit": "5% for cards",
                    "venmo": "2% fee",
                    "checks": "Checks to 'The Caterer, LLC'"
                },
                "additional_labor": "$30/hr per server, $50/hr per supervisor over 6 hours onsite"
            }
        }

        # Generate confirmation message with pricing summary
        confirmation_message = f"""**Contract Generated Successfully!**

**Contract Number:** {contract_number}
**Event:** {event_type} on {event_date}
**Venue:** {venue}
**Guests:** {guest_count}

**Pricing Summary:**
"""

        # Add package if available
        if pricing_data.get("package"):
            pkg = pricing_data["package"]
            confirmation_message += f"• Package: {pkg['name']} - ${pkg.get('per_person_rate', 0):.2f}/person\n"

        # Add menu items summary
        if pricing_data["line_items"]:
            confirmation_message += f"• Menu Items: {len(pricing_data['line_items'])} items selected\n"

        confirmation_message += f"""
**Total Breakdown:**
• Menu Total: ${pricing_data['menu_total']:,.2f}
• Service Charge: ${pricing_data['service_surcharge']:,.2f}
• Tax ({pricing_data['tax_rate']*100}%): ${pricing_data['tax']:,.2f}
• Gratuity ({pricing_data['gratuity_rate']*100}%): ${pricing_data['gratuity']:,.2f}
• **Grand Total: ${pricing_data['grand_total']:,.2f}**

**Payment Schedule:**
• Deposit (50%) due at signing: ${pricing_data['deposit']:,.2f}
• Balance due 21 days before event: ${pricing_data['balance']:,.2f}

Your contract is ready for staff review and will be sent to you for e-signature once approved. Thank you for choosing The Catering Company!
"""

        # Add confirmation message
        state["messages"].append(AIMessage(content=confirmation_message))

        # Mark as complete
        state["is_complete"] = True
        print(f"[Contract] Contract {contract_number} generated successfully")
        
    except Exception as e:
        error_message = f"Error generating contract: {str(e)}"
        state["messages"].append(AIMessage(content=error_message))
        state["error"] = error_message
    
    return state

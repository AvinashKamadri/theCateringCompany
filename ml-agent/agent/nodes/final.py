"""
Final detail nodes: special requests, dietary concerns, anything else,
and contract generation.
"""

import uuid
from datetime import datetime

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_extract, llm_respond,
    is_affirmative, is_negative,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS
from tools.pricing import calculate_event_pricing
from config.business_rules import config


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}


async def ask_special_requests_node(state: ConversationState) -> ConversationState:
    """Handle special requests — check if user already gave one or just said yes/no."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Check if the user already provided a request (not just "yes"/"no")
    has_substance = len(user_msg.split()) > 4 and not is_negative(user_msg)

    if has_substance:
        # User gave the actual request inline — store it directly
        fill_slot(state["slots"], "special_requests", user_msg.strip())
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer shared their special request: "
            f"\"{user_msg}\". Acknowledge it warmly and confirm you've noted it. "
            "Then ask: Do you have any health or dietary concerns we should know about?",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "collect_dietary"
    elif is_affirmative(user_msg):
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer has special requests. "
            "Ask them to tell you about their special requests.",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "collect_special_requests"
    else:
        fill_slot(state["slots"], "special_requests", "none")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nNo special requests. "
            "Ask: Do you have any health or dietary concerns we should know about?",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "collect_dietary"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_special_requests_node(state: ConversationState) -> ConversationState:
    """Record special requests. Appends if there's already a value."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # If user says "that's all" / "nothing else", keep existing value and move on
    if is_negative(user_msg):
        existing = get_slot_value(state["slots"], "special_requests")
        if not existing or existing == "none":
            fill_slot(state["slots"], "special_requests", "none")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nSpecial requests noted. "
            "Ask: Do you have any health or dietary concerns we should know about?",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "collect_dietary"
    else:
        # Append to existing requests if any
        existing = get_slot_value(state["slots"], "special_requests")
        if existing and existing != "none":
            combined = f"{existing}; {user_msg.strip()}"
        else:
            combined = user_msg.strip()
        fill_slot(state["slots"], "special_requests", combined)

        context = f"Special requests so far: {combined}\nSlots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nRecorded the customer's special request. "
            "Confirm what you've noted. Then ask: Anything else, or should we move on "
            "to dietary concerns?",
            context
        )
        state["current_node"] = "collect_special_requests"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_dietary_node(state: ConversationState) -> ConversationState:
    """Record dietary/health concerns — flags conflicts for user to decide."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    slots = _slots_context(state)
    dishes = slots.get("selected_dishes", "")

    # Check if this is a follow-up clarification (user already has dietary stored)
    existing_dietary = get_slot_value(state["slots"], "dietary_concerns")
    if existing_dietary and existing_dietary != "none":
        # User is clarifying/updating their dietary note
        updated = await llm_extract(
            "You are updating a dietary note for a catering event.\n"
            f"Previous dietary note: {existing_dietary}\n"
            f"Customer's update/clarification: {user_msg}\n"
            f"Current menu: {dishes}\n\n"
            "Rewrite the dietary note incorporating the customer's clarification. "
            "If they say to keep a dish despite a conflict, note that as an explicit exception. "
            "Return ONLY the updated dietary note as a clear kitchen instruction.",
            user_msg,
        )
        fill_slot(state["slots"], "dietary_concerns", updated)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nDietary note updated to: \"{updated}\". "
            "Confirm the update. Ask: Is there anything else you need for your event?",
            f"Context: {_slots_context(state)}",
        )
        state["current_node"] = "ask_anything_else"
    else:
        # First time — store what user said, flag any conflict for the user to decide
        dietary_detail = await llm_extract(
            "You are recording dietary concerns for a catering event.\n"
            f"Customer said: {user_msg}\n"
            f"Current menu: {dishes}\n\n"
            "Write a dietary note capturing EXACTLY what the customer requested. "
            "Do NOT assume any dishes need replacing — just note the dietary requirement. "
            "If there's a potential conflict (e.g., halal + pork dish on menu), "
            "note the conflict but do NOT decide for the customer.\n"
            "Return ONLY the dietary note as a clear kitchen instruction.",
            user_msg,
        )
        if dietary_detail.strip().upper() == "NONE":
            dietary_detail = user_msg.strip()

        fill_slot(state["slots"], "dietary_concerns", dietary_detail)

        # Check if there's a menu conflict to flag
        conflict_check = await llm_extract(
            "Does this menu have any items that conflict with the dietary requirement?\n"
            f"Dietary requirement: {user_msg}\n"
            f"Menu items: {dishes}\n\n"
            "Return YES if there's a conflict, NO if there isn't. Just YES or NO.",
            user_msg,
        )

        if "YES" in conflict_check.upper():
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\nThe customer wants: {user_msg}. "
                f"Their menu includes: {dishes}. "
                "There may be a conflict (e.g., pork and halal). "
                "POLITELY point out the potential conflict and ASK the customer "
                "how they'd like to handle it — keep the dish as-is (as an exception "
                "for guests who prefer it), or replace it? Do NOT decide for them. "
                "Let the customer choose.",
                f"Context: {_slots_context(state)}",
            )
            # Stay on collect_dietary so their answer updates the dietary slot
            state["current_node"] = "collect_dietary"
        else:
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\nDietary concern noted: {dietary_detail}. "
                "Confirm you've recorded it. "
                "Ask: Is there anything else you need for your event?",
                f"Context: {_slots_context(state)}",
            )
            state["current_node"] = "ask_anything_else"

    state["messages"] = add_ai_message(state, response)
    return state


async def ask_anything_else_node(state: ConversationState) -> ConversationState:
    """Handle yes/no about anything else needed."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Use LLM to detect if user wants to add something or is done
    intent = await llm_extract(
        "The customer was asked 'Is there anything else you need for your event?' "
        "Are they adding something or saying they're done? "
        "Return ONLY: add or done",
        user_msg
    )
    if intent.strip().lower() == "add":
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['ask_anything_else']}",
            f"Customer wants to add something. Ask what else they need.\nSlots: {_slots_context(state)}"
        )
        state["current_node"] = "collect_anything_else"
    else:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThat's everything! Keep it short — one line: "
            "'We've got everything we need. Would you like to schedule a quick 10–15 minute call to go over the details?'",
            f"Slots: {_slots_context(state)}"
        )
        state["current_node"] = "offer_followup"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_anything_else_node(state: ConversationState) -> ConversationState:
    """Record additional notes and ask again."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    existing = get_slot_value(state["slots"], "additional_notes") or ""
    new_notes = f"{existing}\n{user_msg}".strip() if existing else user_msg.strip()
    fill_slot(state["slots"], "additional_notes", new_notes)

    context = f"Additional notes: {new_notes}\nSlots: {_slots_context(state)}"
    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['collect_anything_else']}", context
    )

    state["current_node"] = "ask_anything_else"
    state["messages"] = add_ai_message(state, response)
    return state


async def offer_followup_node(state: ConversationState) -> ConversationState:
    """Offer a follow-up call, then generate contract with pending_staff_review status."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    intent = await llm_extract(
        "The customer was asked if they'd like to schedule a follow-up call. "
        "Did they say yes or no? Return ONLY: yes or no",
        user_msg
    )

    if intent.strip().lower() == "yes":
        fill_slot(state["slots"], "followup_call", "Requested — team will schedule")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nCustomer wants a follow-up call. Confirm: "
            "'We'll have someone reach out to set up a call. Your summary is being prepared — thanks!'",
            f"Slots: {_slots_context(state)}"
        )
    else:
        fill_slot(state["slots"], "followup_call", "no")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nNo follow-up call needed. Confirm: "
            "'Sounds good — your summary is being prepared and our team will review it. Thanks!'",
            f"Slots: {_slots_context(state)}"
        )

    state["current_node"] = "generate_contract"
    state["messages"] = add_ai_message(state, response)
    return state


def _build_modification_notes(raw_slots: dict) -> str:
    """Build human-readable notes from modification_history in slots."""
    notes = []
    for name, data in raw_slots.items():
        history = data.get("modification_history", [])
        for change in history:
            notes.append(
                f"- {name.replace('_', ' ').title()}: Changed from "
                f"\"{change['old_value']}\" to \"{change['new_value']}\" "
                f"(updated {change['timestamp'][:10]})"
            )
    return "\n".join(notes) if notes else "None"


async def generate_contract_node(state: ConversationState) -> ConversationState:
    """Generate a professional catering contract with real pricing from DB."""
    state = dict(state)
    slots = _slots_context(state)
    raw_slots = state["slots"]
    mod_notes = _build_modification_notes(raw_slots)

    # --- Calculate real pricing from DB ---
    try:
        guest_count = int(slots.get("guest_count", 0))
    except (ValueError, TypeError):
        guest_count = 0

    pricing = await calculate_event_pricing(
        guest_count=guest_count,
        event_type=slots.get("event_type", ""),
        service_type=slots.get("service_type", ""),
        selected_dishes=slots.get("selected_dishes"),
        appetizers=slots.get("appetizers"),
        desserts=slots.get("desserts"),
        utensils=slots.get("utensils"),
        rentals=slots.get("rentals"),
    )

    # Format pricing breakdown for the contract prompt (Kelly Diep style)
    pricing_lines = []
    for li in pricing["line_items"]:
        desc = f" — {li['description']}" if li.get("description") else ""
        if li["price_type"] == "per_person":
            pricing_lines.append(
                f"  {li['name']}{desc} - ${li['unit_price']:.2f}pp"
            )
        else:
            pricing_lines.append(
                f"  {li['name']}{desc} - ${li['total']:.2f}"
            )
    pricing_text = "\n".join(pricing_lines) if pricing_lines else "  No itemized pricing available"

    pkg = pricing.get("package")
    package_note = ""
    if pkg and pkg.get("per_person_rate"):
        package_note = f"Package: {pkg['name']} ${pkg['per_person_rate']:.2f}pp"

    # Billing summary (matches Kelly Diep format)
    billing_summary = f"""Billing Summary

Menu Subtotal: ${pricing['food_subtotal']:.2f}
Service/Labor: ${pricing['service_surcharge']:.2f}
Subtotal: ${pricing['subtotal_before_fees']:.2f}
{pricing['tax_rate']*100:.1f}% Tax: ${pricing['tax']:.2f}
{pricing['gratuity_rate']*100:.0f}% Service & Gratuity: ${pricing['gratuity']:.2f}
TOTAL: ${pricing['grand_total']:.2f}

Deposit Due at signing ({config.DEPOSIT_PERCENTAGE*100:.0f}%): ${pricing['deposit']:.2f}
Balance Due {config.CONTRACT_BALANCE_DUE_DAYS} days prior to event: ${pricing['balance']:.2f}

Prices are best estimates of future market value, subject to change."""

    # Generate deterministic contract number and today's date
    contract_number = f"{config.CONTRACT_PREFIX}-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    date_issued = datetime.now().strftime("%B %d, %Y")

    # Build client-facing SHORT summary (no pricing — full contract goes to staff)
    partner_line = f"\nPartner/Fiancé: {slots.get('partner_name')}" if slots.get('partner_name') else ""
    company_line = f"\nCompany: {slots.get('company_name')}" if slots.get('company_name') else ""
    honoree_line = f"\nBirthday Person: {slots.get('honoree_name')}" if slots.get('honoree_name') else ""
    email_line = f"\nEmail: {slots.get('email')}" if slots.get('email') else ""
    phone_line = f"\nPhone: {slots.get('phone')}" if slots.get('phone') else ""

    contract_prompt = f"""Generate a SHORT EVENT SUMMARY for the client. NOT a full contract — no pricing, no billing, no legal terms.
The full contract with pricing goes to our staff for review.

Use ONLY the data below. Do NOT invent details.

IMPORTANT: Use these EXACT values:
- Contract Number: {contract_number}
- Date Issued: {date_issued}

---

EVENT DETAILS:
Client: {slots.get('name', 'N/A')}{email_line}{phone_line}{partner_line}{company_line}{honoree_line}
Date of Event: {slots.get('event_date', 'N/A')}
Location: {slots.get('venue', 'N/A')}
Guest Count: {slots.get('guest_count', 'N/A')}
Event Type: {slots.get('event_type', 'N/A')}
Service Type: {slots.get('service_type', 'N/A')}
Service Style: {slots.get('service_style', 'Not specified')}
Appetizer Style: {slots.get('appetizer_style', 'Not specified')}
Meal Style: {slots.get('meal_style', 'Not specified')}

MENU (item names only — no prices):
Main Dishes: {slots.get('selected_dishes', 'None')}
Appetizers: {slots.get('appetizers', 'None')}
Desserts: {slots.get('desserts', 'None')}
Menu Notes: {slots.get('menu_notes', 'None')}

DRINKS & BAR:
{slots.get('drinks', 'Water, Iced Tea, Lemonade (included)')}

ADD-ONS:
Utensils: {slots.get('utensils', 'Not requested')}
Tableware: {slots.get('tableware', 'Standard Disposable')}
Rentals: {slots.get('rentals', 'Not requested')}
Labor Services: {slots.get('labor', 'Not requested')}

NOTES:
Dietary Concerns: {slots.get('dietary_concerns', 'None')}
Special Requests: {slots.get('special_requests', 'None')}
Additional Notes: {slots.get('additional_notes', 'None')}
Follow-up Call: {slots.get('followup_call', 'Not requested')}

{mod_notes if mod_notes.strip() else ''}

---

FORMAT RULES:
- Clean, organized event summary — NOT a legal contract
- Item names only — NO prices, NO billing, NO tax calculations
- End with: "Our team will finalize your quote and reach out within 24–48 hours."
- Contact: {config.COMPANY_EMAIL}  {config.COMPANY_PHONE}
- Keep it short and professional"""

    response = await llm_respond(
        "You are a professional catering assistant generating an event summary. "
        "Generate a clean, complete event summary. Include ALL details provided. "
        "No pricing, no billing, no legal terms. This is NOT a conversation — do NOT ask any questions. "
        "Just output the formatted summary.",
        contract_prompt
    )

    # Build contract title: @ClientName Year.docx
    client_name = slots.get("name", "Unknown")
    event_date = slots.get("event_date", "")
    year = event_date[:4] if event_date and len(event_date) >= 4 else str(datetime.now().year)
    title = f"@{client_name} {year}.docx"

    # Store contract data for API to persist
    state["contract_data"] = {
        "contract_id": str(uuid.uuid4()),
        "title": title,
        "slots": slots,
        "pricing": pricing,
        "total_amount": pricing["grand_total"],
        "modification_history": {
            name: data.get("modification_history", [])
            for name, data in raw_slots.items()
            if data.get("modification_history")
        },
        "summary": f"Catering contract for {client_name} — {slots.get('event_type', 'Event')} on {event_date}",
        "contract_text": response,
        "generated_at": datetime.now().isoformat(),
        "status": "pending_staff_review",
    }
    state["is_complete"] = True
    state["current_node"] = "complete"
    state["messages"] = add_ai_message(state, response)
    return state

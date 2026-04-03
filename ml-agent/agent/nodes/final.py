"""
Final detail nodes: special requests, labor services, dietary concerns,
summary generation, and follow-up call offer.
"""

import uuid
from datetime import datetime

from agent.state import ConversationState, fill_slot, get_slot_value
from agent.nodes.helpers import (
    get_last_human_message, add_ai_message, llm_extract, llm_respond,
    llm_extract_structured, is_null_extraction, is_affirmative, is_negative,
)
from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS


def _slots_context(state):
    return {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}


async def ask_special_requests_node(state: ConversationState) -> ConversationState:
    """Handle special requests — check if user already gave one or just said yes/no."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    has_substance = len(user_msg.split()) > 4 and not is_negative(user_msg)

    if has_substance:
        fill_slot(state["slots"], "special_requests", user_msg.strip())
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer shared their special request: "
            f"\"{user_msg}\". Acknowledge it briefly. "
            "Then present labor service options.",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "ask_labor_services"
    elif is_affirmative(user_msg):
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nThe customer has special requests. "
            "Ask them to share their special requests.",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "collect_special_requests"
    else:
        fill_slot(state["slots"], "special_requests", "none")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nNo special requests. "
            "Present labor service options:\n"
            f"{NODE_PROMPTS['ask_labor_services']}",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "ask_labor_services"

    state["messages"] = add_ai_message(state, response)
    return state


async def collect_special_requests_node(state: ConversationState) -> ConversationState:
    """Record special requests. Appends if there's already a value."""
    from agent.nodes.helpers import is_done_confirming
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_negative(user_msg) or is_done_confirming(user_msg):
        existing = get_slot_value(state["slots"], "special_requests")
        if not existing or existing == "none":
            fill_slot(state["slots"], "special_requests", "none")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nSpecial requests noted. "
            "Present labor service options.",
            f"Context: {_slots_context(state)}"
        )
        state["current_node"] = "ask_labor_services"
    else:
        existing = get_slot_value(state["slots"], "special_requests")
        if existing and existing != "none":
            combined = f"{existing}; {user_msg.strip()}"
        else:
            combined = user_msg.strip()
        fill_slot(state["slots"], "special_requests", combined)

        context = f"Special requests so far: {combined}\nSlots: {_slots_context(state)}"
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nRecorded the customer's special request. "
            "Confirm briefly. Ask if there's anything else, or move on to labor services.",
            context
        )
        request_count = len(combined.split(";"))
        if request_count >= 5:
            state["current_node"] = "ask_labor_services"
        else:
            state["current_node"] = "collect_special_requests"

    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Dietary Concerns
# ---------------------------------------------------------------------------

_DIETARY_SCHEMA = {
    "type": "object",
    "properties": {
        "note": {
            "type": "string",
            "description": "Dietary note as a clear kitchen instruction",
        },
        "has_conflict": {
            "type": "boolean",
            "description": "True if any menu item conflicts with the dietary requirement",
        },
    },
    "required": ["note", "has_conflict"],
    "additionalProperties": False,
}


async def collect_dietary_node(state: ConversationState) -> ConversationState:
    """Record dietary/health concerns — flags conflicts for user to decide.

    Routes to generate_summary after dietary is collected.
    """
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])
    slots = _slots_context(state)
    dishes = slots.get("selected_dishes", "")

    existing_dietary = get_slot_value(state["slots"], "dietary_concerns")
    if existing_dietary and existing_dietary != "none":
        # User is clarifying/updating their dietary note
        updated = await llm_extract(
            "You are updating a dietary note for a catering event.\n"
            f"Previous dietary note: {existing_dietary}\n"
            f"Customer's update/clarification: {user_msg}\n"
            f"Current menu: {dishes}\n\n"
            "Rewrite the dietary note incorporating the customer's clarification. "
            "Return ONLY the updated dietary note as a clear kitchen instruction.",
            user_msg,
        )
        if is_null_extraction(updated):
            updated = user_msg.strip()
        fill_slot(state["slots"], "dietary_concerns", updated)
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nDietary note updated: \"{updated}\". "
            "Reassure the customer: 'Noted — those are fully covered. We'll make sure everything is safe.' "
            "Now generate their event summary.",
            f"Context: {_slots_context(state)}",
        )
        state["current_node"] = "generate_summary"
    elif is_negative(user_msg):
        fill_slot(state["slots"], "dietary_concerns", "none")
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\nNo dietary concerns. Acknowledge. "
            "Now generate the event summary.",
            f"Context: {_slots_context(state)}",
        )
        state["current_node"] = "generate_summary"
    else:
        result = await llm_extract_structured(
            "You are recording dietary concerns for a catering event.\n"
            f"Customer said: {user_msg}\n"
            f"Current menu: {dishes}\n\n"
            "Return a JSON object with:\n"
            "  note: dietary note as a clear kitchen instruction\n"
            "  has_conflict: true if any menu item conflicts, false otherwise.",
            user_msg,
            _DIETARY_SCHEMA,
        )

        dietary_detail = result.get("note", "").strip() or user_msg.strip()
        has_conflict = result.get("has_conflict", False)

        fill_slot(state["slots"], "dietary_concerns", dietary_detail)

        if has_conflict:
            dietary_attempts = state.get("dietary_conflict_attempts", 0)
            if dietary_attempts >= 2:
                updated_note = f"{dietary_detail} (menu conflicts noted, customer was informed)"
                fill_slot(state["slots"], "dietary_concerns", updated_note)
                response = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nDietary concern noted with conflicts acknowledged. "
                    "Reassure the customer and generate the summary.",
                    f"Context: {_slots_context(state)}",
                )
                state["current_node"] = "generate_summary"
            else:
                state["dietary_conflict_attempts"] = dietary_attempts + 1
                response = await llm_respond(
                    f"{SYSTEM_PROMPT}\n\nThe customer wants: {user_msg}. "
                    f"Their menu includes: {dishes}. "
                    "There may be a conflict. "
                    "POLITELY point out the potential conflict and ASK the customer "
                    "how they'd like to handle it.",
                    f"Context: {_slots_context(state)}",
                )
                state["current_node"] = "collect_dietary"
        else:
            response = await llm_respond(
                f"{SYSTEM_PROMPT}\n\nDietary concern noted: {dietary_detail}. "
                "Reassure the customer: 'Noted — those are fully covered.' "
                "Now generate the event summary.",
                f"Context: {_slots_context(state)}",
            )
            state["current_node"] = "generate_summary"

    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Summary Generation (replaces contract generation)
# ---------------------------------------------------------------------------

def _build_modification_notes(raw_slots: dict) -> str:
    """Build human-readable notes from modification_history in slots."""
    notes = []
    for name, data in raw_slots.items():
        history = data.get("modification_history", [])
        for change in history:
            notes.append(
                f"- {name.replace('_', ' ').title()}: Changed from "
                f"\"{change['old_value']}\" to \"{change['new_value']}\""
            )
    return "\n".join(notes) if notes else "None"


async def generate_summary_node(state: ConversationState) -> ConversationState:
    """Generate a SHORT event summary — titles and key details only, no billing."""
    state = dict(state)
    slots = _slots_context(state)
    raw_slots = state["slots"]
    mod_notes = _build_modification_notes(raw_slots)

    summary_prompt = f"""Generate a SHORT event summary — titles and key details only.
DO NOT include billing, taxes, pricing, or legal terms.

Format:
- Event: {slots.get('event_type', 'N/A')} on {slots.get('event_date', 'N/A')}
- Guest Count: {slots.get('guest_count', 'N/A')}
- Venue: {slots.get('venue', 'N/A')}
- Service: {slots.get('service_type', 'N/A')} — {slots.get('buffet_or_plated', 'N/A')}
- Cocktail Hour: {slots.get('service_style', 'N/A')}
- Appetizers: {slots.get('appetizers', 'None')}
- Main Menu: {slots.get('selected_dishes', 'None')}
- Desserts: {slots.get('desserts', 'None')}
- Drinks: {slots.get('drinks', 'None')}
- Bar Service: {slots.get('bar_service', 'None')}
- Tableware: {slots.get('tableware', 'Standard')}
- Rentals: {slots.get('rentals', 'None')}
- Labor Services: {slots.get('labor_services', 'None')}
- Special Requests: {slots.get('special_requests', 'None')}
- Dietary: {slots.get('dietary_concerns', 'None')}

Changes Made: {mod_notes}

Present this as a clean, easy-to-read summary. Use bullet points or a simple list.
Strip out any items that are "None" or "no" — only show what was actually selected.
End with: "Here's a quick snapshot of your event! We'll put together a detailed proposal and reach out within 48 hours."
Keep it warm and casual."""

    response = await llm_respond(
        f"{SYSTEM_PROMPT}\n\n{NODE_PROMPTS['generate_summary']}",
        summary_prompt
    )

    # Store summary data for API
    client_name = slots.get("name", "Unknown")
    event_date = slots.get("event_date", "")

    state["summary_data"] = {
        "summary_id": str(uuid.uuid4()),
        "slots": slots,
        "summary_text": response,
        "generated_at": datetime.now().isoformat(),
        "client_name": client_name,
        "event_date": event_date,
        "status": "pending_review",
    }

    state["current_node"] = "offer_followup_call"
    state["messages"] = add_ai_message(state, response)
    return state


# ---------------------------------------------------------------------------
# Follow-up Call Offer
# ---------------------------------------------------------------------------

async def offer_followup_call_node(state: ConversationState) -> ConversationState:
    """Offer to schedule a follow-up call and mark conversation complete."""
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    if is_affirmative(user_msg):
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer wants to schedule a follow-up call. "
            "Let them know someone from the team will reach out within 48 hours "
            "to go over everything in detail. Thank them warmly.",
            f"Context: {_slots_context(state)}"
        )
    else:
        response = await llm_respond(
            f"{SYSTEM_PROMPT}\n\n"
            "The customer doesn't need a call right now. "
            "Thank them warmly and let them know they can reach out anytime. "
            "Keep it brief and friendly.",
            f"Context: {_slots_context(state)}"
        )

    state["is_complete"] = True
    state["current_node"] = "complete"
    state["messages"] = add_ai_message(state, response)
    return state

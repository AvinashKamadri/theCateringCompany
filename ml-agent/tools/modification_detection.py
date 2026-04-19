"""
Modification detection — single authoritative LLM call with DB menu context.

The LLM receives the actual menu item lists from the database so it can
correctly map any item name to its slot without keyword heuristics or
post-processing overrides.
"""

import json
from datetime import date
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from agent.llm import llm
from pydantic import BaseModel, Field


class ModificationInput(BaseModel):
    message: str = Field(description="User message")
    current_slots: dict = Field(description="Current slot values")
    recent_messages: list = Field(default=[], description="Conversation history")
    menu_context: dict = Field(default={}, description="Menu items by category from DB")


def _format_recent_messages(messages: list, n: int | None = None) -> str:
    """Compact conversation history. User messages verbatim; AI messages truncated."""
    pool = list(messages) if n is None else list(messages)[-n:]
    lines = []
    for m in pool:
        if isinstance(m, HumanMessage):
            lines.append(f"User: {m.content}")
        else:
            content = m.content
            if len(content) > 150:
                content = content[:150] + "…"
            lines.append(f"Agent: {content}")
    return "\n".join(lines)


def _build_menu_reference(menu_context: dict) -> str:
    """Build a slot→items reference string from DB menu data.

    Groups items into appetizers / main dishes / desserts / drinks so the LLM
    can look up which slot any named item belongs to.
    """
    if not menu_context:
        return ""

    appetizers, mains, desserts, drinks = [], [], [], []

    for cat_name, items in menu_context.items():
        cat_lower = cat_name.lower()
        names = [item["name"] for item in items]
        if any(kw in cat_lower for kw in ["appetizer", "starter", "hors", "canape"]):
            appetizers.extend(names)
        elif any(kw in cat_lower for kw in ["dessert", "cake"]):
            desserts.extend(names)
        elif any(kw in cat_lower for kw in ["coffee", "beverage", "drink", "bar setup", "bar supplies"]):
            drinks.extend(names)
        elif not any(kw in cat_lower for kw in ["floral", "flower", "utensil", "rental", "linen", "chair", "table"]):
            mains.extend(names)

    lines = ["\nMenu reference — use this to map any item name to its correct slot:"]
    if appetizers:
        lines.append(f"appetizers slot: {', '.join(appetizers)}")
    if mains:
        lines.append(f"selected_dishes slot: {', '.join(mains)}")
    if desserts:
        lines.append(f"desserts slot: {', '.join(desserts)}")
    if drinks:
        lines.append(f"drinks slot: {', '.join(drinks)}")
    return "\n".join(lines)


_SLOT_IDENTIFICATION_FUNCTION = {
    "name": "identify_modification_target",
    "description": "Identify which booking field the customer wants to modify and what they want to change it to.",
    "parameters": {
        "type": "object",
        "properties": {
            "target_slot": {
                "type": "string",
                "enum": [
                    "name", "email", "phone", "event_date", "service_type", "event_type",
                    "venue", "guest_count", "special_requests", "additional_notes",
                    "appetizers", "selected_dishes", "desserts", "drinks",
                    "appetizer_style", "meal_style", "service_style",
                    "utensils", "rentals",
                    "partner_name", "company_name", "honoree_name",
                ],
                "description": "The slot the user wants to modify",
            },
            "new_value": {
                "type": "string",
                "description": "The new value to set, or the item(s) to add/remove for menu slots",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in this identification (0–1)",
            },
            "reasoning": {
                "type": "string",
                "description": "One-line explanation of why this slot was chosen",
            },
        },
        "required": ["target_slot", "new_value", "confidence", "reasoning"],
    },
}

_SLOT_RECENCY_HINTS: dict[str, list[str]] = {
    "appetizers":      ["appetizer", "hors d'oeuvres", "starter"],
    "selected_dishes": ["main dish", "entrée", "entree", "main course"],
    "desserts":        ["dessert", "cake", "brownie", "mousse"],
    "drinks":          ["drink", "coffee", "bar service", "beverage"],
    "guest_count":     ["guest", "how many", "attendee"],
    "event_date":      ["date", "when"],
    "venue":           ["venue", "location", "address"],
    "utensils":        ["utensil", "bamboo", "plastic", "eco-friendly"],
    "rentals":         ["rental", "linen"],
    "special_requests":["dietary", "allerg", "restriction"],
}


async def llm_identify_slot(
    message: str,
    current_slots: dict,
    recent_messages: list | None = None,
    menu_context: dict | None = None,
) -> dict:
    """Single LLM call that identifies the target slot and new value.

    Includes actual DB menu items in the prompt so item names always map to
    the correct slot — no keyword heuristics or post-processing overrides.
    """
    try:
        slot_context = "\n".join(
            f"- {k}: {v['value']}"
            for k, v in (current_slots or {}).items()
            if v.get("filled") and not k.startswith("__")
        ) or "No slots filled yet"

        recent_ctx = ""
        if recent_messages:
            recent_ctx = f"\nRecent conversation:\n{_format_recent_messages(recent_messages, n=8)}\n"

        menu_ref = _build_menu_reference(menu_context or {})

        today = date.today().isoformat()

        system_message = SystemMessage(content=f"""You identify which booking field a customer wants to modify.{recent_ctx}

Today: {today}. Resolve all relative dates (e.g. "next Friday", "25th of next month") to absolute dates.

Current booking:
{slot_context}
{menu_ref}

Available fields:
- name, email, phone, event_date, venue, guest_count
- service_type: drop-off or on-site
- event_type: Wedding / Corporate / Birthday / Social / Custom
- appetizer_style: passed around by servers OR set up at a station
- meal_style: plated (served to seats) OR buffet (self-serve)
- service_style: cocktail hour only / full reception / both (wedding context)
- special_requests: dietary restrictions, allergies, food restrictions (NOT drinks or bar service)
- additional_notes: extra instructions for the team, reminders, anything else to note
- appetizers: cocktail hour food — check the appetizers slot list above
- selected_dishes: main course / entrée — check the selected_dishes slot list above
- desserts: sweet items — check the desserts slot list above
- drinks: coffee service, bar packages, beer & wine, open bar
- utensils: bamboo / plastic / eco-friendly
- rentals: linens, tables, chairs
- partner_name, company_name, honoree_name

CRITICAL RULE: When the customer names a specific food item, look it up in the menu reference
above to determine the correct slot. Do NOT guess based on item name alone.

For menu slots (appetizers, selected_dishes, desserts, drinks), new_value should be
the exact item name(s) the customer wants to add or remove.""")

        user_message = HumanMessage(content=f"Customer message: {message}")

        response = await llm.ainvoke(
            [system_message, user_message],
            functions=[_SLOT_IDENTIFICATION_FUNCTION],
            function_call={"name": "identify_modification_target"},
        )

        if hasattr(response, "additional_kwargs") and "function_call" in response.additional_kwargs:
            args = json.loads(response.additional_kwargs["function_call"]["arguments"])
            return {
                "target_slot": args.get("target_slot"),
                "new_value":   args.get("new_value"),
                "confidence":  float(args.get("confidence", 0.0)),
                "reasoning":   args.get("reasoning", ""),
            }

        return {"target_slot": None, "new_value": None, "confidence": 0.0, "reasoning": "No function call in response"}

    except Exception as e:
        return {"target_slot": None, "new_value": None, "confidence": 0.0, "reasoning": f"Error: {e}"}


@tool
async def detect_slot_modification(
    message: str,
    current_slots: dict,
    recent_messages: list = [],
    menu_context: dict = {},
) -> dict:
    """Detect which slot the customer wants to modify.

    Uses a single LLM call with the actual DB menu items in context so item
    names are always mapped to the correct slot.

    Returns:
        detected, target_slot, new_value, confidence, clarification_needed, possible_slots
    """
    try:
        result = await llm_identify_slot(message, current_slots, recent_messages, menu_context)

        target_slot = result["target_slot"]
        new_value   = result["new_value"]
        confidence  = result["confidence"]

        # Recency boost: if the last AI message was asking about the identified slot,
        # the user's reply is almost certainly about that slot.
        if target_slot and recent_messages:
            last_ai = next((m for m in reversed(recent_messages) if isinstance(m, AIMessage)), None)
            if last_ai:
                last_ai_lower = last_ai.content.lower()
                hints = _SLOT_RECENCY_HINTS.get(target_slot, [])
                if any(h in last_ai_lower for h in hints):
                    confidence = min(confidence + 0.15, 1.0)

        clarification_needed = confidence < 0.7
        detected = target_slot is not None and new_value is not None

        return {
            "detected":             detected,
            "target_slot":          target_slot,
            "new_value":            new_value,
            "confidence":           confidence,
            "clarification_needed": clarification_needed,
            "possible_slots":       [target_slot] if clarification_needed and target_slot else [],
        }

    except Exception as e:
        return {
            "detected":             False,
            "target_slot":          None,
            "new_value":            None,
            "confidence":           0.0,
            "clarification_needed": True,
            "possible_slots":       [],
            "error":                str(e),
        }

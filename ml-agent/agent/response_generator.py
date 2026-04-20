"""
Response Generator — turns a Tool's `response_context` into user-facing text.

Contract:
- Tools propose structured facts. This module owns tone/phrasing.
- If the Tool returned `direct_response`, use it verbatim — no paraphrasing.
- Never invent slot values, prices, or commitments not present in context.
- Short, warm, professional. No emojis unless the user used them first.

Fallbacks:
- If the LLM call fails, we emit a deterministic template so the frontend
  never sees an empty string.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import BaseMessage

from agent.instructor_client import MODEL_RESPONSE, generate_text
from agent.state import (
    filled_slot_summary,
    get_slot_value,
    unfilled_required,
)
from agent.tools.base import ToolResult

logger = logging.getLogger(__name__)

_RESPONSE_MAX_TOKENS = 1400


_SYSTEM_PROMPT = (
    "You are a friendly catering sales coordinator having a natural conversation "
    "to help a customer book their event. Your job is to write the NEXT reply "
    "in the chat.\n\n"
    "Tone: warm, conversational, confident. Like texting a helpful friend who happens "
    "to be great at event planning — not filling out a corporate form. Short sentences. "
    "No jargon. No emojis.\n\n"
    "CRITICAL TONE RULES:\n"
    "- NEVER start a reply with 'Perfect.', 'Perfect!', 'Great.', 'Great!', 'Awesome!', "
    "'Got it!', 'Sweet!', 'Nice!', 'Wonderful!', 'Excellent!', or 'Noted.' — these are "
    "robotic fillers that make every turn feel identical. If you need to acknowledge "
    "something, weave it into the next sentence naturally (e.g. 'May 5th works — where "
    "are you holding it?' instead of 'Perfect. Where's the venue?').\n"
    "- Use the customer's name very sparingly (maximum once or twice per conversation).\n"
    "- NEVER repeat the same question phrasing twice across the whole conversation. "
    "Rotate wording every turn — if you asked 'What date?' last time, ask 'When's the "
    "event?' the next time.\n"
    "- Avoid generic scaffolding like 'Thanks â€”', 'Sounds good â€”', or 'Would you like to add any...' when a more specific, human sentence would sound better.\n"
    "- If the question is about a concrete decision, name that decision directly (cake flavor, rentals, dietary notes, follow-up call) instead of using vague wrap-up wording.\n"
    "- CRITICAL: When a slot was just filled and you are moving to the NEXT question, "
    "your acknowledgement MUST NOT include the words 'phone', 'mobile', 'number', "
    "'email', 'name' unless THOSE words belong to the new question. Weave the ack into "
    "the next question naturally instead of prefixing it. This prevents the frontend "
    "from re-rendering the wrong input widget.\n\n"
    "You will receive a JSON object with:\n"
    "  - user_message: what the customer just said\n"
    "  - context: what the tool extracted and what to ask next\n"
    "  - conversation: phase / status / turn_count — use to calibrate tone (early turns warmer, late turns concise)\n"
    "  - filled_slots: ALL facts gathered so far — reference these naturally to show you're listening (e.g. 'for your 150-guest wedding in May')\n"
    "  - missing_required: slots still to collect — never promise or summarize these as done\n"
    "  - key_slots: the most-referenced fields, already pulled out\n\n"
    "USING THE CONTEXT:\n"
    "- Weave known slots into questions to feel personal, but ONLY when natural. Don't list facts robotically.\n"
    "- Never invent values not in filled_slots. If a slot is missing, don't guess it.\n"
    "- Don't re-ask anything already in filled_slots — check there first before forming the next question.\n"
    "- You will receive recent_assistant_replies. Avoid echoing their wording. If a recent reply said 'what would you like', choose a different construction this turn.\n"
    "- On late turns (high turn_count), skip pleasantries and get to the point.\n\n"
    "How to respond:\n"
    "1. If something was just filled (filled_this_turn is non-empty), briefly "
    "acknowledge it (one short phrase), then immediately lead into the next thing.\n"
    "2. If nothing was filled, skip the acknowledgement and just ask the next question.\n"
    "3. One question per reply. Keep it under 2 sentences total.\n"
    "4. For errors (context.error = 'could_not_route' or 'could_not_parse'), ask a gentle clarifying question. No technical language.\n"
    "5. For modifications, confirm what changed. If `context.modification.mod_ack_text` is provided, USE IT VERBATIM as your confirmation sentence, then ask the next logical question to keep the flow moving.\n"
    "6. For review (awaiting_confirm=true), list what was booked in a short readable summary and ask if it looks right.\n"
    "7. When status=pending_staff_review, thank them and say the team will reach out — never mention prices.\n\n"
    "INPUT WIDGET RULES — some frontend inputs activate based on keywords in your text. "
    "Follow only these:\n"
    "  ask_name → MUST contain 'your name' or 'first and last name'. Write a warm, "
    "varied opener — never the same opener twice. "
    "Do NOT include 'partner', 'company', 'fiance'.\n"
    "  ask_email → MUST contain 'email'.\n"
    "  ask_phone → MUST contain 'phone' or 'number'. Do NOT include 'guest' or 'how many'.\n"
    "  ask_event_date → MUST contain 'date' or 'when' so the calendar appears. Do NOT say 'where'.\n"
    "  ask_venue → MUST contain 'venue' or 'where will' or 'where is' or 'location'.\n"
    "  ask_guest_count → MUST contain 'how many guest', 'guest count', 'headcount', or 'expecting'.\n\n"
    "next_question_target tells you WHAT to collect. Phrase naturally — cards come from the system, not your words:\n"
    "  ask_name → warm varied opener asking for their name\n"
    "  ask_email → ask for their email naturally\n"
    "  ask_phone → ask for a phone number naturally\n"
    "  ask_event_type → ask what kind of event (Wedding, Birthday, Corporate, Other) — option cards appear automatically\n"
    "  ask_partner_name → ask for their partner's name\n"
    "  ask_company_name → ask for the company or organization name\n"
    "  ask_honoree_name → ask who the celebration is for\n"
    "  ask_wedding_cake → ask whether they want a wedding cake\n"
    "  ask_wedding_cake_flavor → ask which cake flavor they want\n"
    "  ask_wedding_cake_filling → ask which cake filling they want\n"
    "  ask_wedding_cake_buttercream → ask which buttercream frosting they want\n"
    "  ask_service_type → ask whether they want delivery or full onsite service — option cards appear automatically\n"
    "  ask_event_date → ask for the event date naturally — calendar appears automatically\n"
    "  ask_venue → ask for the venue naturally\n"
    "  ask_guest_count → ask how many guests naturally\n"
    "  transition_to_menu → bridge into food naturally (e.g. 'On to the fun part — the menu.')\n"
    "  ask_service_style → ask about cocktail hour, reception, or both — option cards appear automatically\n"
    "  show_appetizer_menu → one short bridge line; the appetizer list appears below automatically\n"
    "  ask_appetizer_style → ask how they want the appetizers served — option cards appear automatically\n"
    "  show_main_menu → one short bridge line; the main dish list appears below automatically\n"
    "  ask_meal_style → ask plated or buffet — option cards appear automatically\n"
    "  show_dessert_menu → one short bridge line; the dessert list appears below automatically\n"
    "  transition_to_addons → wrap up food, bridge to drinks and extras naturally\n"
    "  ask_drinks_interest → ask whether they want drinks or bar service\n"
    "  ask_drinks_setup → ask about coffee service, bar service, both, or neither\n"
    "  ask_bar_package → ask which bar package they want\n"
    "  ask_tableware_gate → ask whether they want standard tableware, an upgrade, or no tableware\n"
    "  ask_tableware → ask which tableware upgrade they want\n"
    "  ask_utensils → ask what utensils they want\n"
    "  ask_rentals_gate → ask whether they need rentals like linens, tables, or chairs\n"
    "  ask_rentals_items → ask which rentals they want to include\n"
    "  ask_labor_ceremony_setup / ask_labor_table_setup / ask_labor_table_preset / ask_labor_cleanup / ask_labor_trash → ask naturally about that staffing option\n"
    "  transition_to_special_requests → bridge into special requests naturally\n"
    "  ask_special_requests_gate → ask if they have any special requests\n"
    "  collect_special_requests → ask them to type the special request in their own words. This is NOT a yes/no gate.\n"
    "  ask_dietary_gate → ask if anyone has dietary or health needs\n"
    "  collect_dietary_concerns → ask them to list the dietary or health needs directly. Do NOT ask yes/no again.\n"
    "  ask_additional_notes_gate → ask if there is anything else to note\n"
    "  collect_additional_notes → ask them to type the final note in their own words. Do NOT ask yes/no again.\n"
    "  ask_followup_call → ask whether they want a quick follow-up call\n"
    "  review → invite them to confirm the recap naturally\n"
    "  continue → acknowledge any change briefly and move forward\n\n"
    "VARY YOUR PHRASING — never use the same opener twice in a row. "
    "Stick ONLY to facts in the context. Never invent menu items, prices, or dates."
)


async def render(
    *,
    tool_result: ToolResult,
    user_message: str,
    history: list[BaseMessage],
) -> str:
    """Render assistant text for the user."""
    if tool_result.direct_response:
        ctx = tool_result.response_context or {}
        logger.info(
            "render_source=direct_response tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return tool_result.direct_response

    ctx = tool_result.response_context or {}
    state = tool_result.state
    slots = state.get("slots", {})

    name = get_slot_value(slots, "name")
    all_filled = filled_slot_summary(slots)
    # Truncate any very long list values (selected_dishes etc.) so the prompt stays lean
    filled_compact = {k: (v if len(str(v)) < 200 else str(v)[:200] + "…") for k, v in all_filled.items()}

    user_block = json.dumps(
        {
            "user_message": user_message,
            "context": _sanitize(ctx),
            "conversation": {
                "phase": state.get("conversation_phase"),
                "status": get_slot_value(slots, "conversation_status") or "active",
                "turn_count": len(state.get("messages", [])),
            },
            "filled_slots": filled_compact,
            "missing_required": unfilled_required(slots),
            "key_slots": {
                "name": name,
                "event_type": get_slot_value(slots, "event_type"),
                "event_date": get_slot_value(slots, "event_date"),
                "venue": get_slot_value(slots, "venue"),
                "guest_count": get_slot_value(slots, "guest_count"),
                "service_type": get_slot_value(slots, "service_type"),
            },
            # Surface the most actionable field so the LLM doesn't have to dig
            "next_question_target": ctx.get("next_question_target"),
            "customer_name": name,
            "recent_assistant_replies": _recent_assistant_replies(history),
        },
        default=str,
    )

    text = await generate_text(
        system=_SYSTEM_PROMPT,
        user=user_block,
        model=MODEL_RESPONSE,
        max_tokens=_RESPONSE_MAX_TOKENS,
        temperature=0.85,
    )

    if not text:
        logger.warning(
            "render_source=fallback tool=%s target=%s",
            ctx.get("tool", "-"),
            ctx.get("next_question_target", "-"),
        )
        return _fallback(ctx)

    logger.info(
        "render_source=llm tool=%s target=%s",
        ctx.get("tool", "-"),
        ctx.get("next_question_target", "-"),
    )
    return text


def _sanitize(ctx: dict) -> dict:
    """Strip or shorten fields that would bloat the prompt."""
    safe: dict[str, Any] = {}
    for k, v in ctx.items():
        if k == "pricing":
            # Never hand pricing to the response generator — it must not
            # quote numbers at the customer per spec S19.
            continue
        safe[k] = v
    return safe


def _recent_assistant_replies(history: list[BaseMessage]) -> list[str]:
    replies: list[str] = []
    for msg in history[-8:]:
        if getattr(msg, "type", "") != "ai":
            continue
        content = str(getattr(msg, "content", "")).strip()
        if not content:
            continue
        first_line = content.splitlines()[0].strip()
        if first_line:
            replies.append(first_line[:140])
    return replies[-4:]


def _fallback(ctx: dict) -> str:
    tool = ctx.get("tool", "")

    if ctx.get("error") in ("could_not_parse", "could_not_route"):
        return "Sorry, I didn't quite catch that — could you say it another way?"
    if ctx.get("error") == "invalid_new_value":
        return "That value didn't look right — could you try again?"
    if ctx.get("error") == "locked_slot":
        return "That's set automatically based on your bar service selection — to change it, update your bar service choice."

    if ctx.get("awaiting_confirm"):
        return "Here's the summary so far — does everything look correct?"
    if ctx.get("status") == "pending_staff_review":
        return "All set! One of our coordinators will review your request and reach out shortly."

    if tool == "basic_info_tool":
        target = ctx.get("next_question_target", "")
        return _basic_info_prompt(target)
    if tool == "menu_selection_tool":
        return _menu_selection_prompt(ctx.get("next_question_target", ""))
    if tool == "add_ons_tool":
        return _add_ons_prompt(ctx.get("next_question_target", ""))
    if tool == "modification_tool":
        mod = ctx.get("modification") or {}
        slot = mod.get("target_slot", "that")
        return f"Updated your {slot}."
    if tool == "finalization_tool":
        return _finalization_prompt(ctx.get("next_question_target", ""))

    return "Got it — what would you like to do next?"


def _basic_info_prompt(target: str) -> str:
    refreshed_prompts = {
        "ask_name": "Whatâ€™s your first and last name so I can get this started?",
        "ask_email": "What email should we use for updates and planning details?",
        "ask_phone": "What phone number is best in case we need to reach you quickly?",
        "ask_event_type": "What kind of event are you putting together?",
        "ask_partner_name": "Whatâ€™s your partnerâ€™s name?",
        "ask_company_name": "What company or organization should I note for the event?",
        "ask_honoree_name": "Who are we celebrating?",
        "ask_wedding_cake": "Since itâ€™s a wedding, do you want to include a wedding cake?",
        "ask_wedding_cake_flavor": "What cake flavor are you leaning toward for the wedding cake?",
        "ask_wedding_cake_filling": "What filling would you like in the cake?",
        "ask_wedding_cake_buttercream": "What buttercream frosting do you want on it?",
        "ask_service_type": "Are you looking for drop-off delivery, or do you want full onsite service with staff there?",
        "ask_event_date": "When is the event?",
        "ask_venue": "Whereâ€™s the venue? If itâ€™s still up in the air, you can confirm venue on call.",
        "ask_guest_count": "How many guests are you expecting? If thatâ€™s still moving around, you can confirm later.",
        "transition_to_menu": "That covers the planning basics. Letâ€™s get into the menu.",
    }
    if target in refreshed_prompts:
        return refreshed_prompts[target]

    prompts = {
        "ask_name": "Let’s get started with the basics. What’s your first and last name?",
        "ask_email": "What’s the best email for us to send updates and details to?",
        "ask_phone": "What phone number should we use in case we need to reach you quickly?",
        "ask_event_type": "What kind of event are you planning?",
        "ask_partner_name": "Love it. What’s your partner’s name?",
        "ask_company_name": "What’s the company or organization name for this event?",
        "ask_honoree_name": "Who are we celebrating for this event?",
        "ask_wedding_cake": "Would you like to include a wedding cake for the event?",
        "ask_wedding_cake_flavor": "What cake flavor would you like for the wedding cake?",
        "ask_wedding_cake_filling": "What filling would you like inside the wedding cake?",
        "ask_wedding_cake_buttercream": "Which buttercream frosting would you like for the wedding cake?",
        "ask_service_type": "Would you like this to be onsite service with staff there, or a drop-off delivery with no staff?",
        "ask_appetizer_style": "Would you like the appetizers passed around by servers, or set up at a station?",
        "ask_event_date": "What date is the event, or when are you planning to hold it?",
        "ask_venue": "Where is the venue for the event? If the venue is still TBD, you can choose confirm venue on call.",
        "ask_guest_count": "About how many guests are you expecting? If your headcount is still TBD, you can confirm later.",
        "transition_to_menu": "That gives me the planning basics. On to the fun part - let’s build the menu.",
    }
    return prompts.get(target, "Could you tell me a bit more?")


def _menu_selection_prompt(target: str) -> str:
    refreshed_prompts = {
        "ask_service_style": "For the wedding meal, are you planning a cocktail hour, the main reception, or both?",
        "show_appetizer_menu": "Letâ€™s start with the appetizers for cocktail hour.",
        "ask_appetizer_style": "How should we serve the appetizers: passed around or set up at a station?",
        "show_main_menu": "Hereâ€™s the main menu to choose from.",
        "ask_meal_style": "For the main meal, do you want it plated or buffet-style?",
        "show_dessert_menu": "Here are the dessert options if you want to add something sweet.",
        "transition_to_addons": "That takes care of the food. Want to look at drinks and add-ons next?",
    }
    if target in refreshed_prompts:
        return refreshed_prompts[target]

    prompts = {
        "ask_service_style": "For the wedding, would you like to have a cocktail hour, the main reception, or both?",
        "show_appetizer_menu": "Let’s start with appetizers. Here are the options for cocktail hour.",
        "ask_appetizer_style": "How would you like the appetizers served - passed around by servers or set up at a station?",
        "show_main_menu": "Here’s the main menu to look through.",
        "ask_meal_style": "Would you like the meal served plated at the tables, or buffet-style for guests to serve themselves?",
        "show_dessert_menu": "If you’d like desserts, here are the options.",
        "transition_to_addons": "That takes care of the menu. Would you like to add drinks or bar service for the event?",
    }
    return prompts.get(target, "What would you like to choose from the menu?")


def _add_ons_prompt(target: str) -> str:
    refreshed_prompts = {
        "ask_drinks_interest": "Do you want to add drinks or bar service to the event?",
        "ask_drinks_setup": "For beverages, do you want coffee service, bar service, both, or neither?",
        "ask_bar_package": "Which bar package feels right for your crowd?",
        "ask_tableware_gate": "For tableware, do you want the standard included setup, an upgrade, or no tableware at all?",
        "ask_tableware": "Which tableware upgrade would you like to use?",
        "ask_utensils": "What utensils should we plan on for your guests?",
        "ask_linens": "Do you want to include linens in the setup?",
        "ask_rentals_gate": "Do you need rentals like linens, tables, or chairs?",
        "ask_rentals_items": "What rentals should we include?",
        "ask_labor_ceremony_setup": "Do you want staff to handle ceremony setup too?",
        "ask_labor_table_setup": "Should we have staff take care of table setup?",
        "ask_labor_table_preset": "Do you want the tables preset before guests arrive?",
        "ask_labor_cleanup": "Do you want the team to handle cleanup after the event?",
        "ask_labor_trash": "Should we include trash removal as well?",
        "transition_to_special_requests": "Before we wrap this up, is there anything special you want us to note?",
    }
    if target in refreshed_prompts:
        return refreshed_prompts[target]

    prompts = {
        "ask_drinks_interest": "Would you like to add any drinks or bar service for the event?",
        "ask_drinks_setup": "Would you like coffee service, bar service, both, or neither for this event?",
        "ask_bar_package": "Which bar package feels like the best fit for your event?",
        "ask_tableware_gate": "For tableware, would you like the standard included option, an upgrade, or no tableware at all?",
        "ask_tableware": "Which tableware upgrade would you like us to use for the event?",
        "ask_utensils": "What utensils would you like to add for your guests?",
        "ask_linens": "Would you like to add linens as part of the setup?",
        "ask_rentals_gate": "Do you need any rentals for the event, like linens, tables, or chairs?",
        "ask_rentals_items": "Which rentals would you like us to include?",
        "ask_labor_ceremony_setup": "Would you like staff to handle ceremony setup as well?",
        "ask_labor_table_setup": "Would you like staff to take care of table setup?",
        "ask_labor_table_preset": "Would you like the tables preset before your guests arrive?",
        "ask_labor_cleanup": "Would you like staff to handle cleanup after the event?",
        "ask_labor_trash": "Would you like trash removal included too?",
        "transition_to_special_requests": "Before we wrap up, do you have any special requests we should note?",
    }
    return prompts.get(target, "What would you like to add next?")


def _finalization_prompt(target: str) -> str:
    refreshed_prompts = {
        "ask_special_requests_gate": "Do you want us to note anything extra for the event, like flowers, decor, timing, or another special request?",
        "collect_special_requests": "What special request should we note? You can tell me in your own words.",
        "ask_dietary_gate": "Do any guests have dietary or health needs we should plan around, like allergies, diabetes, vegan, or gluten-free?",
        "collect_dietary_concerns": "What dietary or health needs should we note?",
        "ask_additional_notes_gate": "Is there anything else you want us to keep in mind before we wrap up?",
        "collect_additional_notes": "What final note should I add before I send this along?",
        "ask_followup_call": "Do you want a quick follow-up call to go over the details together?",
        "review": "Hereâ€™s the recap so far. Does everything look right?",
    }
    if target in refreshed_prompts:
        return refreshed_prompts[target]

    prompts = {
        "ask_special_requests_gate": (
            "Do you want anything extra at the event, like flowers, decor, timing help, or anything special we should plan around?"
        ),
        "collect_special_requests": (
            "Tell me what special request you’d like us to note. That could be flowers, decor, timing, setup, or anything extra you have in mind."
        ),
        "ask_dietary_gate": (
            "Does anyone in the group have food needs or health needs we should know about, like allergies, diabetes, vegan, or gluten-free?"
        ),
        "collect_dietary_concerns": "Tell me the food or health needs you’d like us to note, and we’ll make sure they’re included.",
        "ask_additional_notes_gate": "Is there anything else you want us to remember before we finish everything up?",
        "collect_additional_notes": "Tell me any last note you want us to remember before we send this along.",
        "ask_followup_call": "Would you like us to schedule a quick call to go over everything together?",
        "review": "Here’s the summary so far. Does everything look correct to you?",
    }
    return prompts.get(target, "Is there anything else you want us to note?")


__all__ = ["render"]

"""Fallback prompt registry for guarded turns when natural generation is unavailable."""

from __future__ import annotations

import hashlib

PROMPT_REGISTRY_VERSION = "2026-04-20"


ROUTER_SYSTEM_PROMPT = (
    "You are the routing brain for a catering sales agent. "
    "Pick EXACTLY ONE tool to handle the user's latest message, or "
    "decide to clarify if you are uncertain.\n\n"
    "Tools:\n"
    "- basic_info_tool: name, email, phone, event type, event date, venue, "
    "guest count, service type, partner/company/honoree name.\n"
    "- menu_selection_tool: cocktail hour, appetizers, meal style, main dishes, "
    "desserts, custom menu.\n"
    "- add_ons_tool: drinks, bar service / package, coffee, tableware, utensils, "
    "linens, rentals, labor, travel fee.\n"
    "- modification_tool: the user is CHANGING / REMOVING / REPLACING a "
    "previously-filled slot (food, venue, date, guest count, etc).\n"
    "- finalization_tool: special requests, dietary concerns, additional notes, "
    "final confirmation / 'looks good, send it'.\n\n"
    "Routing rules:\n"
    "1. modification_tool ONLY when the user is EXPLICITLY changing a slot that is "
    "already in filled_slots (e.g. 'change my email to...', 'update the venue', 'remove that item'). "
    "A slot that has never been filled cannot be a modification - route to basic_info_tool instead.\n"
    "2. At S3_conditional phase, the user is providing partner_name / honoree_name / company_name "
    "for the FIRST time. Even if the message has 'no' in it (e.g. 'no no my partner is X'), "
    "route to basic_info_tool - this is not a modification.\n"
    "3. If the message is simple conversational filler or a short command "
    "('nice', 'ok', 'continue', 'sounds good', 'done', 'move on', 'proceed', "
    "'that works', 'show', 'show me', 'yes', 'sure', 'let's go', 'go ahead', "
    "'what are my options', 'see the menu', 'ok lets go'), "
    "route to the tool for the current_phase to ask the next question. "
    "3a. Single-word style answers ('passed', 'station', 'plated', 'buffet', "
    "'cocktail hour', 'reception', 'both', 'drop-off', 'onsite') during a "
    "menu phase (S9/S10/S11/S12) -> menu_selection_tool. During S4_service_type -> basic_info_tool.\n"
    "NEVER route these phrases to finalization_tool unless current_phase is already "
    "S16_special_requests, S17_dietary, or S19_review.\n"
    "4. Otherwise, pick the tool whose slots match the user's message + current_phase.\n"
    "5. action='clarify' only when you genuinely cannot tell what the user wants.\n"
    "6. Confidence must reflect your real certainty. Below 0.8 -> clarify.\n"
    "7. Return at most ONE entry in tool_calls."
)


def build_turn_signal_system_prompt(slot_names: list[str]) -> str:
    return (
        "You are extracting routing signals for a catering sales chat. "
        "Do NOT choose a tool directly. Classify the user's latest turn so code can "
        "apply the routing policy.\n\n"
        "Available intents:\n"
        "- answer_current_prompt: the user is answering the current question or directly selecting from the current step.\n"
        "- continue_current_flow: the user is saying continue / show options / move on / asking for the current step's options again.\n"
        "- modify_existing: the user is changing, removing, replacing, or undoing a specific previously captured answer or item.\n"
        "- reopen_previous_section: the user wants to go back to a prior menu/list section, re-pick from options, or see that section's options again without naming concrete item edits.\n"
        "- provide_other_information: the user is volunteering other booking information that is not just the current step and not clearly a modification.\n"
        "- unclear: you genuinely cannot tell.\n\n"
        f"Known slots: {', '.join(slot_names)}\n\n"
        "Rules:\n"
        "1. Use modify_existing only when the message is about changing or correcting something already captured or previously chosen.\n"
        "2. Use reopen_previous_section when the user says things like 'show me appetizers again', 'I want to reselect desserts', 'let's redo the mains', or otherwise wants to revisit a prior section rather than directly edit named items.\n"
        "3. For reopen_previous_section, set referenced_slot to the exact list slot when clear: appetizers, selected_dishes, desserts, or rentals.\n"
        "4. 'actually', 'wait', or 'instead' ALONE do not force modify_existing; use them only when the message is clearly changing prior information.\n"
        "5. If the user is simply continuing, asking to see current options, or answering the current phase naturally, prefer answer_current_prompt or continue_current_flow.\n"
        "6. If the user volunteers information from a different part of the intake flow (for example date + venue + rentals in one message), use provide_other_information.\n"
        "7. referenced_slot must be an exact slot name only when one slot is clearly the main subject.\n"
        "8. proposed_tool should be set only when the user is not simply answering the current step and you have a strong best-tool guess.\n"
        "9. Be conservative with unclear. If the current phase likely explains the message, prefer answer_current_prompt or continue_current_flow."
    )


RESPONSE_SYSTEM_PROMPT = (
    "You are a friendly catering sales coordinator having a natural conversation "
    "to help a customer book their event. Your job is to write the NEXT reply "
    "in the chat.\n\n"
    "Tone: warm, conversational, confident. Like texting a helpful friend who happens "
    "to be great at event planning - not filling out a corporate form. Short sentences. "
    "No jargon. No emojis.\n\n"
    "CRITICAL TONE RULES:\n"
    "- NEVER start a reply with 'Perfect.', 'Perfect!', 'Great.', 'Great!', 'Awesome!', "
    "'Got it!', 'Sweet!', 'Nice!', 'Wonderful!', 'Excellent!', or 'Noted.' These are "
    "robotic fillers that make every turn feel identical. If you need to acknowledge "
    "something, weave it into the next sentence naturally.\n"
    "- Use the customer's name very sparingly (maximum once or twice per conversation).\n"
    "- NEVER repeat the same question phrasing twice across the whole conversation. "
    "Rotate wording every turn.\n"
    "- Avoid generic scaffolding when a more specific, human sentence would sound better.\n"
    "- If the question is about a concrete decision, name that decision directly.\n"
    "- CRITICAL: When a slot was just filled and you are moving to the NEXT question, "
    "your acknowledgement MUST NOT include the words 'phone', 'mobile', 'number', "
    "'email', 'name' unless THOSE words belong to the new question.\n\n"
    "You will receive a JSON object with:\n"
    "  - user_message\n"
    "  - context\n"
    "  - conversation\n"
    "  - filled_slots\n"
    "  - missing_required\n"
    "  - key_slots\n\n"
    "USING THE CONTEXT:\n"
    "- Weave known slots into questions to feel personal, but ONLY when natural.\n"
    "- Never invent values not in filled_slots.\n"
    "- Don't re-ask anything already in filled_slots.\n"
    "- If context.menu_progress is present, treat it as factual guidance, not a script.\n"
    "- You will receive recent_assistant_replies. Avoid echoing their wording.\n"
    "- Any examples or suggested wording in the context are guidance, not a script. Do NOT copy them mechanically.\n"
    "- Stay natural in every phase of the flow, not just the early intake.\n"
    "- On late turns (high turn_count), skip pleasantries and get to the point.\n\n"
    "How to respond:\n"
    "1. If something was just filled, briefly acknowledge it, then immediately lead into the next thing.\n"
    "2. If nothing was filled, skip the acknowledgement and just ask the next question.\n"
    "3. Prefer 1-3 short sentences.\n"
    "4. For errors, ask a gentle clarifying question.\n"
    "5. For modifications, confirm what changed using context.modification as facts.\n"
    "6. For review, list what was booked in a short readable summary and ask if it looks right.\n"
    "7. When status=pending_staff_review, thank them and say the team will reach out.\n\n"
    "INPUT WIDGET RULES:\n"
    "  ask_name -> MUST contain 'your name' or 'first and last name'.\n"
    "  ask_email -> MUST contain 'email'.\n"
    "  ask_phone -> MUST contain 'phone' or 'number'.\n"
    "  ask_event_date -> MUST contain 'date' or 'when'.\n"
    "  ask_venue -> MUST contain 'venue' or 'where will' or 'where is' or 'location'.\n"
    "  ask_guest_count -> MUST contain 'how many guest', 'guest count', 'headcount', or 'expecting'.\n\n"
    "next_question_target tells you WHAT to collect. Phrase naturally - cards come from the system, not your words.\n\n"
    "OUTPUT CONTRACT:\n"
    "- Return your answer in the GeneratedReply schema.\n"
    "- Put the entire user-facing chat reply in reply_text.\n"
    "- Do not return analysis, notes, or multiple alternatives."
)


_BASIC_INFO_PROMPTS = {
    "ask_name": (
        "What is your first and last name?",
        "Can I get your first and last name?",
        "What should I put down as your full name?",
    ),
    "ask_event_type": (
        "What kind of event are you planning?",
        "What are we planning for - wedding, birthday, corporate, or something else?",
        "What type of event is this for?",
    ),
    "ask_partner_name": (
        "What is your partner's name?",
        "Who is your partner for the wedding?",
        "What name should I note for your partner?",
    ),
    "ask_company_name": (
        "What is the company or organization name?",
        "Which company or organization should I note for this event?",
        "What name should I use for the company or organization?",
    ),
    "ask_honoree_name": (
        "Who are we celebrating?",
        "Who is the event for?",
        "Whose celebration is this for?",
    ),
    "ask_wedding_cake": (
        "Would you like to include a wedding cake?",
        "Do you want to add a wedding cake?",
        "Should I include a wedding cake in the plan?",
    ),
    "ask_wedding_cake_flavor": (
        "What cake flavor would you like?",
        "Which cake flavor are you thinking for the wedding cake?",
        "What flavor should we use for the cake?",
    ),
    "ask_wedding_cake_filling": (
        "What filling would you like with it?",
        "Which filling should go with that cake flavor?",
        "What filling do you want inside the cake?",
    ),
    "ask_wedding_cake_buttercream": (
        "What buttercream frosting would you like?",
        "Which buttercream frosting should I note for the cake?",
        "What buttercream would you like on the cake?",
    ),
    "ask_service_type": (
        "Would you like drop-off delivery or full onsite service?",
        "Do you want drop-off service or a full onsite setup with staff?",
        "Should I note drop-off delivery or full onsite service?",
    ),
    "ask_event_date": (
        "What is the event date?",
        "When is the event?",
        "What date should I put down for the event?",
    ),
    "ask_venue": (
        "Where is the venue? If it is still TBD, you can say confirm venue on call.",
        "What venue should I note? If it is not locked in yet, you can say confirm venue on call.",
        "Where will the event be held? If the venue is still TBD, you can say confirm venue on call.",
    ),
    "ask_guest_count": (
        "About how many guests are you expecting?",
        "What guest count should I plan around?",
        "Roughly how many guests are you expecting?",
    ),
    "ask_email": (
        "What is the best email to reach you at?",
        "Which email should we use for updates?",
        "What email should I note for you?",
    ),
    "ask_phone": (
        "What is the best phone number to reach you at?",
        "Which phone number should I use for follow-up?",
        "What number is best if we need to reach you quickly?",
    ),
    "transition_to_menu": (
        "On to the menu. I will start with appetizers, then we will build the rest of the meal.",
        "Let's move to the menu. We will start with appetizers and build from there.",
        "Now for the menu. I will walk you through appetizers first, then the rest of the meal.",
    ),
}

_MENU_SELECTION_PROMPTS = {
    "ask_service_style": (
        "For the wedding, would you like cocktail hour, the reception meal, or both?",
        "Are you planning cocktail hour, the reception meal, or both for the wedding?",
        "Should I note cocktail hour, the reception meal, or both?",
    ),
    "show_appetizer_menu": (
        "Here are the appetizer options - pick as many as you want.",
        "Let's look at appetizers next - choose as many as you want.",
        "Here is the appetizer menu. Pick as many as you'd like.",
    ),
    "ask_appetizer_style": (
        "How would you like the appetizers served: passed around or set up at a station?",
        "Should the appetizers be passed around or served from a station?",
        "How should we serve the appetizers - passed or station?",
    ),
    "show_main_menu": (
        "Here is the main menu - pick 3 to 5 dishes.",
        "Let's look at the main menu next. Pick 3 to 5 dishes.",
        "Here are the main dish options. Choose 3 to 5.",
    ),
    "ask_meal_style": (
        "For the main meal, do you want it plated or buffet-style?",
        "Should the main meal be plated or buffet-style?",
        "How do you want the main meal served - plated or buffet?",
    ),
    "show_dessert_menu": (
        "Here are the dessert options - pick up to 4.",
        "Let's look at desserts next. You can choose up to 4.",
        "Here is the dessert menu. Pick up to 4 items.",
    ),
    "transition_to_addons": (
        "That menu looks good. Want to add drinks, bar service, or other extras?",
        "That takes care of the food. Want to move on to drinks and extras?",
        "The menu is in good shape. Should we look at drinks, bar service, or other add-ons next?",
    ),
}

_ADD_ONS_PROMPTS = {
    "ask_drinks_interest": (
        "Would you like to add drinks or bar service for the event?",
        "Do you want to include drinks or bar service?",
        "Should we add drinks, bar service, or both to the event?",
    ),
    "ask_drinks_setup": (
        "Would you like coffee service, bar service, both, or neither?",
        "For drinks, should I note coffee service, bar service, both, or neither?",
        "What beverage setup do you want - coffee service, bar service, both, or neither?",
    ),
    "ask_bar_package": (
        "Which bar package would you like?",
        "What bar package should I note for the event?",
        "Which bar package feels right for this event?",
    ),
    "ask_tableware_gate": (
        "Would you like standard tableware, an upgrade, or no tableware?",
        "For tableware, should I note standard, an upgrade, or none?",
        "What should I put down for tableware - standard, upgraded, or no tableware?",
    ),
    "ask_tableware": (
        "Which tableware upgrade would you like?",
        "What tableware upgrade should I note?",
        "Which upgraded tableware option do you want?",
    ),
    "ask_utensils": (
        "What utensils would you like to add?",
        "Which utensils should I include?",
        "What utensils should I note for the event?",
    ),
    "ask_linens": (
        "Would you like to include linens?",
        "Should I add linens to the plan?",
        "Do you want linens included?",
    ),
    "ask_rentals_gate": (
        "Do you need any rentals like linens, tables, or chairs?",
        "Should I add any rentals such as linens, tables, or chairs?",
        "Do you want to include rentals like linens, tables, or chairs?",
    ),
    "ask_rentals_items": (
        "Which rentals would you like to include?",
        "What rentals should I add?",
        "Which rental items should I note?",
    ),
    "ask_labor_services": (
        "Which service staff would you like us to handle? Select everything you need.",
        "Pick any event labor you want us to cover, and you can choose more than one.",
        "Which labor services should I include? Choose all that apply.",
    ),
    "transition_to_special_requests": (
        "Before we wrap up, do you have any special requests or notes?",
        "Before I finalize this, is there anything special you want us to note?",
        "Before we move to the last details, do you want to add any special requests or notes?",
    ),
}

_FINALIZATION_PROMPTS = {
    "ask_special_requests_gate": (
        "Do you have any special requests or anything extra you want us to keep in mind?",
        "Any special requests or extra details you want me to note?",
        "Is there anything special you want us to plan around or keep in mind?",
    ),
    "collect_special_requests": (
        "What special request would you like us to note?",
        "What should I write down as the special request?",
        "Tell me the special request in your own words and I will note it.",
    ),
    "ask_dietary_gate": (
        "Does anyone have dietary or health needs we should plan around?",
        "Should I note any dietary or health concerns for the event?",
        "Do any guests have dietary or health needs we should keep in mind?",
    ),
    "collect_dietary_concerns": (
        "What dietary or health needs should we plan around?",
        "What dietary or health concerns should I note?",
        "What food or health needs do you want included?",
    ),
    "ask_additional_notes_gate": (
        "Is there anything else you want us to note before we wrap up?",
        "Any final notes you want me to add before I wrap this up?",
        "Do you want me to include anything else before we finish?",
    ),
    "collect_additional_notes": (
        "What final note would you like us to include?",
        "What last note should I add?",
        "Tell me the final note you want included.",
    ),
    "ask_followup_call": (
        "Would you like a quick follow-up call to go over the final details?",
        "Do you want a quick follow-up call to review everything?",
        "Should I note that you want a follow-up call for the final details?",
    ),
    "review": (
        "Here is the summary so far - does everything look right?",
        "Here is the recap so far - does it all look correct?",
        "This is the summary I have so far - does everything look good?",
    ),
}


def _select_variant(options: tuple[str, ...], seed: str | None = None) -> str:
    if not options:
        return ""
    if not seed:
        return options[0]
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(options)
    return options[index]


def basic_info_prompt(target: str, seed: str | None = None) -> str:
    return _select_variant(_BASIC_INFO_PROMPTS.get(target, ("Could you tell me a bit more?",)), seed)


def menu_selection_prompt(target: str, seed: str | None = None) -> str:
    return _select_variant(_MENU_SELECTION_PROMPTS.get(target, ("What would you like to choose from the menu?",)), seed)


def add_ons_prompt(target: str, seed: str | None = None) -> str:
    return _select_variant(_ADD_ONS_PROMPTS.get(target, ("What would you like to add next?",)), seed)


def finalization_prompt(target: str, seed: str | None = None) -> str:
    return _select_variant(_FINALIZATION_PROMPTS.get(target, ("Is there anything else you want us to note?",)), seed)


def fallback_prompt_for_target(tool: str, target: str | None, seed: str | None = None) -> str:
    if not target:
        return ""

    if tool == "basic_info_tool":
        return basic_info_prompt(target, seed)
    if tool == "menu_selection_tool":
        return menu_selection_prompt(target, seed)
    if tool == "add_ons_tool":
        return add_ons_prompt(target, seed)
    if tool == "finalization_tool":
        return finalization_prompt(target, seed)
    if target in _BASIC_INFO_PROMPTS:
        return basic_info_prompt(target, seed)
    if target in _MENU_SELECTION_PROMPTS:
        return menu_selection_prompt(target, seed)
    if target in _ADD_ONS_PROMPTS:
        return add_ons_prompt(target, seed)
    if target in _FINALIZATION_PROMPTS:
        return finalization_prompt(target, seed)
    return ""


def prompt_for_target(tool: str, target: str | None, seed: str | None = None) -> str:
    """Backward-compatible alias for the fallback registry."""
    return fallback_prompt_for_target(tool, target, seed)


__all__ = [
    "PROMPT_REGISTRY_VERSION",
    "ROUTER_SYSTEM_PROMPT",
    "RESPONSE_SYSTEM_PROMPT",
    "build_turn_signal_system_prompt",
    "basic_info_prompt",
    "menu_selection_prompt",
    "add_ons_prompt",
    "finalization_prompt",
    "fallback_prompt_for_target",
    "prompt_for_target",
]

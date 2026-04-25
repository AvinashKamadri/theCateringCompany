"""Fallback prompt registry for guarded turns when natural generation is unavailable."""

from __future__ import annotations

import hashlib

PROMPT_REGISTRY_VERSION = "2026-04-22-v2"


# --------------------------------------------------------------------------
# Shared preamble — prepended to every system prompt so that the combined
# `instructions` field passed to the OpenAI Responses API exceeds the 1024-
# token prompt-caching threshold. Contents are deliberately stable across
# turns; dynamic state (slots, phase, history) goes in the `input` payload,
# never here. Keep this block append-only: edits invalidate every cached
# prefix and force a full prompt re-bill on the next turn.
# --------------------------------------------------------------------------
AGENT_PREAMBLE = (
    "CATERING SALES INTAKE AGENT — SHARED CONTEXT\n"
    "=============================================\n\n"
    "You are one component of a multi-stage intake agent that helps a customer "
    "book a catering event through a web chat. Each customer turn is processed "
    "by three sequential stages:\n"
    "  1. Router — picks exactly one Tool to handle the turn.\n"
    "  2. Tool — proposes structured facts (slot fills, modifications, pricing).\n"
    "  3. Response Generator — writes the user-facing reply from those facts.\n\n"
    "You may be any one of these stages; your specific role is defined after "
    "this preamble. Shared conventions below apply in every role.\n\n"
    "CONVERSATION PHASES (stored as `current_node` in the DB)\n"
    "--------------------------------------------------------\n"
    "Intake phases run in this order, though the customer can revisit any phase "
    "via modifications at any time:\n"
    "  S1_greeting          — name, email, phone\n"
    "  S2_event_type        — wedding, birthday, corporate, other\n"
    "  S3_conditional       — partner_name / company_name / honoree_name\n"
    "  S4_transition        — hand-off into menu selection\n"
    "  S5_cocktail          — cocktail hour gate + appetizers + appetizer style\n"
    "  S6_main_menu         — main dishes + meal style\n"
    "  S7_dessert           — dessert gate + items\n"
    "  S8_wedding_cake      — cake gate + flavor + filling + buttercream (weddings only); skippable\n"
    "  S9_event_date        — calendar date; skippable\n"
    "  S10_venue            — venue name / address, or TBD placeholder; skippable\n"
    "  S11_guest_count      — integer or TBD placeholder; skippable\n"
    "  S12_service_type     — onsite vs drop-off; skippable\n"
    "  S13_drinks_bar       — drinks interest, coffee, bar package\n"
    "  S14_tableware        — tableware gate + utensils\n"
    "  S15_rentals          — rentals gate + linens\n"
    "  S16_labor            — onsite labor services\n"
    "  S17_special_requests — free-text notes\n"
    "  S18_dietary          — dietary concerns\n"
    "  S19_followup / review — followup call gate + final confirmation\n"
    "  complete             — intake done, pending_staff_review\n\n"
    "TOOL CATALOG\n"
    "------------\n"
    "  basic_info_tool     — owns name, email, phone, event_type, partner/company/honoree name, "
    "service_type, event_date, venue, guest_count, and the wedding cake flow.\n"
    "  menu_selection_tool — owns cocktail_hour, appetizers, appetizer_style, selected_dishes, "
    "meal_style, desserts, custom_menu.\n"
    "  add_ons_tool        — owns drinks, bar_service, bar_package, coffee_service, tableware, "
    "utensils, linens, rentals, labor services, bartender.\n"
    "  modification_tool   — handles any intent to change, remove, undo, or add to something already "
    "captured OR already past in the flow (including sections that were skipped). "
    "First-time answers to the current question go to the owning tool, not here.\n"
    "  finalization_tool   — owns special_requests, dietary_concerns, additional_notes, "
    "followup_call, and the final review. Setting `conversation_status = pending_staff_review` "
    "is exclusive to this tool.\n\n"
    "STATE MODEL\n"
    "-----------\n"
    "Slots live in a dict keyed by slot name; each entry has `{value, filled: bool}`. Public "
    "slots are customer-visible facts (name, menu, pricing inputs). Internal slots are prefixed "
    "with `__` and track UI/flow state (e.g. `__wedding_cake_gate`, `__pending_modification_choice`).\n"
    "`conversation_status` has three lifecycle values: active → pending_staff_review → contract_sent. "
    "Only finalization_tool may transition to pending_staff_review. Nothing else in the pipeline — "
    "router, tools, or response text — should treat a partial TBD answer as an end-of-flow signal.\n\n"
    "CORE CONVENTIONS\n"
    "----------------\n"
    "- Exactly ONE tool runs per turn. Never fan out.\n"
    "- Modifications only apply to filled slots; first-time fills go to the owning tool.\n"
    "- When a user picks TBD / 'confirm on call' / 'skip' for a single field, we record the "
    "placeholder and continue the intake. That choice never ends the conversation.\n"
    "- Output is always structured per the schema; never return free-form JSON outside the schema.\n"
    "=============================================\n\n"
)


ROUTER_SYSTEM_PROMPT = AGENT_PREAMBLE + (
    "# Role\n"
    "You are the intent-first router for a catering sales agent. "
    "Pick EXACTLY ONE tool based on what the user MEANS — not the words they use. "
    "Real customers speak casually: 'mb', 'oh wait', 'nah', 'hold on', 'actually', "
    "'wait no', 'sorry', 'i meant', 'can we change' all signal the same correction intent. "
    "Choose action='clarify' only when you genuinely cannot tell.\n\n"
    "# Tools\n"
    "- basic_info_tool: identity, event type/date/venue/guest count/service type, wedding cake flow.\n"
    "- menu_selection_tool: cocktail hour, appetizers, main dishes, meal style, desserts.\n"
    "- add_ons_tool: drinks, bar, coffee, tableware, utensils, linens, rentals, labor.\n"
    "- modification_tool: any intent to CHANGE, UNDO, REMOVE, or ADD TO a section already visited. "
    "Includes late-flow additions ('add bar', 'add coffee station' during review/finalization). "
    "Also includes contradicting a filled slot ('it's a birthday not a wedding').\n"
    "- finalization_tool: special requests, dietary, followup call, final confirmation.\n\n"
    "# Core Routing Principles\n"
    "P1 INTENT OVER PHASE: current_phase tells you where the flow is, not what the user means. "
    "A user can correct event_type during S16_labor. Route by intent, not phase.\n\n"
    "P2 CONTRADICTION = MODIFICATION: If the user's message contradicts or overrides something "
    "already in filled_slots — even casually ('mb it's a birthday', 'wait no my date is may 5th', "
    "'nah skip the cake') — that is ALWAYS modification_tool, regardless of current_phase.\n\n"
    "P3 LATE ADDITIONS = MODIFICATION: If the user wants to ADD something (bar, coffee, appetizers, "
    "a dish) to a section already completed or skipped, that is modification_tool. The slot does "
    "not need to be currently filled — 'can we add bar?' in S19_review is a modification intent.\n\n"
    "P4 FIRST-TIME FILL = OWNING TOOL: Answering the current question for the FIRST time is "
    "never a modification. Short structured answers ('plated', 'buffet', 'drop-off', 'onsite', "
    "'no drinks') go to the phase owner. Filler words ('ok', 'sure', 'continue', 'move on', "
    "'show me options') also go to the phase owner.\n\n"
    "P5 CONTEXT DISAMBIGUATION: 'drop-off' = service delivery method → basic_info_tool. "
    "'drop the cake' with wedding_cake in filled_slots = removal → modification_tool. "
    "Use context and filled_slots to disambiguate, not just the word.\n\n"
    "P6 CONFIDENCE: If you are not confident (below 0.8), choose action='clarify'. "
    "Return at most ONE entry in tool_calls.\n\n"
    "# Examples — diverse edge cases only\n"
    "1. Context: current_phase=S3b_wedding_cake. filled_slots: event_type=Wedding. "
    "User: 'hey mb it is a birthday actually'\n"
    "   → modification_tool (contradicts filled event_type, even with casual language)\n"
    "2. Context: current_phase=S4_service_type. filled_slots: wedding_cake=Vanilla. "
    "User: 'wait can we drop the cake'\n"
    "   → modification_tool (removing filled wedding_cake — 'drop' is removal here, not drop-off)\n"
    "3. Context: current_phase=S4_service_type. User: 'drop-off'\n"
    "   → basic_info_tool (answering current service_type question — no filled slot contradicted)\n"
    "4. Context: current_phase=S19_review. User: 'can we add a coffee station'\n"
    "   → modification_tool (adding to past add-ons section)\n"
    "5. Context: current_phase=S11_main_menu. User: 'plated'\n"
    "   → menu_selection_tool (answering current meal_style question)\n"
    "6. Context: current_phase=S19_review. User: 'looks good send it'\n"
    "   → finalization_tool (final confirmation intent)\n"
)


def build_turn_signal_system_prompt(slot_names: list[str]) -> str:
    return AGENT_PREAMBLE + (
        "# Role\n"
        "You extract routing SIGNALS for a catering sales chat. You do NOT choose a tool directly — "
        "you classify the user's intent so routing code can apply policy. "
        "Real users speak casually: 'mb', 'oh wait', 'nah', 'hold on', 'sorry', 'i meant', "
        "'wait no', 'actually', 'can we change' all express the same correction intent. "
        "Classify by MEANING, not by exact words.\n\n"
        "# STEP 1 — Reason first (key_indicators)\n"
        "Before choosing an intent, list 2-4 brief observations about the message:\n"
        "  - What did the user say or imply?\n"
        "  - Does it contradict or override anything in filled_slots?\n"
        "  - Is it answering the current phase question or going off-script?\n"
        "  - Does it reference a section already completed/skipped?\n"
        "Write these in key_indicators BEFORE setting intent. This prevents mis-classification.\n\n"
        "# STEP 2 — Choose intent\n"
        "- answer_current_prompt: user is directly answering the question the agent just asked, "
        "for the FIRST time. Short answers ('plated', 'buffet', 'drop-off', 'no drinks', '50 guests') "
        "during the matching phase belong here.\n"
        "- continue_current_flow: user says 'ok', 'sure', 'continue', 'move on', 'show options', "
        "or any conversational nudge to advance without providing new information.\n"
        "- modify_existing: user intends to CHANGE, UNDO, REMOVE, OVERRIDE, or ADD TO something "
        "already captured or already past in the flow. This is the right intent when:\n"
        "  (a) the message contradicts a filled_slot value ('mb it's actually a birthday'),\n"
        "  (b) the user wants to delete/remove something ('skip the cake', 'nah no desserts'),\n"
        "  (c) the user wants to add something to a section already completed ('add bar in menu'),\n"
        "  (d) the user is correcting a prior answer, even without explicit correction words.\n"
        "  Key signal: would accepting this message override or extend something already recorded?\n"
        "- reopen_previous_section: user wants to browse or re-pick from a prior category, "
        "without naming a specific item to change ('show me desserts again', 'redo the mains').\n"
        "- provide_other_information: user volunteers booking info for a DIFFERENT part of the flow "
        "(e.g. gives event_date during a menu phase) and it does NOT contradict anything filled.\n"
        "- unclear: you genuinely cannot determine what the user wants after reasoning.\n\n"
        f"Known slots: {', '.join(slot_names)}\n\n"
        "# Principles\n"
        "- CONTRADICTION WINS: if the message contradicts filled_slots, always classify as modify_existing.\n"
        "- LATE ADDITION WINS: if the user wants something added to a past/skipped section, always modify_existing.\n"
        "- CONTEXT DISAMBIGUATES WORDS: 'drop-off' during S4_service_type = service type answer. "
        "'drop the cake' with wedding_cake in filled_slots = removal modification.\n"
        "- referenced_slot: exact slot name only when the message clearly targets one slot. "
        "For reopen_previous_section, use the list slot: appetizers, selected_dishes, desserts, rentals.\n"
        "- proposed_tool: set only when you have a confident best-tool guess; otherwise null.\n"
        "- reason: one sentence explaining the classification.\n\n"
        "# Examples — diverse edge cases\n"
        "1. current_phase=S3b_wedding_cake. filled_slots: event_type=Wedding. "
        "User: 'hey mb it is a birthday actually'\n"
        "   key_indicators: ['user said mb (my bad)', 'event_type=Wedding already filled', "
        "'message contradicts prior event type', 'soft correction language + new event type']\n"
        "   intent='modify_existing', referenced_slot='event_type', confidence=0.93\n\n"
        "2. current_phase=S4_service_type. filled_slots: wedding_cake=Vanilla. "
        "User: 'wait can we drop the cake'\n"
        "   key_indicators: ['wedding_cake already filled', 'drop = remove in this context', "
        "'not answering service_type', 'references a filled slot for removal']\n"
        "   intent='modify_existing', referenced_slot='wedding_cake', proposed_tool='modification_tool', confidence=0.92\n\n"
        "3. current_phase=S4_service_type. User: 'drop-off'\n"
        "   key_indicators: ['current phase is service_type', 'drop-off is a valid service_type value', "
        "'no filled slots contradicted', 'direct answer to current question']\n"
        "   intent='answer_current_prompt', referenced_slot='service_type', proposed_tool='basic_info_tool', confidence=0.96\n\n"
        "4. current_phase=S19_review. User: 'can we add a coffee station'\n"
        "   key_indicators: ['in review phase, drinks section already past', 'user wants to add coffee', "
        "'coffee_service not currently filled but section is closed', 'this extends a past section']\n"
        "   intent='modify_existing', referenced_slot='coffee_service', proposed_tool='modification_tool', confidence=0.90\n\n"
        "5. current_phase=S11_main_menu. User: 'show me desserts'\n"
        "   key_indicators: ['current phase is mains', 'user asking about desserts', "
        "'no specific item to change — wants to browse', 'desserts section not started yet']\n"
        "   intent='reopen_previous_section', referenced_slot='desserts', confidence=0.88\n"
    )


RESPONSE_SYSTEM_PROMPT = AGENT_PREAMBLE + (
    "You are a friendly catering sales coordinator having a natural conversation "
    "to help a customer book their event. Your job is to write the NEXT reply "
    "in the chat.\n\n"
    "Tone: warm, conversational, confident. Like texting a helpful friend who happens "
    "to be great at event planning - not filling out a corporate form. Short sentences. "
    "No jargon.\n\n"
    "TONE MIRRORING: the user's turn comes with a `tone_profile` and `tone_guidance` "
    "field. Mirror the customer's vibe using that guidance — formal users get polished "
    "sentences, casual users get a friendly conversational feel, funky users get a "
    "relaxed energetic register with light slang. Never invent facts to sound cool. "
    "Default to no emoji unless tone_guidance explicitly allows one.\n\n"
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
    "2a. CRITICAL: when `nothing_was_captured` is true, do NOT claim anything was saved, "
    "locked in, noted, or updated. The user's message did not fit the current question. "
    "Politely re-ask the next_question_target — do not fabricate a confirmation.\n"
    "3. Prefer 1-3 short sentences.\n"
    "4. For errors, ask a gentle clarifying question.\n"
    "5. For modifications, confirm what changed using context.modification as facts.\n"
    "6. For review, list what was booked in a short readable summary and ask if it looks right.\n"
    "7. When status=pending_staff_review, thank them and say the team will reach out.\n"
    "8. CRITICAL WRAP-UP RULE: do NOT end the conversation, say 'we'll be in touch', "
    "'hear from our office', 'reach out', '24-48 hours', 'all set', 'make your event a "
    "success', or any other closing language unless conversation.status == "
    "'pending_staff_review'. If next_question_target is set, you MUST ask that question. "
    "A customer choosing 'TBD' or 'confirm on call' for a single field (like venue or "
    "guest count) is NOT a signal to wrap up — keep the intake going.\n\n"
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
    "ask_other_event_type": (
        "Please specify what kind of event it is (or say confirm on call).",
        "What kind of event is it? You can also say confirm on call.",
        "What should I label the event as? (Or say confirm on call.)",
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
        "Would you like drop-off delivery or full onsite service? (Reply drop-off or onsite.)",
        "Do you want drop-off or onsite service? (Reply drop-off or onsite.)",
        "Service: drop-off or onsite? (Reply drop-off or onsite.)",
    ),
    "ask_event_date": (
        "What date should I put down for the event? (Future date please.)",
        "What is the event date? (Future date â€” YYYY-MM-DD works.)",
        "When is the event? (Future date please.)",
    ),
    "ask_venue": (
        "Where is the venue? If it is still TBD, you can say confirm venue on call.",
        "What venue should I note? If it is not locked in yet, you can say confirm venue on call.",
        "Where will the event be held? If the venue is still TBD, you can say confirm venue on call.",
    ),
    "ask_guest_count": (
        "About how many guests are you expecting? (If TBD, you can say TBD.)",
        "What guest count should I plan around? (Number, or say TBD.)",
        "Roughly how many guests are you expecting? (If TBD, say TBD.)",
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
    # BasicInfoTool uses this target name when it has finished collecting the
    # required basics and is handing off to add-ons.
    "transition_to_addons": (
        "Water and lemonades are on us! Would you like to add coffee or bar service? (yes or no)",
        "Heads up — water and lemonades are already included. Should I add coffee or bar service on top? (yes or no)",
        "Just so you know, water and lemonades are covered. Want to add coffee or bar service? (yes or no)",
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
        "How should we serve the appetizers - passed or station?",
        "Appetizer setup: passed or station?",
        "Do you want the appetizers passed around or set up at a station?",
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
    "ask_dessert_gate": (
        "Would you like to add desserts, or skip them?",
        "Do you want to include desserts, or skip them for this event?",
        "Should I add desserts to the menu, or would you rather skip them?",
    ),
    "transition_to_addons": (
        "That menu looks good. Want to add drinks, bar service, or other extras?",
        "That takes care of the food. Want to move on to drinks and extras?",
        "The menu is in good shape. Should we look at drinks, bar service, or other add-ons next?",
    ),
}

_ADD_ONS_PROMPTS = {
    "ask_drinks_interest": (
        "Water and lemonades are on us! Would you like to add coffee service or bar service? (yes or no)",
        "Heads up — water and lemonades are already included. Would you like to add coffee or bar service on top of that? (yes or no)",
        "Just so you know, water and lemonades are covered! Should I add coffee or bar service as well? (yes or no)",
    ),
    "ask_drinks_setup": (
        "For drinks, do you want coffee service, bar service, both, or neither?",
        "Should I note coffee service, bar service, both, or neither?",
        "Coffee service, bar service, both, or neither?",
    ),
    "ask_bar_package": (
        "Which bar package do you want: beer & wine, beer/wine + 2 signature drinks, or full open bar?",
        "What bar package should I note: beer & wine, beer/wine + 2 signature drinks, or full open bar?",
        "Bar package: beer & wine, beer/wine + 2 signature drinks, or full open bar?",
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
        "Do you need any onsite help like ceremony setup, table setup/preset, cleanup, or trash removal? Choose all that apply.",
        "Which labor/services should we cover onsite (setup, preset, cleanup, trash)? Choose all that apply.",
        "What onsite labor should I include (ceremony setup, table setup, cleanup, trash removal)? Choose all that apply.",
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
    return _select_variant(_BASIC_INFO_PROMPTS.get(target, ("Could you clarify that a bit?",)), seed)


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

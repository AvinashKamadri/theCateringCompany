"""
Shared helper utilities for conversation nodes.
Includes AI generation audit logging on every LLM call.
"""

import os
import re
import time
import logging
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.llm import llm

logger = logging.getLogger(__name__)

# Project ID is set per-conversation by the orchestrator
_current_project_id: str | None = None


def set_current_project_id(project_id: str | None):
    """Set the project ID for AI generation logging in this conversation turn."""
    global _current_project_id
    _current_project_id = project_id


def get_last_human_message(messages) -> str:
    """Extract the last human message content from message list."""
    for msg in reversed(list(messages)):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def is_affirmative(text: str) -> bool:
    """Check if user response is affirmative (yes). Uses word boundaries."""
    t = text.strip().lower()
    # Check negative FIRST — if it contains "no" it's not affirmative
    if re.search(r'\bno\b', t):
        return False
    patterns = [
        # Classic yes words
        r'\byes\b', r'\byeah\b', r'\byep\b', r'\byea\b', r'\bya\b',
        r'\byessir\b', r'\byes sir\b', r'\bhell yeah\b', r'\bheck yeah\b',
        r'\bsure\b', r'\bok\b', r'\bokay\b', r'\bplease\b',
        r'\bdefinitely\b', r'\babsolutely\b', r'\bof course\b',
        r'\bwhy not\b', r'\bfor sure\b',
        # "sounds good/great/fine/perfect"
        r'\bsounds (good|great|fine|perfect|amazing|awesome|wonderful)\b',
        # "looks good/great/fine/perfect" (e.g. "looks good for me")
        r'\blooks (good|great|fine|perfect|amazing|awesome|wonderful)\b',
        # "that's/that works/that's good/fine"
        r'\bthat(\'?s)? (good|great|fine|perfect|works|correct|right)\b',
        # "let's go / let's do it / let's proceed"
        r'\blet\'?s (go|do it|proceed|continue|start|begin)\b',
        r'\blets (go|do it|proceed|continue|start|begin)\b',
        # "go ahead / proceed"
        r'\bgo ahead\b', r'\bproceed\b',
        # "i would / i do / i'd like / i'd love / i want"
        r'\bi would\b', r'\bi do\b', r'\bi\'?d (like|love|want)\b', r'\bi want\b',
        # "bring it on / show me / love to"
        r'\bbring it on\b', r'\bshow me\b', r'\blove to\b',
        # "count me in / i'm in / i'm interested"
        r'\bcount me in\b', r'\bi\'?m in\b', r'\bi\'?m interested\b',
        # "for sure / totally / exactly / correct / right"
        r'\bfor sure\b', r'\btotally\b', r'\bexactly\b', r'\bcorrect\b',
        # "happy with / good with / fine with / cool with"
        r'\b(happy|good|fine|cool) with\b',
        # "that\'s final / yes that\'s it / that\'s all I need"
        r'\bthat\'?s (it|all|final|my final)\b',
    ]
    return any(re.search(p, t) for p in patterns)


def is_negative(text: str) -> bool:
    """Check if user response is negative (no). Uses word boundaries."""
    t = text.strip().lower()
    patterns = [
        # Classic no words
        r'\bno\b', r'\bnah\b', r'\bnope\b', r'\bnone\b',
        r'\bskip\b', r'\bpass\b', r'\bnegative\b',
        # "no thanks / no need / not really"
        r'\bno\s+thanks\b', r'\bno\s+need\b', r'\bnot\s+really\b',
        # "i'm good / im good" (declining)
        r'\bi\'?m\s+good\b', r'\bim\s+good\b',
        # "that's all / thats all / that's it / thats it"
        r'\bthat\'?s\s+all\b', r'\bthats\s+all\b',
        r'\bthat\'?s\s+it\b', r'\bthats\s+it\b',
        # "don't need / dont need / not needed"
        r'\bdon\'?t\s+need\b', r'\bnot\s+needed\b',
        # "not interested / not right now"
        r'\bnot\s+interested\b', r'\bnot\s+right\s+now\b',
        # "forget it / skip it / skip that"
        r'\bforget\s+it\b', r'\bskip\s+it\b', r'\bskip\s+that\b',
        # "i'll pass / pass on that"
        r'\bi\'?ll\s+pass\b', r'\bpass\s+on\s+that\b',
        # "without / not for me"
        r'\bnot\s+for\s+me\b',
    ]
    return any(re.search(p, t) for p in patterns)


async def _log_generation(system_prompt: str, user_message: str, response_text: str,
                          latency_ms: int, entity_type: str = "intake_parse"):
    """Log an AI generation call to the ai_generations audit table."""
    try:
        from database.db_manager import log_ai_generation
        await log_ai_generation(
            entity_type=entity_type,
            model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            project_id=_current_project_id,
            input_summary={
                "system_prompt_length": len(system_prompt),
                "user_message_preview": user_message[:200],
            },
            output=response_text[:2000],
            latency_ms=latency_ms,
            was_applied=True,
        )
    except Exception as e:
        logger.warning(f"Failed to log AI generation: {e}")


def normalize_item_name(name: str) -> str:
    """Strip price annotations for dedup: 'Chicken Satay ($3.50/pp)' → 'chicken satay'"""
    return re.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', name).strip().lower()


async def llm_extract(system_prompt: str, user_message: str) -> str:
    """Call LLM with a system prompt and user message, return response text."""
    start = time.monotonic()
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])
    latency_ms = int((time.monotonic() - start) * 1000)
    text = response.content
    await _log_generation(system_prompt, user_message, text, latency_ms, "intake_parse")
    return text


async def llm_respond(system_prompt: str, context: str) -> str:
    """Generate a friendly agent response given context.

    Automatically injects a slot-authority instruction so the LLM always
    uses CURRENT slot values over stale conversation history (important
    after @AI modifications change a slot mid-flow).

    Also injects a random variation seed so the LLM varies phrasing
    across conversations even at temperature=0.
    """
    import random
    _STYLES = [
        "Start with a short acknowledgment, then ask the question.",
        "Lead with the question directly, keep it punchy.",
        "Use a casual transition word first (like 'Alright', 'So', 'Cool'), then the question.",
        "Acknowledge what they said warmly, then move to the next thing.",
        "Keep it super brief — one short sentence max before the question.",
        "Be a little playful in tone, but still professional.",
        "Use a dash or em-dash mid-sentence for a natural texting feel.",
    ]
    style = random.choice(_STYLES)
    variation = (
        f"\n\nRESPONSE STYLE FOR THIS MESSAGE: {style} "
        "Do NOT copy this instruction literally — just let it influence your phrasing."
    )
    slot_authority = (
        "\n\nCRITICAL: Always use the CURRENT slot/event values provided in the context below, "
        "NOT what was discussed earlier in the conversation. If a value was modified mid-conversation "
        "(e.g., event type changed from Wedding to Birthday), respond based on the CURRENT value only."
    )
    start = time.monotonic()
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt + variation + slot_authority),
        HumanMessage(content=context),
    ])
    latency_ms = int((time.monotonic() - start) * 1000)
    text = response.content
    await _log_generation(system_prompt, context, text, latency_ms, "intake_parse")
    return text


def add_ai_message(state: dict, content: str) -> list:
    """Append an AI message to the state's message list and return new list."""
    return list(state["messages"]) + [AIMessage(content=content)]

"""
Shared helper utilities for conversation nodes.
Includes AI generation audit logging on every LLM call.
"""

import os
import re
import time
import logging
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from agent.llm import llm_cold, llm_warm

logger = logging.getLogger(__name__)

# Project ID is set per-conversation by the orchestrator
_current_project_id: str | None = None

# Conversation messages — set once per turn so llm_respond has full history automatically
_current_messages: list = []


def set_current_project_id(project_id: str | None):
    """Set the project ID for AI generation logging in this conversation turn."""
    global _current_project_id
    _current_project_id = project_id


def set_current_messages(messages: list):
    """Set the conversation messages for this turn so all llm_respond calls get history."""
    global _current_messages
    _current_messages = list(messages) if messages else []


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


def build_numbered_list(items: list[dict], show_price: bool = True, category_headers: bool = False,
                        categories: dict | None = None) -> str:
    """Build a numbered list from DB items in Python — never let the LLM render this.

    Args:
        items: flat list of {"name": ..., "unit_price": ..., "price_type": ...}
        show_price: whether to show prices
        category_headers: whether to group by category
        categories: dict of {category_name: [items]} if category_headers=True
    """
    lines = []
    num = 1

    if category_headers and categories:
        # Group by section so items under same section share one bold header
        current_section = None
        for cat_name, cat_items in categories.items():
            section = cat_items[0].get("section", "") if cat_items else ""
            group = cat_items[0].get("category", cat_name) if cat_items else cat_name

            if section and section != group:
                # Multi-group section (e.g. "Hors D'oeuvres" > "Chicken")
                if section != current_section:
                    lines.append(f"\n**{section}**")
                    current_section = section
                lines.append(f"*{group}*")
            else:
                # Single section = category (e.g. "Signature Combinations")
                lines.append(f"\n**{cat_name}**")
                current_section = cat_name

            for item in cat_items:
                price = ""
                if show_price and item.get("unit_price"):
                    pt = item.get("price_type", "per_person")
                    price = f" (${item['unit_price']:.2f}/{pt})" if pt != "flat" else f" (${item['unit_price']:.2f})"
                lines.append(f"{num}. {item['name']}{price}")
                num += 1
    else:
        for item in items:
            price = ""
            if show_price and item.get("unit_price"):
                pt = item.get("price_type", "per_person")
                price = f" (${item['unit_price']:.2f})" if pt == "flat" else f" (${item['unit_price']:.2f}/{pt})"
            lines.append(f"{num}. {item['name']}{price}")
            num += 1

    return "\n".join(lines)


def normalize_item_name(name: str) -> str:
    """Strip price annotations for dedup: 'Chicken Satay ($3.50/pp)' → 'chicken satay'"""
    return re.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', name).strip().lower()


async def llm_extract(system_prompt: str, user_message: str) -> str:
    """Deterministic extraction — intent classification, JSON parsing, slot filling.

    Uses temperature=0.0 (llm_cold). Always returns structured, predictable output.
    Never use this to generate conversational messages.
    """
    start = time.monotonic()
    response = await llm_cold.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])
    latency_ms = int((time.monotonic() - start) * 1000)
    text = response.content
    await _log_generation(system_prompt, user_message, text, latency_ms, "intake_parse")
    return text


def _format_history(messages: list, n: int = 12) -> str:
    """Format the last N conversation messages as a compact history string."""
    pool = list(messages)[-n:]
    lines = []
    for m in pool:
        if isinstance(m, HumanMessage):
            lines.append(f"Customer: {m.content}")
        elif isinstance(m, AIMessage):
            content = m.content[:200] + "…" if len(m.content) > 200 else m.content
            lines.append(f"Agent: {content}")
    return "\n".join(lines)


async def llm_respond(system_prompt: str, context: str, messages: list | None = None) -> str:
    """Conversational response generation — friendly messages, questions, acknowledgments.

    Two layers of variation to keep the bot feeling natural:
    1. temperature=0.7 (llm_warm) — model-level token sampling variation
    2. Random style seed — structural variation (acknowledgment-first vs question-first, etc.)

    Also injects slot-authority so the LLM always uses CURRENT slot values
    over stale conversation history (important after @AI mid-flow modifications).
    Never use this for extraction or intent classification.

    Pass `messages=state["messages"]` to include recent conversation history so the LLM
    has full context when generating the next response.
    """
    import random
    _STYLES = [
        "Warm and encouraging — like a friend who's genuinely excited to help.",
        "Upbeat and punchy — short, confident, zero fluff.",
        "Chill and laid-back — the kind of person who makes everything feel easy.",
        "Enthusiastic but grounded — real energy, not over-the-top.",
        "Natural and flowing — sounds like someone mid-conversation, not scripted.",
        "Dry wit, friendly — a little understated humor in the phrasing.",
        "Breezy and light — effortless, like they've done this a hundred times.",
    ]
    style = random.choice(_STYLES)
    variation = (
        f"\n\nTONE FOR THIS MESSAGE: {style} "
        "Let this energy come through naturally in your word choice — don't state it or reference it."
    )
    slot_authority = (
        "\n\nCRITICAL: Always use the CURRENT slot/event values provided in the context below, "
        "NOT what was discussed earlier in the conversation. If a value was modified mid-conversation "
        "(e.g., event type changed from Wedding to Birthday), respond based on the CURRENT value only."
        "\n\nSTEP DISCIPLINE (non-negotiable): "
        "Your ONLY job is to phrase the exact question/confirmation described in the instruction above. "
        "NEVER invent a new question. NEVER ask about a topic that wasn't explicitly requested in the "
        "instruction (do not ask about date, venue, guests, desserts, etc. unless the instruction says to). "
        "NEVER advance the conversation to a new step on your own — the Python controller decides flow. "
        "If the instruction says re-ask for X, you ONLY re-ask for X and nothing else."
    )
    msg_list = messages if messages is not None else _current_messages
    if msg_list:
        history = _format_history(msg_list)
        full_context = f"Recent conversation:\n{history}\n\n{context}"
    else:
        full_context = context

    start = time.monotonic()
    response = await llm_warm.ainvoke([
        SystemMessage(content=system_prompt + variation + slot_authority),
        HumanMessage(content=full_context),
    ])
    latency_ms = int((time.monotonic() - start) * 1000)
    text = response.content
    await _log_generation(system_prompt, full_context, text, latency_ms, "intake_parse")
    return text


def norm_llm(text: str) -> str:
    """Normalize a short LLM classification output: strip whitespace, lowercase,
    strip surrounding punctuation/markdown. Use for `Return ONLY: X or Y` prompts."""
    if not text:
        return ""
    t = text.strip().lower()
    t = re.sub(r'^["\'\*`]+|["\'\*`.!?]+$', '', t).strip()
    return t


def add_ai_message(state: dict, content: str) -> list:
    """Append an AI message to the state's message list and return new list."""
    return list(state["messages"]) + [AIMessage(content=content)]

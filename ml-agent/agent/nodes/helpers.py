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
    # Check negative FIRST - if it starts with "no" it's not affirmative
    if re.search(r'\bno\b', t):
        return False
    patterns = [
        r'\byes\b', r'\byeah\b', r'\byep\b', r'\bsure\b', r'\bok\b', r'\bokay\b',
        r'\bplease\b', r'\bdefinitely\b', r'\babsolutely\b', r'\bof course\b',
        r'\byea\b', r'\bya\b', r'\bwhy not\b', r'\bsounds good\b',
        r'\bi would\b', r'\bi do\b', r'\bi\'d like\b',
    ]
    return any(re.search(p, t) for p in patterns)


def is_negative(text: str) -> bool:
    """Check if user response is negative (no). Uses word boundaries."""
    t = text.strip().lower()
    patterns = [
        r'\bno\b', r'\bnah\b', r'\bnope\b', r'\bnone\b', r'\bskip\b', r'\bpass\b',
        r"i'm good", r"im good", r"no thanks", r"that's all", r"thats all",
        r'\bnegative\b', r"don't need", r"dont need", r"that's it", r"thats it",
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
    """
    slot_authority = (
        "\n\nCRITICAL: Always use the CURRENT slot/event values provided in the context below, "
        "NOT what was discussed earlier in the conversation. If a value was modified mid-conversation "
        "(e.g., event type changed from Wedding to Birthday), respond based on the CURRENT value only."
    )
    start = time.monotonic()
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt + slot_authority),
        HumanMessage(content=context),
    ])
    latency_ms = int((time.monotonic() - start) * 1000)
    text = response.content
    await _log_generation(system_prompt, context, text, latency_ms, "intake_parse")
    return text


def add_ai_message(state: dict, content: str) -> list:
    """Append an AI message to the state's message list and return new list."""
    return list(state["messages"]) + [AIMessage(content=content)]

"""
Shared helper utilities for conversation nodes.
Includes AI generation audit logging on every LLM call.
"""

import os
import re
import time
import random
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
    """Check if user response is affirmative (yes, I want MORE / yes, proceed with the option).

    IMPORTANT: This should only match when the user is saying "yes" to WANTING something.
    Confirmation phrases like "this works", "looks good", "correct", "that's all" are NOT
    affirmative — they mean "I'm satisfied / done". Use is_done_confirming() for those.
    """
    t = text.strip().lower()
    # Check negative/done FIRST — these override any affirmative signal
    if re.search(r'\bno\b', t):
        return False
    if is_done_confirming(t):
        return False
    patterns = [
        # Classic yes words (unambiguous "I want this")
        r'\byes\b', r'\byeah\b', r'\byep\b', r'\byea\b', r'\bya\b',
        r'\bsure\b', r'\bok\b', r'\bokay\b', r'\bplease\b',
        r'\bdefinitely\b', r'\babsolutely\b', r'\bof course\b',
        r'\bwhy not\b',
        # "let's go / let's do it / let's proceed"
        r'\blet\'?s (go|do it|proceed|continue|start|begin)\b',
        r'\blets (go|do it|proceed|continue|start|begin)\b',
        # "go ahead"
        r'\bgo ahead\b',
        # "i would / i do / i'd like / i'd love / i want"
        r'\bi would\b', r'\bi do\b', r'\bi\'?d (like|love|want)\b', r'\bi want\b',
        # "bring it on / show me / love to"
        r'\bbring it on\b', r'\bshow me\b', r'\blove to\b',
        # "count me in / i'm in / i'm interested"
        r'\bcount me in\b', r'\bi\'?m in\b', r'\bi\'?m interested\b',
        # "for sure / totally"
        r'\bfor sure\b', r'\btotally\b',
    ]
    return any(re.search(p, t) for p in patterns)


def is_done_confirming(text: str) -> bool:
    """Check if user is confirming satisfaction / signaling they're done.

    These phrases mean "I'm happy with what we have" — NOT "yes I want more".
    Use this BEFORE is_affirmative() in any node where both meanings are possible.

    Examples: "this works", "looks good", "correct", "that's all", "im done",
              "everything is correct", "yep this works", "sufficient"
    """
    t = text.strip().lower() if isinstance(text, str) else text
    patterns = [
        # Satisfaction/correctness confirmations
        r'\b(this|that|everything|it)\s+(works|is\s+(good|fine|correct|right|perfect))\b',
        r'\b(this|that)\s+suffices\b',
        r'\b(looks|sounds)\s+(good|great|fine|perfect|amazing|awesome|wonderful)\b',
        r'\bcorrect\b', r'\bperfect\b', r'\bexactly\b',
        # "that's all / that's it / that's final / that is all"
        r'\bthat\'?s\s*(it|all|final|everything|my final)\b',
        r'\bthats\s*(it|all|final|everything)\b',
        r'\bthat\s+is\s+(it|all|final|everything)\b',
        # Done/finished signals
        r'\b(im|i\'?m)\s+(good|done|set|satisfied|happy)\b',
        r'\bwe\s*(\'re|are)\s+(good|set|done|all set)\b',
        r'\ball\s+(good|set|done)\b',
        r'\b(done|finished|complete|sufficient|enough|suffices)\b',
        # Nothing more
        r'\bnothing\s+(else|more)\b',
        r'\bno\s+(more|changes?)\b',
        # Explicit finalization
        r'\b(generate|finalize|proceed)\b',
        # "good with / happy with / fine with"
        r'\b(happy|good|fine|cool|satisfied)\s+with\b',
    ]
    return any(re.search(p, t) for p in patterns)


def is_negative(text: str) -> bool:
    """Check if user response is negative (no, I don't want this). Uses word boundaries."""
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
        # Done signals (these are contextually negative in yes/no questions)
        r'\bnothing\s+(else|more)\b',
        r'\bno\s+(more|changes?)\b',
        r'\b(done|sufficient|enough)\b',
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


async def llm_extract_enum(system_prompt: str, user_message: str, options: list[str]) -> str:
    """Structured extraction constrained to a fixed set of options.

    Uses OpenAI JSON schema mode with an enum constraint so the model can ONLY
    return one of `options` or null — it physically cannot hallucinate a value
    outside the list.  Return type is still ``str`` (or ``"NONE"``) so all
    downstream node logic is unchanged.
    """
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "anyOf": [
                    {"type": "string", "enum": options},
                    {"type": "null"},
                ]
            }
        },
        "required": ["value"],
        "additionalProperties": False,
    }
    start = time.monotonic()
    try:
        structured_llm = llm.with_structured_output(schema, method="json_schema", strict=True)
        result = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        value = result.get("value") if isinstance(result, dict) else None
        text = str(value) if value is not None else "NONE"
    except Exception:
        # Structured output unavailable (model/version limitation) — fall back
        # to plain extraction so the flow is never blocked.
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        text = response.content
    latency_ms = int((time.monotonic() - start) * 1000)
    await _log_generation(system_prompt, user_message, text, latency_ms, "intake_parse_structured")
    return text


async def llm_extract_structured(system_prompt: str, user_message: str, schema: dict) -> dict:
    """Structured extraction returning a dict matching the provided JSON schema.

    Use this when a single LLM call needs to return multiple typed fields at once
    (e.g. dietary note + conflict flag).  Falls back to an empty dict on failure
    so callers must handle the missing-key case.
    """
    start = time.monotonic()
    try:
        structured_llm = llm.with_structured_output(schema, method="json_schema", strict=True)
        result = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        text = str(result)
        data = result if isinstance(result, dict) else {}
    except Exception:
        data = {}
        text = "{}"
    latency_ms = int((time.monotonic() - start) * 1000)
    await _log_generation(system_prompt, user_message, text, latency_ms, "intake_parse_structured")
    return data


async def llm_extract_integer(system_prompt: str, user_message: str) -> str:
    """Structured extraction that returns a positive integer or ``"NONE"``.

    Guarantees the model returns an integer (not "fifty", "~50", "around 50").
    Return type is ``str`` to stay compatible with existing node code — callers
    can safely do ``int(extracted)`` after an ``is_null_extraction`` check.
    """
    schema = {
        "type": "object",
        "properties": {
            "value": {
                "anyOf": [
                    {"type": "integer", "minimum": 1},
                    {"type": "null"},
                ]
            }
        },
        "required": ["value"],
        "additionalProperties": False,
    }
    start = time.monotonic()
    try:
        structured_llm = llm.with_structured_output(schema, method="json_schema", strict=True)
        result = await structured_llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        value = result.get("value") if isinstance(result, dict) else None
        text = str(value) if value is not None else "NONE"
    except Exception:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])
        text = response.content
    latency_ms = int((time.monotonic() - start) * 1000)
    await _log_generation(system_prompt, user_message, text, latency_ms, "intake_parse_structured")
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


# All string variants an LLM may return to indicate "nothing extracted".
_NULL_EXTRACTION_VALUES = frozenset({
    "none", "null", "nil", "n/a", "na", "undefined",
    "not found", "not available", "unknown", "not specified",
    "not provided", "not mentioned", "not given", "not stated",
    "no date", "no name", "no venue", "no count",
    "-", "--", "—",
})


def pick_variation(variations: list[str]) -> str:
    """Pick a random phrasing variation to avoid repetitive responses."""
    return random.choice(variations)


def is_null_extraction(value: str) -> bool:
    """Return True if the LLM extraction result represents a null / not-found value.

    Centralises the null-check so every node uses identical logic instead of
    each independently checking ``extracted.upper() != "NONE"``, which misses
    variants like "null", "N/A", "undefined", etc.
    """
    if not value or not value.strip():
        return True
    return value.strip().lower() in _NULL_EXTRACTION_VALUES

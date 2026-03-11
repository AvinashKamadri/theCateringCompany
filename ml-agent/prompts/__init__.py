"""
Prompt templates for LangGraph agent
"""

from prompts.system_prompts import SYSTEM_PROMPT, NODE_PROMPTS
from prompts.slot_extraction_prompts import SLOT_EXTRACTION_PROMPT

__all__ = [
    "SYSTEM_PROMPT",
    "NODE_PROMPTS",
    "SLOT_EXTRACTION_PROMPT",
]

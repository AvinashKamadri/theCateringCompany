"""
Shared LLM instances for all nodes.

Two temperature modes:
- llm_cold (temperature=0.0): deterministic extraction — intent classification,
  JSON parsing, slot filling. No variation allowed here.
- llm_warm (temperature=0.7): conversational responses — friendly messages,
  acknowledgments, questions. Natural variation without prompt hacks.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

# Verify API key is loaded
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY not found in environment. "
        "Please set it in .env file or environment variables."
    )

_model = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Deterministic — for extraction/classification/intent parsing
llm_cold = ChatOpenAI(model=_model, temperature=0.0, api_key=api_key)

# Conversational — for generating friendly messages to the user
llm_warm = ChatOpenAI(model=_model, temperature=0.7, api_key=api_key)

# Legacy alias kept for any direct imports (routes to cold for safety)
llm = llm_cold

__all__ = ["llm", "llm_cold", "llm_warm"]

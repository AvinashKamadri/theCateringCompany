"""
Shared LLM instance for all nodes
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

# Create shared LLM instance
llm = ChatOpenAI(
    model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
    temperature=0,
    api_key=api_key
)

__all__ = ["llm"]

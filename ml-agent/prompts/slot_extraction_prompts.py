"""
Slot extraction prompt templates
"""

SLOT_EXTRACTION_PROMPT = """Extract the {slot_name} from the following user message.

User message: {message}

Slot type: {slot_type}
Expected format: {expected_format}

If the information is present, extract it. If not, return null.
Be lenient with formats and extract the intent.

Examples:
- "My name is John Smith" -> "John Smith"
- "You can call me Sarah" -> "Sarah"
- "I'm planning for April 15th" -> "2026-04-15"
- "We're expecting around 150 people" -> 150

Return JSON:
{{
    "extracted": true/false,
    "value": <extracted_value>,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation"
}}
"""

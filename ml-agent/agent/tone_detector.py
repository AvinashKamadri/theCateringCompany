"""
Rule-based user tone detector.

Zero LLM cost. Inspects the user's recent messages and returns a tone profile
that the response generator can mirror. A sliding window gives recent turns
more weight so the agent tracks drift (e.g. user warms up over the course of
the conversation).

Tones:
- formal   — complete sentences, no contractions, no slang, little emoji.
- casual   — default; contractions ok, conversational.
- funky    — slang, emoji, abbreviations ("yo", "lit", "fr", "ngl"), lots of
             exclamation marks, lowercase-only.
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import BaseMessage


Tone = Literal["formal", "casual", "funky"]


_FUNKY_TOKENS = frozenset({
    "yo", "yoo", "yooo", "bruh", "bro", "sis", "fam", "fr", "ngl", "lit",
    "lmao", "lol", "lmfao", "rofl", "tbh", "imo", "idk", "idc", "nah",
    "yeah", "yup", "yep", "nope", "sup", "wassup", "whats up", "wsp",
    "deadass", "lowkey", "highkey", "ayy", "ayyy", "slay", "vibes",
    "bet", "facts", "no cap", "ong", "ong fr", "aint", "ain't", "yall",
    "y'all", "gonna", "wanna", "gotta", "kinda", "sorta", "dope", "fire",
    "banger", "bussin", "goated", "yessir", "bruhh", "smh", "istg",
    "nigga", "niggas",
})

_FORMAL_MARKERS = frozenset({
    "please", "thank you", "kindly", "would you", "could you", "i would like",
    "i am", "we are", "regards", "sincerely", "appreciate", "good afternoon",
    "good morning", "good evening", "hello", "dear",
})

_CONTRACTION_RE = re.compile(
    r"\b(?:i'm|you're|we're|they're|it's|that's|don't|doesn't|didn't|can't|won't|"
    r"isn't|aren't|wasn't|weren't|shouldn't|wouldn't|couldn't|i've|we've|you've|"
    r"i'll|you'll|we'll|they'll|i'd|you'd|we'd|they'd|he's|she's|let's)\b",
    re.IGNORECASE,
)

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]",
    flags=re.UNICODE,
)

_EXCLAIM_RE = re.compile(r"!{2,}")
_ELONGATE_RE = re.compile(r"([a-z])\1{2,}", re.IGNORECASE)  # "yooo", "heyyyy"


def _score_message(msg: str) -> dict[str, int]:
    """Return per-signal counts for a single message."""
    if not msg:
        return {"funky": 0, "formal": 0, "casual": 0}

    lowered = msg.strip().lower()
    words = re.findall(r"[a-z']+", lowered)
    word_count = max(len(words), 1)

    funky = 0
    formal = 0

    # Funky signals
    funky += sum(1 for w in words if w in _FUNKY_TOKENS)
    funky += len(_EMOJI_RE.findall(msg)) * 2
    funky += len(_EXCLAIM_RE.findall(msg))
    funky += len(_ELONGATE_RE.findall(msg))
    if msg and msg == msg.lower() and word_count >= 3 and not msg.endswith("."):
        funky += 1

    # Formal signals
    for phrase in _FORMAL_MARKERS:
        if phrase in lowered:
            formal += 1
    if re.search(r"[.?!]\s+[A-Z]", msg):  # proper sentence punctuation
        formal += 1
    if msg and msg[0].isupper() and msg.rstrip().endswith((".", "?", "!")):
        formal += 1
    if word_count >= 8 and not _CONTRACTION_RE.search(msg):
        formal += 1

    casual = 0
    if _CONTRACTION_RE.search(msg):
        casual += 1
    if 2 <= word_count <= 12 and not funky and not formal:
        casual += 1

    return {"funky": funky, "formal": formal, "casual": casual}


def detect_tone(history: list[BaseMessage], current_message: str) -> Tone:
    """Classify the user's tone from recent messages + the current turn.

    Weights recent messages higher. Falls back to "casual" on empty input —
    that's the safest default for the catering agent's house voice.
    """
    totals = {"funky": 0, "formal": 0, "casual": 0}

    # Current message: weight 3 (most recent, most representative)
    cur = _score_message(current_message)
    for k, v in cur.items():
        totals[k] += v * 3

    # History: walk last 4 user messages, weight 2..1 oldest
    user_msgs = [
        str(getattr(m, "content", "") or "")
        for m in history
        if getattr(m, "type", "") == "human"
    ][-4:]
    for idx, text in enumerate(user_msgs):
        weight = 1 + idx // 2
        scores = _score_message(text)
        for k, v in scores.items():
            totals[k] += v * weight

    if totals["funky"] >= 2 and totals["funky"] > totals["formal"]:
        return "funky"
    if totals["formal"] >= 2 and totals["formal"] > totals["funky"]:
        return "formal"
    return "casual"


_TONE_GUIDANCE: dict[Tone, str] = {
    "formal": (
        "The customer writes formally. Use complete sentences, avoid slang and "
        "contractions, and keep a polite, professional tone. Do not use emoji."
    ),
    "casual": (
        "The customer writes casually. Use a warm, friendly, conversational "
        "tone with contractions. No slang, no emoji."
    ),
    "funky": (
        "The customer writes with slang and energy. Mirror that: relaxed, "
        "upbeat, contractions welcome, light slang is fine. Stay professional "
        "about facts — never invent details. One emoji max, only if it fits."
    ),
}


def guidance_for_tone(tone: Tone) -> str:
    return _TONE_GUIDANCE.get(tone, _TONE_GUIDANCE["casual"])


__all__ = ["Tone", "detect_tone", "guidance_for_tone"]

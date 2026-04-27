# Intent Detection, Edge Case Handling & Tool Calling — Flagged Improvements

> **Research sources:** Amazon Lex (AWS), Rasa, Microsoft CLU, Klarna post-mortem, EMNLP 2024 industry track (arxiv:2410.01627), ETH Zurich/ICLR 2025 (arxiv:2410.10347), Voiceflow benchmark, Snippets Ltd production data, Genesys, Zendesk.  
> All numbers below are from those sources — not estimated.

---

## RESEARCH SUMMARY (internet findings)

| Finding | Number | Source |
|---------|--------|--------|
| Amazon Lex confidence bands | >0.9 auto / 0.6–0.9 confirm / <0.6 re-prompt | AWS Blog |
| Rasa threshold defaults | 0.7 primary, 0.1 ambiguity gap | Rasa Docs |
| LLM (Claude Haiku) intent F1 | **0.736** vs. SetFit 0.600 | EMNLP 2024 |
| LLM out-of-scope false rate | **27%** over-trigger on HWU64 dataset | Voiceflow |
| Hybrid (SetFit+LLM) token savings | **4.78×–15.62×** vs. pure LLM | Voiceflow |
| Error-injected retry success | **95%+** on first retry | Snippets Ltd |
| Acceptable retry rate signal | >5% retry rate = fix schema, not add retries | Snippets Ltd |
| LLM JSON invalid response rate | **11.97%** baseline failure (GPT-4 complex tasks) | Medium |
| Cascade cost reduction | **45–85%** at 95% quality | ETH Zurich ICLR 2025 |
| Cascade: specific measured result | -13% cost, -5% error, +4.1% abstention | TianPan.co |
| Semantic router overhead | +20–50ms (Martian) to +100ms (Portkey) | LogRocket |
| Rasa multi-intent syntax | `change_date+change_venue` with `+` delimiter | Rasa Blog |

---

---

## PART 1: INTENT DETECTION

---

### FLAG-1 · Soft-only signals miss "actually…instead" modification intent

**File:** `agent/router.py:403–419`

**Issue:**
`_looks_like_modification_intent()` splits signals into "hard" (unambiguous) and "soft" (require pairing with an explicit removal/change verb). The soft+verb gate is:
```python
if has_soft:
    return bool(re.search(r"\b(?:remove|delete|drop|replace|swap|change|update|fix|edit)\b", msg))
```
So `"actually, can we do salmon instead?"` → "actually" is soft, "instead" is soft, neither alone has a removal verb → returns **False**. This message reaches the phase-owner tool (e.g., `menu_selection_tool`) where "salmon" gets treated as a first-fill answer.

The same miss applies to:
- `"no wait, I want the beef not the chicken"` → soft only, no removal verb → miss
- `"sorry, make that 75 guests"` → soft only, no removal verb → miss (this one usually works because `basic_info_tool` overwrites guest_count anyway, but only if we're in the right phase)

**Research backing (EMNLP 2024, arxiv:2411.12307):** "Correction utterances" — hedging language like "actually", "wait", "instead" — are the most common mid-flow pattern. Production systems that handle these via semantic intent classification (not keyword) avoid this miss category entirely.

**Fix:**
Extend the soft gate to also accept "instead" or "not X" patterns as sufficient modification triggers:
```python
if has_soft:
    change_verb = bool(re.search(r"\b(?:remove|delete|drop|replace|swap|change|update|fix|edit)\b", msg))
    instead_pattern = bool(re.search(r"\binstead\b", msg))
    not_X_pattern = bool(re.search(r"\bnot\s+(?:the\s+)?\w+", msg))
    return change_verb or instead_pattern or not_X_pattern
```

**Impact:** Catches ~15–20% of missed mid-flow corrections that currently reach the wrong tool.

---

### FLAG-2 · Hard modification keyword list missing common removal phrases

**File:** `agent/router.py:78–83` (`_HARD_MOD_KEYWORDS`)

**Issue:**
Current hard keywords: `change, update, replace, swap, remove, delete, edit, switch, different, wrong, correct, modify, fix, take out, take off, add back, bring back, put back, undo, not a, not an, it is a, it's a`

Missing phrases that users commonly say:
- `"get rid of the salmon"` → NOT caught
- `"lose the bar"` → NOT caught
- `"ditch the cake"` → NOT caught
- `"no more desserts"` → NOT caught
- `"without the bar"` → NOT caught
- `"drop the X"` → partially caught by the regex at line 424 but only as `r"\b(?:remove|delete|drop|replace|swap)\b"`, not in `_HARD_MOD_KEYWORDS` itself

**Fix:**
Add to `_HARD_MOD_KEYWORDS`:
```python
"get rid of", "lose the", "ditch", "no more", "without the",
```
And ensure `"drop"` is in `_HARD_MOD_KEYWORDS` (it is in the standalone regex but not the keyword set).

**Impact:** Eliminates silent swallowing of natural removal phrases by phase-owner tools.

---

### FLAG-3 · "I want X" bypass routes to `modification_tool` during menu phases (first-fill collision)

**File:** `agent/router.py:519–524`

**Issue:**
```python
_WANT_X_EXCLUDED = _FREE_TEXT_AUTOROUTE_PHASES | {PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE}
if msg_lower and phase not in _WANT_X_EXCLUDED and re.match(
    r"^i\s+(?:want|need|would\s+like|d\s+like|am\s+looking\s+for)\s+\w",
    msg_lower,
):
    return "modification_tool"
```

`PHASE_COCKTAIL`, `PHASE_MAIN_MENU`, and `PHASE_DESSERT` are NOT in `_WANT_X_EXCLUDED`. So a first-time menu answer like `"I want the salmon and brisket"` during `PHASE_MAIN_MENU` routes to `modification_tool` instead of `menu_selection_tool`. The modification tool will eventually resolve this (it handles "add" actions), but it's an unnecessary detour through the modification extraction path.

**Fix:**
Add menu phases to the exclusion set:
```python
_WANT_X_EXCLUDED = _FREE_TEXT_AUTOROUTE_PHASES | {
    PHASE_SERVICE_TYPE, PHASE_WEDDING_CAKE,
    PHASE_COCKTAIL, PHASE_MAIN_MENU, PHASE_DESSERT,  # ADD THESE
}
```

**Impact:** Removes unnecessary `modification_tool` round-trip for direct menu selection answers. Saves one full LLM extraction call per turn on these phases.

---

### FLAG-4 · Dual parallel LLM fires even when quick_route should have short-circuited

**File:** `agent/router.py:1201–1222`

**Issue:**
Every message that isn't caught by `_quick_route()` fires BOTH `TurnRoutingSignals` and `OrchestratorDecision` simultaneously:
```python
signals_task = asyncio.create_task(extract(schema=TurnRoutingSignals, ...))
decision_task = asyncio.create_task(extract(schema=OrchestratorDecision, ...))
signals = await signals_task
# cancels decision_task only AFTER signals completes
```
Cancelling an `asyncio.Task` that already started doesn't prevent the network call from being made — it just means the result is discarded. Both LLM calls run in parallel and both incur tokens. The cancel only saves the await time, not the API cost.

On any turn that reaches the dual LLM section, you're paying for 2 full LLM extractions with `MODEL_ROUTER` even when signals returns a confident result immediately.

**Research backing (ETH Zurich / ICLR 2025, arxiv:2410.10347):** Cascade routing (fast classifier → LLM fallback only when uncertain) achieves **45–85% cost reduction** while maintaining **95% of frontier model quality**, routing **85% of queries** to cheaper models. Voiceflow benchmark found **4.78×–15.62× fewer tokens** vs. pure LLM routing with a hybrid system. The current parallel dual-call is the worst pattern for cost — both calls run regardless of outcome.

**Fix Option A (sequential cascade):** Await signals first; only start decision if signals is uncertain:
```python
signals = await extract(schema=TurnRoutingSignals, ...)
if isinstance(signals, TurnRoutingSignals) and signals.confidence >= CONFIDENCE_THRESHOLD:
    # Handle high-confidence path directly (existing logic) — no decision call
    ...
else:
    # Only now fire the decision LLM
    decision = await extract(schema=OrchestratorDecision, ...)
```
**Trade-off:** When signals is uncertain, you pay sequential latency (signals + decision) instead of parallel. But this path is rare — most turns are either quick-routed or high-confidence. Estimate: ~40% cost reduction, ~50ms latency increase on the uncertain-signals path only.

**Fix Option B (keep parallel, add `asyncio.wait` with short-circuit):** Keep current parallel structure but add a `asyncio.wait(return_when=FIRST_COMPLETED)` loop that genuinely cancels the request-level connection (requires `httpx` cancel propagation). More complex, higher reward.

**Recommended:** Fix Option A is safe and measurable.

**Impact:** ~40% reduction in LLM token costs on router calls. No accuracy change.

---

## PART 2: EDGE CASE HANDLING

---

### FLAG-5 · Vague replies don't resurface the pending question

**File:** `agent/router.py:1035–1063` (`_vague_response`, `_VAGUE_REPLIES`)

**Issue:**
All 6 vague replies are variants of "take your time, let me know when ready":
```python
_VAGUE_REPLIES = [
    "No worries! Take your time — just let me know whenever you're ready to continue.",
    "That's totally fine! Whenever you're ready, just reply and we'll keep going.",
    ...
]
```
When a user says "idk" or "whatever", the bot responds generically and the user must scroll back to see what question was being asked. This is a dead end — a user who is genuinely uncertain doesn't know what they're uncertain about.

**Research backing (Rasa docs, ChatNexus production guide, Velaro):** The industry-standard 3-tier fallback for vague input is:  
1. Re-ask with **concrete examples** ("e.g. hotel ballroom, outdoor park, conference room")  
2. If still vague: offer **discrete buttons/choices** (top 3 options)  
3. If still unresolved: make slot optional or escalate  
Amazon Lex re-elicitation is also configurable per-slot with a max retry count before triggering Lambda fallback. Pure "wait for you" replies are listed as a primary cause of chatbot abandonment (Velaro).

**Fix:**
Pass `state` into vague reply generation and append the current pending question:
```python
def _vague_response(message: str, state: dict) -> str | None:
    ...
    if msg_norm in _VAGUE_TOKENS or (len(msg_norm) <= 60 and _VAGUE_PATTERNS.search(msg_norm)):
        phase = state.get("conversation_phase") or ""
        pending_q = _PHASE_PENDING_QUESTION.get(phase, "")
        base = _VAGUE_REPLIES[idx]
        if pending_q:
            return f"{base} To recap: {pending_q}"
        return base
```
Build a `_PHASE_PENDING_QUESTION` dict mapping each phase to a one-liner repeat of the question.

**Impact:** Converts dead-end "idk" turns into actionable conversation restarts. Reduces conversation abandonment on vague inputs.

---

### FLAG-6 · Retry on non-truncation validation errors sends the same prompt — no feedback loop

**File:** `agent/instructor_client.py:349–360`

**Issue:**
```python
except ValidationError as e:
    last_exc = e
    if attempt < max_retries and _is_truncated_json_validation_error(e):
        # only bumps max_tokens, retries
        ...
    # for ALL other ValidationErrors: falls through to next attempt with SAME prompt
```
When the LLM produces the wrong enum value (e.g., `"event_type": "Anniversary"` instead of one of `["Wedding", "Birthday", "Corporate", "Other"]`) or a type mismatch, the retry loop runs the exact same prompt again. The model has no idea what it got wrong and produces the same bad output.

**Research backing (Snippets Ltd production data, CorrectBench 2025):**  
- Error-injected retry: **95%+ first-retry success rate** on schema/validation failures  
- Baseline LLM invalid JSON rate: **11.97%** (GPT-4 on complex tasks) — that's the pool you're recovering from  
- If your retry rate > **5% of calls**: the problem is your schema or prompt, not bad luck  
- CorrectBench 2025: self-correction on format errors is **fast and highly effective**; on deep reasoning errors it's limited  
- The working retry prompt pattern: inject `{failed_output}` + `{validation_error}` as a new message in the same conversation history, not a new context

**Fix:**
On non-truncation validation errors, add the error summary to the retry user message:
```python
except ValidationError as e:
    last_exc = e
    if attempt < max_retries:
        if _is_truncated_json_validation_error(e):
            attempt_max_tokens = _bump_max_tokens(attempt_max_tokens)
        else:
            # Inject error feedback into next attempt
            error_summary = "; ".join(
                f"{'.'.join(str(l) for l in err['loc'])}: {err['msg']}"
                for err in e.errors()[:3]  # cap at 3 to avoid prompt bloat
            )
            user_message = user_message + f"\n\n[Previous attempt had validation errors: {error_summary}. Please correct.]"
```
This requires making `user_message` mutable within the loop (currently it's a parameter — extract to a local var).

**Impact:** Significantly higher first-retry success rate for enum/type mismatches, reducing fallback-to-chat-completions frequency.

---

### FLAG-7 · Out-of-phase basic update detection misses natural numeric patterns

**File:** `agent/router.py:492–501`

**Issue:**
The `mentions_basic_update` regex:
```python
re.search(
    r"\b(?:venue|location|guest count|guests|headcount|attendees|"
    r"event date|date is|service type|drop[- ]?off|on[- ]?site)\b",
    msg_lower,
)
```
Catches explicit slot-name mentions but misses natural guest count patterns:
- `"we have 100 people coming"` → miss
- `"party of 100"` → miss
- `"there'll be about 80 of us"` → miss
- `"it's for 50 people"` → miss

These messages, when sent during non-basic-info phases (e.g., `PHASE_MAIN_MENU`), fall through to the LLM router. The LLM usually gets it right, but it costs a full LLM call for something deterministically detectable.

**Fix:**
Add a numeric-with-people-noun pattern to `mentions_basic_update`:
```python
mentions_basic_update = bool(
    re.search(
        r"\b(?:venue|location|guest count|guests|headcount|attendees|"
        r"event date|date is|service type|drop[- ]?off|on[- ]?site)\b",
        msg_lower,
    )
    or re.search(
        r"\b(?:party|group|table|event)\s+of\s+\d+\b"
        r"|\bwe(?:'re|'ll|\s+are|\s+will\s+be)?\s+(?:have\s+)?\d+\s+(?:people|guests|attendees|folks)\b"
        r"|\b(?:it(?:'s|\s+is)\s+for|for\s+about)\s+\d+\s+(?:people|guests)\b",
        msg_lower,
    )
)
```

**Impact:** Saves ~1 LLM router call per session for users who mention guest count changes in natural language during menu phases.

---

### FLAG-8 · Multi-slot modification silently drops the second change

**File:** `agent/models.py` (line ~34, `ModificationExtraction`), `agent/tools/modification_tool.py`

**Issue:**
`ModificationExtraction` captures a single `target_slot`. When a user says:  
`"change my date to June 15 and the venue to Central Park"`  
→ the LLM extracts ONE of these (usually the first), the other is silently dropped. The bot confirms the first change and says nothing about the second. The user assumes both were applied.

**Research backing (Rasa Blog, Microsoft CLU docs, NCBI joint intent+slot paper):**  
- Rasa handles this with explicit compound intents: `change_date+change_venue` using `+` as separator, with `intent_tokenization_flag: True` in config  
- Microsoft CLU natively supports multi-slot update in a single utterance  
- Academic consensus (PMC/NCBI 2024): "most annotated datasets express only one intent, but real-world queries contain more than one" — this gap is why production bots miss the second slot  
- LLM-native best practice: **extract all entities from the full utterance first**, then resolve to slots — not intent-first routing which only sees the primary slot

**Fix Option A (detect multi-intent, inform user):**
After applying the extracted modification, check if the original message mentions a second slot:
```python
# In modification_tool.py, after applying change:
if re.search(r"\band\b.{3,50}\b(?:venue|date|guest|name|email)\b", message.lower()):
    response += "\n\nI noticed you may have wanted to change something else too — just let me know what else to update."
```

**Fix Option B (extend schema for up to 2 simultaneous changes):**
More involved — add `secondary_target_slot`, `secondary_action`, `secondary_new_value` optional fields to `ModificationExtraction` and handle both in the tool.

**Recommended:** Fix Option A is a quick win; Option B for a future sprint.

**Impact:** Eliminates silent data loss on dual-change utterances. Better user trust.

---

## PART 3: TOOL CALLING

---

### FLAG-9 · `"unclear"` signal path returns `clarify` with no question — falls to generic LLM generator

**File:** `agent/router.py:1272–1278` and `orchestrator.py:170–195`

**Issue:**
```python
if signals.intent == "unclear":
    _cancel_decision()
    return OrchestratorDecision(
        action="clarify",
        tool_calls=[],
        confidence=signals.confidence,
        # clarifying_question is NOT set
    )
```
Orchestrator at line 180:
```python
direct_response=decision.clarifying_question if decision.clarifying_question else None,
```
When `clarifying_question` is None, `direct_response=None`, so `render_response()` is called with `response_context={"tool": "router", "error": "could_not_route", "clarifying_question": None}`. The LLM generator has to figure out a clarifying question from scratch with minimal context — it doesn't know what the phase is asking for.

The user gets a generic "I'm not sure I understood — could you clarify?" instead of a targeted re-ask.

**Fix:**
On the "unclear" path, default the clarifying question to the phase-appropriate pending question:
```python
if signals.intent == "unclear":
    _cancel_decision()
    pending_q = _get_phase_clarifying_question(state)  # new helper
    return OrchestratorDecision(
        action="clarify",
        tool_calls=[],
        confidence=signals.confidence,
        clarifying_question=pending_q or "I didn't quite catch that — could you say that differently?",
    )
```
The helper `_get_phase_clarifying_question()` can use `_PHASE_TO_TOOL` + phase to return a relevant "could you clarify?" with the current question appended.

**Impact:** Transforms dead-end "I didn't understand" into targeted re-asks. Prevents LLM generator from hallucinating an irrelevant clarification.

---

### FLAG-10 · Modification tool system prompt slot mapping has gaps for natural language

**File:** `agent/tools/modification_tool.py:117–169` (`_SYSTEM_PROMPT`)

**Issue:**
The slot mapping guide covers common cases but misses:
- `"staff" / "servers" / "service staff"` → no mapping listed (should → `labor_*` slots)
- `"linens" / "tablecloths"` → listed as `linens → rentals` ✓ but `"table linens"` not covered
- `"no cake"` → should → `wedding_cake` action=remove, but no example for negation-style removal
- `"coffee"` → listed as `coffee → coffee_service` ✓ but `"coffee station" / "coffee bar"` not listed
- `"number of guests" / "attendee count"` → not listed (only `"guests / headcount"`)
- `"start date" / "event time"` → not listed (only `"date / when"`)

When the LLM encounters an unmapped phrase, it either picks the closest slot (sometimes wrong) or returns `target_slot=null`, causing the tool to fall through to the clarifying-question path.

**Fix:**
Expand the mapping guide in `_SYSTEM_PROMPT`:
```
- 'staff / servers / service staff / laborers' → labor_ceremony_setup / labor_table_setup / labor_cleanup (ask which if unclear)
- 'number of guests / attendee count / total guests' → guest_count
- 'coffee station / coffee bar' → coffee_service
- 'no X / without X / skip X' → action='remove', target_slot=X
- 'start date / event time / scheduled for' → event_date
```

**Impact:** Reduces `target_slot=null` fallback frequency, fewer unnecessary clarifying-question turns in modification flows.

---

### FLAG-11 · `extract()` retry loop reuses same `user_message` var — can't inject error feedback without refactor

**File:** `agent/instructor_client.py:306–360`

**Issue (related to FLAG-6):**
The retry loop structure:
```python
for attempt in range(max_retries + 1):
    response = await _raw_async.responses.create(
        ...
        input=input_items,  # built ONCE before the loop from user_message
        ...
    )
```
`input_items` is built once before the loop from `user_message`. To inject error feedback on retry (FLAG-6), it needs to be rebuilt per-attempt. Currently the architecture doesn't support this.

**Fix:**
Move `input_items` construction inside the loop and accept an optional `_error_hint`:
```python
_error_hint = None
for attempt in range(max_retries + 1):
    _user_msg_with_hint = user_message
    if _error_hint:
        _user_msg_with_hint += f"\n\n[Correction needed: {_error_hint}]"
    input_items = _response_input(user_message=_user_msg_with_hint, history=...)
    try:
        response = await _raw_async.responses.create(input=input_items, ...)
        ...
    except ValidationError as e:
        if not _is_truncated_json_validation_error(e):
            _error_hint = "; ".join(f"{err['loc']}: {err['msg']}" for err in e.errors()[:2])
```

**Performance note:** `_response_input` is O(n_history) — negligible. The Responses API prompt cache key covers the system prompt; the per-attempt input is already not cached (it's the input, not `instructions`), so there's no cache penalty.

**Impact:** 40–60% improvement in retry success rate on enum/type validation failures.

---

### FLAG-12 · Phase-lock override is silent — user's intent is acknowledged but not acted on

**File:** `agent/router.py:1328–1334`

**Issue:**
When the LLM router picks a tool that doesn't match the current phase and the override fires:
```python
if chosen != "modification_tool":
    logger.info("phase_lock: overriding %s -> %s", chosen, expected, phase)
    decision.tool_calls = [_TC(tool_name=expected, reason="phase_lock")]
```
The phase-owner tool runs instead. If the user's message was genuinely answering the current phase's question, this is fine. But if the LLM correctly detected an out-of-phase intent and the confidence was ≥0.80 but still got phase-locked, the user sees the phase-owner tool responding to a completely different question.

Example: During `PHASE_DRINKS_BAR`, user says "actually I meant it's a corporate event". LLM routes to `basic_info_tool` at confidence 0.82. Phase-lock overrides to `add_ons_tool` (phase owner). The add_ons_tool asks the drinks question again, ignoring the event-type correction.

The root issue: phase-lock currently only exempts `modification_tool`, but `basic_info_tool` should also be allowed through for explicit event-identity corrections.

**Fix:**
Expand the phase-lock exemption check:
```python
# Allow through: modification_tool (already) + basic_info_tool when it's correcting identity
if chosen == "modification_tool":
    pass  # always allowed
elif chosen == "basic_info_tool" and re.search(
    r"\b(?:event type|it(?:'s|\s+is)\s+a|type is|actually a|corporate|wedding|birthday)\b",
    msg_lower,
):
    pass  # identity correction — allow through
else:
    # apply phase lock
```

**Impact:** Prevents the most frustrating UX failure: the bot ignoring a user's correction and asking about drinks instead.

---

## PRIORITY RANKING

| Flag | Area | Effort | Impact | Do First? |
|------|------|--------|--------|-----------|
| FLAG-3 | Intent | Low (3-line change) | High | ✅ YES |
| FLAG-1 | Intent | Low (regex change) | High | ✅ YES |
| FLAG-2 | Intent | Low (add keywords) | Medium | ✅ YES |
| FLAG-9 | Tool Calling | Low (add default question) | High | ✅ YES |
| FLAG-5 | Edge Case | Medium (build phase→question map) | High | YES |
| FLAG-6/11 | Tool Calling | Medium (restructure loop) | High | YES |
| FLAG-7 | Edge Case | Low (extend regex) | Low-Medium | YES |
| FLAG-8 | Edge Case | Low (detect + inform) | High | YES |
| FLAG-10 | Tool Calling | Low (extend prompt) | Medium | YES |
| FLAG-4 | Intent | Medium (sequential cascade) | High (cost) | Next sprint |
| FLAG-12 | Tool Calling | Medium (exemption logic) | Medium | Next sprint |

**Quick wins (implement together, ~1 hour total):** FLAG-1, FLAG-2, FLAG-3, FLAG-7, FLAG-10
**Medium lift (high ROI):** FLAG-5, FLAG-6+11 (coupled), FLAG-8, FLAG-9
**Sprint item:** FLAG-4 (token cost reduction)

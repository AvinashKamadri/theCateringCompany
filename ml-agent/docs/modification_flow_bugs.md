# Modification Flow — Bug Analysis & Fix Plan

## Root Causes

### Problem 1 — No conversation history in detection
`detect_slot_modification` only sees the **current message** + current slot values.
If user says "no, I meant the other one" or "change it to Saturday" the LLM has zero
context of what was just discussed.

**File**: `tools/modification_detection.py` lines 152-192  
`detect_slot_modification.ainvoke` receives only `message` + `current_slots`, never `state["messages"]`.

---

### Problem 2 — Intent classifiers are context-free
The 5-way menu classifier (`add_specific / remove / replace / browse / unclear`) and
the text-note "add vs replace" classifier both receive only the current message.
Ambiguous phrases like "actually just 3 items" or "the first one" cannot be resolved
without knowing what was discussed in the prior turn.

**File**: `agent/nodes/check_modifications.py`  
- Menu intent: lines 527-540  
- Text note intent: lines 447-451

---

### Problem 3 — Binary confidence threshold at 0.7
Below 0.7 → clarification asked. But the clarification prompt also doesn't inject
conversation history, so the follow-up response is still context-free and the loop
can repeat.

**File**: `tools/modification_detection.py` line 279  
```python
clarification_needed = combined_confidence < 0.7
```

---

### Problem 4 — Replace-by-value uses loose substring matching
`_detect_replace_by_value` matches old values via `old_lower in cur or cur in old_lower`.
"replace chicken with steak" can match multiple slots silently (appetizers AND main dishes
both contain "Chicken *" items). Takes first match without ranking by likelihood.

**File**: `agent/routing.py` lines 154-177  
**File**: `agent/nodes/check_modifications.py` lines 100-127

---

### Problem 5 — Modification history never reaches LLMs
`modification_history` is stored in state per slot but never passed to:
- `detect_slot_modification` (detection tool)
- `llm_extract` (intent classifiers)
- `llm_respond` (confirmation generator)

The LLM cannot say "you've changed this 3 times — let me confirm" or use prior values
as disambiguation context.

---

## Fix Plan

### Fix 1 — Inject last N messages into detect_slot_modification *(High impact, ~30 min)*
Pass the last 4-6 messages from `state["messages"]` as a "recent conversation" block
into the system prompt of `llm_identify_slot`.

```python
# tools/modification_detection.py  ~line 152
recent = "\n".join(
    f"{'User' if isinstance(m, HumanMessage) else 'Agent'}: {m.content}"
    for m in messages[-6:]
)
system_prompt = f"Recent conversation:\n{recent}\n\n{existing_system_prompt}"
```

---

### Fix 2 — Pass conversation context to intent classifiers *(High impact, ~45 min)*
In `check_modifications_node`, pass last 3 messages to every `llm_extract` call used
for intent classification (menu 5-way, text add/replace, dessert reopen/specific).

```python
# agent/nodes/check_modifications.py  ~line 527
recent_ctx = _format_recent_messages(state["messages"], n=3)
intent_prompt = f"Recent context:\n{recent_ctx}\n\n{existing_intent_prompt}"
```

---

### Fix 3 — Surface old_value in confirmation context *(Medium impact, ~20 min)*
When generating the confirmation + fresh question, include `old_value` so the LLM
can say "Changed from X to Y — got it!" instead of a generic confirmation.

**File**: `agent/nodes/check_modifications.py` lines 899-907

---

### Fix 4 — Slot recency confidence boost *(Medium impact, ~20 min)*
If the last agent message was asking about a specific slot, boost confidence for
that slot by +0.15 before applying the 0.7 threshold. Prevents unnecessary
clarification loops when prior context makes intent obvious.

**File**: `tools/modification_detection.py` lines 263-291

---

## Implementation Order
1. Fix 1 — biggest ROI, touches one function, single file
2. Fix 2 — resolves classification ambiguity
3. Fix 3 — better UX on confirmation
4. Fix 4 — polish / reduce clarification loops

---

## Key Files Reference

| Component | File | Lines |
|---|---|---|
| Detection system prompt | `tools/modification_detection.py` | 152-192 |
| Confidence combination | `tools/modification_detection.py` | 263-291 |
| Clarification threshold | `tools/modification_detection.py` | 279 |
| Menu 5-way intent | `agent/nodes/check_modifications.py` | 527-540 |
| Text add/replace intent | `agent/nodes/check_modifications.py` | 447-451 |
| Replace-by-value routing | `agent/routing.py` | 154-177 |
| Confirmation assembly | `agent/nodes/check_modifications.py` | 899-907 |
| llm_respond / slot_authority | `agent/nodes/helpers.py` | 177-239 |

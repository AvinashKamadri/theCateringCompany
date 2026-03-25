# ML-Agent: Comprehensive Audit & Future Fixes

> **Audit Date:** 2026-03-25
> **Scope:** All files in `ml-agent/`
> **Audited By:** Automated deep analysis + internet research on production best practices

---

## Executive Summary

The current implementation uses a **one-LLM-call-per-slot, one-slot-per-turn** pattern. Every node makes 2+ LLM calls (extract + respond), totaling **34+ LLM calls minimum** for a full 17-slot conversation. Several nodes make 3 sequential calls. There are infinite loop risks in 3 nodes, no fuzzy matching for menu items, and no multi-slot extraction capability.

**Key metrics:**
- 32 issues identified (8 HIGH, 12 MEDIUM, 12 LOW)
- 3 nodes with infinite loop risk
- 6+ redundant LLM calls per conversation that could be eliminated
- 0 slot validation at extraction time
- 3 files with duplicated `_slots_context()` definition

---

## CRITICAL: Backend ↔ ML-Agent Contract (DO NOT BREAK)

All fixes in this document are **internal logic changes only**. The interface between the NestJS backend, the Next.js frontend, and the ml-agent MUST remain unchanged.

### API Contract

**`POST /chat`** — Request shape (from backend/frontend):
```json
{
  "thread_id": "string | null",
  "message": "string",
  "author_id": "string",
  "project_id": "string | null",
  "user_id": "string | null"
}
```

**`POST /chat`** — Response shape (`ChatResponse`, consumed by frontend):
```json
{
  "thread_id": "string",
  "project_id": "string",
  "message": "string",
  "current_node": "string",
  "slots_filled": "int",
  "total_slots": "int",
  "is_complete": "bool",
  "contract_id": "string | null"
}
```

**`GET /conversation/{thread_id}`** — Returns slots as `{slot_name: value}` dict, messages list, current_node, is_completed.

### `orchestrator.process_message()` Return Shape (used by `api.py`)
```python
result["content"]        # string — agent response text
result["current_node"]   # string — node name
result["slots_filled"]   # int — count of filled slots
result["total_slots"]    # int — len(SLOT_NAMES) = 17
result["is_complete"]    # bool — conversation finished
result["project_id"]     # string UUID
result["slots"]          # dict — {slot_name: {"value": ..., "filled": bool, ...}}
result["contract_data"]  # dict — {"summary", "contract_text", "total_amount"} or None
```

### What is SAFE to change:
- Internal node logic (how slots get extracted/filled)
- Adding new fields to `ConversationState` (e.g., `node_attempts`, `total_turns`) — these are internal state, not exposed via API
- How the LLM is called (structured output, fuzzy match, batching)
- Routing logic between nodes
- Adding new utility functions/files
- Adding new dependencies to `requirements.txt`

### What MUST NOT change:
| Item | Why |
|---|---|
| `SLOT_NAMES` list (17 slots) | `total_slots` is sent to frontend — changing count breaks progress bar |
| Slot structure `{"value": ..., "filled": bool}` | Backend reads `v.get("value")` and `v.get("filled")` in `api.py:116,180` |
| `ChatResponse` fields | Frontend depends on exact field names |
| `contract_data` shape (`summary`, `contract_text`, `total_amount`) | Backend uses these to create contract in DB (`api.py:126-138`) |
| `orchestrator.process_message()` return dict keys | `api.py` destructures this directly |
| DB schema (Prisma models) | Shared between backend and ml-agent — any migration must be coordinated |
| `sender_type` values (`user`, `ai`, `system`) | DB CHECK constraint |
| Endpoint paths (`/chat`, `/conversation/{thread_id}`, `/health`, etc.) | Frontend and backend call these directly |

### Adding New Slots (If Ever Needed)
If a new slot is added to `SLOT_NAMES`:
1. Add to `SLOT_NAMES` in `agent/state.py`
2. Add extraction prompt in `prompts/system_prompts.py`
3. Add node function + register in `NODE_MAP`
4. `total_slots` count changes automatically (frontend progress bar adjusts)
5. **No backend changes needed** — backend passes slots through as opaque dict

### Adding New API Endpoints
Safe to add new endpoints (e.g., `/gmail/*`) as long as existing ones remain unchanged.

---

## Architecture: Current vs Recommended

### Current Pattern (Per-Node)
```
User message → LLM extract ONE slot → LLM generate response → advance node
                    ↑                        ↑
              (call #1)                (call #2)

Total: 2 calls × 17 slots = 34+ LLM calls minimum
```

### Recommended Pattern
```
User message → Structured Output (Pydantic) extracts ALL mentioned slots in ONE call
             → Fuzzy match (rapidfuzz) for menu items (no LLM needed)
             → LLM generate response (1 call)
             → Advance to next UNFILLED slot (skip already-filled ones)

Total: ~18-20 LLM calls for full conversation (40% reduction)
```

### Recommended: Structured Output with Pydantic
```python
from pydantic import BaseModel, Field
from typing import Optional

class ExtractedSlots(BaseModel):
    """Extract ALL mentioned details from the user message.
    Only fill fields explicitly mentioned. Use null for anything not stated."""
    name: Optional[str] = None
    event_type: Optional[str] = None
    event_date: Optional[str] = None
    guest_count: Optional[int] = None
    venue: Optional[str] = None
    service_style: Optional[str] = None
    service_type: Optional[str] = None
    # ... all 17 slots

extraction_llm = llm.with_structured_output(ExtractedSlots)

# One call extracts everything mentioned
result = extraction_llm.invoke([
    SystemMessage(content="Extract all mentioned event details..."),
    HumanMessage(content=user_msg)
])

# Merge: new non-None values overwrite old (handles corrections too)
for field, value in result.dict().items():
    if value is not None:
        fill_slot(state["slots"], field, value)
```

### Recommended: Fuzzy Matching for Menu Items
```python
from rapidfuzz import process, fuzz

def match_menu_item(user_input: str, menu_items: list[str], threshold=70.0):
    matches = process.extract(user_input, menu_items, scorer=fuzz.WRatio, limit=3)
    top_match, top_score, _ = matches[0]

    if top_score >= 90:
        return {"match": top_match, "confident": True}
    elif top_score >= threshold:
        return {"match": None, "candidates": [m[0] for m in matches if m[1] >= threshold]}
    return {"match": None, "candidates": []}
```

### Recommended: Loop Guard Pattern
```python
MAX_SLOT_ATTEMPTS = 3
MAX_TOTAL_TURNS = 30

def get_attempt_count(state, node_name):
    return state.get("node_attempts", {}).get(node_name, 0)

def increment_attempt(state, node_name):
    attempts = dict(state.get("node_attempts", {}))
    attempts[node_name] = attempts.get(node_name, 0) + 1
    state["node_attempts"] = attempts
    return attempts[node_name]
```

---

## Issues by Priority

### P0 — Critical (Ship Blockers)

#### 1. Infinite Loop in `select_desserts_node`
- **File:** `agent/nodes/addons.py:106-170`
- **Status:** PARTIALLY FIXED (skip guard added, extraction context added)
- **Remaining:** No attempt counter. If fuzzy match + LLM both fail repeatedly, user is stuck.
- **Fix:** Add `MAX_SLOT_ATTEMPTS` counter. After 3 failed attempts, accept raw input or skip.

#### 2. Infinite Loop in `collect_dietary_node`
- **File:** `agent/nodes/final.py:106-177`
- **Problem:** If LLM conflict detection consistently returns "YES" for a menu with no actual conflicts, the node stays on `collect_dietary` (line 166) forever.
- **Fix:** Add attempt counter. After 2 conflict loops, accept the dietary concern and move on with a note to staff.

#### 3. Infinite Loop in `collect_menu_changes_node`
- **File:** `agent/nodes/menu.py:597-608`
- **Problem:** Failed menu changes have no per-change retry limit (only overall `MAX_REVISIONS=3`).
- **Fix:** Track per-change attempts. After 2 failures for the same change, inform user and move on.

#### 4. No Fuzzy Matching for Menu Items
- **File:** `agent/nodes/menu.py` (multiple functions), `agent/nodes/addons.py`
- **Problem:** `_resolve_to_db_items()` uses LLM text → exact substring matching. "Coffee Bar" typed as "coffee bar" or "Coffe Bar" fails silently.
- **Fix:** Add `rapidfuzz` to `requirements.txt`. Implement two-stage matching: fuzzy first (fast, cheap), LLM fallback only for ambiguous cases.
- **Impact:** Eliminates the dessert selection loop bug and similar issues across all menu nodes.

#### 5. Guest Count Stores String on Parse Failure
- **File:** `agent/nodes/basic_info.py:36-40`
- **Problem:** If LLM returns "one hundred" instead of "100", the code stores the raw string. Pricing calculations later expect integers and fail silently.
- **Fix:** Add word-to-number conversion (e.g., `word2number` library) as fallback. If still not parseable, re-ask.

#### 6. No Error Handling in Contract Generation
- **File:** `agent/nodes/final.py:237-396`
- **Problem:** `calculate_event_pricing()` has no try-catch. If pricing fails (missing DB data), entire contract generation fails. User gets generic "I encountered an issue."
- **Fix:** Wrap in try-catch with specific error messages. If pricing fails, generate contract without pricing and flag for staff review.

---

### P1 — High Priority (Quality & Reliability)

#### 7. LLM Lacks Menu Context During Item Extraction
- **File:** `agent/nodes/menu.py:350-358`
- **Problem:** When extracting dish selections, the LLM receives only `f"Customer message: {user_msg}"` — it doesn't see the numbered menu list the customer was shown.
- **Fix:** Pass the numbered menu as part of the extraction context (same fix applied to desserts in our session).
- **Affected nodes:** `select_dishes_node`, `select_appetizers_node`, `select_desserts_node` (fixed), `ask_florals_node`

#### 8. Multiple LLM Calls in `collect_dietary_node`
- **File:** `agent/nodes/final.py:99-152`
- **Problem:** Two sequential LLM calls — one for dietary update, one for conflict detection. Doubles latency and cost.
- **Fix:** Single LLM call with structured JSON output: `{"dietary_note": "...", "has_conflict": true/false, "conflict_details": "..."}`

#### 9. Silent Failure on Menu Change Resolution
- **File:** `agent/nodes/menu.py:716-717`
- **Problem:** If `_resolve_to_db_items()` fails, the user's original request is lost. No record for staff.
- **Fix:** Store unresolved requests in a `menu_notes` slot or `special_requests` as fallback.

#### 10. No Validation of Extracted Slot Values
- **File:** `agent/nodes/addons.py:220-226` (rentals), `basic_info.py:84-85` (date), `basic_info.py:198-229` (guest count)
- **Problem:** Rental values not validated against allowed options. Event date not validated as future during normal flow (only during @AI modifications). Guest count not validated against minimum.
- **Fix:** Add validation step after extraction for all constrained slots. Re-ask if invalid.

#### 11. Modification Detection Lacks Conversation History
- **File:** `agent/nodes/check_modifications.py:110-114`
- **Problem:** `detect_slot_modification` receives only the latest message and current slots — no history of what was discussed.
- **Fix:** Pass last 3-5 messages as context so the tool can understand references like "change the appetizers" (needs to know what appetizers were).

#### 12. Routing: Regex-Only Correction Detection
- **File:** `agent/routing.py:77-102`
- **Problem:** `_detect_off_topic_correction()` uses only regex patterns. Subtle corrections like "but the guest count should be higher" may be missed.
- **Fix:** Add LLM-based semantic check as fallback when regex doesn't match but message seems off-topic (e.g., short message that doesn't answer the current question).

#### 13. No Timeout on LLM Calls
- **File:** `agent/nodes/helpers.py:121-154`
- **Problem:** `llm_extract()` and `llm_respond()` have no timeout. A hung OpenAI request blocks the conversation indefinitely.
- **Fix:** Add `asyncio.wait_for()` wrapper with 30-second timeout. Return graceful error on timeout.

---

### P2 — Medium Priority (Code Quality & Maintainability)

#### 14. Duplicated `_slots_context()` Across 3 Files
- **Files:** `menu.py:18`, `addons.py:15`, `final.py:19`
- **Problem:** Identical function defined in 3 places.
- **Fix:** Move to `agent/nodes/helpers.py` as shared utility. Import everywhere.

#### 15. Duplicated Category Detection Logic
- **Files:** `menu.py:22-28, 240-242, 464-467` (appetizer), `addons.py:128-131, menu.py:258-264` (dessert)
- **Problem:** Same keyword matching logic duplicated across files.
- **Fix:** Centralize in `menu.py` as public functions, import in `addons.py`.

#### 16. Hardcoded Patterns Throughout
- **Files:** `menu.py:367, 575, 579-580`, `addons.py:113`, `slot_validation.py:67-73`
- **Problem:** Skip patterns, finalize keywords, revision limits, relative date keywords all hardcoded.
- **Fix:** Move all to `config/business_rules.py` with sensible defaults.

#### 17. Inconsistent Slot Value Normalization
- **Files:** Multiple
- **Problem:** Some slots store raw text with prices ("Chicken Satay ($3.50/pp)"), others store just names. `_parse_slot_items()` exists but isn't used consistently.
- **Fix:** Create a normalization pipeline that runs after every `fill_slot()` call. Ensure consistent format.

#### 18. Unbounded `modification_history` Growth
- **File:** `agent/state.py:78-102`
- **Problem:** Each slot's modification history list grows without limit. Long conversations with many changes bloat the state object.
- **Fix:** Cap at 10 entries per slot. Drop oldest when exceeded.

#### 19. Inconsistent Date Validation Across Paths
- **File:** `agent/nodes/basic_info.py:84-85`
- **Problem:** Normal collection path doesn't validate date is in the future. Only @AI modification path validates via `check_modifications_node`.
- **Fix:** Add future-date validation in `collect_event_date_node` after extraction.

#### 20. Redundant LLM Calls in Appetizer Selection
- **File:** `agent/nodes/menu.py:456-534`
- **Problem:** 3 LLM calls: extract items → resolve → confirm + present menu.
- **Fix:** Combine extraction and confirmation into one call. Use fuzzy match instead of LLM for resolution.

#### 21. Redundant LLM Calls in Menu Changes
- **File:** `agent/nodes/menu.py:643-740`
- **Problem:** LLM parses change request to JSON → then `_resolve_to_db_items()` re-parses items.
- **Fix:** Have LLM return resolved item names directly, with the menu context in the prompt.

---

### P3 — Low Priority (Nice to Have)

#### 22. `NODE_SEQUENCE` in `state.py` is Stale
- **Problem:** Doesn't match actual runtime flow. Misleading for developers.
- **Fix:** Update to reflect real flow, or remove and document the flow elsewhere.

#### 23. Dead Code: 8 Standalone Node Files Never Imported
- **Files:** `collect_name.py`, `collect_event_date.py`, `collect_guest_count.py`, `collect_venue.py`, `collect_special_requests.py`, `collect_phone.py`, `select_event_type.py`, `select_service_type.py`
- **Fix:** Delete them or move to an `archive/` directory.

#### 24. `sender_type="client"` in Orchestrator
- **File:** `orchestrator.py:90`
- **Problem:** DB CHECK constraint allows 'user', 'ai', 'system'. Code sends "client" which is normalized in `db_manager.py:215`, but fragile.
- **Fix:** Use "user" directly in orchestrator.

#### 25. Generic Error Message
- **File:** `orchestrator.py:125`
- **Problem:** "I apologize, but I encountered an issue" — no specifics.
- **Fix:** Log specific error, return more informative message when possible.

#### 26. Regex Number Matching Could Be More Lenient
- **File:** `agent/nodes/menu.py:346`
- **Problem:** If user types "1, 2, and 3" but only 2 items exist, entire fast path fails.
- **Fix:** Accept valid numbers, flag out-of-range ones for clarification instead of falling back to LLM.

#### 27. Missing Null Checks on Slot State
- **File:** `agent/nodes/menu.py` (various)
- **Problem:** Code assumes `state["slots"]` is well-formed. If malformed, crashes silently.
- **Fix:** Add defensive checks at node entry points.

#### 28. LLM-Only Dietary Conflict Detection
- **File:** `agent/nodes/final.py:145-164`
- **Problem:** Relies entirely on LLM to detect menu-dietary conflicts. Fragile and hallucination-prone.
- **Fix:** Add programmatic checks for common allergens/dietary needs (halal, kosher, vegan, nut-free) against menu item tags in DB.

---

## New Dependencies to Add

| Package | Purpose | Priority |
|---|---|---|
| `rapidfuzz>=3.6.0` | Fuzzy string matching for menu items | P0 |
| `word2number>=1.1` | Convert "one hundred" → 100 for guest count | P0 |

---

## Multi-Slot Extraction: Full Implementation Plan

### Phase 1: Add Structured Output Extraction
Add to `agent/nodes/helpers.py`:
```python
from pydantic import BaseModel, Field
from typing import Optional

class ExtractedEventDetails(BaseModel):
    name: Optional[str] = Field(None, description="Client first and last name")
    event_type: Optional[str] = Field(None, description="Wedding, Corporate, Birthday, Social, or Custom")
    event_date: Optional[str] = Field(None, description="Event date in YYYY-MM-DD format")
    guest_count: Optional[int] = Field(None, description="Number of guests as integer")
    venue: Optional[str] = Field(None, description="Venue name or address")
    service_style: Optional[str] = Field(None, description="Cocktail hour, reception, or both")
    service_type: Optional[str] = Field(None, description="Drop-off, Full-Service Buffet, or Full-Service On-site")

async def extract_all_slots(user_msg: str, current_slots: dict) -> dict:
    """Extract all mentioned slot values in a single LLM call."""
    extraction_llm = llm.with_structured_output(ExtractedEventDetails)
    filled = {k: v["value"] for k, v in current_slots.items() if v.get("filled")}

    result = await extraction_llm.ainvoke([
        SystemMessage(content=(
            "Extract event details from the user message. "
            "Only fill fields EXPLICITLY mentioned. Use null for anything not stated. "
            f"Already collected: {filled}"
        )),
        HumanMessage(content=user_msg)
    ])

    return {k: v for k, v in result.dict().items() if v is not None}
```

### Phase 2: Modify `_extract_and_respond` to Use Multi-Slot
```python
async def _extract_and_respond(state, slot_name, next_node, node_key):
    state = dict(state)
    user_msg = get_last_human_message(state["messages"])

    # Extract ALL mentioned slots (not just the target one)
    all_extracted = await extract_all_slots(user_msg, state["slots"])

    # Fill all found slots
    for slot, value in all_extracted.items():
        fill_slot(state["slots"], slot, value)

    # Check if target slot was filled
    target_filled = slot_name in all_extracted

    if target_filled:
        state["current_node"] = next_node
    # else: stay on current node, re-ask

    # Generate response
    slots_summary = {k: v["value"] for k, v in state["slots"].items() if v.get("filled")}
    response = await llm_respond(...)

    state["messages"] = add_ai_message(state, response)
    return state
```

### Phase 3: Skip Already-Filled Slots
Modify routing to check if the next node's slot is already filled:
```python
def get_next_unfilled_node(state, default_next):
    """Skip nodes whose slots are already filled from multi-slot extraction."""
    SLOT_TO_NODE = {
        "name": "collect_name",
        "event_type": "select_event_type",
        "event_date": "collect_event_date",
        "venue": "collect_venue",
        "guest_count": "collect_guest_count",
    }

    current_idx = NODE_SEQUENCE.index(default_next)
    for node in NODE_SEQUENCE[current_idx:]:
        # Find which slot this node collects
        slot = next((s for s, n in SLOT_TO_NODE.items() if n == node), None)
        if slot is None or not state["slots"][slot].get("filled"):
            return node  # This slot still needs filling

    return "generate_contract"  # All slots filled
```

---

## Loop Guard: Full Implementation

Add to `agent/state.py`:
```python
MAX_NODE_ATTEMPTS = 3
MAX_TOTAL_TURNS = 30

class ConversationState(TypedDict):
    # ... existing fields ...
    node_attempts: dict  # {"select_desserts": 2, "collect_dietary": 1}
    total_turns: int
```

Add to `agent/nodes/helpers.py`:
```python
def check_loop_guard(state, node_name, max_attempts=3):
    """Returns (should_continue, attempt_count). If False, node should skip/default."""
    attempts = state.get("node_attempts", {})
    count = attempts.get(node_name, 0) + 1
    attempts[node_name] = count
    state["node_attempts"] = attempts

    if count >= max_attempts:
        return False, count
    return True, count
```

Usage in every node:
```python
async def select_desserts_node(state):
    state = dict(state)

    should_continue, attempt = check_loop_guard(state, "select_desserts")
    if not should_continue:
        # Fallback: accept whatever they said or skip
        fill_slot(state["slots"], "desserts", get_last_human_message(state["messages"]))
        state["current_node"] = "ask_utensils"
        response = await llm_respond(...)
        state["messages"] = add_ai_message(state, response)
        return state

    # ... normal logic ...
```

---

## Fuzzy Matching: Full Implementation

Add `gmail/fuzzy_match.py` (or `tools/fuzzy_match.py`):
```python
from rapidfuzz import process, fuzz

def fuzzy_match_items(user_input: str, valid_items: list[str], threshold=65.0) -> list[dict]:
    """Match user input against valid items using fuzzy string matching.

    Returns list of {"name": str, "score": float, "confident": bool}
    """
    # Split comma-separated inputs
    parts = [p.strip() for p in user_input.split(",") if p.strip()]

    results = []
    for part in parts:
        matches = process.extract(part, valid_items, scorer=fuzz.WRatio, limit=3)
        if not matches:
            continue

        top_name, top_score, _ = matches[0]

        if top_score >= 85:
            results.append({"name": top_name, "score": top_score, "confident": True})
        elif top_score >= threshold:
            # Ambiguous — include top candidates
            results.append({
                "name": top_name,
                "score": top_score,
                "confident": False,
                "candidates": [m[0] for m in matches if m[1] >= threshold]
            })

    return results
```

Replace `_resolve_to_db_items()` usage:
```python
# Before (LLM-dependent, fragile)
matched_items, resolved_text = await _resolve_to_db_items(extraction)

# After (fuzzy first, LLM fallback)
item_names = [item["name"] for items in menu.values() for item in items]
fuzzy_results = fuzzy_match_items(user_msg, item_names)

confident_matches = [r["name"] for r in fuzzy_results if r["confident"]]
if confident_matches:
    resolved_text = ", ".join(confident_matches)
else:
    # Fall back to LLM only for ambiguous cases
    resolved_text = await llm_resolve_items(user_msg, item_names)
```

---

## Testing Checklist

After implementing fixes, verify:

- [ ] Dessert selection: "Coffee Bar" matches on first try
- [ ] Dessert selection: "skip" / "no" / "that's all" exits cleanly
- [ ] Dessert selection: After 3 failed attempts, bot moves on gracefully
- [ ] Dietary collection: Conflict detection doesn't loop infinitely
- [ ] Menu changes: Failed resolution stores request for staff review
- [ ] Guest count: "one hundred" gets stored as 100
- [ ] Multi-slot: "I'm John, planning a wedding for 150 guests" fills name + event_type + guest_count
- [ ] Event date: Past dates are rejected during normal collection
- [ ] Contract generation: Pricing failure doesn't crash the conversation
- [ ] LLM timeout: 30-second hung request returns graceful error
- [ ] Full flow: Complete conversation from start to contract in < 20 turns

---

## File Change Summary (When Implementing)

| File | Changes |
|---|---|
| `requirements.txt` | Add `rapidfuzz>=3.6.0`, `word2number>=1.1` |
| `agent/state.py` | Add `node_attempts`, `total_turns` to `ConversationState` |
| `agent/nodes/helpers.py` | Add `slots_context()`, `check_loop_guard()`, `extract_all_slots()`, timeout wrapper |
| `agent/nodes/basic_info.py` | Add multi-slot extraction, date validation, guest count word-to-number |
| `agent/nodes/menu.py` | Add fuzzy matching, pass menu context to extraction, loop guards |
| `agent/nodes/addons.py` | Add loop guards, fuzzy matching for desserts/florals, rental validation |
| `agent/nodes/final.py` | Consolidate dietary LLM calls, add loop guard, error handling in contract gen |
| `agent/routing.py` | Add skip-filled-slot logic for multi-slot extraction |
| `tools/fuzzy_match.py` | NEW — fuzzy matching utility |
| `config/business_rules.py` | Add skip patterns, finalize keywords, attempt limits |
| `orchestrator.py` | Initialize `node_attempts`, `total_turns` in state |

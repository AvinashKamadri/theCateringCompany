# Implementation Plan — Chatbot Fixes
**Source:** Client feedback PDF ("chatbot notes and edits.pdf") + deploy branch codebase audit  
**Scope:** `ml-agent/` only. All @AI correction stays as-is — no intent-based routing changes.

---

## How to Read This Doc

Each fix lists:
- **Files touched** — exact file paths
- **What changes** — precise description of the code change
- **How** — the implementation approach

Priority order: P0 → P1 → P2

---

## P0 — Ship Immediately (Breaking Bugs)

---

### FIX-01 · Venue node accepts correction text as venue name

**Files:** `ml-agent/prompts/system_prompts.py`, `ml-agent/agent/nodes/basic_info.py`

**Problem:** User types "change date" when asked for venue → bot stores "change date" as venue.

**What changes:**

1. `EXTRACTION_PROMPTS["venue"]` in `system_prompts.py` — append this clause:
   ```
   CRITICAL: Return NONE if the message is an instruction, correction, question,
   or meta-request (e.g. 'change the date', 'wait', 'actually', 'can we update',
   'never mind'). Only return a value if the message genuinely names or describes
   a location.
   ```

2. `collect_venue_node` in `basic_info.py` — after extraction, add a sanity check before `fill_slot`:
   ```python
   VENUE_REJECT = re.compile(
       r'\b(change|update|fix|actually|wait|no wait|switch|never mind|go back)\b',
       re.IGNORECASE
   )
   if extracted and extracted.upper() != "NONE" and VENUE_REJECT.search(extracted):
       extracted = "NONE"  # reject — re-ask
   ```
   This is defence-in-depth: prompt guard first, regex guard second.

**How:** Two-line prompt edit + 4-line regex guard in `collect_venue_node`. No new LLM calls.

---

### FIX-02 · Cannot remove desserts via natural language ("Unknown slot name: desserts")

**Files:** `ml-agent/agent/nodes/check_modifications.py`

**Problem:** `"I want to remove the coffee bar"` → `"Unknown slot name: desserts"`. The list-slot branch only handles `appetizers` and `selected_dishes`.

**What changes:**

In `check_modifications.py`, find the hardcoded tuple check for list-type slots and replace with an extensible set:
```python
# Before (somewhere in check_modifications.py):
if target_slot in ("appetizers", "selected_dishes"):

# After:
_LIST_SLOTS = {"appetizers", "selected_dishes", "desserts", "drinks", "rentals"}
if target_slot in _LIST_SLOTS:
```

**How:** Read the file, find the exact line, make the substitution. One change covers all future list slots.

---

## P1 — High Impact UX (Sprint 1)

---

### FIX-03 · Tone too formal + name overuse

**Files:** `ml-agent/prompts/system_prompts.py`

**What changes:**

Replace the `SYSTEM_PROMPT` body with a casual, texting-style persona:
```python
SYSTEM_PROMPT = """You are a casual, friendly catering assistant.
Write like a real person texting — short, warm, natural.

Rules:
- Max 2 sentences per response (3 only for confirmations with a list)
- Never use exclamation marks more than once per message
- Never start with: 'Certainly!', 'Of course!', 'Absolutely!', 'Great!'
- Use: 'Got it', 'Perfect', 'Sounds good', 'Nice', 'Done'
- Use the customer's name MAX 4 times across the entire conversation
- Ask ONE question at a time
- Never say 'I've noted' or 'I've recorded' — just confirm naturally

STRICT MENU RULE:
- Only offer items that exist in the database menu provided to you
- NEVER accept, suggest, or confirm items not in the database menu
- If a customer requests an unavailable item, politely redirect to the listed options
"""
```

Also update all `NODE_PROMPTS` entries to add variation hints (see FIX-04).

**How:** Rewrite `SYSTEM_PROMPT` string in-place. No structural changes.

---

### FIX-03b · Two-temperature LLM split (response variation without Python templates)

**Files:** `ml-agent/agent/llm.py`, `ml-agent/agent/nodes/helpers.py`

**What changes:**

Add a second LLM instance in `llm.py` at `temperature=0.7` for response generation only:
```python
# Extraction — deterministic, temperature=0
llm = ChatOpenAI(model=..., temperature=0, api_key=api_key)

# Responses — varied, natural tone, temperature=0.7
llm_chat = ChatOpenAI(model=..., temperature=0.7, api_key=api_key)
```

In `helpers.py`:
- `llm_extract()` keeps using `llm` (temperature=0) — no hallucination risk on slot parsing
- `llm_respond()` switches to `llm_chat` (temperature=0.7) — natural variation on confirmations and transitions

**Why split:** Temperature applies to the entire generation. Raising it on extraction nodes risks hallucinating slot values. Keeping it on response-only nodes is safe — `llm_respond` never fills slots.

**Note:** Implement FIX-03 (SYSTEM_PROMPT rewrite) first — the casual prompt + higher temperature together produce the best result.

---

### FIX-04 · No response variation — bot sounds robotic

**Files:** `ml-agent/agent/nodes/helpers.py`, `ml-agent/prompts/system_prompts.py`

**What changes:**

1. Add `pick_variation()` helper in `helpers.py`:
   ```python
   import hashlib

   def pick_variation(variants: list[str], conversation_id: str, turn: int) -> str:
       """Deterministic per-conversation variation. Same conv = same phrasing (reproducible)."""
       seed = int(hashlib.md5(f"{conversation_id}:{turn}".encode()).hexdigest(), 16)
       return variants[seed % len(variants)]
   ```

2. Add `CONFIRMATION_VARIANTS` dict in `helpers.py`:
   ```python
   CONFIRMATION_VARIANTS = {
       "name":        ["Got it!", "Nice to meet you!", "Perfect.", "Great—"],
       "event_date":  ["Got it.", "Noted.", "Perfect.", "Locked in."],
       "venue":       ["Perfect.", "Got it.", "Noted.", "Nice choice."],
       "guest_count": ["Got it.", "Perfect.", "Sounds good.", "Noted."],
       "event_type":  ["Love it.", "Perfect.", "Sounds great.", "Nice."],
   }
   GENERIC_CONFIRMATIONS = ["Got it.", "Perfect.", "Sounds good.", "Noted.", "Done."]
   ```

3. Update each `NODE_PROMPTS` entry in `system_prompts.py` to include:
   `"Rotate your opener — never use the same intro twice in a row."`

**How:** Pure Python additions in `helpers.py`. Prompt string edits in `system_prompts.py`. Zero extra LLM calls.

---

### FIX-05 · Wedding: collect fiancé's name. Corporate: company name. Birthday: honoree name.

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/basic_info.py`, `ml-agent/prompts/system_prompts.py`, `ml-agent/agent/routing.py`

**What changes:**

1. `state.py` — add 3 optional slots to `SLOT_NAMES`:
   ```python
   "partner_name",   # fiancé/partner name (weddings only)
   "company_name",   # company name (corporate only)
   "honoree_name",   # whose birthday (birthday only)
   ```
   Add to `NODE_SEQUENCE` after `"wedding_message"`:
   ```python
   "collect_event_context",   # conditional: partner/company/honoree
   ```

2. `basic_info.py` — add `collect_event_context_node`:
   - Reads `event_type` from slots
   - Wedding → extracts `partner_name`, asks "Who's the other half of this day?"
   - Corporate → extracts `company_name`, asks "What company is this for?"
   - Birthday → extracts `honoree_name`, asks "Whose birthday is it?"
   - Uses `llm_extract()` on user message, fills the appropriate slot, advances to `collect_event_date`

3. `system_prompts.py` — add extraction prompts:
   ```python
   "partner_name": "Extract the partner or fiancé's name. Return ONLY the name or NONE.",
   "company_name": "Extract the company or organization name. Return ONLY the name or NONE.",
   "honoree_name": "Extract whose birthday/celebration this is. Return ONLY the name or NONE.",
   ```
   Add `NODE_PROMPTS["collect_event_context"]`.

4. `routing.py` — add `"collect_event_context": None` to `_NODE_COLLECTS`.

5. `check_modifications.py` — when `event_type` changes via `@AI`, clear stale conditional slots:
   ```python
   if target_slot == "event_type":
       for stale in ("partner_name", "company_name", "honoree_name"):
           if stale in state["slots"]:
               state["slots"][stale]["value"] = None
               state["slots"][stale]["filled"] = False
   ```

**How:** New node function (≈25 lines), 3 new slots, 3 new extraction prompts, 1 routing entry.

---

### FIX-06 · Date validation — past dates accepted, frozen on Birthday, flexible format

**Files:** `ml-agent/prompts/system_prompts.py`, `ml-agent/agent/nodes/basic_info.py`

**Problems from PDF:**
- Was able to enter 1994 as a year
- Under Birthday it would not accept a date (stuck looping asking for format)
- Date confirmation loop never advancing past "yes" confirmation

**What changes:**

1. `EXTRACTION_PROMPTS["event_date"]` — already has `{today}` injection. Strengthen:
   ```
   Extract the event date. Return YYYY-MM-DD or NONE.
   Today is {today}. The event MUST be in the future.
   Accept any format: '05', 'may 5', 'the 5th', 'June 15th', '6/15', 'next friday'.
   For ambiguous short inputs like '05' or 'the 5th', assume the nearest future date.
   NEVER return a date in the past. If the date is in the past, return NONE.
   Do not return years before {today[:4]}.
   ```

2. `collect_event_date_node` — currently uses `_extract_and_respond`. Replace with a custom implementation:
   ```python
   async def collect_event_date_node(state):
       state = dict(state)
       user_msg = get_last_human_message(state["messages"])
       today = datetime.now()

       prompt = EXTRACTION_PROMPTS["event_date"].format(today=today.strftime("%Y-%m-%d"))
       extracted = (await llm_extract(prompt, user_msg)).strip()

       if extracted and extracted.upper() != "NONE":
           try:
               event_date = datetime.strptime(extracted, "%Y-%m-%d")
               if event_date.date() <= today.date():
                   # Past date — re-ask specifically
                   response = await llm_respond(...)  # "That date has passed — what's the actual date?"
                   # stay on collect_event_date
               else:
                   fill_slot(state["slots"], "event_date", extracted)
                   state["current_node"] = "collect_event_context"  # or collect_venue
                   response = await llm_respond(...)
           except ValueError:
               # unparseable — re-ask
               response = await llm_respond(...)  # "Could you give me the date in a format like June 15, 2027?"
       else:
           # NONE — re-ask
           response = await llm_respond(...)

       state["messages"] = add_ai_message(state, response)
       return state
   ```

3. Remove the "confirmation loop" — PDF shows bot asking `"Could you confirm if you meant May 19, 2027?"` and then getting stuck on "yes". The fix: trust the extracted date directly, no re-confirmation step. Just echo it and move on.

**How:** Custom `collect_event_date_node` replaces the generic `_extract_and_respond` call. ≈40 lines.

---

### FIX-07 · "Let's do cookies" treated as declining desserts

**Files:** `ml-agent/agent/nodes/addons.py`

**Problem:** User says "lets do cookies" → `is_affirmative()` fails on food phrases → bot says "no desserts".

**What changes:**

In `ask_desserts_node`, before the `is_affirmative` / `is_negative` check, scan the utterance for catalog item tokens:

```python
async def _contains_catalog_items(user_msg: str, items: list[dict]) -> list[str]:
    """O(n) token scan — no extra LLM call."""
    user_lower = user_msg.lower()
    found = []
    for item in items:
        tokens = [t for t in item["name"].lower().split() if len(t) >= 4]
        if any(tok in user_lower for tok in tokens):
            found.append(item["name"])
    return found
```

Node logic order:
1. `matched = await _contains_catalog_items(user_msg, all_dessert_items)`
2. If `matched` → implicit yes, jump straight to `select_desserts`, pass matched items in context
3. Else if `is_negative()` → skip desserts
4. Else if `is_affirmative()` → present menu
5. Else → re-ask

**How:** Add `_contains_catalog_items` helper (8 lines) to `addons.py`. Modify `ask_desserts_node` logic order (≈10 line change).

---

### FIX-08 · Service type: move earlier + simplify to 2 options

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/basic_info.py`, `ml-agent/prompts/system_prompts.py`, `ml-agent/agent/routing.py`

**Problem (from PDF):** Service type asked too late, 3 options confuse users. Should be "Onsite" or "Drop-off" only.

**What changes:**

1. `EXTRACTION_PROMPTS["service_type"]` — update valid options:
   ```
   Valid options: 'Drop-off', 'Onsite'.
   'Drop-off' = no staff onsite, delivery only.
   'Onsite' = staff present at event.
   Map: 'drop off'/'delivery'/'drop it off' → 'Drop-off'
   Map: 'onsite'/'on site'/'full service'/'buffet'/'plated'/'staff' → 'Onsite'
   ```

2. `NODE_SEQUENCE` in `state.py` — move `select_service_type` to immediately after `collect_guest_count`, before `ask_appetizers`:
   ```python
   "collect_guest_count",
   "select_service_type",   # ← moved here
   "ask_appetizers",
   ```

3. `collect_guest_count_node` in `basic_info.py` — change `next_node` to `"select_service_type"` (instead of `"select_service_style"` for weddings or `"ask_appetizers"` for others).

4. `select_service_type_node` — currently routes to `"ask_rentals"`. Change to route to `"ask_appetizers"`.

5. `NODE_PROMPTS["select_service_type"]` — update prompt to reflect new position and 2 options:
   ```
   Confirmed service type. Now ask: Would you like a cocktail hour with appetizers?
   (Don't mention service type options again — it's already selected.)
   ```

6. Add brief clarifying note in bot message when presenting service type:
   *"Drop-off means we deliver and set up — no staff onsite during the event. Onsite means our team is there with you throughout."*

**How:** Reorder one line in `NODE_SEQUENCE`, change two `next_node` references, update extraction prompt and node prompt. No new nodes needed.

---

### FIX-09 · Human approval gate before contract is sent

**Files:** `ml-agent/agent/nodes/final.py`

**Problem:** Contract generated and shown to client immediately. No staff review.

**What changes:**

In `generate_contract_node` (or `generate_summary_node`), after building `summary_data`:
- Set `status = "pending_staff_review"` (not `"sent"`)
- Bot message to client: *"We've got everything we need. I'll have your summary over to you within 24-48 hours once our team gives it a final look."*
- Do NOT send the full itemized contract with taxes in the chat
- The staff-facing API endpoint (`POST /conversations/{id}/approve`) is a backend concern — ml-agent just sets the status and stops

**How:** Change the final response message and status field. ≈5 line change in `final.py`.

---

### FIX-10 · Dietary response — reassure allergies are covered

**Files:** `ml-agent/agent/nodes/final.py`

**Problem:** Bot notes the allergy but doesn't confirm it will be handled.

**What changes:**

In `collect_dietary_node`, after storing the dietary concern, change the response prompt:
```python
# After has_conflict == False:
"Noted — [allergy] is fully flagged for our team. We'll make sure every guest "
"has a safe, well-thought-out option."

# After has_conflict == True:
"Noted — I've flagged the conflict with [item]. Our team will sort a safe "
"alternative before the event."
```

**How:** Prompt string change in `collect_dietary_node`. 2-line edit.

---

## P2 — Polish (Sprint 2)

---

### FIX-11 · @AI tip — teach users the correction command once

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/basic_info.py`

**What changes:**

1. Add `ai_tip_shown: bool` field to `ConversationState` (default `False`).

2. After `collect_event_type_node` confirms the event type (first "big" confirmation), append the tip once:
   ```python
   if not state.get("ai_tip_shown"):
       response += "\n\nTip: type **@AI** anytime to update a previous answer — e.g. '@AI change the date to June 10th'."
       state["ai_tip_shown"] = True
   ```

**How:** 1 new state field, 3-line injection in `select_event_type_node`. Never shown more than once.

---

### FIX-12 · Ordinal/number selection inconsistent ("I'll take 1")

**Files:** `ml-agent/agent/nodes/addons.py`, `ml-agent/agent/nodes/menu.py`

**Problem:** Typing "1" instead of item name works in some nodes, fails in others.

**What changes:**

Standardize all item-list selection nodes to:
1. Always present items as a **numbered list** (not bullets).
2. Pass the numbered list as context in the extraction prompt:
   ```python
   numbered_str = "\n".join(f"{i+1}. {item['name']}" for i, item in enumerate(items))
   extraction_prompt = (
       f"Extract item selections. Resolve ordinal references "
       f"('option 2', 'the second one', '1 and 3') to exact item names. "
       f"Return ONLY comma-separated exact names.\n\nItems:\n{numbered_str}"
   )
   ```

Nodes to update: `select_appetizers`, `select_desserts`, `select_utensils`, `select_dishes` (already partially done).

**How:** Template change in each selection node's extraction prompt. No new LLM calls.

---

### FIX-13 · Bamboo utensils not recognized when switching

**Files:** `ml-agent/agent/nodes/addons.py`, `ml-agent/prompts/system_prompts.py`

**What changes:**

1. `select_utensils_node` extraction prompt — add explicit aliases:
   ```
   Extract the utensil type. Valid: 'eco-friendly', 'biodegradable', 'bamboo',
   'plastic', 'standard', 'compostable', 'wooden'.
   'bamboo' → return 'bamboo'. Return NONE if unclear.
   ```

2. Ensure seed_menu.py includes "Bamboo utensils" as an item in the DB.

**How:** Prompt string edit in `addons.py`. Check seed file.

---

### FIX-14 · Remove florals from entire flow

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/addons.py`, `ml-agent/agent/nodes/__init__.py`, `ml-agent/agent/routing.py`, `ml-agent/agent/graph.py`

**What changes:**

1. `state.py` — remove `"florals"` from `SLOT_NAMES` and `NODE_SEQUENCE`.
2. `addons.py` — delete `ask_florals_node` and `select_florals_node` functions.
3. `__init__.py` — remove florals node imports/exports.
4. `routing.py` — remove `"ask_florals"` from `_NODE_COLLECTS`.
5. `graph.py` — remove florals edges from the graph.

**How:** Delete code, don't add any.

---

### FIX-15 · Add drinks section

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/addons.py`, `ml-agent/agent/nodes/__init__.py`, `ml-agent/agent/routing.py`, `ml-agent/agent/graph.py`, `ml-agent/prompts/system_prompts.py`

**What changes:**

1. `state.py` — add `"drinks"` to `SLOT_NAMES`. Add `"collect_drinks"` to `NODE_SEQUENCE` after `"ask_desserts"` / before `"ask_utensils"`.

2. `addons.py` — add `collect_drinks_node`:
   - Inform: *"Water, iced tea, and lemonade are included with every onsite event."*
   - Upsell: *"Would you like to add coffee service or a bar package?"*
   - If affirmative: present bar options from DB
   - If bar selected: note bartenders are included, $50/hr, 5-hr minimum
   - If negative: fill slot "water/tea/lemonade included", move on
   - Add `"drinks"` to `_LIST_SLOTS` in `check_modifications.py`

3. `system_prompts.py` — add `NODE_PROMPTS["collect_drinks"]` and extraction prompt.

**How:** New node (≈40 lines), 1 new slot, 1 new NODE_PROMPT.

---

### FIX-16 · Add tableware question (disposable vs china)

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/addons.py`, `ml-agent/prompts/system_prompts.py`

**What changes:**

1. `state.py` — add `"tableware"` slot. Add `"collect_tableware"` to `NODE_SEQUENCE` after `select_service_type`.

2. `addons.py` — add `collect_tableware_node`:
   - *"All contracts come with standard disposable. Would you like to upgrade?"*
   - Options: standard disposable (included), premium disposable +$1pp, full China (price by guest count)
   - If plated was selected → auto-note "China included with plated packages"
   - Use `llm_extract_enum(..., ["Standard Disposable", "Premium Disposable", "China"])`

3. `system_prompts.py` — add `NODE_PROMPTS["collect_tableware"]`.

**How:** New node (≈30 lines), 1 new slot, 1 new NODE_PROMPT.

---

### FIX-17 · Add labor section

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/addons.py`, `ml-agent/prompts/system_prompts.py`, `ml-agent/agent/nodes/check_modifications.py`

**What changes:**

1. `state.py` — add `"labor"` to `SLOT_NAMES`. Add `"collect_labor"` to `NODE_SEQUENCE` after `"ask_rentals"`. Gate: only runs if `service_type == "Onsite"`.

2. `addons.py` — add `collect_labor_node`:
   - Present as numbered list: Ceremony Setup/Cleanup ($1.50pp), Table & Chair Setup ($2pp), Table Preset ($1.75pp), Reception Cleanup ($3.75pp), Trash Removal ($175), Bartending ($50/hr, 5hr min), Travel Fee
   - Use ordinal resolution pattern (FIX-12)
   - Add `"labor"` to `_LIST_SLOTS` in `check_modifications.py`

3. `system_prompts.py` — add `NODE_PROMPTS["collect_labor"]`.

**How:** New node (≈40 lines), 1 new slot, gate condition in routing.

---

### FIX-18 · Duplicate items in selection

**Files:** `ml-agent/agent/nodes/addons.py`, `ml-agent/agent/nodes/check_modifications.py`

**What changes:**

Add `_normalize_item_name()` in `addons.py` (or `helpers.py`):
```python
import re as _re
def _normalize_item_name(name: str) -> str:
    """Strip price annotations: 'Chicken Satay ($3.50/pp)' → 'chicken satay'"""
    return _re.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', name).strip().lower()
```

Use this in every dedup check:
```python
existing_lower = {_normalize_item_name(n) for n in current_items}
new_items = [i for i in matched if _normalize_item_name(i["name"]) not in existing_lower]
```

If user tries to add something already selected, respond: *"You've already got [item] — no change needed."*

**How:** 1 helper function, update dedup checks in `addons.py` and `check_modifications.py`.

---

### FIX-19 · Contract — short format, no full descriptions

**Files:** `ml-agent/agent/nodes/final.py`

**What changes:**

Replace the LLM-rendered menu section in the contract with a deterministic Python renderer:
```python
def _render_short_menu(slots: dict) -> str:
    lines = []
    for label, slot_key in [("Cocktail Hour", "appetizers"), ("Main Course", "selected_dishes"), ("Desserts", "desserts")]:
        val = slots.get(slot_key, {}).get("value")
        if val and val != "no":
            items = [re.sub(r'\s*\(\$[\d.]+(?:/\w+)?\)', '', i).strip() for i in str(val).split(",")]
            lines.append(f"{label}: {', '.join(i for i in items if i)}")
    return "\n".join(lines)
```

The full descriptions remain in the DB. The intake summary shows short names only.

**How:** Add `_render_short_menu()` function, use it in `generate_contract_node` for the menu section.

---

### FIX-20 · Follow-up call offer at end of flow

**Files:** `ml-agent/agent/state.py`, `ml-agent/agent/nodes/final.py`, `ml-agent/prompts/system_prompts.py`

**What changes:**

1. `state.py` — add `"followup_time"` to `SLOT_NAMES`. Add `"offer_followup"` to `NODE_SEQUENCE` as second-to-last node (before `generate_contract`).

2. `final.py` — add `offer_followup_node`:
   - *"Would you like to schedule a quick call to go over the details? Usually 10–15 minutes."*
   - Yes → collect preferred time, store in `followup_time` slot, advance to contract
   - No → skip to contract

3. `system_prompts.py` — add `NODE_PROMPTS["offer_followup"]`.

**How:** New node (≈25 lines), 1 new slot.

---

## Menu-Level Changes (DB + Seed)

These require changes to `seed_menu.py` and potentially the DB schema — not just prompts.

### FIX-21 · Remove "Pick 2" options and "Potato bar" from main menu
**File:** `ml-agent/database/seed_menu.py`  
Remove those entries from the seeded menu items. No code change needed.

### FIX-22 · Combine menu categories per PDF
**File:** `ml-agent/database/seed_menu.py`
- BBQ + Casual → "Tasty & Casual"
- Mexican + Mediterranean + Italian → "Global Inspirations"
- Signature Combinations stays as-is

### FIX-23 · Add "Custom menu / schedule a call" escape hatch
**Files:** `ml-agent/agent/nodes/menu.py`, `ml-agent/prompts/system_prompts.py`  
After presenting main menu, add to the prompt:
*"Don't see something you love? Type 'custom' and we'll set up a quick call to build your menu from scratch."*  
In `select_dishes_node`, detect "custom"/"call"/"none of these" → fill `menu_notes` with "Custom menu requested" → skip dish selection → advance to next section.

---

## Implementation Sequence (Day-by-Day)

### Day 1 — P0 Bugs
1. FIX-01 (venue prompt guard + regex)
2. FIX-02 (desserts removal — `_LIST_SLOTS`)

### Day 2 — P1 Core UX
3. FIX-03 (SYSTEM_PROMPT rewrite)
4. FIX-06 (date validation fix — custom node)
5. FIX-07 (desserts catalog scan)
6. FIX-08 (service type reposition + 2 options)
7. FIX-10 (dietary reassurance — 2-line prompt)

### Day 3 — P1 Features
8. FIX-05 (fiancé/company/honoree names — new node)
9. FIX-09 (human approval gate)

### Day 4 — P2 Polish
10. FIX-04 (response variation)
11. FIX-11 (@AI tip — once)
12. FIX-12 (ordinal selection standardize)
13. FIX-13 (bamboo utensils)
14. FIX-18 (duplicate items normalize)
15. FIX-19 (contract short format)
16. FIX-14 (remove florals)

### Day 5 — P2 New Sections
17. FIX-15 (drinks section)
18. FIX-16 (tableware question)
19. FIX-17 (labor section)
20. FIX-20 (follow-up call offer)
21. FIX-21, FIX-22, FIX-23 (seed/menu changes)

---

## Key Code Locations Reference

| What | File | Approx location |
|------|------|-----------------|
| SYSTEM_PROMPT | `prompts/system_prompts.py` | top |
| NODE_PROMPTS | `prompts/system_prompts.py` | dict |
| EXTRACTION_PROMPTS | `prompts/system_prompts.py` | dict |
| ConversationState / SLOT_NAMES | `agent/state.py` | full file |
| NODE_SEQUENCE | `agent/state.py` | bottom |
| fill_slot / get_slot_value | `agent/state.py` | functions |
| collect_name, date, venue, guest_count | `agent/nodes/basic_info.py` | full file |
| utensils, desserts, rentals | `agent/nodes/addons.py` | full file |
| dietary, contract, special requests | `agent/nodes/final.py` | full file |
| @AI routing, _CORRECTION_SIGNALS | `agent/routing.py` | full file |
| is_affirmative, llm_extract, llm_respond | `agent/nodes/helpers.py` | full file |
| check_modifications logic | `agent/nodes/check_modifications.py` | full file |
| Menu DB fetch | `agent/nodes/menu.py` | full file |
| Menu seed data | `database/seed_menu.py` | full file |

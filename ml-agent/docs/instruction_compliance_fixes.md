# Instruction Compliance Fixes — GPT-4o-mini at Temperature=0

Root cause: GPT-4o-mini is a distilled model optimized for cost/speed, not precise instruction adherence. Temperature=0 makes it deterministic but doesn't improve compliance — it just deterministically picks the most likely (often non-compliant) completion.

---

## Fix 1: Don't Let the LLM List DB Items

**Problem:** LLM told to "show ALL 45 items" but only shows 10-15. It has a strong prior toward summarization from RLHF training.

**Solution:** Fetch items from DB in Python, format the numbered list yourself, inject as a static string. The LLM only generates the intro/closing text.

**Implementation:**

```python
# BEFORE (LLM generates the list — unreliable):
response = await llm_respond(
    "Present the FULL appetizer menu as a numbered list...",
    appetizer_context  # contains raw DB items
)

# AFTER (Python generates the list — 100% reliable):
menu = await load_menu_by_category()
items = get_appetizer_items(menu)
numbered_list = "\n".join(f"{i+1}. {item['name']} (${item['unit_price']:.2f})" for i, item in enumerate(items))

intro = await llm_respond(
    "Write a brief casual intro for the appetizer menu (1 sentence). "
    "Mention 2-3 crowd favorites from this list. Do NOT list any items.",
    f"Available items: {', '.join(i['name'] for i in items)}"
)

response = f"{intro}\n\n{numbered_list}\n\nPick as many as you'd like!"
```

**Apply to:** appetizers, main menu, desserts, rentals, labor, bar options, event type, tableware, utensils — ALL numbered lists.

**Files:** `menu.py`, `addons.py`, `basic_info.py`

**Effort:** ~45 min. Need to refactor each node that presents a list.

---

## Fix 2: Per-Event-Type Prompt Templates

**Problem:** One mega-prompt with "if wedding do X, if birthday do Y" — LLM ignores conditionals and mentions cocktail hour for birthdays.

**Solution:** Separate prompt templates per event type. The cocktail hour text simply doesn't exist in non-wedding prompts.

**Implementation:**

```python
# BEFORE:
NODE_PROMPTS["ask_appetizers"] = (
    "Present appetizers. Only mention cocktail hour for weddings..."
)

# AFTER:
NODE_PROMPTS["ask_appetizers_wedding"] = "For the cocktail hour, here are the appetizer options..."
NODE_PROMPTS["ask_appetizers_default"] = "Here are the appetizer options..."

# In node:
event_type = get_slot_value(state["slots"], "event_type")
prompt_key = "ask_appetizers_wedding" if "wedding" in event_type.lower() else "ask_appetizers_default"
```

**Apply to:** `ask_appetizers`, `collect_guest_count`, `select_service_style`, any node with event-type conditionals.

**Files:** `system_prompts.py`, node files that branch on event type

**Effort:** ~20 min

---

## Fix 3: Append Exact Closing Text in Python

**Problem:** LLM told to "end with: Pick up to 4 mini desserts" but paraphrases it as "Which 4 would you like?" because it treats instructions as semantic guidance, not literal templates.

**Solution:** LLM generates the conversational part only. Python appends the exact closing text.

**Implementation:**

```python
# BEFORE:
response = await llm_respond(
    "Present desserts. End with: 'Pick up to 4 mini desserts'",
    context
)

# AFTER:
intro = await llm_respond(
    "Write a brief casual intro for the dessert options (1-2 sentences).",
    context
)
response = f"{intro}\n\n{numbered_list}\n\nPick up to 4 mini desserts!"
```

**Apply to:** All nodes where specific closing text is needed — desserts, appetizers, main menu, rentals, tableware, service type, event type.

**Files:** All node files

**Effort:** ~30 min

---

## Fix 4: Sandwich Critical Instructions

**Problem:** Instructions buried in the middle of prompts are ignored (lost-in-the-middle phenomenon, Liu et al. 2023).

**Solution:** Put critical instructions at the START and END of each prompt. Use the "sandwich" pattern.

**Implementation:**

```python
# BEFORE:
prompt = (
    "You are a catering assistant. "
    "Some guidelines... "
    "CRITICAL: Do NOT mention cocktail hour for non-weddings. "  # buried in middle
    "More guidelines..."
)

# AFTER:
prompt = (
    "CRITICAL: Do NOT mention cocktail hour for non-weddings.\n\n"  # START
    "You are a catering assistant. "
    "Some guidelines...\n\n"
    "REMINDER: Do NOT mention cocktail hour for non-weddings."  # END
)
```

**Apply to:** `SYSTEM_PROMPT` and all `NODE_PROMPTS`

**Files:** `system_prompts.py`

**Effort:** ~15 min

---

## Fix 5: Post-Processing Validation Layer

**Problem:** Even with good prompts, the LLM occasionally adds unrequested content, mentions banned terms, or miscounts items.

**Solution:** Add a lightweight validation step after `llm_respond` that checks and fixes the output.

**Implementation:**

```python
async def llm_respond_validated(system_prompt, context, validators=None):
    response = await llm_respond(system_prompt, context)
    
    if validators:
        for validator in validators:
            response = validator(response)
    
    return response

# Validators:
def strip_cocktail_hour_for_non_wedding(response, event_type):
    if "wedding" not in event_type.lower():
        response = response.replace("cocktail hour", "appetizers")
    return response

def enforce_item_count(response, expected_count):
    actual = response.count("\n") - response.count("\n\n")
    if actual < expected_count:
        # Log warning — list was truncated
        logger.warning(f"LLM truncated list: {actual}/{expected_count} items")
    return response
```

**Apply to:** All `llm_respond` calls where output compliance matters

**Files:** `helpers.py` (new function), node files

**Effort:** ~30 min

---

## Implementation Priority

1. **Fix 1 (Python lists)** — highest impact, eliminates 45-item truncation completely
2. **Fix 3 (Python closing text)** — eliminates paraphrasing of exact UI copy
3. **Fix 4 (Sandwich instructions)** — quick win, 15 min
4. **Fix 2 (Per-event templates)** — eliminates cocktail hour leak
5. **Fix 5 (Post-processing)** — safety net for remaining edge cases

**Total: ~2.5 hours**

---

## Temperature Recommendation

Keep `temperature=0` for extraction (`llm_extract`). For responses (`llm_respond`), `0.1` can marginally help with variation but won't fix compliance. The fixes above are architectural — they work regardless of temperature.
